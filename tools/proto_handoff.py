#!/usr/bin/env python3
"""Two-process late-binding handoff (source GPU -> destination GPU over MSS-capped TCP), evaluation-grade.

Question: can execution handoff be decoupled from bulk continuity-state transfer?

    source (edge A)                                     destination (edge B)
      PREP -> run session to chunk M, serialize            provision buffers (not timed)
      PREPARED <------------------------------------       READY = migration start (t_mig)
      policy ours   : fast msg (in-flight + meta) ------>  restore, freeze sink refresh, resume at M
                      sink (durable) in background ----->  receiver thread; atomic bind at a chunk boundary
      policy full   : everything ---------------------->   restore all, then resume (stall = transfer)
      policy cold   : GO -------------------------------->  fresh start at chunk M (official restart path)
      policy replay : seed frames ---------------------->   local replay (sinkhist, pos-faithful), resume
      policy repeat : nothing moves; destination runs the same session again (determinism check)

Transport (identical for every policy): plain TCP, TCP_MAXSEG capped (--mss), TCP_NODELAY, sender-side token
bucket for bandwidth below native (--bw <= 0 means native). Clocks: NTP-style ping-pong at connect; source
timestamps are mapped into the destination clock. Every (policy, bandwidth, rep) is one run directory under
results/evaluation/<experiment>/ with config.json, events.csv, metrics.csv, network.csv, summary.json,
host_info.json, git_commit.txt and stdout.log.

Usage (physical): tools/eval/run_single_handoff.sh. Same host: tools/run_proto.sh.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import struct
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for p in (REPO_ROOT, REPO_ROOT / "tools", REPO_ROOT / "tools" / "eval"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np  # noqa: E402

from common import (DEFAULT_MSS, MSS_WARNINGS, CsvLog, EventLog, ResourceSampler, Throttle, clock_sync_client, clock_sync_server,  # noqa: E402
                    effective_mss, host_info, run_dir, tcp_accept, tcp_connect, tcp_listen, write_json)

MB = 1024.0 * 1024.0
POLICIES = {
    # name: (components sent before the destination may resume, components sent in the background)
    "ours": ({"inflight", "meta"}, {"sink"}),            # refresh frozen until the true sink binds
    "ours_refresh": ({"inflight", "meta"}, {"sink"}),    # adaptive refresh left on; true sink overwrites at bind
    "full": ({"sink", "recent", "meta", "vae", "inflight"}, set()),
    "cold": (set(), set()),
    "replay": ({"seeds"}, set()),
    "repeat": (set(), set()),
}


# ----------------------------------------------------------------------------- framing
def send_msg(sock: socket.socket, kind: str, header: dict, payload, throttle: Throttle | None, chunk: int = 1 << 20):
    """payload: bytes-like or a list of bytes-like buffers (sent back to back, no concatenation copy)."""
    parts = payload if isinstance(payload, list) else [payload]
    total = sum(memoryview(b).nbytes for b in parts)
    hdr = json.dumps({"kind": kind, "t_send": time.time(), **header}).encode()
    sock.sendall(struct.pack("!QQ", len(hdr), total))
    sock.sendall(hdr)
    for b in parts:
        view = memoryview(b).cast("B")
        off = 0
        while off < len(view):
            n = min(chunk, len(view) - off)
            if throttle is not None:
                throttle.take(n)
            sock.sendall(view[off:off + n])
            off += n


def recv_exact(sock: socket.socket, n: int, pool: bytearray | None = None):
    """Read exactly n bytes. With `pool` (preallocated, large enough) the bytes land in pool[:n] with no
    allocation; allocating a multi-GB bytearray holds the GIL for hundreds of ms and stalls generation."""
    if pool is not None and n <= len(pool):
        buf = memoryview(pool)[:n]
    else:
        buf = bytearray(n)
    view = memoryview(buf)
    got = 0
    while got < n:
        r = sock.recv_into(view[got:], min(1 << 22, n - got))
        if r == 0:
            raise ConnectionError("socket closed")
        got += r
    return buf


def recv_msg(sock: socket.socket, pool: bytearray | None = None):
    lens = recv_exact(sock, 16)
    hl, pl = struct.unpack("!QQ", bytes(lens))
    hdr = json.loads(bytes(recv_exact(sock, hl)).decode())
    t0 = time.time()
    payload = recv_exact(sock, pl, pool) if pl else bytearray()
    hdr["t_recv_start"] = t0
    hdr["t_recv"] = time.time()
    return hdr, payload


def sha256_parts(parts) -> str:
    h = hashlib.sha256()
    for b in parts:
        h.update(memoryview(b).cast("B"))
    return h.hexdigest()


_HASH_POOL = None


def _pool():
    global _HASH_POOL
    if _HASH_POOL is None:
        from concurrent.futures import ThreadPoolExecutor

        _HASH_POOL = ThreadPoolExecutor(max_workers=16)
    return _HASH_POOL


def component_digest(parts) -> str:
    """Digest of a component as sha256 over the per-buffer sha256 digests (buffers = tensors, in header
    order). Per-buffer hashing runs in a thread pool (hashlib releases the GIL), so verification keeps up
    with a 10 GbE link without sitting on the transfer's critical path."""
    futs = [_pool().submit(lambda b=b: hashlib.sha256(memoryview(b).cast("B")).digest()) for b in parts]
    h = hashlib.sha256()
    for f in futs:
        h.update(f.result())
    return h.hexdigest()


