"""Input-history codecs for the XB recompute baselines (osdi/expXB/preregistration.md).

Frames are the runtime's camera frames: uint8 RGB [N, H, W, 3] at the model resolution (the runtime normalizes them with
x / 127.5 - 1, so bit-exact uint8 frames give bit-exact replay inputs). A segment (the frames one transfer carries) is
encoded independently, so a target that is abandoned never shares state with the next one (no-reuse rule).

Lossless: zlib (levels 1 / 6), PNG per frame, FFV1 (bgr0, level 3, intra), x264rgb with qp 0. Lossy (sensitivity only): H.264 yuv420p at
CRF 23 / 28. "raw" is the uncompressed upper bound.
"""

from __future__ import annotations

import io
import zlib

import numpy as np

LOSSLESS = ("raw", "zlib1", "zlib6", "png", "ffv1", "x264rgb_qp0")
LOSSY = ("h264_crf23", "h264_crf28")


def _video_encode(frames: np.ndarray, codec: str, pix_fmt: str, options: dict, fmt: str = "matroska") -> bytes:
    import av

    buf = io.BytesIO()
    with av.open(buf, "w", format=fmt) as c:
        st = c.add_stream(codec, rate=16)
        st.width, st.height, st.pix_fmt = frames.shape[2], frames.shape[1], pix_fmt
        st.options = {k: str(v) for k, v in options.items()}
        for f in frames:
            for p in st.encode(av.VideoFrame.from_ndarray(np.ascontiguousarray(f), format="rgb24")):
                c.mux(p)
        for p in st.encode():
            c.mux(p)
    return buf.getvalue()


def _video_decode(data: bytes) -> np.ndarray:
    import av

    with av.open(io.BytesIO(data), "r") as c:
        return np.stack([fr.to_ndarray(format="rgb24") for fr in c.decode(video=0)])


def encode(frames: np.ndarray, codec: str) -> bytes:
    frames = np.ascontiguousarray(frames, dtype=np.uint8)
    n, h, w, _ = frames.shape
    head = np.array([n, h, w], dtype=np.int32).tobytes()
    if codec == "raw":
        return head + frames.tobytes()
    if codec in ("zlib1", "zlib6"):
        return head + zlib.compress(frames.tobytes(), int(codec[-1]))
    if codec == "png":
        from PIL import Image

        parts = []
        for f in frames:
            b = io.BytesIO(); Image.fromarray(f).save(b, format="PNG", compress_level=6); b = b.getvalue()
            parts.append(np.array([len(b)], dtype=np.int64).tobytes() + b)
        return head + b"".join(parts)
    if codec == "ffv1":
        return _video_encode(frames, "ffv1", "bgr0", {"level": 3, "g": 1, "slices": 4, "slicecrc": 1})
    if codec == "x264rgb_qp0":
        return _video_encode(frames, "libx264rgb", "rgb24", {"qp": 0, "preset": "veryfast"})
    if codec.startswith("h264_crf"):
        return _video_encode(frames, "libx264", "yuv420p", {"crf": int(codec[8:]), "preset": "veryfast"})
    raise ValueError(codec)


def decode(data: bytes, codec: str) -> np.ndarray:
    if codec in ("raw", "zlib1", "zlib6"):
        n, h, w = np.frombuffer(data[:12], dtype=np.int32)
        body = data[12:] if codec == "raw" else zlib.decompress(data[12:])
        return np.frombuffer(body, dtype=np.uint8).reshape(n, h, w, 3)
    if codec == "png":
        from PIL import Image

        n = int(np.frombuffer(data[:4], dtype=np.int32)[0]); off, out = 12, []
        for _ in range(n):
            ln = int(np.frombuffer(data[off:off + 8], dtype=np.int64)[0]); off += 8
            out.append(np.asarray(Image.open(io.BytesIO(data[off:off + ln])).convert("RGB"))); off += ln
        return np.stack(out)
    return _video_decode(data)


def psnr(a: np.ndarray, b: np.ndarray) -> float:
    mse = float(np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2))
    return 99.0 if mse == 0 else 10 * np.log10(255.0 ** 2 / mse)


