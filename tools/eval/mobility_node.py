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
        orig = self.pm._timed_stream_decode

        def timed_decode(denoised_pred, _orig=orig):
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
        self.bound = False; self.have_fast = False; self.full = False; self.cold = False

    def restore_full(self):
        self.full = True; self.bound = True; self.cold = False

    def cold_restart(self, c):
        time.sleep(0.05); self.cold = True; self.bound = False; self.full = False
        return np.zeros(4, dtype=np.uint8), 50.0

    def use_cached_reference(self):
        self.service_s = None
        return None

    def unpack(self, header, payload):
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

    def release(self):
        pass


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
                      reference=str(self.ref_path) if self.ref_path else "baseline", commit=_git_commit())
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
                    "last_fp": None, "bind_at": None, "promotions": [], "snapshots": [], "versions": set(), "await_manifest": False, "unpacked_version": None}
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
        send_msg(conn, "GO", {"from": self.label, "run_id": r["id"], "call": r["call"], "t_go": time.time(), "mode": mode, "recent_slots": n_rs, "fresh_pending": fresh}, b"", None)
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
            if r["bound_call"] is None and r["sink_verified"] and r["pending_cold"] is None and not r["await_manifest"]:
                self._unpack_sink()
                shifted = self.rt.bind()
                r["bound_call"] = c; r["bind_at"] = c
                self.event("sink_bind", call=c, slots_rerotated=shifted, at_resume=False, **self._bound_version())
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
            row = {"call": c, "t_out": t_out, "owner": self.label, "chunk_s": dt, "psnr": ps, "ssim": ss, "missing": not produced,
                   "sink_bound": r["bound_call"] is not None and c >= r["bound_call"], "gpu_mem_alloc_mb": self.rt.gpu_mem_mb(), "sink_slot_pos": pos,
                   "t_decode": dec[-1][0] if dec else None, "n_frames": sum(n for _, n in dec),
                   "sink_vfp": None if fp is None else json.dumps(fp), "promotion": promo, "fp_ms": fp_ms}
            r["metrics"].row(**{k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in row.items()})
            self.send("METRIC", **{k: v for k, v in row.items() if k != "sink_vfp"})
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