class RecvPool:
    """Two preallocated receive buffers used alternately: while the bytes of message i are being hashed
    (thread pool), message i+1 lands in the other buffer. A buffer is reused only once its digest is done,
    so hashing is never on the receive path for back-to-back components (FullMigration)."""

    def __init__(self, nbytes: int):
        self.bufs = [bytearray(nbytes), bytearray(nbytes)]
        self.pending = [None, None]
        self.idx = 0

    def next(self) -> bytearray:
        self.idx ^= 1
        fut = self.pending[self.idx]
        if fut is not None:
            fut.result()
            self.pending[self.idx] = None
        return self.bufs[self.idx]

    def hold(self, fut) -> None:
        """Mark the buffer handed out by the last next() as busy until `fut` completes."""
        self.pending[self.idx] = fut

    def drain(self) -> None:
        for f in self.pending:
            if f is not None:
                f.result()
        self.pending = [None, None]


def payload_slices(header: dict, payload):
    view = memoryview(payload)
    return [view[t["offset"]:t["offset"] + t["nbytes"]] for t in header["tensors"]]


# ----------------------------------------------------------------------------- state packing
def _np_dtype(t):
    import torch

    return {torch.bfloat16: ("bf16", np.uint16), torch.float16: ("f16", np.float16), torch.float32: ("f32", np.float32),
            torch.int64: ("i64", np.int64), torch.int32: ("i32", np.int32), torch.bool: ("bool", np.bool_)}[t.dtype]


def tensor_to_bytes(t) -> tuple[dict, np.ndarray]:
    """GPU tensor -> (meta, host numpy array). One device-to-host copy; no further copies."""
    import torch

    tag, _ = _np_dtype(t)
    c = t.detach().contiguous().cpu()
    if t.dtype == torch.bfloat16:
        c = c.view(torch.int16)
    return {"shape": list(t.shape), "dtype": tag}, c.numpy()


def bytes_to_tensor(meta: dict, raw: memoryview, device):
    """host bytes -> GPU tensor. torch.frombuffer is zero-copy; .to(device) is the single copy."""
    import torch

    tag = meta["dtype"]
    tdt = {"bf16": torch.int16, "f16": torch.float16, "f32": torch.float32, "i64": torch.int64, "i32": torch.int32, "bool": torch.bool}[tag]
    t = torch.frombuffer(bytearray(raw) if not isinstance(raw, (bytes, bytearray)) and raw.readonly else raw, dtype=tdt).reshape(meta["shape"])
    if tag == "bf16":
        t = t.view(torch.bfloat16)
    return t.to(device)


def pack_component(snap: dict, comp: str, sink: int, fsl: int, checksum: str = "async") -> tuple[dict, list]:
    """Serialize one component of a serialize_state() snapshot into (header, [buffers]). D2H happens here."""
    import torch

    t0 = time.perf_counter()
    parts: list[tuple[str, dict, np.ndarray]] = []
    if comp in ("sink", "recent"):
        lo, hi = (0, sink * fsl) if comp == "sink" else (sink * fsl, None)
        for li, layer in enumerate(snap["kv"]):
            for key in ("k", "v"):
                m, b = tensor_to_bytes(layer[key][:, lo:hi])
                parts.append((f"kv/{li}/{key}", m, b))
            if comp == "sink":
                m, b = tensor_to_bytes(snap["ring"][li]["pos"][:, :sink])
                parts.append((f"ring/{li}/pos_sink", m, b))
    elif comp == "meta":
        for li, r in enumerate(snap["ring"]):
            for key in ("global_end_index", "local_end_index", "pos"):
                m, b = tensor_to_bytes(r[key]); parts.append((f"ring/{li}/{key}", m, b))
        for key in ("kv_cache_starts", "kv_cache_ends", "timestep"):
            m, b = tensor_to_bytes(snap["pipeline"][key]); parts.append((f"pipeline/{key}", m, b))
        m, b = tensor_to_bytes(snap["session"]["last_image"]); parts.append(("session/last_image", m, b))
    elif comp == "inflight":
        m, b = tensor_to_bytes(snap["pipeline"]["hidden_states"]); parts.append(("pipeline/hidden_states", m, b))
    elif comp == "vae":
        for attr in ("_enc_feat_map", "_feat_map"):
            for i, t in enumerate(snap["vae"][attr] or []):
                if hasattr(t, "shape"):
                    m, b = tensor_to_bytes(t); parts.append((f"vae/{attr}/{i}", m, b))
    else:
        raise ValueError(comp)
    torch.cuda.synchronize()
    d2h_s = time.perf_counter() - t0
    header = {"comp": comp, "tensors": [], "scalars": {}, "d2h_s": d2h_s}
    buffers = []
    off = 0
    for name, m, b in parts:
        n = b.nbytes
        header["tensors"].append({"name": name, "offset": off, "nbytes": n, **m})
        buffers.append(b)
        off += n
    header["nbytes"] = off
    if checksum == "inline":  # legacy: hash before sending (adds hashing time to the critical path)
        header["sha256"] = sha256_parts(buffers)
    if comp == "meta":
        header["scalars"] = {
            "ring": [{"total_steps": r["total_steps"], "current_step": r["current_step"]} for r in snap["ring"]],
            "evict": snap["evict"],
            "session": {k: v for k, v in snap["session"].items() if k != "last_image"},
            "pm_processed": snap["pipeline"]["pm_processed"],
            "vae_flags": {k: v for k, v in snap["vae"].items() if k in ("_enc_conv_idx", "_conv_idx", "first_encode", "first_decode", "first_batch")},
        }
    return header, buffers