# ---------------------------------------------------------------- input history used by the recompute baselines
SEG_FRAMES = 32   # frames per encoded segment: segments are encoded, sent and decoded in a pipeline


class InputHistory:
    """The session's camera frames as the runtime uses them: uint8 [T, H, W, 3] of one clip, repeated end to end
    (frame i is clip[i mod T]). Every node holds the clip; the recompute baselines nevertheless transfer the history, and
    the destination checks the decoded frames against its own copy and replays from the decoded frames."""

    def __init__(self, clip: np.ndarray):
        self.clip = np.ascontiguousarray(clip, dtype=np.uint8)
        self.T = len(self.clip)

    def frames(self, lo: int, hi: int) -> np.ndarray:
        return self.clip[np.arange(lo, hi) % self.T]


def synthetic_clip(h: int, w: int, n: int = 16) -> np.ndarray:
    """Dry runs only: a smooth moving pattern (compressible, deterministic, identical on every node)."""
    y, x = np.mgrid[0:h, 0:w]
    return np.stack([np.stack([(x + 7 * t) % 256, (y + 3 * t) % 256, ((x + y) // 2 + 5 * t) % 256], -1) for t in range(n)]).astype(np.uint8)


def segments(lo: int, hi: int, seg: int = SEG_FRAMES) -> list[tuple[int, int]]:
    return [(a, min(a + seg, hi)) for a in range(lo, hi, seg)]


def covered(have: list[tuple[int, int]], lo: int, hi: int) -> bool:
    """Whether the union of the half-open intervals `have` covers [lo, hi)."""
    pos = lo
    for a, b in sorted(have):
        if a > pos:
            break
        pos = max(pos, b)
        if pos >= hi:
            return True
    return pos >= hi


# ---------------------------------------------------------------- estimated remote delivery bytes (nothing is transmitted)
DELIVERY_CRFS = (23, 28)   # CRF 23 reported, CRF 28 sensitivity (preregistration section 2)


class DeliveryEncoder:
    """Encodes the output stream that a host serving a user at another edge would have to send toward that edge: H.264
    (libx264, yuv420p, preset veryfast, tune zerolatency: no B-frames, no lookahead, one packet per frame) at each CRF.
    A new stream (starting with a keyframe) begins whenever its key (ownership, user edge) changes. The encoded sizes are
    an ESTIMATE of remote delivery bytes: the testbed does not transmit the output stream."""

    def __init__(self, crfs=DELIVERY_CRFS, fps: int = 16):
        self.crfs, self.fps = tuple(int(c) for c in crfs), fps
        self.key = None
        self.ctx = {}
        self.n = 0

    def _open(self, w: int, h: int):
        import fractions

        import av

        self.ctx = {}
        for crf in self.crfs:
            cc = av.CodecContext.create("libx264", "w")
            cc.width, cc.height, cc.pix_fmt = w, h, "yuv420p"
            cc.time_base = fractions.Fraction(1, self.fps); cc.framerate = fractions.Fraction(self.fps, 1)
            cc.options = {"crf": str(crf), "preset": "veryfast", "tune": "zerolatency"}
            self.ctx[crf] = cc
        self.n = 0

    def push(self, key, frames: np.ndarray) -> dict:
        """Encode one chunk's frames [n, H, W, 3] uint8; returns {crf: (bytes, keyframes)} and the encode time."""
        import time as _t

        import av

        t0 = _t.perf_counter()
        if key != self.key or not self.ctx:
            self._open(frames.shape[2], frames.shape[1]); self.key = key
        out = {crf: [0, 0] for crf in self.crfs}
        for f in frames:
            vf = av.VideoFrame.from_ndarray(np.ascontiguousarray(f), format="rgb24")
            for crf, cc in self.ctx.items():
                vf.pts = self.n
                for p in cc.encode(vf):
                    out[crf][0] += p.size; out[crf][1] += int(p.is_keyframe)
            self.n += 1
        return {"bytes": {crf: v[0] for crf, v in out.items()}, "keyframes": {crf: v[1] for crf, v in out.items()}, "enc_s": _t.perf_counter() - t0}
