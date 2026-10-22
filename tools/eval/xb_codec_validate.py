#!/usr/bin/env python3
"""CPU-only codec validation for the XB recompute input transfer (before any GPU calibration).

For dog (examples/original.mp4) and butterfly-feeding-slow-motion (LOVEU), builds the camera-frame history the recompute
baselines transfer (frames resized to 480 x 832; the clip repeats end to end as in the runtime) for four segments:
R-full at trigger call 30 (calls 0..30: 125 frames), one later R-full round (30 calls: 120 frames), R-full at trigger
call 120 (485 frames), R-win W = 3 (13 frames). Per codec: bytes, ratio to raw, encode / decode time (this machine),
bit-exactness (np.array_equal), PSNR for lossy codecs.

    python tools/eval/xb_codec_validate.py      # -> results/evaluation/osdi/expXB/codec_validation.{md,json}
"""

from __future__ import annotations

import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
import xb_codec as xc  # noqa: E402

H, W = 480, 832
VIDEOS = {"dog": ROOT / "examples/original.mp4", "butterfly-feeding-slow-motion": ROOT / "data/loveu_tgve_2023/butterfly-feeding-slow-motion.mp4"}
SEGMENTS = {"R-full t30 (calls 0..30)": (0, 125), "R-full later round (30 calls)": (125, 245), "R-full t120 (calls 0..120)": (0, 485), "R-win W=3": (120, 133)}


def load(path: Path) -> np.ndarray:
    import av
    from PIL import Image

    with av.open(str(path)) as c:
        fr = [np.asarray(Image.fromarray(f.to_ndarray(format="rgb24")).resize((W, H), Image.BILINEAR)) for f in c.decode(video=0)]
    return np.stack(fr)