def unpack_into_snapshot(header: dict, payload, device, snap: dict, sink: int, fsl: int) -> dict:
    """Merge a received component into a destination-side snapshot dict understood by restore_state().
    Verifies the checksum when present (records header['checksum_ok']) and times the H2D copies."""
    import torch

    if "sha256" in header:  # inline mode only
        header["checksum_ok"] = sha256_parts([payload]) == header["sha256"]
    t0 = time.perf_counter()
    view = memoryview(payload)
    tensors = {t["name"]: bytes_to_tensor(t, view[t["offset"]:t["offset"] + t["nbytes"]], device) for t in header["tensors"]}
    torch.cuda.synchronize(device)
    header["h2d_s"] = time.perf_counter() - t0
    comp = header["comp"]
    if comp in ("sink", "recent"):
        for li in range(len(snap["kv"])):
            for key in ("k", "v"):
                t = tensors[f"kv/{li}/{key}"]
                if comp == "sink":
                    snap["kv"][li][key][:, :sink * fsl] = t
                else:
                    snap["kv"][li][key][:, sink * fsl:] = t
            if comp == "sink":
                snap.setdefault("sink_pos", {})[li] = tensors[f"ring/{li}/pos_sink"]
        snap.setdefault("have", set()).add(comp)
    elif comp == "meta":
        for li in range(len(snap["ring"])):
            for key in ("global_end_index", "local_end_index", "pos"):
                snap["ring"][li][key] = tensors[f"ring/{li}/{key}"]
            snap["ring"][li]["total_steps"] = header["scalars"]["ring"][li]["total_steps"]
            snap["ring"][li]["current_step"] = header["scalars"]["ring"][li]["current_step"]
        snap["evict"] = header["scalars"]["evict"]
        for key in ("kv_cache_starts", "kv_cache_ends", "timestep"):
            snap["pipeline"][key] = tensors[f"pipeline/{key}"]
        snap["pipeline"]["pm_processed"] = header["scalars"]["pm_processed"]
        snap["session"].update(header["scalars"]["session"])
        snap["session"]["last_image"] = tensors["session/last_image"]
        snap["vae"].update(header["scalars"]["vae_flags"])
        snap.setdefault("have", set()).add("meta")
    elif comp == "inflight":
        snap["pipeline"]["hidden_states"] = tensors["pipeline/hidden_states"]
        snap.setdefault("have", set()).add("inflight")
    elif comp == "vae":
        for attr in ("_enc_feat_map", "_feat_map"):
            fm = snap["vae"][attr]
            for i in range(len(fm)):
                name = f"vae/{attr}/{i}"
                if name in tensors:
                    fm[i] = tensors[name]
        snap.setdefault("have", set()).add("vae")
    return snap


# ----------------------------------------------------------------------------- runtime
def parse_sweep(s: str) -> list[tuple[str, float]]:
    out = []
    for item in s.split(","):
        pol, bw = item.split(":")
        out.append((pol, 0.0 if bw in ("native", "0", "inf") else float(bw)))
    return out


def build_runtime(args):
    import torch

    from models.data import TextDataset
    from models.util import set_seed
    from streamv2v.inference import SingleGPUInferencePipeline
    from streamv2v.inference_common import load_mp4_as_tensor, merge_cli_config
    import state_ablation as sa

    torch.set_grad_enabled(False)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    import os

    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.use_deterministic_algorithms(True, warn_only=True)
    torch.cuda.set_device(args.gpu_id)
    device = torch.device(f"cuda:{args.gpu_id}")
    config = merge_cli_config(args.config_path, args)
    config.profile = False
    set_seed(args.seed)
    pm = SingleGPUInferencePipeline(config, device)
    pm.load_model(args.checkpoint_folder)
    pl = pm.pipeline
    chunk = pm.base_chunk_size * pl.num_frame_per_block
    total_calls = args.migration_chunk + max(args.post_chunks, getattr(args, "max_post_chunks", args.post_chunks))
    needed = 1 + chunk + total_calls * chunk
    video = load_mp4_as_tensor(args.video_path, resize_hw=(args.height, args.width))
    reps = (needed + video.shape[1] - 1) // video.shape[1]
    if reps > 1:
        video = video.repeat(1, reps, 1, 1)
    video = video[:, :needed].to(torch.bfloat16).unsqueeze(0).pin_memory()
    prompt = TextDataset(args.prompt_file_path)[0]
    runner = sa.Runner(pm, video, prompt, args, device)
    return sa, runner, pm, pl, device


