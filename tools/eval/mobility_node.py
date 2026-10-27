#!/usr/bin/env python3
"""Phase 3 node: one process per physical host (one GPU) for repeated mobility A -> B -> C -> D.

A node can be, at different times, the execution owner (runs StreamDiffusionV2 generation, measures
continuity per chunk) and a holder/forwarder of fragments of the durable Sink. It is driven entirely by
tools/eval/mobility_orchestrate.py over one MSS-capped control connection; data (fragments and the
execution-handoff fragment) travels node-to-node over separate MSS-capped TCP connections.

Reused from Phase 1 (tools/proto_handoff.py), unchanged: serialize_state/pack_component (sink, inflight,
meta), send_msg/recv_msg framing, parallel per-tensor digests, unpack_into_snapshot, bind_sink_into_live,
per-chunk PSNR/SSIM against the bit-exact same-seed baseline, EventLog/CsvLog/ResourceSampler.

The Sink is transferred as fixed-size fragments of its EXACT Phase 1 serialization (transport bookkeeping
only): every fragment carries session_id, sink_version, fragment_id, byte_offset, length, sha256, holder.
A node verifies each fragment on arrival, refuses fragments of another sink_version, and, once all
fragments are present, verifies the whole-Sink digest against the source's before it may bind.

    python tools/eval/mobility_node.py --label B --gpu_id 0 --ctl_port 29811 --data_port 29812
    python tools/eval/mobility_node.py --label B --dry_run --ctl_port 29821 --data_port 29822   # no torch, fake payloads (protocol test only)

Experiment D execution modes (EXEC_HANDOFF mode): "fast" = M1 (in-flight rows + metadata, 2.67 MiB; Phase 1 `ours`);
"full" = Full migration (stop, transfer every state component - sink, recent, meta, vae, inflight - then resume; Phase 1
`full`), sent in the background so the orchestrator can redirect it (FULL_SEND / FULL_CANCEL) when the user moves on
before it completes; "cold" = Cold restart (no state; the new owner restarts from the prompt with fresh caches,
Phase 1 `cold`). --cold_start starts a node after the trigger (OTTER cold destination): no baseline run; the PSNR
reference is read from the cache a warm node of the same host and configuration wrote (bit-exact on the same GPU).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import struct
import sys
import threading
import time
from pathlib import Path

T_MAIN = time.time()   # process start (interpreter start-up before this line is not included)

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT, REPO_ROOT / "tools", REPO_ROOT / "tools" / "eval"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np  # noqa: E402

from common import DEFAULT_MSS, MSS_WARNINGS, CsvLog, EventLog, ResourceSampler, Throttle, clock_sync_server, effective_mss, host_info, tcp_accept, tcp_connect, tcp_listen  # noqa: E402
from proto_handoff import MB, RecvPool, _pool, component_digest, estimate_sink_bytes, payload_slices, recv_exact, recv_msg, send_msg  # noqa: E402

REJOIN_DB = 35.0
# Node identity reported in HELLO and checked by the orchestrator (osdi/audi_s0_w2_provenance.md): what the node
# generates (input, prompt, seed, size, window), which GPU, and the launch token of the orchestrator that started it.
IDENTITY_FIELDS = ("label", "video_path", "prompt_file_path", "seed", "height", "width", "noise_scale", "gpu_id", "migration_chunk", "post_chunks",
                   "dry_run", "cold_start", "launch_id")
IDENTITY_FLAGS = {f: "--" + f for f in IDENTITY_FIELDS}


def _norm_path(p: str) -> str:
    """Repository-relative form of a path argument (relative arguments are resolved against the repository root, the
    node's working directory), so the same file compares equal on every host."""
    q = Path(p) if os.path.isabs(p) else REPO_ROOT / p
    q = Path(os.path.normpath(q))
    try:
        return str(q.relative_to(REPO_ROOT))
    except ValueError:
        return str(q)


# every generation-relevant argument (ports, bind address, MSS, interface and logging flags excluded): its hash is the
# configuration fingerprint
CONFIG_FIELDS = IDENTITY_FIELDS[:-1] + ("config_path", "checkpoint_folder", "fps", "step", "model_type", "fixed_noise_scale", "t2v", "use_taehv",
                                        "normalize_latents", "use_tensorrt", "fast", "sink_fp", "block_ck", "dry_sink_mb", "dry_service_s")


def file_sha256(p: str | None) -> str | None:
    if not p:
        return None
    q = Path(p) if os.path.isabs(p) else REPO_ROOT / p
    if not q.is_file():
        return None
    h = hashlib.sha256()
    with open(q, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 22), b""):
            h.update(blk)
    return h.hexdigest()


def node_identity(a, hash_inputs: bool = True) -> dict:
    """Identity reported in HELLO: the identity fields, the SHA-256 of the input video and prompt files (content, not
    names), and a fingerprint of the generation configuration."""
    out = {}
    for f in IDENTITY_FIELDS:
        v = getattr(a, f, None)
        out[f] = _norm_path(v) if (f.endswith("_path") and v) else v
    cfg = {f: (_norm_path(getattr(a, f)) if (f.endswith(("_path", "_folder")) and getattr(a, f, None)) else getattr(a, f, None)) for f in CONFIG_FIELDS}
    out["config_fingerprint"] = hashlib.sha256(json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()[:16]
    if hash_inputs:
        out["video_sha256"], out["prompt_sha256"] = file_sha256(a.video_path), file_sha256(a.prompt_file_path)
    return out
FULL_COMPS = ("inflight", "meta", "recent", "sink", "vae")   # Phase 1 `full` sends sorted(fg) in this order
_DIGESTS = None


def digest_async(parts):
    """Component digest (Phase 1 definition) in a separate executor, so it never waits on its own hash pool."""
    global _DIGESTS
    if _DIGESTS is None:
        from concurrent.futures import ThreadPoolExecutor

        _DIGESTS = ThreadPoolExecutor(max_workers=6)
    return _DIGESTS.submit(component_digest, parts)


class CountingThrottle(Throttle):
    """Token bucket (rate 0 = unshaped) that counts the bytes it released, so a cancelled transfer reports what it put
    on the wire (overcounts by at most the 1 MiB chunk being sent when the socket was closed)."""

    def __init__(self, bw_bps: float):
        super().__init__(bw_bps)
        self.count = 0

    def take(self, n: int):
        super().take(n)
        self.count += n


def ref_cache_path(a) -> Path:
    tag = f"{socket.gethostname().split('.')[0]}_gpu{a.gpu_id}_{Path(a.video_path).stem}_seed{a.seed}_k{a.step}_M{a.migration_chunk}_N{a.post_chunks}_{a.height}x{a.width}"
    return REPO_ROOT / "results/evaluation/_reference_cache" / f"{tag}.npz"


def ref_record_path(a) -> Path:
    """Per-call record of the node baseline (W / R / N): output-frame digest, Sink value fingerprints, slot positions."""
    return ref_cache_path(a).with_suffix(".record.json")


def frame_digest(fr) -> str | None:
    return None if fr is None else hashlib.blake2b(np.ascontiguousarray(fr).tobytes(), digest_size=16).hexdigest()


def codec_support() -> dict:
    """XB preflight, reported in HELLO: PyAV present, FFV1 lossless round trip bit-exact, libx264 encodes (remote delivery
    estimate, lossy-input sensitivity) and H.264 decodes."""
    try:
        import av

        import xb_codec as xc
    except Exception as exc:  # noqa: BLE001
        return {"av": None, "ffv1_roundtrip": False, "libx264": False, "error": repr(exc)}
    out = {"av": av.__version__}
    f = xc.synthetic_clip(64, 64, 3)
    try:
        out["ffv1_roundtrip"] = bool(np.array_equal(xc.decode(xc.encode(f, "ffv1"), "ffv1"), f))
    except Exception as exc:  # noqa: BLE001
        out["ffv1_roundtrip"] = False; out["ffv1_error"] = repr(exc)
    try:
        out["libx264"] = xc.decode(xc.encode(f, "h264_crf23"), "h264_crf23").shape == f.shape
        out["libx264_delivery"] = xc.DeliveryEncoder().push(0, f)["bytes"][23] > 0
    except Exception as exc:  # noqa: BLE001
        out["libx264"] = False; out["libx264_error"] = repr(exc)
    return out


class CachedReference:
    """PSNR reference for a cold-started node: the uninterrupted same-seed frames a warm node computed on this host.
    Loaded in a background thread (not on the critical path); a call not loaded yet is read directly from the file."""

    def __init__(self, path: Path):
        self.path, self.d, self.t_loaded = path, {}, None
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        with np.load(self.path) as z:
            for k in z.files:
                self.d[int(k)] = z[k]
        self.t_loaded = time.time()

    def get(self, c):
        if c in self.d:
            return self.d[c]
        with np.load(self.path) as z:
            return z[str(c)] if str(c) in z.files else None


def frag_table(nbytes: int, frag_bytes: int) -> list[dict]:
    frags = []
    off = 0
    i = 0
    while off < nbytes:
        n = min(frag_bytes, nbytes - off)
        frags.append({"id": i, "off": off, "len": n}); off += n; i += 1
    return frags


def _git_commit() -> str:
    try:
        import subprocess

        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=10).stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def sha256_hex(view) -> str:
    return hashlib.sha256(memoryview(view).cast("B")).hexdigest()