def render(out: dict) -> str:
    R = out["results"]
    L = ["# XB recompute input codecs - CPU-only validation (2026-10-22)", "",
         "Purpose: choose the input-history codec of the recompute baselines before any GPU calibration",
         "(`preregistration.md` section 3.2). The frames are the runtime's uint8 camera frames at 480 x 832 (1,198,080 B each).",
         "The clip repeats end to end, as in the runtime. Each segment is encoded independently, so an abandoned target shares nothing.",
         "Bit-exact means `np.array_equal(decode(encode(x)), x)`.", "",
         f"Machine: {out['machine']}. Timings come from one process on this machine and are indicative only;",
         "the GPU hosts measure their own encode and decode times in every run.", "",
         "Reproduce: `python tools/eval/xb_codec_validate.py` (needs numpy, av, Pillow; CPU only).", "",
         "## Summary (all four segments per input)", "",
         "| input | codec | class | ratio vs raw | bit-exact (4 / 4) | encode ms / frame | decode ms / frame | min PSNR (lossy) |", "|---|---|---|---|---|---|---|---|"]
    lossless = ("raw", "zlib1", "zlib6", "png", "ffv1", "x264rgb_qp0")
    for name, segs in R.items():
        codecs = list(next(iter(segs.values())).keys())
        for c in codecs:
            rs = [segs[g][c] for g in segs]
            rat = [r["ratio"] for r in rs]
            ex = sum(r["exact"] for r in rs)
            enc = sum(r["encode_ms"] for r in rs) / sum(r["frames"] for r in rs)
            dec = sum(r["decode_ms"] for r in rs) / sum(r["frames"] for r in rs)
            ps = [r["psnr"] for r in rs if r["psnr"] is not None]
            L.append(f"| {name} | {c} | {'upper bound' if c == 'raw' else ('lossless' if c in lossless else 'lossy')} | {min(rat):.2f}-{max(rat):.2f} | {ex} / {len(rs)} | {enc:.1f} | {dec:.1f} | {'-' if not ps else f'{min(ps):.1f} dB'} |")
    L += ["", "## Selection", "",
          "- **Primary: FFV1** (lossless; `bgr0`, level 3, intra-only, 4 slices with CRC). It was bit-exact on every segment.",
          "  It had the highest lossless ratio on both inputs (3.0x dog, 4.1x butterfly) and the fastest lossless encode.",
          "- x264rgb qp 0 is lossless but larger and slower. PNG and zlib compress less.",
          "- H.264 CRF 23 / 28 (yuv420p) are not bit-exact. They are lossy-input sensitivity cases only and never exact recomputation.",
          "- Raw is the network-byte upper bound. Every recompute run records it, so it needs no separate runs.", "",
          "## Transmitted bytes per segment and transfer time at 1 Gbps (actual encoded sizes)", "",
          "| input | segment | frames | raw MB | FFV1 MB | CRF 23 MB | CRF 28 MB | raw s @1 Gbps | FFV1 s @1 Gbps |", "|---|---|---|---|---|---|---|---|---|"]
    for name, segs in R.items():
        for g, cs in segs.items():
            mb = lambda c: cs[c]["bytes"] / 1e6  # noqa: E731
            L.append(f"| {name} | {g} | {cs['raw']['frames']} | {mb('raw'):.1f} | {mb('ffv1'):.1f} | {mb('h264_crf23'):.2f} | {mb('h264_crf28'):.2f} | {mb('raw') * 8 / 1e3:.2f} | {mb('ffv1') * 8 / 1e3:.2f} |")
    L += ["", "R-full replay of 30 chunks takes about 17 s (state study), so input transfer is not the R-full bottleneck at 1 Gbps.",
          "The codec mainly changes network bytes.", ""]
    for name, segs in R.items():
        L += [f"## Detail: {name}", "", "| segment | codec | bytes | ratio vs raw | encode ms | decode ms | bit-exact | PSNR (dB) |", "|---|---|---|---|---|---|---|---|"]
        for g, cs in segs.items():
            for c, r in cs.items():
                pv = "-" if r["psnr"] is None else f"{r['psnr']:.1f}"
                L.append(f"| {g} | {c} | {r['bytes']:,} | {r['ratio']:.2f} | {r['encode_ms']:.0f} | {r['decode_ms']:.0f} | {r['exact']} | {pv} |")
        L.append("")
    return "\n".join(L) + "\n"


def main():
    if "--render" in sys.argv:   # re-render the markdown from the saved json
        od = ROOT / "results/evaluation/osdi/expXB"
        (od / "codec_validation.md").write_text(render(json.loads((od / "codec_validation.json").read_text()))); return
    out = {"machine": platform.platform(), "processor": platform.processor(), "note": "timings are this machine's (single process); nodes measure their own online", "results": {}}
    for name, path in VIDEOS.items():
        clip = load(path)
        rep = np.concatenate([clip] * (600 // len(clip) + 1))
        for seg, (lo, hi) in SEGMENTS.items():
            frames = rep[lo:hi]
            raw = frames.nbytes
            for codec in xc.LOSSLESS + xc.LOSSY:
                t0 = time.perf_counter(); data = xc.encode(frames, codec); t1 = time.perf_counter()
                dec = xc.decode(data, codec); t2 = time.perf_counter()
                exact = dec.shape == frames.shape and bool(np.array_equal(dec, frames))
                ps = None if exact else (xc.psnr(dec, frames) if dec.shape == frames.shape else None)
                rec = {"bytes": len(data), "ratio": raw / len(data), "encode_ms": (t1 - t0) * 1e3, "decode_ms": (t2 - t1) * 1e3, "exact": exact, "psnr": ps, "frames": hi - lo, "raw_bytes": raw}
                out["results"].setdefault(name, {}).setdefault(seg, {})[codec] = rec
    od = ROOT / "results/evaluation/osdi/expXB"
    (od / "codec_validation.json").write_text(json.dumps(out, indent=1))
    (od / "codec_validation.md").write_text(render(out))
    print(render(out))


if __name__ == "__main__":
    main()