# ----------------------------------------------------------------------------- source (edge A)
def send_state(conn, h, b, throttle, digests: dict):
    """Send one component; its digest is computed concurrently (thread pool) and collected into `digests`,
    which the source ships once in the END message. Nothing waits for hashing on the data path."""
    fut = _pool().submit(component_digest, b)
    digests[h["comp"]] = fut
    t0 = time.time()
    send_msg(conn, "STATE", h, b, throttle)
    return t0, time.time()


def run_source(args):
    import torch

    sa, runner, pm, pl, device = build_runtime(args)
    sink, fsl = pl.num_sink_tokens, pl.frame_seq_length
    srv = tcp_listen(args.bind, args.port, args.mss)
    print(f"[source] listening on {args.bind}:{args.port} mss={args.mss}", flush=True)
    conn = tcp_accept(srv, args.mss)
    clock_sync_server(conn)
    send_msg(conn, "HELLO", {"host_info": host_info(args.gpu_id), "mss_effective": effective_mss(conn), "mss_warnings": list(MSS_WARNINGS),
                             "args": vars(args)}, b"", None)
    M = args.migration_chunk
    while True:
        hdr, _ = recv_msg(conn)
        if hdr["kind"] == "DONE":
            break
        assert hdr["kind"] == "PREP", hdr["kind"]
        policy, bw = hdr["policy"], float(hdr["bw_mbps"])
        print(f"[source] {policy} @ {bw or 'native'} Mbps rep {hdr.get('rep')}: running to M={M}", flush=True)
        session = runner.start()
        t_run0 = time.time()
        for c in range(M):
            runner.step(session, c)
        torch.cuda.synchronize(device)
        t_ser0 = time.time()
        snap = sa.serialize_state(pl, pm, session)  # device-side clone of the live state
        torch.cuda.synchronize(device)
        t_ser1 = time.time()
        send_msg(conn, "PREPARED", {"t_run_to_M_s": t_ser0 - t_run0, "t_serialize_start": t_ser0, "t_serialize_end": t_ser1,
                                    "gpu_mem_alloc_mb": torch.cuda.memory_allocated(device) / MB}, b"", None)
        hdr, _ = recv_msg(conn)
        assert hdr["kind"] == "READY", hdr["kind"]
        throttle = Throttle(bw * 1e6) if bw > 0 else None
        fg, bg = POLICIES[policy]
        log = {"policy": policy, "bytes_by_comp": {}, "d2h_by_comp": {}, "t_send_by_comp": {}}
        digests: dict = {}
        if policy == "replay":
            hist_end = max(1, hdr.get("last_refresh_call", -1) + 1)
            idx = list(range(0, runner.first)) + [runner.first + cc * runner.chunk + f for cc in list(range(0, hist_end)) + list(range(M - 3, M)) for f in range(runner.chunk)]
            frames = ((runner.video[0, :, idx].float().permute(1, 2, 3, 0) * 0.5 + 0.5).clamp(0, 1) * 255).to(torch.uint8).contiguous().numpy()
            t0 = time.time()
            send_msg(conn, "SEEDS", {"n_frames": int(frames.shape[0]), "hist_end": hist_end, "sha256": sha256_parts([frames])}, frames, throttle)
            log["bytes_by_comp"]["seeds"] = frames.nbytes; log["t_send_by_comp"]["seeds"] = [t0, time.time()]
        else:
            for comp in sorted(fg):
                h, b = pack_component(snap, comp, sink, fsl)
                t0, t1 = send_state(conn, {"fg": True, **h}, b, throttle, digests)
                log["bytes_by_comp"][comp] = h["nbytes"]; log["d2h_by_comp"][comp] = h["d2h_s"]; log["t_send_by_comp"][comp] = [t0, t1]
        send_msg(conn, "GO", {"policy": policy, "t_go": time.time()}, b"", None)
        for comp in sorted(bg):
            h, b = pack_component(snap, comp, sink, fsl)
            t0, t1 = send_state(conn, {"fg": False, **h}, b, throttle, digests)
            log["bytes_by_comp"][comp] = h["nbytes"]; log["d2h_by_comp"][comp] = h["d2h_s"]; log["t_send_by_comp"][comp] = [t0, t1]
        log["digests"] = {comp: f.result() for comp, f in digests.items()}
        send_msg(conn, "END", {"t_end": time.time(), **log}, b"", None)
        del snap
        torch.cuda.empty_cache()
    conn.close()
    srv.close()


# ----------------------------------------------------------------------------- destination (edge B)
def bind_sink_into_live(pl, snap, sink, fsl, device, cfg_thr, refresh_was_frozen: bool) -> int:
    """Atomic bind of the transferred sink into the live ring buffer. With refresh frozen, slot positions can
    only have moved by a t_refresh realign, so transferred keys are re-rotated by the per-slot delta."""
    from models.wan.causal_model import _shift_temporal_rope

    freqs = pl.generator.model.freqs.to(device)
    shifted = 0
    for li, layer in enumerate(pl.kv_cache1):
        k_x = snap["kv"][li]["k"][:, :sink * fsl]; v_x = snap["kv"][li]["v"][:, :sink * fsl]; pos_x = snap["sink_pos"][li]
        for b in range(k_x.shape[0]):
            for sidx in range(sink):
                lo, hi = sidx * fsl, (sidx + 1) * fsl
                kk = k_x[b, lo:hi]
                if refresh_was_frozen:
                    delta = int(layer["pos"][b, sidx].item() - pos_x[b, sidx].item())
                    if delta != 0:
                        kk = _shift_temporal_rope(kk, freqs, delta); shifted += 1
                else:
                    layer["pos"][b, sidx] = pos_x[b, sidx]
                layer["k"][b, lo:hi] = kk; layer["v"][b, lo:hi] = v_x[b, lo:hi]
    for block in pl.generator.model.blocks:
        block.self_attn.adapt_sink_thr = cfg_thr
    return shifted