# ----------------------------------------------------------------------------- runtime adapters
class GpuRuntime:
    """Real StreamDiffusionV2 generation on one GPU (same code paths as Phase 1)."""

    def __init__(self, args):
        import torch

        from proto_handoff import bind_sink_into_live, build_runtime, pack_component, unpack_into_snapshot

        self.torch, self.pack_component, self.unpack_into_snapshot, self.bind_sink_into_live = torch, pack_component, unpack_into_snapshot, bind_sink_into_live
        args.max_post_chunks = args.post_chunks
        self.sa, self.runner, self.pm, self.pl, self.device = build_runtime(args)
        self.sink, self.fsl = self.pl.num_sink_tokens, self.pl.frame_seq_length
        self.cfg_thr = float(getattr(self.pm.config, "adapt_sink_threshold", -1))
        self.k = len(self.pl.denoising_step_list)
        self.args = args
        self.session = None
        self.snap = None
        self.decodes = []   # (t_decode_wall, n_frames) of each VAE decode call since the last step() (D0 instrumentation)
        import collections

        self.last_latents = collections.deque(maxlen=4)   # Experiment VD-2: the latent frames of the last decode calls (capture_latents)
        self.capture_latents = False
        orig = self.pm._timed_stream_decode

        def timed_decode(denoised_pred, _orig=orig):
            if self.capture_latents:
                self.last_latents.append(denoised_pred.detach().clone())
            video = _orig(denoised_pred)
            torch.cuda.synchronize(self.device)
            self.decodes.append((time.time(), int(video.shape[1])))
            return video
        self._decode_orig, self._decode_timed = orig, timed_decode
        self.pm._timed_stream_decode = timed_decode

    def instrument(self, on: bool):
        """G9: switch the decode-completion hook (the only per-chunk OTTER instrumentation inside generation)."""
        self.pm._timed_stream_decode = self._decode_timed if on else self._decode_orig

    def mem(self, tag: str):
        torch = self.torch
        print(f"[{self.args.label}] gpu mem {tag}: allocated {torch.cuda.memory_allocated(self.device) / MB:.0f} MB, reserved {torch.cuda.memory_reserved(self.device) / MB:.0f} MB", flush=True)

    def sink_value_fp(self) -> list[float]:
        """W / R / N: per layer and sink slot, the float64 sum of the slot's VALUE cache (all Stream-Batch rows). Values are
        not RoPE-rotated, so a t_refresh realignment leaves them unchanged; a promotion (or a bind) changes them."""
        torch, fsl, n = self.torch, self.fsl, self.sink
        sums = [layer["v"][:, s * fsl:(s + 1) * fsl].sum(dtype=torch.float64) for layer in self.sa.kv_layers(self.pl) for s in range(n)]
        return torch.stack(sums).tolist()

    def block_checksums(self) -> dict:
        """Task B: per (layer, key, row, sink slot) an order-sensitive int64 checksum of the bf16 block (int16 view x fixed
        pseudo-random int64 weights, wrapping), plus every slot's RoPE position per layer and row. 360 checksums per call
        on the GPU (~1.7 GB read); exact block identity up to hash collisions (2^-64 per block)."""
        torch, fsl, n = self.torch, self.fsl, self.sink
        if not hasattr(self, "_ck_w"):
            g = torch.Generator(device="cpu").manual_seed(20261020)
            self._ck_w = torch.randint(-(1 << 62), 1 << 62, (fsl * self.pl.generator.model.blocks[0].self_attn.k.out_features,), generator=g, dtype=torch.int64).to(self.device)
        cks, pos = [], []
        for layer in self.sa.kv_layers(self.pl):
            rows = layer["k"].shape[0]
            for key in ("k", "v"):
                for b in range(rows):
                    for s_ in range(n):
                        blk = layer[key][b, s_ * fsl:(s_ + 1) * fsl].reshape(-1).view(torch.int16).to(torch.int64)
                        cks.append(int((blk * self._ck_w[: blk.numel()]).sum().item()))
            pos.append(layer["pos"].tolist())
        return {"blocks": cks, "pos_all": pos}

    def baseline(self, M: int, N: int, keep_frames: bool = True, write_ref: bool = True):
        """The uninterrupted reference session (calls 0 .. M + N - 1). Also records per call the output-frame digest, the
        Sink value fingerprints (--sink_fp) and the sink-slot positions (`self.base_record`, written next to the reference
        cache); digests and fingerprints are computed after the timed call."""
        torch = self.torch
        self.mem("after model load")
        session = self.runner.start()
        self.mem("after baseline session start")
        base, times = {}, []
        self.base_record = []
        for c in range(M + N):
            t0 = time.perf_counter(); fr = self.runner.step(session, c); torch.cuda.synchronize(self.device); times.append(time.perf_counter() - t0)
            self.base_record.append({"call": c, "frame_digest": frame_digest(fr), "sink_vfp": self.sink_value_fp() if self.args.sink_fp else None,
                                     "sink_slot_pos": self.sa.slot_positions(self.pl)["sink_slot_pos"], "service_s": times[-1],
                                     **(self.block_checksums() if getattr(self.args, "block_ck", False) else {})})
            if fr is not None and keep_frames:
                base[c] = fr
            self.runner.noise_hist[c] = float(session.noise_scale)
            if c in (M, M + N - 1):
                self.mem(f"baseline call {c}")
        self.base = base
        self.service_s = float(np.median(times[M:]))
        if getattr(self.args, "block_ck", False):
            # Task B RoPE round-trip test sample: sink K blocks of three layers (row 0), taken before the cache is released
            layers = self.sa.kv_layers(self.pl)
            self.rope_sample = {li: layers[li]["k"][0, :self.sink * self.fsl].clone() for li in (0, len(layers) // 2, len(layers) - 1)}
        if write_ref:
            self.write_reference()
            ref_record_path(self.args).write_text(json.dumps(self.base_record))
        del session
        self.pm.reset_stream_state(reset_vae_flags=True)  # drop the baseline session's caches before the run allocates its own
        import gc

        gc.collect(); torch.cuda.empty_cache()
        self.mem("after baseline cleanup")
        return self.service_s

    def write_reference(self):
        """Cache the reference frames for a later cold-started node on this host (written once per configuration)."""
        path = ref_cache_path(self.args)
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.stem + f".tmp{os.getpid()}.npz")
        np.savez(tmp, **{str(c): fr for c, fr in self.base.items()})
        os.replace(tmp, path)
        print(f"[{self.args.label}] reference cached: {path.name}", flush=True)

    def use_cached_reference(self):
        path = ref_cache_path(self.args)
        if not path.exists():
            raise SystemExit(f"cold start needs the reference cache {path} (start a warm node with the same configuration on this host once)")
        self.base = CachedReference(path)
        rp = ref_record_path(self.args)
        self.base_record = json.loads(rp.read_text()) if rp.exists() else None
        self.service_s = None
        # Runner.start() records the canonical denoising schedule on its first call; a cold node never runs a session
        # before provisioning, so record it here (no session has run yet, so the schedule is still the configured one)
        if not hasattr(self.runner, "_canonical_steps"):
            self.runner._canonical_steps = self.pl.denoising_step_list.detach().clone()
        return path

    def gpu_mem_mb(self):
        return self.torch.cuda.memory_allocated(self.device) / MB

    def reset_peak(self):
        self.torch.cuda.reset_peak_memory_stats(self.device)

    def peak_mem_mb(self):
        return {"peak_allocated_mb": self.torch.cuda.max_memory_allocated(self.device) / MB, "peak_reserved_mb": self.torch.cuda.max_memory_reserved(self.device) / MB}

    # --- source side
    def run_to(self, M: int):
        self.mem("before run_to")
        self.session = self.runner.start()
        for c in range(M):
            self.runner.step(self.session, c)
        self.torch.cuda.synchronize(self.device)
        self.mem(f"after run_to({M})")

    def serialize_live(self) -> dict:
        snap = self.sa.serialize_state(self.pl, self.pm, self.session)
        self.torch.cuda.synchronize(self.device)
        self.mem("after serialize")
        return snap

    def pack(self, snap: dict, comp: str, recent_n: int = 0):
        return self.pack_component(snap, comp, self.sink, self.fsl, recent_n=recent_n)

    # --- destination side
    def provision(self):
        """Fresh buffers for a session this node may receive (not timed)."""
        self.session = self.runner.fresh_destination()
        self.snap = self.sa.serialize_state(self.pl, self.pm, self.session)
        for layer in self.snap["kv"]:
            layer["k"].zero_(); layer["v"].zero_()
        self.snap["have"] = set()
        self.torch.cuda.synchronize(self.device)

    def unpack(self, header: dict, payload):
        self.unpack_into_snapshot(header, payload, self.device, self.snap, self.sink, self.fsl)
        return header.get("h2d_s")

    def restore_fast(self):
        # Task A: a received recent_n component sits in the snapshot's recent region (zeros elsewhere); restoring the
        # "recent" component then writes exactly the transferred slots into the live ring (the rest stays zero, as in M1)
        comps = {"meta", "inflight"} | ({"recent"} if "recent_n" in self.snap.get("have", set()) else set())
        self.sa.restore_state(self.pl, self.pm, self.session, self.snap, comps)
        for block in self.pl.generator.model.blocks:
            block.self_attn.adapt_sink_thr = -1  # refresh frozen until the true Sink binds
        self.torch.cuda.synchronize(self.device)

    def recent_fp(self) -> dict:
        """Task A consumption check: per layer, the live ring's recent-slot positions and value fingerprints (float64 sums
        per row and slot); logged by the source at the handoff and by the destination before its first call."""
        torch, fsl, sink = self.torch, self.fsl, self.sink
        out = {}
        for li, layer in enumerate(self.sa.kv_layers(self.pl)):
            n = layer["pos"].shape[1]
            out[li] = {"pos": layer["pos"][:, sink:].tolist(),
                       "vsum": [[float(layer["v"][b, s * fsl:(s + 1) * fsl].sum(dtype=torch.float64)) for s in range(sink, n)] for b in range(layer["pos"].shape[0])]}
        return out

    def bind(self) -> int:
        shifted = self.bind_sink_into_live(self.pl, self.snap, self.sink, self.fsl, self.device, self.cfg_thr, refresh_was_frozen=True)
        self.torch.cuda.synchronize(self.device)
        return shifted

    def restore_full(self):
        """Full migration: every component received (Phase 1 `full`: restore_state with all components)."""
        self.sa.restore_state(self.pl, self.pm, self.session, self.snap, set(self.sa.STATE_COMPONENTS))
        for block in self.pl.generator.model.blocks:
            block.self_attn.adapt_sink_thr = self.cfg_thr
        self.torch.cuda.synchronize(self.device)

    def cold_restart(self, c: int):
        """Cold restart (Phase 1 `cold`): new session from [last_image of a fresh destination session, chunk c]."""
        for block in self.pl.generator.model.blocks:
            block.self_attn.adapt_sink_thr = self.cfg_thr
        self.session, frames, ms = self.runner.restart_at(self.session, c)
        return frames, ms

    def step(self, c: int, override=None, skip: bool = False):
        self.decodes = []
        t0 = time.perf_counter()
        fr = None
        if not skip:   # skip: the cold restart consumed chunk c (Phase 1: no model call at the restart call)
            fr = self.runner.step(self.session, c)
            self.torch.cuda.synchronize(self.device)
        if override is not None:
            fr = override
        dt = time.perf_counter() - t0
        ref = self.base.get(c)
        ps = ss = None
        if fr is not None and ref is not None:
            ps = float(np.mean([self.sa.psnr(ref[f].astype(np.float32) / 255.0, fr[f].astype(np.float32) / 255.0) for f in range(min(ref.shape[0], fr.shape[0]))]))
            ss = float(self.sa.ssim(ref[-1].astype(np.float32) / 255.0, fr[-1].astype(np.float32) / 255.0))
        self.last_frames = fr   # Experiment RD: decoded output frames of this call (read-only; no effect on generation)
        return fr is not None, ps, ss, dt, self.sa.slot_positions(self.pl)["sink_slot_pos"]

    # ---- XB recompute: input history (uint8 camera frames) and replay inputs
    def input_history(self):
        """The uint8 frames the runtime normalizes (x / 127.5 - 1 -> bf16). Checked once against the runtime's own input
        tensor, so a bit-exact uint8 transfer gives a bit-exact replay input (`input_check`)."""
        if getattr(self, "_hist", None) is None:
            import xb_codec as xc
            from streamv2v.inference_common import load_mp4_as_tensor

            torch = self.torch
            v = load_mp4_as_tensor(self.args.video_path, resize_hw=(self.args.height, self.args.width), normalize=False)   # [C, T, H, W], uint8 values
            u8 = v.round().clamp(0, 255).to(torch.uint8)
            vid = self.runner.video[0]
            n = min(u8.shape[1], vid.shape[1])
            self.input_check = bool(torch.equal((u8[:, :n].float() / 127.5 - 1.0).to(torch.bfloat16), vid[:, :n]))
            self._hist = xc.InputHistory(u8.permute(1, 2, 3, 0).contiguous().numpy())
            self._written = []
        return self._hist

    def write_inputs(self, lo: int, frames):
        """Replay from the transferred frames: overwrite frames [lo, lo + n) of the runtime input with the decoded ones."""
        torch = self.torch
        vid = self.runner.video
        hi = min(lo + len(frames), vid.shape[2])
        if hi <= lo:
            return
        t = (torch.from_numpy(frames[: hi - lo]).permute(3, 0, 1, 2).float() / 127.5 - 1.0).to(torch.bfloat16)
        vid[0, :, lo:hi].copy_(t)
        self._written.append((lo, hi))

    # ---- Experiment VD-2 (emulator-only reconstruction operations; none is used by a frozen path)
    def _sync(self):
        self.torch.cuda.synchronize(self.device)

    def vae_dec_cache_copy(self):
        return [t.detach().clone() for t in self.sa.vae_cache_tensors(self.pl, "dec")]

    def vae_dec_fidelity(self, ref: list) -> dict:
        """Per cached decoder tensor: max |diff| and relative Frobenius error of the live cache vs `ref`."""
        cur = self.sa.vae_cache_tensors(self.pl, "dec")
        if len(cur) != len(ref):
            return {"error": f"layout changed: {len(cur)} vs {len(ref)} tensors"}
        rows = []
        for i, (a, b) in enumerate(zip(cur, ref)):
            if a.shape != b.shape:
                rows.append({"layer": i, "shape_mismatch": [list(a.shape), list(b.shape)]}); continue
            d = (a.float() - b.float())
            rows.append({"layer": i, "max_abs": float(d.abs().max().item()), "rel_fro": float(d.norm().item() / (b.float().norm().item() + 1e-12)), "numel": int(a.numel())})
        rel = [r["rel_fro"] for r in rows if "rel_fro" in r]
        return {"per_layer": rows, "median_rel_fro": float(sorted(rel)[len(rel) // 2]) if rel else None, "worst_rel_fro": max(rel) if rel else None,
                "worst_layer": max(rows, key=lambda r: r.get("rel_fro", -1))["layer"] if rel else None}

    def decode_latents(self, lats: list) -> float:
        """DR-k: decode the given latent frames in order through the live VAE decoder cache (output discarded); seconds."""
        self._sync(); t0 = time.perf_counter()
        with self.torch.no_grad():
            for z in lats:
                self._decode_orig(z)
        self._sync()
        return time.perf_counter() - t0

    def frames_to_images(self, frames):
        """uint8 [n, H, W, 3] -> the pipeline's image tensor [1, 3, n, H, W] in [-1, 1] (as load_mp4_as_tensor)."""
        t = self.torch.from_numpy(np.ascontiguousarray(frames)).to(self.device).permute(3, 0, 1, 2).float() / 127.5 - 1.0
        return t.unsqueeze(0).to(self.torch.bfloat16)

    def temp_sink_prepare(self, images, c: int) -> tuple[list, float]:
        """TS: run the model's own prepare on `images` (a new session, as the cold-restart path) and return the sink
        slots (K, V, pos per layer) it writes; the live session becomes this new session. Seconds measured."""
        torch = self.torch
        self._sync(); t0 = time.perf_counter()
        torch.manual_seed(self.args.seed * 100003 + c + 1)
        self.runner.reset_attention_eviction_state()
        self.pl.denoising_step_list = self.runner._canonical_steps.clone()
        self.session, _ = self.pm.start_stream_session(self.runner.prompt, images, self.args.noise_scale)
        self._sync(); dt = time.perf_counter() - t0
        n = self.sink * self.fsl
        saved = [(layer["k"][:, :n].detach().clone(), layer["v"][:, :n].detach().clone(), layer["pos"][:, :self.sink].detach().clone()) for layer in self.sa.kv_layers(self.pl)]
        return saved, dt

    def write_sink_slots(self, saved: list) -> int:
        """TS: write the K / V of the sink slots the prepare actually filled (prepare writes 2 of 3; the third is filled
        by the first generated chunk, so it stays zero until the exact bind). Positions are NOT written: the live
        positions come from the source's meta (0, 1, 2), and the bind's re-rotation relies on them. Returns the number
        of slots written per layer."""
        from models.wan.causal_model import KV_POS_EMPTY

        n_written = 0
        for layer, (k, v, pos) in zip(self.sa.kv_layers(self.pl), saved):
            filled = [s_ for s_ in range(self.sink) if int(pos[0, s_].item()) != KV_POS_EMPTY]
            for s_ in filled:
                layer["k"][:, s_ * self.fsl:(s_ + 1) * self.fsl] = k[:, s_ * self.fsl:(s_ + 1) * self.fsl]
                layer["v"][:, s_ * self.fsl:(s_ + 1) * self.fsl] = v[:, s_ * self.fsl:(s_ + 1) * self.fsl]
            n_written = len(filled)
        self._sync()
        return n_written

    def zero_sink_slots(self):
        n = self.sink * self.fsl
        for layer in self.sa.kv_layers(self.pl):
            layer["k"][:, :n].zero_(); layer["v"][:, :n].zero_()
        self._sync()

    def replay_one_chunk(self, c: int) -> tuple[float, int]:
        """RP-1: a session prepared on the chunk before the last one, then the last chunk generated (replayed); the live
        session becomes it (recent KV, VAE caches and in-flight rows regenerated). Seconds and replayed calls."""
        self._sync(); t0 = time.perf_counter()
        self.session, _ms, _seed, replayed = self.runner.replay_restart(c, 2, sink0=False)
        self._sync()
        return time.perf_counter() - t0, int(replayed)

    def freeze_refresh(self):
        for block in self.pl.generator.model.blocks:
            block.self_attn.adapt_sink_thr = -1

    # ---- Experiment VD-3 (emulator-only; none is used by a frozen path)
    _DEC_ATTRS = ("_conv_idx", "first_decode")

    def vae_dec_state_copy(self) -> dict:
        """TSinKC: the live decoder cache tensors and their bookkeeping (after the TS prepare's own decode)."""
        vm = self.pl.vae.model
        return {"tensors": self.vae_dec_cache_copy(),
                "attrs": {a: (list(getattr(vm, a)) if isinstance(getattr(vm, a, None), list) else getattr(vm, a, None)) for a in self._DEC_ATTRS}}

    def vae_dec_state_write(self, saved: dict) -> tuple[float, str]:
        """TSinKC: write a saved decoder state back into the live cache (the fast-path restore zeroed it). Returns the
        copy time (an emulation artifact: a node implementation skips the zeroing) and the digest of the live cache."""
        self._sync(); t0 = time.perf_counter()
        cur = self.sa.vae_cache_tensors(self.pl, "dec")
        assert len(cur) == len(saved["tensors"]), "decoder cache layout changed"
        for t, b in zip(cur, saved["tensors"]):
            t.copy_(b)
        vm = self.pl.vae.model
        for a, v in saved["attrs"].items():
            if v is not None:
                setattr(vm, a, list(v) if isinstance(v, list) else v)
        self._sync()
        return time.perf_counter() - t0, self.dec_digest(cur)

    def dec_digest(self, tensors=None) -> str:
        import hashlib

        h = hashlib.sha256()
        for t in (tensors if tensors is not None else self.sa.vae_cache_tensors(self.pl, "dec")):
            h.update(t.detach().float().cpu().numpy().tobytes())
        return h.hexdigest()

    def noise_latents(self, like: list, seed: int) -> tuple[list, dict]:
        """DR2noise: seeded standard-normal latent frames with the shape / dtype of the real ones (their std recorded)."""
        g = self.torch.Generator(device=self.device); g.manual_seed(int(seed))
        out = [self.torch.randn(z.shape, generator=g, device=self.device, dtype=self.torch.float32).to(z.dtype) for z in like]
        return out, {"seed": int(seed), "real_std": [float(z.float().std().item()) for z in like], "real_mean": [float(z.float().mean().item()) for z in like]}

    def temp_slots_left(self, saved: list) -> int:
        """After the bind: the number of (layer, slot) pairs whose K still equals the temporary Sink (must be 0)."""
        from models.wan.causal_model import KV_POS_EMPTY

        n = 0
        for layer, (k, v, pos) in zip(self.sa.kv_layers(self.pl), saved):
            for s_ in range(self.sink):
                if int(pos[0, s_].item()) != KV_POS_EMPTY and self.torch.equal(layer["k"][:, s_ * self.fsl:(s_ + 1) * self.fsl], k[:, s_ * self.fsl:(s_ + 1) * self.fsl]):
                    n += 1
        return n

    # ---- Experiment VD-4 (emulator-only oracle diagnostics; none is used by a frozen path)
    def _slot(self, s_):
        return slice(s_ * self.fsl, (s_ + 1) * self.fsl)

    def n_slots(self) -> int:
        return int(self.sa.kv_layers(self.pl)[0]["pos"].shape[1])

    def restore_all_from(self, snap: dict):
        """V0: every component from the source snapshot, refresh unfrozen (the Phase 1 full path on that snapshot)."""
        self.sa.restore_state(self.pl, self.pm, self.session, snap, set(self.sa.STATE_COMPONENTS))
        for block in self.pl.generator.model.blocks:
            block.self_attn.adapt_sink_thr = self.cfg_thr
        self._sync()

    def write_snap_slots(self, snap: dict, slots: list, kv_override: dict | None = None) -> int:
        """Oracle: write the snapshot's K and V of `slots` into every live layer (positions are not written: the live
        meta came from the same snapshot; checked separately). kv_override {slot: [(k, v) per layer]} replaces the
        snapshot's values (quantized Sink)."""
        layers = self.sa.kv_layers(self.pl)
        assert len(layers) == len(snap["kv"]), "layer count differs from the snapshot"
        for li, layer in enumerate(layers):
            for s_ in slots:
                k, v = kv_override[s_][li] if kv_override else (snap["kv"][li]["k"][:, self._slot(s_)], snap["kv"][li]["v"][:, self._slot(s_)])
                layer["k"][:, self._slot(s_)] = k
                layer["v"][:, self._slot(s_)] = v
        self._sync()
        return len(layers)

    def kv_digest(self, slots: list, part: str, snap: dict | None = None, kv_override: dict | None = None) -> str:
        """SHA-256 over every layer of K or V of `slots`: live (snap None), the snapshot's, or an override's."""
        import hashlib

        h = hashlib.sha256()
        layers = self.sa.kv_layers(self.pl) if snap is None else snap["kv"]
        for li, layer in enumerate(layers):
            for s_ in slots:
                if kv_override is not None:
                    t = kv_override[s_][li][0 if part == "k" else 1]
                else:
                    t = layer[part][:, self._slot(s_)]
                h.update(t.detach().contiguous().view(self.torch.uint8).cpu().numpy().tobytes())
        return h.hexdigest()

    def temp_digest(self, saved: list, slots: list, part: str) -> str:
        """SHA-256 over every layer of K or V of `slots` in a saved temporary Sink [(k, v, pos) per layer]."""
        import hashlib

        h = hashlib.sha256()
        for k, v, _pos in saved:
            for s_ in slots:
                h.update((k if part == "k" else v)[:, self._slot(s_)].detach().contiguous().view(self.torch.uint8).cpu().numpy().tobytes())
        return h.hexdigest()

    def slot_equal(self, slots: list, part: str, snap: dict | None = None, saved: list | None = None, override: dict | None = None) -> list:
        """Addendum 1: per layer, per slot, whether the live K or V is bitwise equal to the snapshot's (snap), an
        override's (quantized Sink) or a saved temporary Sink's (saved)."""
        torch = self.torch
        out = []
        for li, layer in enumerate(self.sa.kv_layers(self.pl)):
            row = []
            for s_ in slots:
                if override is not None:
                    ref = override[s_][li][0 if part == "k" else 1]
                elif snap is not None:
                    ref = snap["kv"][li][part][:, self._slot(s_)]
                else:
                    ref = saved[li][0 if part == "k" else 1][:, self._slot(s_)]
                a = layer[part][:, self._slot(s_)]
                row.append(a.shape == ref.shape and a.dtype == ref.dtype and bool(torch.equal(a.contiguous().view(torch.uint8), ref.contiguous().view(torch.uint8))))
            out.append(row)
        return out

    def dec_layout(self, snap: dict) -> dict:
        """Addendum 1: the live decoder cache against the snapshot, entry by entry of `_feat_map` (tensor or not, shape,
        dtype, bitwise equality) and the bookkeeping attributes."""
        torch = self.torch
        vm = self.pl.vae.model
        live, src = getattr(vm, "_feat_map", None), snap["vae"].get("_feat_map")
        out = {"entries_live": len(live) if isinstance(live, list) else None, "entries_snapshot": len(src) if isinstance(src, list) else None,
               "tensors": 0, "layout_mismatch": [], "unequal": [], "bytes": 0}
        if isinstance(live, list) and isinstance(src, list) and len(live) == len(src):
            for i, (a, b) in enumerate(zip(live, src)):
                ta, tb = isinstance(a, torch.Tensor), isinstance(b, torch.Tensor)
                if ta != tb or (ta and (tuple(a.shape) != tuple(b.shape) or a.dtype != b.dtype)):
                    out["layout_mismatch"].append(i); continue
                if ta:
                    out["tensors"] += 1; out["bytes"] += int(a.numel() * a.element_size())
                    if not torch.equal(a.contiguous().view(torch.uint8), b.contiguous().view(torch.uint8)):
                        out["unequal"].append(i)
        out["layout_ok"] = out["entries_live"] is not None and out["entries_live"] == out["entries_snapshot"] and not out["layout_mismatch"] and out["tensors"] > 0
        out["tensors_equal"] = out["layout_ok"] and not out["unequal"]
        attrs = {a: (getattr(vm, a, None) == snap["vae"].get(a)) for a in self._DEC_ATTRS}
        out["attrs"] = attrs
        out["attrs_equal"] = all(attrs.values())
        return out

    def kv_nbytes(self, slots: list) -> int:
        layers = self.sa.kv_layers(self.pl)
        return int(sum(2 * layer["k"][:, self._slot(s_)].numel() * layer["k"].element_size() for layer in layers for s_ in slots))

    def positions(self, slots: list, snap: dict | None = None) -> list:
        """Per layer, the recorded position of each slot (live or snapshot)."""
        src = [r["pos"] for r in snap["ring"]] if snap is not None else [layer["pos"] for layer in self.sa.kv_layers(self.pl)]
        return [[int(p[0, s_].item()) for s_ in slots] for p in src]

    def positions_all(self, slots: list, snap: dict | None = None) -> list:
        """Addendum 1b: per layer, per batch row, the recorded position of each slot (live or snapshot). `positions`
        (row 0 only) is kept as frozen for the original checks."""
        src = [r["pos"] for r in snap["ring"]] if snap is not None else [layer["pos"] for layer in self.sa.kv_layers(self.pl)]
        return [[[int(p[b, s_].item()) for s_ in slots] for b in range(p.shape[0])] for p in src]

    def dec_state_from_snap(self, snap: dict) -> dict:
        fm = snap["vae"].get("_feat_map") or []
        return {"tensors": [t for t in fm if isinstance(t, self.torch.Tensor)],
                "attrs": {a: (list(snap["vae"][a]) if isinstance(snap["vae"].get(a), list) else snap["vae"].get(a)) for a in self._DEC_ATTRS}}

    def rotate_temp(self, saved: list, deltas: list) -> tuple[list, dict]:
        """A1: the temporary Sink's keys re-rotated per layer and slot by deltas[layer][slot] (values untouched).
        Returns the rotated copy and the round-trip error (rotate by -delta and compare with the original keys)."""
        from models.wan.causal_model import _shift_temporal_rope

        freqs = self.pl.generator.model.freqs.to(self.device)
        out, worst, n_rot, per = [], 0.0, 0, []
        for li, ((k, v, pos), dl) in enumerate(zip(saved, deltas)):
            k2 = k.clone()
            for s_, d in enumerate(dl):
                rec = {"layer": li, "slot": s_, "delta": d, "k_elements_changed": 0, "k_elements": int(k[:, self._slot(s_)].numel()), "round_trip_max_abs": 0.0}
                per.append(rec)   # addendum 1: per layer and slot (slots the prepare left empty carry delta None)
                if d is None or d == 0:
                    continue
                for b in range(k.shape[0]):
                    r = _shift_temporal_rope(k[b, self._slot(s_)], freqs, int(d))
                    back = _shift_temporal_rope(r, freqs, -int(d))
                    err = float((back.float() - k[b, self._slot(s_)].float()).abs().max().item())
                    worst = max(worst, err)
                    rec["round_trip_max_abs"] = max(rec["round_trip_max_abs"], err)
                    bits = {1: self.torch.uint8, 2: self.torch.int16, 4: self.torch.int32}[k.element_size()]   # bitwise, one integer per element
                    rec["k_elements_changed"] += int((r.contiguous().view(bits) != k[b, self._slot(s_)].contiguous().view(bits)).sum().item())
                    k2[b, self._slot(s_)] = r
                    n_rot += 1
            out.append((k2, v, pos))
        return out, {"rotated_slot_layers": n_rot, "round_trip_max_abs": worst, "per_layer_slot": per}

    def quantize_slots(self, snap: dict, slots: list, mode: str) -> tuple[dict, int]:
        """Exploratory: the snapshot's K / V of `slots` quantized and dequantized. fp8: e4m3 with a per-tensor scale;
        int4: symmetric, groups of 64 along the last dimension. Returns {slot: [(k, v) per layer]} and the payload bytes."""
        torch = self.torch

        def q(t):
            x = t.float()
            if mode == "fp8":
                sc = x.abs().amax().clamp(min=1e-12) / 448.0
                return (x / sc).to(torch.float8_e4m3fn).float().mul(sc).to(t.dtype), x.numel() + 4
            g = x.reshape(*x.shape[:-1], x.shape[-1] // 64, 64)
            sc = g.abs().amax(-1, keepdim=True).clamp(min=1e-12) / 7.0
            return (torch.round(g / sc).clamp(-8, 7) * sc).reshape(x.shape).to(t.dtype), x.numel() // 2 + sc.numel() * 2
        out, nb = {}, 0
        for s_ in slots:
            out[s_] = []
            for li in range(len(snap["kv"])):
                kq, bk = q(snap["kv"][li]["k"][:, self._slot(s_)]); vq, bv = q(snap["kv"][li]["v"][:, self._slot(s_)])
                out[s_].append((kq, vq)); nb += bk + bv
        return out, int(nb)

    def restore_inputs(self):
        """Undo write_inputs (lossy sensitivity runs) so the next run starts from the original input."""
        if not getattr(self, "_written", None):
            return
        torch = self.torch
        for lo, hi in self._written:
            f = self._hist.frames(lo, hi)
            self.runner.video[0, :, lo:hi].copy_((torch.from_numpy(f).permute(3, 0, 1, 2).float() / 127.5 - 1.0).to(torch.bfloat16))
        self._written = []

    def release(self):
        self.snap = None; self.session = None
        self.pm.reset_stream_state(reset_vae_flags=True)
        import gc

        gc.collect(); self.torch.cuda.empty_cache()
        self.mem("after release")


class FakeRuntime:
    """Protocol test double (no torch): fixed-size random Sink, sleep-based generation, PSNR marker values.
    Never used for reported results."""

    def __init__(self, args):
        self.args = args
        self.service_s = args.dry_service_s
        self.rng = np.random.default_rng(1234)
        self.sink_bytes = self.rng.integers(0, 256, size=args.dry_sink_mb << 20, dtype=np.uint8)
        self.k = 2
        self.bound = False
        self.have_fast = False
        self.full = False
        self.cold = False
        self.decodes = []
        self.fp_ver = 0
        self.promote_calls = {int(x) for x in str(args.dry_promote_calls or "").split(",") if x}
        self.base_record = None
        self.staged = None       # VACW loopback: the last unpacked Sink image; bind() makes it the live Sink
        self.n_dirty = 0         # dry promotions applied to the live Sink since the last bind (each dirties dry_dirty_frags fragments)

    def sink_value_fp(self):
        return [float(self.fp_ver)]

    def baseline(self, M, N, keep_frames=True, write_ref=True):
        self.base_record = [{"call": c, "frame_digest": f"dry{c}", "sink_vfp": [0.0] if self.args.sink_fp else None, "sink_slot_pos": [0, 1, 2], "service_s": self.service_s}
                            for c in range(M + N)]
        return self.service_s

    def gpu_mem_mb(self):
        return 0.0

    def reset_peak(self):
        pass

    def peak_mem_mb(self):
        return {"peak_allocated_mb": 0.0, "peak_reserved_mb": 0.0}

    def run_to(self, M):
        pass

    def serialize_live(self):
        return {}

    def pack(self, snap, comp, recent_n=0):
        if comp == "recent_n":
            n = int(recent_n)
            b = self.rng.integers(0, 256, size=max(1, n) << 20, dtype=np.uint8)
            return {"comp": comp, "tensors": [{"name": "kv/0/k/0/3", "offset": 0, "nbytes": len(b), "shape": [len(b)], "dtype": "bf16"}], "nbytes": len(b) if n else 0, "d2h_s": 0.0,
                    "scalars": {"recent_slots": {"0": [[3, 4, 5][:n]]}}}, [b] if n else []
        if comp == "sink":
            b = self.sink_bytes
            n = len(b) // 4
            header = {"comp": "sink", "tensors": [{"name": f"kv/{i}", "offset": i * n, "nbytes": n, "shape": [n], "dtype": "bf16"} for i in range(4)], "nbytes": len(b), "d2h_s": 0.0}
            return header, [b[i * n:(i + 1) * n] for i in range(4)]
        size = {"meta": 2 << 20, "inflight": 200 << 10, "recent": len(self.sink_bytes), "vae": 2 * len(self.sink_bytes)}[comp]
        b = self.rng.integers(0, 256, size=size, dtype=np.uint8)
        return {"comp": comp, "tensors": [{"name": comp, "offset": 0, "nbytes": len(b), "shape": [len(b)], "dtype": "bf16"}], "nbytes": len(b), "d2h_s": 0.0}, [b]

    def provision(self):
        self.bound = False; self.have_fast = False; self.full = False; self.cold = False; self.provisioned = True

    def restore_full(self):
        self.full = True; self.bound = True; self.cold = False

    def cold_restart(self, c):
        time.sleep(0.05); self.cold = True; self.bound = False; self.full = False
        return np.zeros(4, dtype=np.uint8), 50.0

    def use_cached_reference(self):
        self.service_s = None
        return None

    def unpack(self, header, payload):
        if not getattr(self, "provisioned", False):
            # mirrors GpuRuntime.unpack, which writes into the provisioned receive snapshot (self.snap) and fails without it
            raise RuntimeError("unpack on a runtime without provisioned receive buffers")
        if header["comp"] in ("inflight", "meta"):
            self.have_fast = True
        if header["comp"] == "sink":
            self.staged = np.frombuffer(bytes(payload), dtype=np.uint8).copy()
        return 0.0

    def recent_fp(self):
        return {}

    def restore_fast(self):
        pass

    def bind(self):
        self.bound = True; self.fp_ver += 1
        if self.staged is not None:
            self.sink_bytes = self.staged.copy(); self.n_dirty = 0   # the live Sink is exactly the bound image (I5 / I7 in the loopback)
        return 73

    def dirty(self, c: int):
        """Dry promotion at call c: change a known set of fragments of the live Sink (fragment j of the promotion's set
        = (n_dirty * dry_dirty_frags + j) mod n_frags, first bytes of the fragment), so a fresh snapshot differs from the
        bound image by a predictable fragment set."""
        fb = int(self.args.dry_frag_bytes); nf = max(1, len(self.sink_bytes) // fb)
        ids = [((self.n_dirty * self.args.dry_dirty_frags) + j) % nf for j in range(self.args.dry_dirty_frags)]
        for fi in ids:
            self.sink_bytes[fi * fb:fi * fb + 16] = self.rng.integers(0, 256, size=16, dtype=np.uint8)
        self.n_dirty += 1
        return ids

    def step(self, c, override=None, skip=False):
        self.last_frames = None
        if skip:
            self.decodes = []
            return False, None, None, 0.0, [0, 1, 6]
        time.sleep(self.args.dry_service_s)
        if self.bound and c in self.promote_calls:
            self.fp_ver += 1   # dry promotion (protocol test of the version-event accounting)
            self.dirty(c)      # and the live Sink changes by a known fragment set (VACW loopback)
        self.decodes = [(time.time(), 4)]
        if self.cold:
            ps = 19.5 + self.rng.normal(0, 0.5)
        elif self.full:
            ps = 99.0
        else:
            ps = 44.0 + self.rng.normal(0, 0.5) if self.bound else 16.5 + self.rng.normal(0, 0.3)
        return True, float(ps), 0.9 if self.bound else 0.6, self.args.dry_service_s, [0, 1, 6]

    # Experiment VD-2 doubles (sleep-based; no state)
    last_latents = []
    capture_latents = False

    def vae_dec_cache_copy(self):
        return [0]

    def vae_dec_fidelity(self, ref):
        return {"per_layer": [{"layer": 0, "max_abs": 0.0, "rel_fro": 0.01, "numel": 1}], "median_rel_fro": 0.01, "worst_rel_fro": 0.01, "worst_layer": 0}

    def decode_latents(self, lats):
        time.sleep(0.001 * max(1, len(lats))); return 0.001 * max(1, len(lats))

    def frames_to_images(self, frames):
        return frames

    def temp_sink_prepare(self, images, c):
        time.sleep(0.002); self.cold = False; self.bound = False; return [("k", "v", "pos")], 0.002

    def write_sink_slots(self, saved):
        self.temp_sink = True; return 2

    def zero_sink_slots(self):
        self.temp_sink = False

    def replay_one_chunk(self, c):
        time.sleep(0.003); return 0.003, 1

    def freeze_refresh(self):
        pass

    # Experiment VD-3 doubles
    def vae_dec_state_copy(self):
        return {"tensors": [0], "attrs": {}}

    def vae_dec_state_write(self, saved):
        return 0.0001, "fake-dec-digest"

    def dec_digest(self, tensors=None):
        return "fake-dec-digest"

    def noise_latents(self, like, seed):
        return list(like), {"seed": int(seed), "real_std": [], "real_mean": []}

    def temp_slots_left(self, saved):
        return 0

    # Experiment VD-4 doubles (deterministic strings; no state)
    def n_slots(self):
        return 6

    def restore_all_from(self, snap):
        self.full = True; self.bound = True

    def write_snap_slots(self, snap, slots, kv_override=None):
        return 30

    def kv_digest(self, slots, part, snap=None, kv_override=None):
        return f"fake-{part}-{'-'.join(map(str, slots))}"

    def temp_digest(self, saved, slots, part):
        return f"fake-{part}-{'-'.join(map(str, slots))}"

    def kv_nbytes(self, slots):
        return 575078880 * len(slots)

    def slot_equal(self, slots, part, snap=None, saved=None, override=None):
        return [[True] * len(slots) for _ in range(30)]

    def dec_layout(self, snap):
        return {"entries_live": 1, "entries_snapshot": 1, "tensors": 1, "layout_mismatch": [], "unequal": [], "bytes": 0,
                "layout_ok": True, "tensors_equal": True, "attrs": {}, "attrs_equal": True}

    def positions(self, slots, snap=None):
        return [[[0, 1, 6, 31, 32, 33][s_] for s_ in slots] for _ in range(30)]

    def positions_all(self, slots, snap=None):
        return [[[[0, 1, 6, 31, 32, 33][s_] for s_ in slots] for _ in range(2)] for _ in range(30)]

    def dec_state_from_snap(self, snap):
        return {"tensors": [0], "attrs": {}}

    def rotate_temp(self, saved, deltas):
        return saved, {"rotated_slot_layers": 0, "round_trip_max_abs": 0.0}

    def quantize_slots(self, snap, slots, mode):
        return {s_: [] for s_ in slots}, 1000

    def input_history(self):
        if getattr(self, "_hist", None) is None:
            import xb_codec as xc

            self._hist = xc.InputHistory(xc.synthetic_clip(self.args.height, self.args.width)); self.input_check = True
        return self._hist

    def write_inputs(self, lo, frames):
        pass

    def restore_inputs(self):
        pass

    def release(self):
        self.provisioned = False   # as GpuRuntime.release drops the receive snapshot


# ----------------------------------------------------------------------------- node
class Node:
    def __init__(self, args):
        self.a = args
        self.label = args.label
        self.me = socket.gethostname()
        self.rt = FakeRuntime(args) if args.dry_run else GpuRuntime(args)
        self.t_runtime_ready = time.time()   # model weights loaded, CUDA initialized
        self.ref_path = None
        self.recv_pool = None   # Full migration: Phase 1's two preallocated receive buffers (allocated before a run, untimed)
        self.lock = threading.Lock()
        self.ctl = None
        self.ctl_lock = threading.Lock()
        self.run = None  # per-run state dict
        self.flows: dict[str, dict] = {}
        self.off = 0.0  # unused on the node side (orchestrator converts); kept for symmetry
        self.data_srv = tcp_listen(args.bind, args.data_port, args.mss)
        threading.Thread(target=self._data_accept_loop, daemon=True).start()

    def _thread_init(self):
        """torch.set_grad_enabled(False) is thread-local: every worker thread that may touch the model must
        disable autograd itself, or forward passes keep their activations and the GPU fills up."""
        if not self.a.dry_run:
            self.rt.torch.set_grad_enabled(False)

    # ------------------------------------------------------------------ control plane
    def send(self, kind: str, **fields):
        with self.ctl_lock:
            send_msg(self.ctl, kind, {"label": self.label, "host": self.me, **fields}, b"", None)

    def event(self, event: str, t: float | None = None, **detail):
        t = time.time() if t is None else t
        r = self.run
        if r is not None:
            r["ev"].log(event, t, **detail)
        self.send("EVENT", event=event, t=t, detail=detail)

    def reply(self, cmd_id, **fields):
        self.send("REPLY", cmd_id=cmd_id, **fields)

    def serve(self):
        srv = tcp_listen(self.a.bind, self.a.ctl_port, self.a.mss)
        self.t_listen = time.time()
        print(f"[{self.label}] {self.me}: control {self.a.ctl_port}, data {self.a.data_port}, mss {self.a.mss}; waiting for the orchestrator", flush=True)
        while True:
            self.ctl = tcp_accept(srv, self.a.mss)
            clock_sync_server(self.ctl)
            self.send("HELLO", host_info=host_info(self.a.gpu_id), mss_effective=effective_mss(self.ctl), mss_warnings=list(MSS_WARNINGS),
                      service_s=self.rt.service_s, dry_run=self.a.dry_run, data_port=self.a.data_port, k=self.rt.k, pid=os.getpid(),
                      cold_start=bool(self.a.cold_start), t_main=T_MAIN, t_runtime_ready=self.t_runtime_ready, t_listen=self.t_listen,
                      reference=str(self.ref_path) if self.ref_path else "baseline", commit=_git_commit(), codecs=self._codecs(),
                      identity=node_identity(self.a))
            try:
                while True:
                    hdr, payload = recv_msg(self.ctl)
                    if hdr["kind"] == "SHUTDOWN":
                        print(f"[{self.label}] shutdown", flush=True); return
                    threading.Thread(target=self._dispatch, args=(hdr,), daemon=True).start()
            except (ConnectionError, OSError) as exc:
                print(f"[{self.label}] control connection lost: {exc}", flush=True)

    def _dispatch(self, hdr: dict):
        kind, cid = hdr["kind"], hdr.get("cmd_id")
        self._thread_init()
        try:
            fn = getattr(self, "cmd_" + kind.lower())
            out = fn(hdr) or {}
            self.reply(cid, ok=True, **out)
        except Exception as exc:  # noqa: BLE001
            import traceback

            traceback.print_exc()
            self.reply(cid, ok=False, error=repr(exc))

    # ------------------------------------------------------------------ commands
    def cmd_run_begin(self, h):
        if hasattr(self.rt, "restore_inputs"):
            self.rt.restore_inputs()   # XB lossy-input runs overwrite replay inputs; every run starts from the original input
        rd = REPO_ROOT / h["run_rel"] / f"node_{self.label}"
        rd.mkdir(parents=True, exist_ok=True)
        ev = EventLog(rd / "events.csv", self.me, h["t0"] if h.get("t0") else None)
        metrics = CsvLog(rd / "metrics.csv", ["call", "t_out", "owner", "chunk_s", "psnr", "ssim", "missing", "sink_bound", "gpu_mem_alloc_mb", "sink_slot_pos", "t_decode", "n_frames",
                                              "sink_vfp", "promotion", "fp_ms"])
        if getattr(self.rt, "base_record", None) is not None:
            (rd / "baseline_record.json").write_text(json.dumps(self.rt.base_record))
        frag_log = CsvLog(rd / "fragments.csv", ["t", "event", "session_id", "sink_version", "fragment_id", "src", "dst", "bytes", "flow", "ok"])
        sampler = ResourceSampler(rd / "network.csv", self.me, self.a.gpu_id if not self.a.dry_run else None, self.a.iface); sampler.start()
        self.run = {"id": h["run_id"], "dir": rd, "ev": ev, "metrics": metrics, "frag_log": frag_log, "sampler": sampler, "session_id": h["session_id"],
                    "manifest": None, "sink": None, "have": set(), "frag_ok": {}, "sink_complete_t": None, "sink_verified": None, "sink_verified_t": None,
                    "owner": False, "stop_owner": False, "gen_thread": None, "call": None, "bound_call": None, "rejoin_call": None, "first_out_t": None,
                    "sink_unpacked": False, "bind_requested": False, "pending_handoff": None,
                    "full_pack": None, "full_xfer": None, "dropped_flows": set(), "pending_cold": None, "n_owned": 0, "epoch": 0,
                    "last_fp": None, "bind_at": None, "promotions": [], "snapshots": [], "versions": set(), "await_manifest": False, "unpacked_version": None,
                    "xb": None, "xb_snap_req": None, "xb_store": None, "xb_rc": None, "wait_sink": False,
                    "exact_check": bool(h.get("exact_check")), "delivery": h.get("delivery"), "user_edge": h.get("user_edge"), "deliv_q": None, "deliv_thread": None}
        if self.run["delivery"]:
            import queue

            self.run["deliv_q"] = queue.Queue()
            self.run["deliv_thread"] = threading.Thread(target=self._delivery_worker, args=(self.run,), daemon=True); self.run["deliv_thread"].start()
        self.flows = {}
        self.rt.reset_peak()   # G9: peak memory_allocated / reserved over this run
        return {}

    def _build_sink_manifest(self, snap: dict, frag_bytes: int, k: int) -> tuple[dict, bytearray, dict]:
        """Pack the Sink of `snap` into one contiguous host buffer; fragment table with per-fragment SHA-256; whole digest.
        Returns (manifest, buffer, timings)."""
        t0 = time.time()
        header, bufs = self.rt.pack(snap, "sink")
        buf = bytearray(header["nbytes"]); mv = memoryview(buf)
        for t, b in zip(header["tensors"], bufs):
            mv[t["offset"]:t["offset"] + t["nbytes"]] = memoryview(b).cast("B")
        t1 = time.time()
        digest = component_digest(payload_slices(header, buf))
        frags = frag_table(header["nbytes"], frag_bytes)
        futs = [_pool().submit(sha256_hex, mv[f["off"]:f["off"] + f["len"]]) for f in frags]
        for f, fu in zip(frags, futs):
            f["sha256"] = fu.result()
        t2 = time.time()
        r = self.run
        man = {"session_id": r["session_id"], "sink_version": digest[:16], "sink_digest": digest, "nbytes": header["nbytes"], "header": header, "frags": frags,
               "frag_bytes": int(frag_bytes), "snapshot_k": k}
        return man, buf, {"pack_s": t1 - t0, "hash_s": t2 - t1}

    def _install_store(self, man: dict, buf: bytearray, verified: bool):
        """Make `man` this node's current manifest with `buf` as the buffer object fragments are served from / received into.
        VACW (design section 1.2, Amendment 1): the store is {buf, man, hash}; `hash[f]` is the SHA-256 of the bytes held
        for f; `have` = ids whose hash equals the current manifest's entry. A fresh capture installs a NEW buffer object
        (flows started earlier keep the old one by reference); a manifest update keeps the buffer."""
        r = self.run
        with self.lock:
            r["sink"] = {"buf": buf, "man": man, "hash": ({f["id"]: f["sha256"] for f in man["frags"]} if verified else {})}
            r["manifest"] = man
            r["versions"].add(man["sink_version"])
            r["have"] = set(range(len(man["frags"]))) if verified else set()
            r["frag_ok"] = {f["id"]: True for f in man["frags"]} if verified else {}
            r["sink_complete_t"] = r["sink_verified_t"] = time.time() if verified else None
            r["sink_verified"] = True if verified else None
            r["sink_unpacked"] = False

    def cmd_source_prep(self, h):
        """A: run the session to chunk M, serialize, build the fragment table of the exact Sink serialization."""
        r = self.run
        M = int(h["M"])
        t0 = time.time()
        self.rt.run_to(M)
        t1 = time.time()
        snap = self.rt.serialize_live()
        t2 = time.time()
        # one contiguous host copy of the exact serialization (fragments are byte ranges of it)
        man, buf, _tm = self._build_sink_manifest(snap, int(h["frag_bytes"]), 0)
        t3 = time.time()
        self._install_store(man, buf, verified=True)
        r["snapshots"].append({"k": 0, "digest": man["sink_digest"], "sink_version": man["sink_version"], "t": t3, "call": M})
        r["live_snap"] = snap; r["call"] = M; r["owner"] = True  # A owns execution (not generating until told)
        self.event("source_prepared", t3, M=M, run_to_M_s=t1 - t0, serialize_s=t2 - t1, pack_hash_s=t3 - t2, sink_nbytes=man["nbytes"], n_frags=len(man["frags"]), sink_version=man["sink_version"])
        return {"manifest": man, "t_prepared": t3}

    def cmd_manifest(self, h):
        """B/C/D: learn the Sink's identity and layout; preallocate the receive buffer; provision GPU buffers."""
        r = self.run
        self._install_store(h["manifest"], bytearray(h["manifest"]["nbytes"]), verified=False)
        self.rt.provision()
        if h.get("full_pool") and self.recv_pool is None:
            # same size rule as Phase 1's destination (largest component, the VAE caches, fits); kept for the process lifetime
            a = self.a
            n = (2 * (a.dry_sink_mb << 20) + (64 << 20)) if a.dry_run else int(estimate_sink_bytes(self.rt.k, a.height, a.width, a.model_type) * 2.2) + (64 << 20)
            self.recv_pool = RecvPool(n)
        self.event("provisioned", sink_nbytes=r["manifest"]["nbytes"], n_frags=len(r["manifest"]["frags"]), recv_pool_mb=self.recv_pool and len(self.recv_pool.bufs[0]) / MB)
        return {}

    def cmd_manifest_update(self, h):
        """VACW: a fresh snapshot S_k became the active manifest. The buffer is kept; a held fragment stays valid iff its
        content hash equals the new manifest's entry (design section 1.2); the node reports its valid holdings. The node
        that captured S_k already runs on it (no-op here). Bind / staging state is reset for the new snapshot."""
        r = self.run
        new = h["manifest"]
        t0 = time.time()
        with self.lock:
            st = r["sink"]; old = r["manifest"]
            same = old is not None and old["sink_version"] == new["sink_version"]
            if not same:
                assert st is not None and new["nbytes"] == old["nbytes"] and len(new["frags"]) == len(old["frags"]), "manifest layout changed within a session"
                st["man"] = new; r["manifest"] = new; r["versions"].add(new["sink_version"])
                valid = {f["id"] for f in new["frags"] if st["hash"].get(f["id"]) == f["sha256"]}
                n_stale = sum(1 for fid, hsh in st["hash"].items() if hsh != new["frags"][fid]["sha256"])
                r["have"] = valid; r["frag_ok"] = {fid: True for fid in valid}
                complete = len(valid) == len(new["frags"])
                r["sink_complete_t"] = t0 if complete else None
                r["sink_verified"] = None; r["sink_verified_t"] = None
                r["sink_unpacked"] = False
            else:
                valid = set(r["have"]); n_stale = 0; complete = False
            r["await_manifest"] = False
        if not same:
            self.event("manifest_update", t0, sink_version=new["sink_version"], prev=old["sink_version"], snapshot_k=new.get("snapshot_k"), n_valid=len(valid), n_stale=n_stale,
                       n_absent=len(new["frags"]) - len(valid) - n_stale, complete=complete)
            if complete:
                threading.Thread(target=self._verify_sink, args=(t0,), daemon=True).start()
        return {"valid": sorted(valid), "n_stale": n_stale, "same": same, "complete": complete, "owner": r["owner"], "bound": r["bound_call"] is not None}

    def cmd_exec_handoff(self, h):
        """Current owner: stop at the next chunk boundary and hand over. mode "fast" (M1): ship in-flight rows + metadata
        to `to`; "cold": no state, only the call number; "full": pack every state component and send it in the
        background (redirectable with FULL_CANCEL / FULL_SEND)."""
        r = self.run
        assert r["owner"], "not the execution owner"
        mode = h.get("mode", "fast")
        t_req = time.time()
        if r["gen_thread"] is not None and r["gen_thread"].is_alive():
            r["stop_owner"] = True
            r["gen_thread"].join()
        t_stop = time.time()
        r["owner"] = False
        snap = r.pop("live_snap", None)
        if snap is None and mode != "cold":   # cold restart ships no state: nothing to serialize
            snap = self.rt.serialize_live()
        t_ser = time.time()
        if mode == "full":
            comps, nbytes = [], 0
            for comp in FULL_COMPS:
                hdr, bufs = self.rt.pack(snap, comp)
                comps.append((hdr, bufs, digest_async(bufs))); nbytes += hdr["nbytes"]
            del snap
            t_packed = time.time()
            r["full_pack"] = {"comps": comps, "call": r["call"], "nbytes": nbytes}
            self._release_source_session()
            self.event("exec_stop", t_stop, call=r["call"], to=h["to"], mode=mode, wait_boundary_s=t_stop - t_req, serialize_s=t_ser - t_stop, pack_s=t_packed - t_ser, state_bytes=nbytes)
            self._full_send(h)
            return {"t_stop": t_stop, "t_fg_sent": None, "t_packed": t_packed, "call": r["call"], "fg_bytes": 0, "state_bytes": nbytes}
        conn = tcp_connect(h["to_host"], int(h["to_port"]), self.a.mss, timeout=60)
        nbytes = 0
        was_bound = r["bound_call"] is not None
        fresh = bool(h.get("fresh")) and was_bound   # VACW: a bound owner captures S_k at the handoff boundary (design 1.1 / 1.3)
        n_rs = int(h.get("recent_slots", 0) or 0)
        fast_comps = ("inflight", "meta") + (("recent_n",) if n_rs > 0 else ())
        if mode == "fast" and n_rs > 0:
            self.event("recent_handoff_src", call=r["call"], recent_slots=n_rs, fp=self.rt.recent_fp())
        for comp in (fast_comps if mode == "fast" else ()):
            hdr, bufs = self.rt.pack(snap, comp, recent_n=n_rs) if comp == "recent_n" else self.rt.pack(snap, comp)
            send_msg(conn, "FG", {"from": self.label, "run_id": r["id"], "session_id": r["session_id"], **hdr}, bufs, None)
            nbytes += hdr["nbytes"]
        send_msg(conn, "GO", {"from": self.label, "run_id": r["id"], "call": r["call"], "t_go": time.time(), "mode": mode, "recent_slots": n_rs, "fresh_pending": fresh,
                              "wait_sink": bool(h.get("wait_sink"))}, b"", None)
        t_sent = time.time()
        conn.close()
        out = {}
        if fresh:
            # S_k: the Sink this owner was generating on (the ring is frozen: generation stopped at the boundary), from the
            # same serialization as the fast path; new buffer object (I3 / I4), per-fragment hashes, whole digest
            k = int(h.get("snapshot_k") or len(r["snapshots"]))
            man, buf, tm = self._build_sink_manifest(snap, int(h.get("frag_bytes") or r["manifest"]["frag_bytes"]), k)
            t_cap = time.time()
            self._install_store(man, buf, verified=True)
            r["snapshots"].append({"k": k, "digest": man["sink_digest"], "sink_version": man["sink_version"], "t": t_cap, "call": r["call"]})
            self.event("snapshot_captured", t_cap, call=r["call"], snapshot_k=k, sink_version=man["sink_version"], pack_s=tm["pack_s"], hash_s=tm["hash_s"], capture_s=t_cap - t_sent,
                       n_frags=len(man["frags"]), prev_version=r["snapshots"][-2]["sink_version"] if len(r["snapshots"]) > 1 else None)
            out = {"fresh_manifest": man, "t_captured": t_cap, "capture": {**tm, "capture_s": t_cap - t_sent}}
        del snap
        self._release_source_session()
        self.event("exec_stop", t_stop, call=r["call"], to=h["to"], mode=mode, wait_boundary_s=t_stop - t_req, serialize_s=t_ser - t_stop, fg_bytes=nbytes, fg_send_s=t_sent - t_ser, was_bound=was_bound, fresh=fresh)
        return {"t_stop": t_stop, "t_fg_sent": t_sent, "call": r["call"], "fg_bytes": nbytes, "was_bound": was_bound, **out}

    def _release_source_session(self):
        if self.label == "A":
            self.rt.session = None; self.rt.snap = None
            self.rt.torch.cuda.empty_cache() if hasattr(self.rt, "torch") else None

    def _full_send(self, h):
        r = self.run
        st = {"xfer": h.get("xfer"), "to": h["to"], "cancel": False, "sock": None, "pacer": CountingThrottle(float(h.get("rate_bps") or 0)), "done": False}
        r["full_xfer"] = st
        st["thread"] = threading.Thread(target=self._full_sender, args=(st, h), daemon=True); st["thread"].start()

    def _full_sender(self, st: dict, h: dict):
        r = self.run; fp = r["full_pack"]
        t_start = time.time(); err = None
        try:
            conn = tcp_connect(h["to_host"], int(h["to_port"]), self.a.mss, timeout=60); st["sock"] = conn
            self.event("full_send_start", t_start, xfer=st["xfer"], to=st["to"], state_bytes=fp["nbytes"], rate_bps=float(h.get("rate_bps") or 0))
            for hdr, bufs, _ in fp["comps"]:
                if st["cancel"]:
                    raise ConnectionError("cancelled")
                send_msg(conn, "FG", {"from": self.label, "run_id": r["id"], "session_id": r["session_id"], "full": True, "xfer": st["xfer"], **hdr}, bufs, st["pacer"])
            if st["cancel"]:
                raise ConnectionError("cancelled")
            digests = {hdr["comp"]: fut.result() for hdr, _, fut in fp["comps"]}
            send_msg(conn, "GO", {"from": self.label, "run_id": r["id"], "call": fp["call"], "t_go": time.time(), "mode": "full", "xfer": st["xfer"], "digests": digests}, b"", None)
            st["done"] = True
            conn.close()
        except (ConnectionError, OSError) as exc:
            err = repr(exc)
        self.event("full_send_end", xfer=st["xfer"], to=st["to"], t_start=t_start, bytes=st["pacer"].count, completed=st["done"], cancelled=st["cancel"], error=None if st["done"] else err)

    def cmd_full_send(self, h):
        """Redirect: the node holding the packed full state sends it to a new destination."""
        assert self.run["full_pack"] is not None, "no packed full state here"
        self._full_send(h)
        return {}

    def cmd_full_cancel(self, h):
        st = self.run["full_xfer"]
        if st is None or st["done"]:
            return {"bytes": st["pacer"].count if st else 0, "completed": bool(st and st["done"])}
        st["cancel"] = True
        try:
            if st["sock"] is not None:
                st["sock"].shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        st["thread"].join(timeout=30)
        return {"bytes": st["pacer"].count, "completed": st["done"]}

    def cmd_sink_drop(self, h):
        """M1 only (restart): forget this session's Sink fragments here; fragments of the listed (cancelled) flows that
        are still on the wire are drained and discarded on arrival."""
        r = self.run
        with self.lock:
            r["dropped_flows"].update(h.get("flows", []))
            n = len(r["have"])
            if self.label != "A":
                r["have"] = set(); r["frag_ok"] = {}; r["sink_complete_t"] = None; r["sink_verified"] = None; r["sink_verified_t"] = None; r["sink_unpacked"] = False
                if r["sink"] is not None:
                    r["sink"]["hash"] = {}
                r["epoch"] += 1   # FRAG_RECV reports carry the epoch they were added in: older ones were dropped here
        self.event("sink_dropped", fragments=n, flows=list(h.get("flows", [])), epoch=r["epoch"])
        return {"dropped": n, "epoch": r["epoch"]}

    def cmd_flow_start(self, h):
        """Holder: open one data connection to `dst` and send the listed fragments at `rate_bps` (0 = unshaped)."""
        r = self.run
        fl = {"id": h["flow_id"], "dst": h["dst"], "host": h["dst_host"], "port": int(h["dst_port"]), "queue": list(h["frag_ids"]), "closed": bool(h.get("closed", True)),
              "cancel": False, "throttle": Throttle(float(h["rate_bps"])) if float(h["rate_bps"]) > 0 else None, "sent": set(), "bytes": 0, "lock": threading.Lock(), "cv": threading.Condition()}
        with self.lock:
            self.flows[fl["id"]] = fl
        th = threading.Thread(target=self._sender, args=(fl,), daemon=True); th.start()
        fl["thread"] = th
        return {}

    def cmd_flow_add(self, h):
        fl = self.flows[h["flow_id"]]
        with fl["cv"]:
            fl["queue"].extend(int(x) for x in h["frag_ids"])
            if h.get("closed"):
                fl["closed"] = True
            fl["cv"].notify_all()
        return {}

    def cmd_flow_set_rate(self, h):
        fl = self.flows.get(h["flow_id"])
        if fl is None:
            return {"missing": True}
        rate = float(h["rate_bps"])
        with fl["lock"]:
            if rate <= 0:
                fl["throttle"] = None
            elif fl["throttle"] is None:
                fl["throttle"] = Throttle(rate)
            else:
                fl["throttle"].rate = rate / 8.0
        return {}

    def cmd_flow_cancel(self, h):
        fl = self.flows.get(h["flow_id"])
        if fl is None:
            return {"missing": True}
        with fl["cv"]:
            fl["cancel"] = True; fl["cv"].notify_all()
        fl["thread"].join(timeout=30)
        return {"sent": sorted(fl["sent"]), "bytes": fl["bytes"]}

    def cmd_status(self, h):
        r = self.run
        return {"have": len(r["have"]) if r else 0, "owner": bool(r and r["owner"]), "call": r["call"] if r else None, "flows": [f for f, fl in self.flows.items() if fl["thread"].is_alive()]}

    def cmd_exec_start(self, h):
        """Owner that has not started generating (the source after SOURCE_PREP): start generating now. Used when the
        move happens later (placement lookahead). The Sink snapshot taken at the trigger stays the transferred version;
        the handoff will serialize the live in-flight/meta state."""
        r = self.run
        assert r["owner"], "not the execution owner"
        r.pop("live_snap", None)
        if h.get("source_bound"):
            # XB: the source keeps generating its own uninterrupted session after the trigger; its live Sink is already
            # bound (nothing to unpack or re-bind). Frozen paths never pass this flag.
            r["bound_call"] = r["call"]; r["bind_at"] = r["call"]; r["sink_unpacked"] = True
        r["stop_owner"] = False; r["first_out_t"] = None
        r["gen_thread"] = threading.Thread(target=self._generate, daemon=True); r["gen_thread"].start()
        self.event("exec_start", call=r["call"])
        return {"call": r["call"]}

    def cmd_exec_stop(self, h):
        r = self.run
        if r["gen_thread"] is not None and r["gen_thread"].is_alive():
            r["stop_owner"] = True; r["gen_thread"].join()
        r["owner"] = False
        return {"call": r["call"]}

    def cmd_run_end(self, h):
        r = self.run
        if r is None:
            return {}
        if r["gen_thread"] is not None and r["gen_thread"].is_alive():
            r["stop_owner"] = True; r["gen_thread"].join()
        for fl in list(self.flows.values()):
            with fl["cv"]:
                fl["cancel"] = True; fl["cv"].notify_all()
        if r["full_xfer"] is not None and not r["full_xfer"]["done"]:
            self.cmd_full_cancel({})
        if r.get("xb") is not None and not r["xb"]["done"]:
            r["xb"]["cancel"] = True
        if r.get("xb_rc") is not None:
            r["xb_rc"]["cancel"] = True
            with r["xb_rc"]["cv"]:
                r["xb_rc"]["cv"].notify_all()
        self.rt.restore_inputs()
        if r.get("deliv_q") is not None:
            r["deliv_q"].put(None); r["deliv_thread"].join(timeout=120)
        r["full_pack"] = None
        r["sampler"].finish(); r["metrics"].close(); r["frag_log"].close()
        net = (r["dir"] / "network.csv").read_text() if (r["dir"] / "network.csv").exists() else ""
        out = {"have": len(r["have"]), "n_frags": len(r["manifest"]["frags"]) if r["manifest"] else 0, "sink_verified": r["sink_verified"],
               "bound_call": r["bound_call"], "rejoin_call": r["rejoin_call"], "network_csv": net, "gpu_mem_alloc_mb": self.rt.gpu_mem_mb(), **self.rt.peak_mem_mb(),
               "baseline_record": getattr(self.rt, "base_record", None) if self.a.sink_fp else None, "promotion_calls": list(r["promotions"])}
        out["snapshots"] = list(r["snapshots"]); out["versions_seen"] = sorted(r["versions"])
        self.rt.release()
        r["sink"] = None; r.pop("live_snap", None)
        self.run = None
        return out

    # ------------------------------------------------------------------ data plane: sender
    def _sender(self, fl: dict):
        r = self.run
        # the flow binds its manifest and buffer object here (I3 / I4, Amendment 1): a fresh capture installs a new object,
        # this flow keeps the old one by reference; a fragment is copied under the node lock immediately before it is sent
        with self.lock:
            st = r["sink"]; man = st["man"]; mv = memoryview(st["buf"])
        try:
            conn = tcp_connect(fl["host"], fl["port"], self.a.mss, timeout=60)
        except Exception as exc:  # noqa: BLE001
            self.event("flow_connect_failed", flow=fl["id"], dst=fl["dst"], error=repr(exc)); return
        send_msg(conn, "FLOW_HELLO", {"flow_id": fl["id"], "from": self.label, "run_id": r["id"], "session_id": r["session_id"], "sink_version": man["sink_version"]}, b"", None)
        self.event("flow_start", flow=fl["id"], dst=fl["dst"], n_queued=len(fl["queue"]))
        while True:
            with fl["cv"]:
                while not fl["queue"] and not fl["closed"] and not fl["cancel"]:
                    fl["cv"].wait(0.05)
                if fl["cancel"] or (not fl["queue"] and fl["closed"]):
                    break
                fid = int(fl["queue"].pop(0))
            f = man["frags"][fid]
            with self.lock:
                held = st["hash"].get(fid)
                data = bytes(mv[f["off"]:f["off"] + f["len"]]) if held == f["sha256"] else None
            if data is None:
                self.event("flow_skip_not_held", flow=fl["id"], fragment_id=fid, stale=held is not None); continue
            with fl["lock"]:
                thr = fl["throttle"]
            t0 = time.time()
            send_msg(conn, "FRAG", {"session_id": r["session_id"], "sink_version": man["sink_version"], "fragment_id": fid, "byte_offset": f["off"], "length": f["len"],
                                    "sha256": f["sha256"], "holder": self.label, "flow_id": fl["id"], "dst": fl["dst"]}, data, thr)
            del data
            t1 = time.time()
            fl["sent"].add(fid); fl["bytes"] += f["len"]
            r["frag_log"].row(t=f"{t1:.6f}", event="sent", session_id=r["session_id"], sink_version=man["sink_version"], fragment_id=fid, src=self.label, dst=fl["dst"], bytes=f["len"], flow=fl["id"], ok="")
            self.send("FRAG_SENT", flow_id=fl["id"], fragment_id=fid, dst=fl["dst"], bytes=f["len"], t_start=t0, t_end=t1)
        try:
            send_msg(conn, "FLOW_END", {"flow_id": fl["id"], "cancelled": fl["cancel"]}, b"", None)
            conn.close()
        except OSError:
            pass
        self.event("flow_end", flow=fl["id"], dst=fl["dst"], cancelled=fl["cancel"], n_sent=len(fl["sent"]), bytes=fl["bytes"])

    # ------------------------------------------------------------------ XB external baselines (osdi/expXB/preregistration.md)
    # Pre-copy (Llumnix-style): the source keeps generating and serving; a copier sends the state in rounds (fragments whose
    # content hash changed since last sent) and switches over atomically at a chunk boundary. Recompute
    # (ServerlessLLM-style): the destination re-runs the session from inputs while the source serves. None of this touches
    # OTTER's M1 / M2 / M3 paths.
    def _xb_pack(self, snap: dict, comp: str):
        header, bufs = self.rt.pack(snap, comp)
        buf = bytearray(header["nbytes"]); mv = memoryview(buf)
        for t, b in zip(header["tensors"], bufs):
            mv[t["offset"]:t["offset"] + t["nbytes"]] = memoryview(b).cast("B")
        return header, buf

    def _xb_snapshot(self) -> tuple[int, dict]:
        """Consistent state at the next chunk boundary of the generating owner (or now, if it is not generating)."""
        r = self.run
        if r["gen_thread"] is None or not r["gen_thread"].is_alive():
            return r["call"], self.rt.serialize_live()
        ev = threading.Event(); r["xb_snap_req"] = ev
        while not ev.wait(0.05):
            if r["gen_thread"] is None or not r["gen_thread"].is_alive():
                r["xb_snap_req"] = None
                return r["call"], self.rt.serialize_live()
        c, snap = r.pop("xb_snap")
        return c, snap

    def _xb_send_dirty(self, task: dict, conn, snap: dict, comps, whole=()) -> tuple[int, dict, dict]:
        """Send the fragments of `comps` whose hash differs from what the destination holds (all of `whole`).
        Returns (bytes sent, headers, component digests)."""
        fb = task["frag_bytes"]; sent = 0; headers, digests = {}, {}
        for comp in comps:
            header, buf = self._xb_pack(snap, comp)
            headers[comp] = {k: v for k, v in header.items() if k != "sha256"}
            digests[comp] = component_digest(payload_slices(header, buf))
            mv = memoryview(buf)
            frags = frag_table(len(buf), fb)
            hashes = [fu.result() for fu in [_pool().submit(sha256_hex, mv[f["off"]:f["off"] + f["len"]]) for f in frags]]
            for f, hsh in zip(frags, hashes):
                if task["cancel"]:
                    return sent, headers, digests
                if comp not in whole and task["held"].get((comp, f["id"])) == hsh:
                    continue
                send_msg(conn, "PFRAG", {"task": task["id"], "comp": comp, "fragment_id": f["id"], "byte_offset": f["off"], "length": f["len"], "sha256": hsh,
                                         "comp_nbytes": len(buf)}, mv[f["off"]:f["off"] + f["len"]], task["throttle"])
                task["held"][(comp, f["id"])] = hsh; sent += f["len"]
            del mv, buf
        return sent, headers, digests

    def cmd_precopy_start(self, h):
        """Source (generating owner): start a pre-copy task toward `to`."""
        r = self.run
        assert r["owner"], "pre-copy needs the generating owner"
        task = {"id": h["task"], "to": h["to"], "host": h["to_host"], "port": int(h["to_port"]), "variant": h["variant"], "frag_bytes": int(h["frag_bytes"]),
                "threshold": int(h["threshold_bytes"]), "round_limit": int(h["round_limit"]), "min_shrink": float(h["min_shrink"]),
                "throttle": Throttle(float(h["rate_bps"])) if float(h["rate_bps"]) > 0 else None, "cancel": False, "switching": False, "held": {}, "rounds": [], "done": False}
        r["xb"] = task
        task["thread"] = threading.Thread(target=self._precopy, args=(task,), daemon=True); task["thread"].start()
        return {}

    def _precopy(self, task: dict):
        self._thread_init()
        r = self.run
        comps = FULL_COMPS if task["variant"] == "full" else ("sink",)
        try:
            conn = tcp_connect(task["host"], task["port"], self.a.mss, timeout=60)
        except Exception as exc:  # noqa: BLE001
            self.event("xb_precopy_failed", task=task["id"], error=repr(exc)); return
        prev = None
        while not task["cancel"]:
            t0 = time.time()
            c, snap = self._xb_snapshot()
            t1 = time.time()
            sent, _, _ = self._xb_send_dirty(task, conn, snap, comps)
            del snap
            rnd = {"round": len(task["rounds"]) + 1, "boundary_call": c, "dirty_bytes": sent, "snapshot_s": t1 - t0, "send_s": time.time() - t1}
            task["rounds"].append(rnd)
            self.event("xb_precopy_round", task=task["id"], **rnd)
            if task["cancel"]:
                break
            reason = ("threshold" if sent <= task["threshold"] else "round_limit" if rnd["round"] >= task["round_limit"]
                      else "no_shrink" if (prev is not None and prev > 0 and sent > (1 - task["min_shrink"]) * prev) else None)
            prev = sent
            if reason:
                task["switch_reason"] = reason; break
        if task["cancel"]:
            conn.close(); self.event("xb_precopy_cancelled", task=task["id"], rounds=len(task["rounds"])); return
        # atomic switchover at a chunk boundary: stop after the current call, serialize, send the final dirty set
        task["switching"] = True
        t_req = time.time()
        if r["gen_thread"] is not None and r["gen_thread"].is_alive():
            r["stop_owner"] = True; r["gen_thread"].join()
        r["owner"] = False
        t_stop = time.time()
        c = r["call"]
        snap = self.rt.serialize_live()
        whole = () if task["variant"] == "full" else ("inflight", "meta")
        final_comps = comps if task["variant"] == "full" else ("sink", "inflight", "meta")
        sent, headers, digests = self._xb_send_dirty(task, conn, snap, final_comps, whole=whole)
        del snap
        send_msg(conn, "PSWITCH", {"task": task["id"], "from": self.label, "call": c, "variant": task["variant"], "headers": headers, "digests": digests, "t_go": time.time()}, b"", None)
        conn.close()
        task["done"] = True
        self.event("xb_precopy_switch", task=task["id"], call=c, final_bytes=sent, reason=task.get("switch_reason"), wait_boundary_s=t_stop - t_req,
                   rounds=len(task["rounds"]), t_sent=time.time())

    def cmd_precopy_cancel(self, h):
        task = (self.run or {}).get("xb")
        if task is None or task["id"] != h["task"]:
            return {"missing": True}
        if task["switching"]:
            task["thread"].join(timeout=600)
            return {"switched": True}
        task["cancel"] = True
        task["thread"].join(timeout=120)
        return {"switched": False, "rounds": len(task["rounds"])}

    def cmd_xb_prepare(self, h):
        """Destination of a pre-copy task: fresh buffers (warm, untimed) and an empty receive store."""
        r = self.run
        r["xb_store"] = {"task": h["task"], "comps": {}}
        if h.get("provision", True):
            self.rt.provision()
        if h.get("inputs"):
            # recompute baselines: load the uint8 input history once (untimed) and check it reproduces the runtime input
            hist = self.rt.input_history()
            self.event("xb_input_check", ok=self.rt.input_check, clip_frames=hist.T)
            return {"input_check": self.rt.input_check}
        return {}

    def _xb_recv_frag(self, conn, hdr: dict, pl: int):
        r = self.run
        st = r["xb_store"]
        data = recv_exact(conn, pl)
        if st is None or st["task"] != hdr["task"]:
            self.event("xb_fragment_discarded", task=hdr["task"]); return
        ok = sha256_hex(memoryview(data)) == hdr["sha256"]
        c = st["comps"].get(hdr["comp"])
        if c is None:   # allocate the component buffer once (dict.setdefault would build a full-size buffer for every fragment)
            c = st["comps"][hdr["comp"]] = {"buf": bytearray(int(hdr["comp_nbytes"])), "hash": {}}
        if ok:
            memoryview(c["buf"])[hdr["byte_offset"]:hdr["byte_offset"] + hdr["length"]] = memoryview(data)
            c["hash"][hdr["fragment_id"]] = hdr["sha256"]
        else:
            self.event("xb_fragment_hash_failed", task=hdr["task"], comp=hdr["comp"], fragment_id=hdr["fragment_id"])

    def _xb_switch(self, hdr: dict):
        """Destination: verify every component against the source's digest at the boundary, then resume at that call."""
        self._thread_init()
        r = self.run
        st = r["xb_store"]
        t0 = time.time()
        ok = {}
        for comp, dg in hdr["digests"].items():
            c = (st or {}).get("comps", {}).get(comp)
            ok[comp] = c is not None and component_digest(payload_slices(hdr["headers"][comp], c["buf"])) == dg
        all_ok = bool(ok) and all(ok.values())
        t1 = time.time()
        self.event("xb_switch_verified", t1, task=hdr["task"], ok=all_ok, components_ok=ok, verify_s=t1 - t0, call=hdr["call"], variant=hdr["variant"])
        if not all_ok:
            return   # never resume on an unverified state (the run is then incomplete and invalid)
        if hdr["variant"] == "full":
            for comp in FULL_COMPS:
                self.rt.unpack(dict(hdr["headers"][comp]), st["comps"][comp]["buf"])
            self.rt.restore_full()
            shifted = None
        else:
            for comp in ("inflight", "meta"):
                self.rt.unpack(dict(hdr["headers"][comp]), st["comps"][comp]["buf"])
            self.rt.restore_fast()
            self.rt.unpack(dict(hdr["headers"]["sink"]), st["comps"]["sink"]["buf"])
            shifted = self.rt.bind()
        r["xb_store"] = None
        self._xb_become_owner(int(hdr["call"]), hdr["from"], hdr["t_go"], "precopy_" + hdr["variant"], restore_s=time.time() - t1, slots_rerotated=shifted)

    def _xb_become_owner(self, call: int, src: str, t_go: float, mode: str, **extra):
        r = self.run
        r["call"] = call; r["owner"] = True; r["stop_owner"] = False; r["first_out_t"] = None
        r["bound_call"] = call; r["bind_at"] = call; r["rejoin_call"] = None; r["pending_cold"] = None; r["n_owned"] += 1
        r["last_fp"] = None; r["wait_sink"] = False; r["await_manifest"] = False
        self.event("sink_bind", call=call, slots_rerotated=extra.get("slots_rerotated"), at_resume=True, xb=mode)
        self.event("resume", call=call, src=src, t_go_src=t_go, mode=mode, ownership=r["n_owned"], gpu_mem_alloc_mb=self.rt.gpu_mem_mb(), **extra)
        r["gen_thread"] = threading.Thread(target=self._generate, daemon=True); r["gen_thread"].start()

    def _codec_pool(self):
        if getattr(self, "_cpool", None) is None:
            from concurrent.futures import ThreadPoolExecutor

            self._cpool = ThreadPoolExecutor(max_workers=4)   # PyAV releases the GIL while encoding / decoding
        return self._cpool

    def _xb_frames_geom(self):
        return (self.rt.runner.first, self.rt.runner.chunk) if not self.a.dry_run else (5, 4)

    def cmd_xb_send_inputs(self, h):
        """Source of a recompute task: encode the input history frames [f_lo, f_hi) with `codec` in segments and send the
        encoded bytes. Segments are encoded in a thread pool while earlier ones are on the wire (pipelined); every byte
        sent is the codec's actual output. An empty range sends one empty `last` segment."""
        import xb_codec as xc

        hist = self.rt.input_history()
        lo, hi, codec = int(h["f_lo"]), int(h["f_hi"]), h["codec"]
        segs = xc.segments(lo, hi) or [(lo, lo)]
        t0 = time.time()

        def enc(a, b):
            t = time.perf_counter()
            if b <= a:
                return b"", 0.0, 0
            f = hist.frames(a, b)
            return xc.encode(f, codec), time.perf_counter() - t, f.nbytes

        futs = [self._codec_pool().submit(enc, a, b) for a, b in segs]
        conn = tcp_connect(h["to_host"], int(h["to_port"]), self.a.mss, timeout=60)
        thr = Throttle(float(h["rate_bps"])) if float(h.get("rate_bps") or 0) > 0 else None
        sent = raw = 0
        enc_s = 0.0
        for i, ((a, b), fu) in enumerate(zip(segs, futs)):
            data, es, rb = fu.result()
            send_msg(conn, "PINPUT", {"task": h["task"], "from": self.label, "f_lo": a, "f_hi": b, "codec": codec, "raw_bytes": rb, "enc_s": es,
                                      "last": i == len(segs) - 1, "part": h.get("part")}, data, thr)
            sent += len(data); raw += rb; enc_s += es
        conn.close()
        self.event("xb_inputs_sent", task=h["task"], part=h.get("part"), codec=codec, f_lo=lo, f_hi=hi, frames=max(0, hi - lo), segments=len(segs),
                   bytes=sent, raw_bytes=raw, enc_cpu_s=enc_s, send_s=time.time() - t0)
        return {"send_s": time.time() - t0, "bytes": sent, "raw_bytes": raw}

    def _xb_decode_inputs(self, rc: dict, hdr: dict, payload: bytes):
        """Destination: decode one segment, check it bit for bit against this node's own copy of the frames, and write the
        decoded frames into the replay input (the replay consumes the transferred frames, lossless or lossy)."""
        import xb_codec as xc

        a, b, codec = int(hdr["f_lo"]), int(hdr["f_hi"]), hdr["codec"]
        exact, ps, dec_s = True, None, 0.0
        if b > a:
            t = time.perf_counter()
            dec = xc.decode(payload, codec)
            dec_s = time.perf_counter() - t
            ref = self.rt.input_history().frames(a, b)
            if dec.shape != ref.shape:
                exact = False; rc["input_error"] = f"segment [{a}, {b}) decoded to {dec.shape}, expected {ref.shape}"
            else:
                exact = bool(np.array_equal(dec, ref))
                if not exact:
                    ps = xc.psnr(dec, ref)
                if not rc["cancel"]:
                    self.rt.write_inputs(a, dec)
        with rc["cv"]:
            if b > a and "input_error" not in rc:
                rc["have"].append((a, b))
            rc["exact"] = rc["exact"] and exact
            rc["input_bytes"] += len(payload); rc["cv"].notify_all()
        self.event("xb_inputs_received", task=hdr["task"], part=hdr.get("part"), codec=codec, f_lo=a, f_hi=b, bytes=len(payload), raw_bytes=hdr.get("raw_bytes"),
                   enc_s=hdr.get("enc_s"), decode_s=dec_s, exact=exact, psnr=ps, last=bool(hdr.get("last")))

    def _wait_frames(self, rc: dict, lo: int, hi: int) -> bool:
        """Block until the decoded input history covers frames [lo, hi) (False if the task was cancelled)."""
        import xb_codec as xc

        t0 = time.time()
        with rc["cv"]:
            while not xc.covered(rc["have"], lo, hi) and not rc["cancel"]:
                rc["cv"].wait(0.02)
        rc["input_wait_s"] += time.time() - t0
        return not rc["cancel"]

    def _codecs(self):
        if not hasattr(self, "_codec_info"):
            self._codec_info = codec_support()
        return self._codec_info

    def _ref_match(self, c: int, ps) -> bool | None:
        """Output equivalence: this call's output frames are bit-identical to the uninterrupted reference (frame digest)."""
        if self.a.dry_run:
            return ps == 99.0
        rec = getattr(self.rt, "base_record", None)
        if not rec or c >= len(rec) or rec[c].get("frame_digest") is None:
            return None
        return frame_digest(self.rt.last_frames) == rec[c]["frame_digest"]

    def _delivery_worker(self, r: dict):
        """Estimated remote delivery bytes (nothing is sent): encode each chunk this node serves to a user at another edge."""
        import xb_codec as xc

        enc = xc.DeliveryEncoder(r["delivery"])
        while True:
            item = r["deliv_q"].get()
            if item is None:
                return
            c, key, frames = item
            if frames is None:
                if not self.a.dry_run:
                    continue
                first, chunk = self._xb_frames_geom(); frames = self.rt.input_history().frames(first + chunk * c, first + chunk * (c + 1))
            try:
                res = enc.push(key, np.asarray(frames))
            except Exception as exc:  # noqa: BLE001
                self.event("xb_delivery_error", call=c, error=repr(exc)); continue
            self.event("xb_delivery_enc", call=c, ownership=key[0], user_edge=key[1], frames=int(len(frames)),
                       bytes_crf23=res["bytes"].get(23), bytes_crf28=res["bytes"].get(28), keyframes=res["keyframes"].get(23), enc_s=res["enc_s"])

    def cmd_user_edge(self, h):
        if self.run is not None:
            self.run["user_edge"] = h["edge"]
        return {}

    def cmd_rtt_probe(self, h):
        """Host-to-host round-trip time on the data plane (TCP echo of an empty message; LAN only, includes the
        Python and TCP stack overhead)."""
        conn = tcp_connect(h["to_host"], int(h["to_port"]), self.a.mss, timeout=30)
        out = []
        try:
            for i in range(int(h.get("n") or 20)):
                t0 = time.perf_counter()
                send_msg(conn, "ECHO", {"seq": i}, b"", None)
                recv_msg(conn)
                out.append((time.perf_counter() - t0) * 1e3)
        finally:
            conn.close()
        return {"rtt_ms": out}

    def _state_digests(self, call: int) -> dict:
        """Per-component digests of the live session state (the components Full migration moves)."""
        if self.a.dry_run:
            return {comp: f"dry:{comp}:{call}" for comp in FULL_COMPS}
        snap = self.rt.serialize_live()
        out = {}
        for comp in FULL_COMPS:
            header, buf = self._xb_pack(snap, comp)
            out[comp] = component_digest(payload_slices(header, buf))
            del buf
        del snap
        return out

    def cmd_xb_state_digests(self, h):
        """Source of a recompute exactness gate: digests of its state at the stop boundary (it is not generating)."""
        r = self.run
        t0 = time.time()
        d = self._state_digests(r["call"])
        self.event("xb_source_state_digests", call=r["call"], digest_s=time.time() - t0)
        return {"digests": d, "call": r["call"], "digest_s": time.time() - t0}

    def cmd_recompute_start(self, h):
        """Destination of a recompute task. full: replay the session from call 0 up to `target` (rounds driven by the
        orchestrator); win: nothing until RECOMPUTE_FINISH."""
        r = self.run
        rc = {"task": h["task"], "variant": h["variant"], "W": int(h.get("W") or 0), "target": int(h.get("target") or 0), "dest_call": 0, "finish": None,
              "cancel": False, "input_bytes": 0, "have": [], "exact": True, "input_wait_s": 0.0, "cv": threading.Condition(), "session": None, "replayed": 0}
        r["xb_rc"] = rc
        if rc["variant"] == "full":
            rc["thread"] = threading.Thread(target=self._recompute_full, args=(rc,), daemon=True); rc["thread"].start()
        return {}

    def _replay_step(self, rc: dict, c: int):
        first, chunk = self._xb_frames_geom()
        if not self._wait_frames(rc, 0, first + chunk * (c + 1)):   # replay call c consumes frames [first + chunk c, + chunk)
            return
        if self.a.dry_run:
            time.sleep(self.a.dry_service_s)
        else:
            self.rt.runner.step(rc["session"], c); self.rt.torch.cuda.synchronize(self.rt.device)
        rc["replayed"] += 1

    def _recompute_full(self, rc: dict):
        self._thread_init()
        first, _chunk = self._xb_frames_geom()
        if not self._wait_frames(rc, 0, first):   # the session's first batch (frames 0 .. first - 1)
            self.event("xb_recompute_cancelled", task=rc["task"], dest_call=0); return
        if not self.a.dry_run:
            self.rt.session = None; rc["session"] = self.rt.runner.start()   # same seeds -> the source's trajectory
        t_round = time.time()
        while not rc["cancel"]:
            while rc["dest_call"] < rc["target"] and not rc["cancel"]:
                self._replay_step(rc, rc["dest_call"]); rc["dest_call"] += 1
            if rc["finish"] is not None and rc["dest_call"] >= rc["finish"]:
                break
            self.event("xb_recompute_round", task=rc["task"], dest_call=rc["dest_call"], round_s=time.time() - t_round)
            with rc["cv"]:
                while rc["target"] <= rc["dest_call"] and rc["finish"] is None and not rc["cancel"]:
                    rc["cv"].wait(0.05)
                if rc["finish"] is not None:
                    rc["target"] = rc["finish"]
            t_round = time.time()
        if rc["cancel"]:
            self.event("xb_recompute_cancelled", task=rc["task"], dest_call=rc["dest_call"]); return
        if rc.get("verify"):
            # exactness gate (--xb_verify_state; timing of such runs is not used): the replayed state at the resume call vs
            # the source's state at its stop boundary, per component
            t0 = time.time()
            if not self.a.dry_run:
                self.rt.session = rc["session"]
            mine = self._state_digests(rc["dest_call"])
            ok = {comp: mine.get(comp) == dg for comp, dg in rc["verify"].items()}
            self.event("xb_recompute_state_verified", task=rc["task"], call=rc["dest_call"], ok=bool(ok) and all(ok.values()) and set(ok) == set(FULL_COMPS),
                       components_ok=ok, verify_s=time.time() - t0)
        self._recompute_resume(rc)

    def _recompute_resume(self, rc: dict):
        if not self.a.dry_run:
            self.rt.session = rc["session"]
            for block in self.rt.pl.generator.model.blocks:
                block.self_attn.adapt_sink_thr = self.rt.cfg_thr
        elif rc["variant"] == "full":
            self.rt.full = True; self.rt.bound = True; self.rt.cold = False   # fake runtime: an exact replay
        else:
            self.rt.full = False; self.rt.bound = True; self.rt.cold = True
        self._xb_become_owner(int(rc["finish"]), rc.get("src", "?"), time.time(), "recompute_" + rc["variant"], replayed=rc["replayed"],
                              inputs_exact=rc["exact"], input_error=rc.get("input_error"), input_wait_s=rc["input_wait_s"], input_bytes=rc["input_bytes"])

    def cmd_recompute_target(self, h):
        rc = self.run["xb_rc"]
        with rc["cv"]:
            rc["target"] = max(rc["target"], int(h["target"])); rc["cv"].notify_all()
        return {}

    def cmd_recompute_finish(self, h):
        """The source stopped after call c - 1: finish the replay up to c and resume there."""
        rc = self.run["xb_rc"]
        rc["src"] = h.get("src")
        rc["verify"] = h.get("verify_digests")
        if rc["variant"] == "full":
            with rc["cv"]:
                rc["finish"] = int(h["call"]); rc["cv"].notify_all()
            return {}
        rc["finish"] = int(h["call"])
        threading.Thread(target=self._recompute_win, args=(rc,), daemon=True).start()
        return {}

    def _recompute_win(self, rc: dict):
        self._thread_init()
        t0 = time.time()
        c, W = rc["finish"], rc["W"]
        first, chunk = self._xb_frames_geom()
        # replay_restart(c, W, sink0=False) seeds from [frame before chunk c - W, chunk c - W] and replays chunks c - W + 1 .. c - 1
        if not self._wait_frames(rc, first + chunk * (c - W) - 1, first + chunk * c):
            self.event("xb_recompute_cancelled", task=rc["task"], dest_call=0); return
        t_inputs = time.time()
        if self.a.dry_run:
            for _ in range(W):
                time.sleep(self.a.dry_service_s)
            rc["replayed"] = W
        else:
            self.rt.session = None
            rc["session"], _ms, _seed, rc["replayed"] = self.rt.runner.replay_restart(c, W, sink0=False)
        self.event("xb_recompute_window", task=rc["task"], W=W, input_wait_s=t_inputs - t0, replay_s=time.time() - t_inputs)
        self._recompute_resume(rc)

    def cmd_recompute_cancel(self, h):
        rc = (self.run or {}).get("xb_rc")
        if rc is not None and rc["task"] == h["task"]:
            rc["cancel"] = True
            with rc["cv"]:
                rc["cv"].notify_all()
        return {}

    # ------------------------------------------------------------------ data plane: receiver
    def _data_accept_loop(self):
        while True:
            conn = tcp_accept(self.data_srv, self.a.mss)
            threading.Thread(target=self._data_conn, args=(conn,), daemon=True).start()

    def _data_conn(self, conn: socket.socket):
        r = self.run
        self._thread_init()
        full = {"bytes": 0, "digests": {}, "xfer": None, "from": None, "go": False}   # Full migration receive on this connection
        try:
            while True:
                lens = recv_exact(conn, 16)
                hl, pl = struct.unpack("!QQ", bytes(lens))
                hdr = json.loads(bytes(recv_exact(conn, hl)).decode())
                kind = hdr["kind"]
                if kind == "FRAG":
                    self._recv_frag(conn, hdr, pl)
                elif kind == "FG":
                    t_start = time.time()
                    pool = self.recv_pool if (hdr.get("full") and self.recv_pool is not None and pl <= len(self.recv_pool.bufs[0])) else None
                    payload = recv_exact(conn, pl, pool.next() if pool else None)
                    t_recv = time.time()
                    h2d = self.rt.unpack(hdr, payload)
                    if hdr.get("full"):
                        full["bytes"] += pl; full["xfer"] = hdr.get("xfer"); full["from"] = hdr["from"]
                        full["digests"][hdr["comp"]] = digest_async(payload_slices(hdr, payload))
                        if pool:
                            pool.hold(full["digests"][hdr["comp"]])   # the buffer is reused only after its digest is done
                    self.event("fg_recv", t_recv, comp=hdr["comp"], bytes=pl, t_send_src=hdr["t_send"], t_recv_start=t_start, h2d_s=h2d, src=hdr["from"], full=bool(hdr.get("full")))
                elif kind == "GO":
                    full["go"] = True
                    if hdr.get("mode") == "full":
                        threading.Thread(target=self._verify_full, args=(hdr, full["digests"]), daemon=True).start()
                    self._become_owner(hdr)
                elif kind == "PFRAG":
                    self._xb_recv_frag(conn, hdr, pl)
                elif kind == "PSWITCH":
                    if pl:
                        recv_exact(conn, pl)
                    self._xb_switch(hdr)
                elif kind == "PINPUT":
                    payload = bytes(recv_exact(conn, pl)) if pl else b""
                    rc = r["xb_rc"]
                    if rc is not None and rc["task"] == hdr["task"] and not rc["cancel"]:
                        self._codec_pool().submit(self._xb_decode_inputs, rc, hdr, payload)   # decode off the receive path
                    else:
                        # no reuse across targets: inputs of a cancelled / other task are dropped
                        self.event("xb_inputs_discarded", task=hdr["task"], bytes=pl, f_lo=hdr.get("f_lo"), f_hi=hdr.get("f_hi"))
                elif kind == "ECHO":
                    if pl:
                        recv_exact(conn, pl)
                    send_msg(conn, "ECHO_R", {"seq": hdr.get("seq")}, b"", None)
                elif kind in ("FLOW_HELLO", "FLOW_END"):
                    if pl:
                        recv_exact(conn, pl)
                    if kind == "FLOW_HELLO":
                        if hdr["sink_version"] != (r["manifest"] or {}).get("sink_version"):
                            # a flow of a superseded snapshot reaching an updated node (VACW: cancelled by the orchestrator; its fragments are judged by hash)
                            stale = hdr["sink_version"] in r["versions"]
                            self.event("flow_version_stale" if stale else "sink_version_mismatch", flow=hdr["flow_id"], got=hdr["sink_version"], expected=(r["manifest"] or {}).get("sink_version"))
                    if kind == "FLOW_END":
                        break
                else:
                    if pl:
                        recv_exact(conn, pl)
        except (ConnectionError, OSError):
            pass
        finally:
            conn.close()
            if full["bytes"] and not full["go"]:
                # a redirected Full migration: the partial state is discarded (the next transfer overwrites every component)
                self.event("full_recv_aborted", xfer=full["xfer"], src=full["from"], bytes=full["bytes"])

    def _verify_full(self, go: dict, local: dict):
        """Full migration: per-component digests of the received bytes vs the sender's (Phase 1 checksums), off the
        critical path; the Sink component's digest is also compared with the manifest's Sink digest."""
        r = self.run
        ok = {c: (local[c].result() == d) if c in local else False for c, d in (go.get("digests") or {}).items()}
        sink_d = local["sink"].result() if "sink" in local else None
        man = r["manifest"] or {}
        self.event("full_state_verified", xfer=go.get("xfer"), components_ok=ok, all_ok=bool(ok) and all(ok.values()) and set(ok) == set(FULL_COMPS),
                   sink_digest=sink_d and sink_d[:16], sink_digest_matches_manifest=(sink_d == man.get("sink_digest")) if sink_d else None)

    def _recv_frag(self, conn, hdr: dict, pl: int):
        r = self.run
        with self.lock:
            man = r["manifest"]; st = r["sink"]
        fid = int(hdr["fragment_id"]); off = int(hdr["byte_offset"]); n = int(hdr["length"])
        ok = True; dup = False
        if hdr["session_id"] != r["session_id"]:
            recv_exact(conn, pl)
            self.event("fragment_rejected_version", fragment_id=fid, got=hdr["sink_version"], expected=man["sink_version"], src=hdr["holder"], reason="session")
            self.send("FRAG_RECV", fragment_id=fid, src=hdr["holder"], flow_id=hdr["flow_id"], bytes=pl, t_start=time.time(), t_end=time.time(), ok=False, dup=False, rejected="session")
            return
        f = man["frags"][fid]
        cross = hdr["sink_version"] != man["sink_version"]
        if hdr["sha256"] != f["sha256"]:
            # content check against this node's current manifest (design 1.2): a fragment of a superseded snapshot whose
            # content the active snapshot does not need; under a single manifest this is exactly the old version test
            stale = cross and hdr["sink_version"] in r["versions"]
            recv_exact(conn, pl)  # drain; never combine fragments of different Sink versions
            kind = "hash_stale" if stale else ("version" if cross else "hash")
            self.event("fragment_rejected_hash" if stale else "fragment_rejected_version", fragment_id=fid, got=hdr["sink_version"], expected=man["sink_version"], src=hdr["holder"], reason=kind)
            self.send("FRAG_RECV", fragment_id=fid, src=hdr["holder"], flow_id=hdr["flow_id"], bytes=pl, t_start=time.time(), t_end=time.time(), ok=False, dup=False, rejected=kind,
                      sink_version=hdr["sink_version"], active_version=man["sink_version"])
            return
        assert f["off"] == off and f["len"] == n == pl, (f, off, n, pl)
        if hdr["flow_id"] in r["dropped_flows"]:
            # M1 only: a fragment of a flow cancelled when this owner was abandoned, still on the wire after the drop
            t0 = time.time(); recv_exact(conn, pl); t1 = time.time()
            r["frag_log"].row(t=f"{t1:.6f}", event="recv", session_id=r["session_id"], sink_version=man["sink_version"], fragment_id=fid, src=hdr["holder"], dst=self.label, bytes=n, flow=hdr["flow_id"], ok="discarded")
            self.send("FRAG_RECV", fragment_id=fid, src=hdr["holder"], flow_id=hdr["flow_id"], bytes=n, t_start=t0, t_end=t1, ok=True, dup=False, discarded=True)
            return
        t_start = time.time()
        with self.lock:
            dup = st["hash"].get(fid) == f["sha256"]   # already held with the right content
        if dup:
            recv_exact(conn, pl)  # already held: receive into scratch, do not overwrite verified bytes
            t_end = time.time()
        else:
            scratch = bytearray(n); view = memoryview(scratch)
            got = 0
            while got < n:
                k = conn.recv_into(view[got:], n - got)
                if k == 0:
                    raise ConnectionError("peer closed mid-fragment")
                got += k
            t_end = time.time()
            ok = sha256_hex(view) == f["sha256"] == hdr["sha256"]
            complete = False
            with self.lock:
                epoch = r["epoch"]
                if ok and r["manifest"] is man:
                    # verified: replace the fragment's bytes in place under the lock (a sender copies under the same lock: I3 / I4)
                    memoryview(st["buf"])[off:off + n] = view
                    st["hash"][fid] = f["sha256"]
                    r["have"].add(fid); r["frag_ok"][fid] = True
                    complete = len(r["have"]) == len(man["frags"]) and r["sink_complete_t"] is None
                    if complete:
                        r["sink_complete_t"] = t_end
                elif ok:
                    ok = False   # the manifest changed while this fragment was on the wire: judged against the one it was accepted under; re-sent if still needed
                else:
                    r["frag_ok"][fid] = False
            del view, scratch
            if complete:
                threading.Thread(target=self._verify_sink, args=(t_end,), daemon=True).start()
        if cross and ok and not dup:
            self.event("fragment_accepted_cross_version", fragment_id=fid, got=hdr["sink_version"], active=man["sink_version"], src=hdr["holder"])
        r["frag_log"].row(t=f"{t_end:.6f}", event="recv", session_id=r["session_id"], sink_version=man["sink_version"], fragment_id=fid, src=hdr["holder"], dst=self.label, bytes=n, flow=hdr["flow_id"], ok=ok and not dup)
        self.send("FRAG_RECV", fragment_id=fid, src=hdr["holder"], flow_id=hdr["flow_id"], bytes=n, t_start=t_start, t_end=t_end, ok=ok, dup=dup, t_send=hdr.get("t_send"),
                  epoch=epoch if not dup else r["epoch"], sink_version=hdr["sink_version"], active_version=man["sink_version"], cross_version=cross)

    def _verify_sink(self, t_complete: float):
        self._thread_init()
        r = self.run
        with self.lock:
            st = r["sink"]; man = st["man"]
        digest = component_digest(payload_slices(man["header"], st["buf"]))
        t_v = time.time()
        with self.lock:
            ok = digest == man["sink_digest"] and r["manifest"] is man   # I2: whole digest of the active snapshot
            if r["manifest"] is man:
                r["sink_verified"] = ok; r["sink_verified_t"] = t_v
        self.event("sink_complete", t_complete, n_frags=len(man["frags"]), bytes=man["nbytes"], sink_version=man["sink_version"])
        self.event("sink_verified", t_v, ok=ok, verify_s=t_v - t_complete, digest=digest[:16], sink_version=man["sink_version"])
        if ok and not r["owner"]:
            # not generating: stage the Sink on the GPU now so a later bind is immediate
            self._unpack_sink()

    def _unpack_sink(self):
        r = self.run
        if r["sink_unpacked"]:
            return
        t0 = time.time()
        with self.lock:
            st = r["sink"]
        h2d = self.rt.unpack(dict(st["man"]["header"]), st["buf"])
        r["sink_unpacked"] = True; r["unpacked_version"] = st["man"]["sink_version"]
        self.event("sink_h2d", h2d_s=h2d, staged_s=time.time() - t0, sink_version=st["man"]["sink_version"])

    # ------------------------------------------------------------------ execution ownership
    def _become_owner(self, go: dict):
        r = self.run
        mode = go.get("mode", "fast")
        t0 = time.time()
        # every ownership starts afresh (a revisited owner binds and rejoins again; earlier values stay in events.csv)
        r["call"] = int(go["call"]); r["owner"] = True; r["stop_owner"] = False; r["first_out_t"] = None
        r["bound_call"] = None; r["rejoin_call"] = None; r["pending_cold"] = None; r["n_owned"] += 1
        r["last_fp"] = None; r["bind_at"] = None
        r["await_manifest"] = bool(go.get("fresh_pending"))   # VACW: the leaving owner is capturing S_k; bind only after MANIFEST_UPDATE (I1 / I5)
        r["wait_sink"] = bool(go.get("wait_sink"))            # XB wait-for-Sink ablation
        extra = {}
        if mode == "full":
            self.rt.restore_full()
            r["bound_call"] = r["call"]   # the Sink is part of the transferred state
            r["bind_at"] = r["call"]
            self.event("sink_bind", call=r["call"], slots_rerotated=0, at_resume=True, full_state=True)
        elif mode == "cold":
            frames, ms = self.rt.cold_restart(r["call"])
            r["pending_cold"] = {"skip": r["call"], "emit": r["call"] + self.rt.k - 1, "frames": frames}
            extra = {"cold_restart_ms": ms}
        else:
            self.rt.restore_fast()
            have = self.rt.snap.get("have", set()) if getattr(self.rt, "snap", None) else set()
            if "recent_n" in have or int(go.get("recent_slots", 0) or 0) > 0:
                self.event("recent_handoff_dst", call=r["call"], recent_slots=int(go.get("recent_slots", 0) or 0), fp=self.rt.recent_fp(), received="recent_n" in have)
            if r["sink_verified"] and not r["await_manifest"]:
                self._unpack_sink()
                shifted = self.rt.bind()
                r["bound_call"] = r["call"]; r["bind_at"] = r["call"]
                self.event("sink_bind", call=r["call"], slots_rerotated=shifted, at_resume=True, **self._bound_version())
        t1 = time.time()
        self.event("resume", t1, call=r["call"], src=go["from"], t_go_src=go["t_go"], restore_s=t1 - t0, gpu_mem_alloc_mb=self.rt.gpu_mem_mb(), mode=mode, ownership=r["n_owned"], **extra)
        r["gen_thread"] = threading.Thread(target=self._generate, daemon=True); r["gen_thread"].start()

    def _bound_version(self) -> dict:
        with self.lock:
            man = self.run["sink"]["man"]
        return {"sink_version": man["sink_version"], "digest": man["sink_digest"][:16], "unpacked_version": self.run["unpacked_version"]}

    def _generate(self):
        self._thread_init()
        r = self.run
        while not r["stop_owner"]:
            c = r["call"]
            req = r["xb_snap_req"]
            if req is not None:
                # XB pre-copy round: a consistent snapshot at this chunk boundary (state after call c - 1)
                r["xb_snap"] = (c, self.rt.serialize_live()); r["xb_snap_req"] = None; req.set()
            if r["bound_call"] is None and r["sink_verified"] and r["pending_cold"] is None and not r["await_manifest"]:
                self._unpack_sink()
                shifted = self.rt.bind()
                r["bound_call"] = c; r["bind_at"] = c
                self.event("sink_bind", call=c, slots_rerotated=shifted, at_resume=False, **self._bound_version())
            if r["wait_sink"] and r["bound_call"] is None:
                time.sleep(0.005)   # XB wait-for-Sink ablation: no Sink-less generation
                continue
            pc = r["pending_cold"]
            if pc is not None and c in (pc["skip"], pc["emit"]):
                produced, ps, ss, dt, pos = self.rt.step(c, override=pc["frames"] if c == pc["emit"] else None, skip=c == pc["skip"] and c != pc["emit"])
            else:
                produced, ps, ss, dt, pos = self.rt.step(c)
            t_out = time.time()
            if produced and r["first_out_t"] is None:
                r["first_out_t"] = t_out; self.event("first_output", t_out, call=c)
            if r["bound_call"] is not None and r["rejoin_call"] is None and ps is not None and ps >= REJOIN_DB:
                r["rejoin_call"] = c; self.event("rejoin", t_out, call=c, calls_after_bind=c - r["bound_call"], psnr=ps)
            dec = list(self.rt.decodes)
            fp = promo = fp_ms = None
            if self.a.sink_fp:
                # owner-side Sink version tracking (W / R / N): a value change between two consecutive calls of this ownership
                # that is not the bind at this call is a promotion (an owner-side Sink-version event)
                t_fp = time.perf_counter(); fp = self.rt.sink_value_fp(); fp_ms = (time.perf_counter() - t_fp) * 1e3
                promo = r["last_fp"] is not None and fp != r["last_fp"] and r["bind_at"] != c
                if promo:
                    changed = [i for i, (x, y) in enumerate(zip(fp, r["last_fp"])) if x != y]
                    r["promotions"].append(c)
                    self.event("sink_promotion", call=c, n_changed=len(changed), changed=changed[:96], bound=r["bound_call"] is not None, ownership=r["n_owned"])
                r["last_fp"] = fp
            ref_match = self._ref_match(c, ps) if (r["exact_check"] and produced) else None
            if r["deliv_q"] is not None and produced and r["user_edge"] not in (None, self.label):
                r["deliv_q"].put((c, (r["n_owned"], r["user_edge"]), self.rt.last_frames))   # served to a user at another edge
            row = {"call": c, "t_out": t_out, "owner": self.label, "chunk_s": dt, "psnr": ps, "ssim": ss, "missing": not produced,
                   "sink_bound": r["bound_call"] is not None and c >= r["bound_call"], "gpu_mem_alloc_mb": self.rt.gpu_mem_mb(), "sink_slot_pos": pos,
                   "t_decode": dec[-1][0] if dec else None, "n_frames": sum(n for _, n in dec),
                   "sink_vfp": None if fp is None else json.dumps(fp), "promotion": promo, "fp_ms": fp_ms}
            r["metrics"].row(**{k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in row.items()})
            self.send("METRIC", **{k: v for k, v in row.items() if k != "sink_vfp"}, **({"ref_match": ref_match} if ref_match is not None else {}))
            r["call"] = c + 1
            if r["call"] >= self.a.migration_chunk + self.a.post_chunks:
                self.event("window_exhausted", call=r["call"]); break


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--label", type=str, required=True, help="A, B, C or D")
    p.add_argument("--bind", type=str, default="0.0.0.0")
    p.add_argument("--ctl_port", type=int, default=29811)
    p.add_argument("--data_port", type=int, default=29812)
    p.add_argument("--mss", type=int, default=DEFAULT_MSS)
    p.add_argument("--iface", type=str, default=None)
    p.add_argument("--dry_run", action="store_true", help="protocol test without torch (fake Sink); never for reported results")
    p.add_argument("--dry_sink_mb", type=int, default=64)
    p.add_argument("--dry_service_s", type=float, default=0.2)
    p.add_argument("--dry_promote_calls", type=str, default="", help="dry run: calls at which a bound fake Sink changes (version-event accounting test)")
    p.add_argument("--dry_dirty_frags", type=int, default=3, help="dry run: fragments of the live fake Sink changed per dry promotion (VACW loopback)")
    p.add_argument("--dry_frag_bytes", type=int, default=4 << 20, help="dry run: fragment size the dirty set is aligned to (= the orchestrator's --frag_bytes)")
    p.add_argument("--sink_fp", action="store_true", help="W / R / N: per-call Sink value fingerprints (baseline and owned calls) and owner-side promotion events")
    p.add_argument("--recent_slots", type=int, default=0, help="(unused: Experiment A passes recent_slots per run in EXEC_HANDOFF; kept for the dry-run driver)")
    p.add_argument("--block_ck", action="store_true", help="Task B: per-call block checksums of every (layer, key, row, sink slot) and all slot positions in the baseline record")
    p.add_argument("--cold_start", action="store_true", help="OTTER cold destination: no baseline run; PSNR reference from the warm node's cache")
    p.add_argument("--launch_id", type=str, default="", help="token of the orchestrator invocation that started this node (echoed in HELLO; identity check)")
    # model / workload (same defaults as Phase 1)
    p.add_argument("--config_path", type=str, default=str(REPO_ROOT / "configs/wan_causal_dmd_v2v.yaml"))
    p.add_argument("--checkpoint_folder", type=str, default=str(REPO_ROOT / "ckpts/wan_causal_dmd_v2v"))
    p.add_argument("--prompt_file_path", type=str, default=str(REPO_ROOT / "examples/prompt.txt"))
    p.add_argument("--video_path", type=str, default=str(REPO_ROOT / "examples/original.mp4"))
    p.add_argument("--output_folder", type=str, default=str(REPO_ROOT / "results/evaluation"))
    p.add_argument("--noise_scale", type=float, default=0.8)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--width", type=int, default=832)
    p.add_argument("--fps", type=int, default=16)
    p.add_argument("--step", type=int, default=2)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--gpu_id", type=int, default=0)
    p.add_argument("--model_type", type=str, default="T2V-1.3B")
    p.add_argument("--fixed_noise_scale", action="store_true", default=False)
    p.add_argument("--t2v", action="store_true", default=False)
    p.add_argument("--profile", action="store_true", default=False)
    p.add_argument("--use_taehv", action="store_true", default=False)
    p.add_argument("--normalize_latents", action="store_true", default=False)
    p.add_argument("--use_tensorrt", action="store_true", default=False)
    p.add_argument("--fast", action="store_true", default=False)
    p.add_argument("--migration_chunk", type=int, default=30)
    p.add_argument("--post_chunks", type=int, default=220, help="baseline/window length after migration (must cover the longest run)")
    a = p.parse_args(argv)
    a.mss = a.mss or None
    return a


def main():
    a = parse_args()
    node = Node(a)
    if a.cold_start:
        node.ref_path = node.rt.use_cached_reference()
        print(f"[{a.label}] cold start: runtime ready {node.t_runtime_ready - T_MAIN:.1f} s after process start; reference {node.ref_path}", flush=True)
    else:
        print(f"[{a.label}] baseline ({a.migration_chunk + a.post_chunks} calls){' [dry run]' if a.dry_run else ''}", flush=True)
        s = node.rt.baseline(a.migration_chunk, a.post_chunks)
        print(f"[{a.label}] baseline done; service time {s * 1e3:.0f} ms/chunk", flush=True)
    node.serve()


if __name__ == "__main__":
    main()