def run_dest(args):
    import torch

    sa, runner, pm, pl, device = build_runtime(args)
    sink, fsl = pl.num_sink_tokens, pl.frame_seq_length
    M, N = args.migration_chunk, args.post_chunks
    me = socket.gethostname()
    min_bw = min([bw for _, bw in parse_sweep(args.sweep) if bw > 0] or [0])
    cfg_thr = float(getattr(pm.config, "adapt_sink_threshold", -1))
    workload = Path(args.video_path).stem
    k_steps = len(pl.denoising_step_list)

    # 1. bit-exact baseline on this GPU (same seeds -> same frames as the source would have produced)
    est_sink_bytes = k_steps * 2 * pl.num_transformer_blocks * sink * fsl * pl.num_heads * 128 * 2
    N_base = N
    if min_bw > 0:
        N_base = max(N, int((est_sink_bytes * 8 / (min_bw * 1e6) + 30 * 0.55) / 0.55) + 1)  # 0.55 s/chunk conservative service time
    print(f"[dest] baseline run ({M + N_base} calls; window up to {N_base} post-migration calls for the slowest bandwidth)", flush=True)
    session = runner.start()
    baseline, chunk_times, sink_pos_hist = {}, [], {}
    for c in range(M + N_base):
        t0 = time.perf_counter()
        fr = runner.step(session, c)
        torch.cuda.synchronize(device)
        chunk_times.append(time.perf_counter() - t0)
        if fr is not None:
            baseline[c] = fr
        sink_pos_hist[c] = sa.slot_positions(pl)["sink_slot_pos"]
        runner.noise_hist[c] = float(session.noise_scale)
    service_s = float(np.median(chunk_times[M:]))
    refresh = [c for c in range(1, M + N_base) if sink_pos_hist[c] != sink_pos_hist[c - 1]]
    pre = [c for c in refresh if c < M]
    runner.last_refresh_call = pre[-1] if pre else -1
    print(f"[dest] baseline done; service time {service_s * 1e3:.0f} ms/chunk; refresh calls {refresh}", flush=True)

    sock = tcp_connect(args.host, args.port, args.mss)
    sync = clock_sync_client(sock)
    hello, _ = recv_msg(sock)
    assert hello["kind"] == "HELLO"
    off = sync["offset_s"]  # source_wall ~= dest_wall + off

    def to_dest(t):
        return None if t is None else t - off

    print(f"[dest] connected to {args.host}; clock offset {off * 1e3:+.2f} ms, rtt_min {sync['rtt_min_s'] * 1e3:.2f} ms, "
          f"mss {effective_mss(sock)} (source {hello.get('mss_effective')})", flush=True)

    # receive pool: largest single component (VAE caches ~3 GB at 480x832) + margin; allocated once, reused
    pool = RecvPool(int(estimate_sink_bytes(k_steps, args.height, args.width, args.model_type) * 2.2) + (64 << 20))
    print(f"[dest] receive pool 2 x {len(pool.bufs[0]) / MB:.0f} MB preallocated", flush=True)
    results = []
    for rep in range(1, args.reps + 1):
        for policy, bw in parse_sweep(args.sweep):
            bw_tag = "native" if bw <= 0 else f"{bw:g}"
            rd = run_dir(args.experiment, policy=policy, bw=bw_tag, rep=rep, workload=workload, seed=args.seed, k=k_steps, mss=args.mss or 0)
            out_log = open(rd / "stdout.log", "a")

            def log(msg):
                print(msg, flush=True); out_log.write(msg + "\n"); out_log.flush()

            log(f"[dest] === {policy} @ {bw_tag} Mbps rep {rep} -> {rd.name} ===")
            write_json(rd / "config.json", {"experiment": args.experiment, "policy": policy, "bw_mbps": bw, "rep": rep, "workload": workload, "video_path": args.video_path,
                                            "seed": args.seed, "k": k_steps, "migration_chunk": M, "post_chunks": N, "mss": args.mss, "transport": "tcp+tcp_maxseg+token-bucket",
                                            "shaper": "sender token bucket" if bw > 0 else "none (native)", "args": vars(args), "service_s": service_s, "refresh_calls_baseline": refresh})
            write_json(rd / "host_info.json", {"dest": host_info(args.gpu_id), "source": hello.get("host_info"), "clock_sync": sync,
                                               "mss_dest": effective_mss(sock), "mss_source": hello.get("mss_effective"), "mss_warnings_dest": list(MSS_WARNINGS), "mss_warnings_source": hello.get("mss_warnings")})
            ev = EventLog(rd / "events.csv", me)
            metrics = CsvLog(rd / "metrics.csv", ["call", "rel", "t_out_rel", "chunk_s", "psnr", "ssim", "missing", "sink_bound", "gpu_mem_alloc_mb", "sink_slot_pos"])
            sampler = ResourceSampler(rd / "network.csv", me, args.gpu_id, args.iface); sampler.start()

            send_msg(sock, "PREP", {"policy": policy, "bw_mbps": bw, "rep": rep, "last_refresh_call": runner.last_refresh_call}, b"", None)
            prep, _ = recv_msg(sock)
            assert prep["kind"] == "PREPARED"
            # provisioning: allocate buffers on this GPU (not part of the handoff time)
            session = runner.fresh_destination()
            snap = sa.serialize_state(pl, pm, session)
            for layer in snap["kv"]:
                layer["k"].zero_(); layer["v"].zero_()
            snap["have"] = set()
            torch.cuda.synchronize(device)
            t_mig = time.time()
            ev.set_ref(t_mig)
            ev.log("migration_start", t_mig, policy=policy, bw_mbps=bw)
            ev.log("source_serialize", to_dest(prep["t_serialize_start"]), end=to_dest(prep["t_serialize_end"]),
                   seconds=prep["t_serialize_end"] - prep["t_serialize_start"], source_gpu_mem_mb=prep.get("gpu_mem_alloc_mb"))
            send_msg(sock, "READY", {"policy": policy, "bw_mbps": bw, "last_refresh_call": runner.last_refresh_call}, b"", None)

            bytes_cat, checksum_ok = {}, {}
            h2d_total = 0.0
            local_digest: dict = {}  # comp -> future(digest), computed from the received bytes in the hash pool

            def hash_later(hdr, payload):
                # the payload lives in a pool buffer; hash its tensor slices in the thread pool and keep the
                # buffer reserved until the digest is done (the other buffer takes the next message meanwhile)
                fut = _pool().submit(component_digest, payload_slices(hdr, payload))
                local_digest[hdr["comp"]] = fut
                pool.hold(fut)

            def verify_all(end_hdr):
                for comp, d in (end_hdr.get("digests") or {}).items():
                    fut = local_digest.get(comp)
                    ok = (fut.result() == d) if fut is not None else None
                    checksum_ok[comp] = ok
                    ev.log("checksum", comp=comp, ok=ok)

            while True:
                hdr, payload = recv_msg(sock, pool.next())
                if hdr["kind"] == "GO":
                    ev.log("go", to_dest(hdr["t_go"])); break
                if hdr["kind"] == "SEEDS":
                    bytes_cat["seeds"] = len(payload); checksum_ok["seeds"] = sha256_parts([payload]) == hdr["sha256"]
                    ev.log("fg_recv", hdr["t_recv"], comp="seeds", bytes=len(payload), t_send_src=to_dest(hdr["t_send"]), checksum_ok=checksum_ok["seeds"])
                else:
                    unpack_into_snapshot(hdr, payload, device, snap, sink, fsl)
                    hash_later(hdr, payload)
                    bytes_cat[hdr["comp"]] = len(payload); h2d_total += hdr.get("h2d_s", 0.0)
                    ev.log("fg_recv", hdr["t_recv"], comp=hdr["comp"], bytes=len(payload), t_send_src=to_dest(hdr["t_send"]), d2h_s=hdr.get("d2h_s"), h2d_s=hdr.get("h2d_s"))

            bound_call = None
            if policy == "full":
                sa.restore_state(pl, pm, session, snap, set(sa.STATE_COMPONENTS))
            elif policy in ("ours", "ours_refresh"):
                sa.restore_state(pl, pm, session, snap, {"meta", "inflight"})
                if policy == "ours":
                    for block in pl.generator.model.blocks:
                        block.self_attn.adapt_sink_thr = -1  # freeze promotions until the true sink binds
                    ev.log("refresh_frozen")
            elif policy == "replay":
                session, ms, seed_bytes, replayed = runner.replay_restart(M, 3, True, True, True)
                ev.log("replay_done", replay_ms=ms, replayed_calls=replayed)
            elif policy == "repeat":
                session = runner.start()
                for c in range(M):
                    runner.step(session, c)
            torch.cuda.synchronize(device)
            t_resume = ev.log("resume", gpu_mem_alloc_mb=torch.cuda.memory_allocated(device) / MB)

            bg = {"sink_t_first": None, "sink_t_end": None, "bytes": 0, "end": None, "h2d_s": 0.0, "checksum_ok": None, "t_send_src": None}

            def receiver():
                while True:
                    hdr, payload = recv_msg(sock, pool.next())
                    if hdr["kind"] == "END":
                        verify_all(hdr); bg["checksum_ok"] = checksum_ok.get("sink"); bg["end"] = hdr; break
                    if bg["sink_t_first"] is None:
                        bg["sink_t_first"] = hdr["t_recv_start"]; bg["t_send_src"] = to_dest(hdr["t_send"])
                        ev.log("sink_recv_start", hdr["t_recv_start"], t_send_src=bg["t_send_src"])
                    unpack_into_snapshot(hdr, payload, device, snap, sink, fsl)
                    bg["bytes"] += len(payload); bg["h2d_s"] += hdr.get("h2d_s", 0.0)
                    bg["sink_t_end"] = time.time()  # bytes are on the GPU: the sink can bind now; verification follows
                    ev.log("sink_ready", bg["sink_t_end"], bytes=len(payload), h2d_s=hdr.get("h2d_s"), d2h_s=hdr.get("d2h_s"))
                    hash_later(hdr, payload)

            th = threading.Thread(target=receiver, daemon=True); th.start()

            pending_cold = None
            if policy == "cold":
                session, frames0, ms = runner.restart_at(session, M)
                ev.log("cold_restart_done", restart_ms=ms)
                pending_cold = (M + k_steps - 1, frames0)
            first_out = None
            rows = []
            last_pos = sink_pos_hist.get(M - 1)
            n_calls = N
            if policy in ("ours", "ours_refresh") and bw > 0:
                est_sink_bytes = k_steps * 2 * len(pl.kv_cache1) * sink * fsl * pl.num_heads * 128 * 2
                n_calls = max(N, int((est_sink_bytes * 8 / (bw * 1e6) + 30 * service_s) / service_s) + 1)
                if n_calls > N:
                    ev.log("window_extended", calls=n_calls)
            for c in range(M, M + n_calls):
                if policy in ("ours", "ours_refresh") and bound_call is None and bg["sink_t_end"] is not None:
                    shifted = bind_sink_into_live(pl, snap, sink, fsl, device, cfg_thr, refresh_was_frozen=(policy == "ours"))
                    bound_call = c
                    ev.log("sink_bind", call=c, slots_rerotated=shifted, checksum_ok=bg["checksum_ok"])
                t0 = time.perf_counter()
                fr = None if (pending_cold is not None and c == M) else runner.step(session, c)
                if pending_cold is not None and c == pending_cold[0]:
                    fr = pending_cold[1]
                torch.cuda.synchronize(device)
                chunk_s = time.perf_counter() - t0
                t_out = time.time()
                ref = baseline.get(c)
                ps = ss = None
                if fr is not None and ref is not None:
                    ps = float(np.mean([sa.psnr(ref[f].astype(np.float32) / 255.0, fr[f].astype(np.float32) / 255.0) for f in range(min(ref.shape[0], fr.shape[0]))]))
                    ss = float(sa.ssim(ref[-1].astype(np.float32) / 255.0, fr[-1].astype(np.float32) / 255.0))
                if fr is not None and first_out is None:
                    first_out = t_out; ev.log("first_output", t_out, call=c)
                pos_now = sa.slot_positions(pl)["sink_slot_pos"]
                if last_pos is not None and pos_now != last_pos:
                    ev.log("adaptive_refresh_or_realign", t_out, call=c, sink_slot_pos=pos_now)
                last_pos = pos_now
                row = {"call": c, "rel": c - M, "t_out_rel": t_out - t_mig, "chunk_s": chunk_s, "psnr": ps, "ssim": ss, "missing": fr is None,
                       "sink_bound": bound_call is not None and c >= bound_call, "gpu_mem_alloc_mb": torch.cuda.memory_allocated(device) / MB, "sink_slot_pos": pos_now}
                rows.append(row)
                metrics.row(**{k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in row.items()})
            th.join(timeout=900)
            sampler.finish(); metrics.close()
            end = bg["end"] or {}
            if end:
                ev.log("source_end", to_dest(end.get("t_end")), bytes_by_comp=end.get("bytes_by_comp"), d2h_by_comp=end.get("d2h_by_comp"))

            def win(lo, hi, key="psnr"):
                v = [r[key] for r in rows if lo <= r["rel"] <= hi and r[key] is not None]
                return float(np.mean(v)) if v else None

            rejoin = None
            if bound_call is not None:
                for r in rows:
                    if r["call"] >= bound_call and r["psnr"] is not None and r["psnr"] >= 35.0:
                        rejoin = r["call"] - bound_call; break
            after_bind = [r["psnr"] for r in rows if bound_call is not None and r["call"] >= bound_call + 8 and r["psnr"] is not None]
            outs = [r for r in rows if not r["missing"]]
            cont_ready = None
            if bound_call is not None:
                cont_ready = next((r["t_out_rel"] for r in rows if r["call"] == bound_call), None)
            elif policy in ("full", "repeat") and first_out:
                cont_ready = first_out - t_mig
            summary = {
                "policy": policy, "bw_mbps": bw, "rep": rep, "run_dir": str(rd), "service_s": service_s, "k": k_steps, "workload": workload, "seed": args.seed,
                "first_output_latency_s": (first_out - t_mig) if first_out else None, "resume_latency_s": t_resume - t_mig,
                "sink_recv_start_rel_s": (bg["sink_t_first"] - t_mig) if bg["sink_t_first"] else None,
                "sink_ready_rel_s": (bg["sink_t_end"] - t_mig) if bg["sink_t_end"] else None,
                "continuity_ready_rel_s": cont_ready, "bound_call": bound_call, "rejoin_calls_after_bind": rejoin,
                "bytes_fg_by_comp": bytes_cat, "bytes_bg_sink": bg["bytes"], "total_bytes": sum(bytes_cat.values()) + bg["bytes"],
                "checksum_ok": {**checksum_ok, "sink": bg["checksum_ok"]},
                "serialize_s": prep["t_serialize_end"] - prep["t_serialize_start"], "d2h_by_comp": end.get("d2h_by_comp"), "h2d_fg_s": h2d_total, "h2d_sink_s": bg["h2d_s"],
                "psnr_M0": win(0, 0), "psnr_M0_7": win(0, 7), "psnr_M16_end": win(16, 10**6), "ssim_M0_7": win(0, 7, "ssim"), "ssim_M16_end": win(16, 10**6, "ssim"),
                "psnr_after_bind_8": float(np.mean(after_bind)) if after_bind else None,
                "missing_chunks": sum(1 for r in rows if r["missing"]),
                "hiccup_chunks": sum(1 for a_, b_ in zip(outs, outs[1:]) if (b_["t_out_rel"] - a_["t_out_rel"]) > 2 * service_s),
                "gpu_mem_alloc_mb_max": max(r["gpu_mem_alloc_mb"] for r in rows),
                "clock_offset_s": off, "rtt_min_s": sync["rtt_min_s"], "mss_dest": effective_mss(sock), "mss_source": hello.get("mss_effective"),
                "validation": {
                    "full_identical": (all((r["psnr"] or 0) >= 99 for r in outs)) if policy == "full" else None,
                    "repeat_identical": (all((r["psnr"] or 0) >= 99 for r in outs)) if policy == "repeat" else None,
                    # every received component must have a matching digest (a missing digest fails, not skips)
                    "checksums_all_ok": all(checksum_ok.get(c) is True for c in bytes_cat) and (bg["checksum_ok"] is True or not bg["bytes"]),
                },
            }
            write_json(rd / "summary.json", summary)
            results.append(summary)
            tf = summary["first_output_latency_s"]
            log(f"[dest] {policy} @ {bw_tag}: first output {tf if tf is None else round(tf, 2)} s, continuity-ready {cont_ready if cont_ready is None else round(cont_ready, 2)} s, "
                f"bytes fg {sum(bytes_cat.values()) / MB:.1f} MB bg {bg['bytes'] / MB:.0f} MB, PSNR M+16.. {summary['psnr_M16_end'] if summary['psnr_M16_end'] is None else round(summary['psnr_M16_end'], 1)} dB, "
                f"checksums {summary['validation']['checksums_all_ok']}")
            out_log.close()
            del snap
            torch.cuda.empty_cache()
    send_msg(sock, "DONE", {}, b"", None)
    sock.close()
    if args.out_dir:
        Path(args.out_dir).mkdir(parents=True, exist_ok=True)
        write_json(Path(args.out_dir) / "proto_results.json", results)
    print(f"[dest] done; {len(results)} runs under results/evaluation/{args.experiment}/")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--role", choices=["source", "dest"], required=True)
    p.add_argument("--host", type=str, default="127.0.0.1", help="dest: source host to connect to")
    p.add_argument("--bind", type=str, default="0.0.0.0", help="source: address to listen on")
    p.add_argument("--port", type=int, default=29777)
    p.add_argument("--mss", type=int, default=DEFAULT_MSS, help="TCP_MAXSEG cap on every socket (0 = kernel default)")
    p.add_argument("--iface", type=str, default=None, help="NIC to sample in network.csv (default: all non-loopback)")
    p.add_argument("--experiment", type=str, default="single_handoff")
    p.add_argument("--reps", type=int, default=1)
    p.add_argument("--sweep", type=str, default="ours:1000,full:1000,cold:1000,replay:1000", help="policy:bw_mbps,... (bw native/0 = unshaped)")
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
    p.add_argument("--gpu_id", type=int, required=True)
    p.add_argument("--model_type", type=str, default="T2V-1.3B")
    p.add_argument("--fixed_noise_scale", action="store_true", default=False)
    p.add_argument("--t2v", action="store_true", default=False)
    p.add_argument("--profile", action="store_true", default=False)
    p.add_argument("--use_taehv", action="store_true", default=False)
    p.add_argument("--normalize_latents", action="store_true", default=False)
    p.add_argument("--use_tensorrt", action="store_true", default=False)
    p.add_argument("--fast", action="store_true", default=False)
    p.add_argument("--migration_chunk", type=int, default=30)
    p.add_argument("--post_chunks", type=int, default=80)
    p.add_argument("--out_dir", type=str, default=None, help="optional: also write a combined proto_results.json here")
    a = p.parse_args()
    a.mss = a.mss or None
    # The input video must cover the longest adaptive window (slowest shaped bandwidth): sink time / service + 30 chunks.
    bws = [bw for _, bw in parse_sweep(a.sweep) if bw > 0]
    a.max_post_chunks = a.post_chunks
    if bws:
        a.max_post_chunks = max(a.post_chunks, int((estimate_sink_bytes(a.step, a.height, a.width, a.model_type) * 8 / (min(bws) * 1e6) + 30 * 0.55) / 0.55) + 1)
    return a


def estimate_sink_bytes(k: int, height: int, width: int, model_type: str = "T2V-1.3B") -> int:
    """Upper-bound estimate of the durable sink (K+V, bf16, all Stream-Batch rows) from the config, before the model is loaded."""
    layers, heads = (40, 40) if model_type == "T2V-14B" else (30, 12)
    fsl = (height // 16) * (width // 16)
    sink_slots = 3
    return k * layers * sink_slots * fsl * heads * 128 * 2 * 2


if __name__ == "__main__":
    a = parse_args()
    run_source(a) if a.role == "source" else run_dest(a)
