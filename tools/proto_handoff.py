#!/usr/bin/env python3
"""Two-process late-binding handoff prototype (source GPU -> destination GPU over a TCP socket).

Question answered: can generation move before its bulk continuity state moves?

    source (GPU a)                                  destination (GPU b)
      run session to chunk M                          allocate buffers (provisioning, not timed)
      serialize state                                 send READY  ---------------------------> t_mig
      policy ours : fast msg (in-flight + meta) ----> restore, freeze sink refresh, resume at M
                    sink (1.6 GB) in background ----> receiver thread; atomic bind at a chunk boundary
      policy full : everything ---------------------> restore all, then resume (stall = transfer)
      policy cold : GO ------------------------------> fresh start at chunk M (official restart path)
      policy replay: seed frames -------------------> local replay (sinkhist, pos-faithful), resume

All bytes go through one TCP connection with a sender-side token bucket (--bw_mbps). Both
processes read the same input video (the camera stream is local to each edge); only state crosses
the link. Continuity is scored at the destination against its own bit-exact baseline run.

Usage (same host, two GPUs):
    python tools/proto_handoff.py --role dest   --gpu_id 1 --sweep ours:1000,full:1000,cold:1000 --out_dir results/state_migration/proto
    python tools/proto_handoff.py --role source --gpu_id 0 --sweep ours:1000,full:1000,cold:1000
(tools/run_proto.sh launches both.)
"""

from __future__ import annotations

import argparse
import json
import socket
import struct
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for p in (REPO_ROOT, REPO_ROOT / "tools"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np  # noqa: E402

MB = 1024.0 * 1024.0


# ----------------------------------------------------------------------------- framing + throttle
class Throttle:
    """Sender-side token bucket: bytes are released at `bw_bps` with a small burst."""

    def __init__(self, bw_bps: float, burst_bytes: int = 1 << 20):
        self.rate = float(bw_bps) / 8.0  # bytes/s
        self.burst = burst_bytes
        self.tokens = float(burst_bytes)
        self.t = time.perf_counter()

    def take(self, n: int):
        if self.rate <= 0:
            return
        while True:
            now = time.perf_counter()
            self.tokens = min(self.burst, self.tokens + (now - self.t) * self.rate)
            self.t = now
            if self.tokens >= n:
                self.tokens -= n
                return
            time.sleep(min(0.01, (n - self.tokens) / self.rate))


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


def recv_exact(sock: socket.socket, n: int) -> bytearray:
    buf = bytearray(n)
    view = memoryview(buf)
    got = 0
    while got < n:
        r = sock.recv_into(view[got:], min(1 << 22, n - got))
        if r == 0:
            raise ConnectionError("socket closed")
        got += r
    return buf


def recv_msg(sock: socket.socket):
    lens = recv_exact(sock, 16)
    hl, pl = struct.unpack("!QQ", bytes(lens))
    hdr = json.loads(bytes(recv_exact(sock, hl)).decode())
    payload = recv_exact(sock, pl) if pl else bytearray()
    hdr["t_recv"] = time.time()
    return hdr, payload


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


def pack_component(snap: dict, comp: str, sink: int, fsl: int) -> tuple[dict, list]:
    """Serialize one component of a serialize_state() snapshot into (header, [buffers])."""
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
    header = {"comp": comp, "tensors": [], "scalars": {}}
    buffers = []
    off = 0
    for name, m, b in parts:
        n = b.nbytes
        header["tensors"].append({"name": name, "offset": off, "nbytes": n, **m})
        buffers.append(b)
        off += n
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
    """Merge a received component into a destination-side snapshot dict understood by restore_state()."""
    import torch

    view = memoryview(payload)
    tensors = {t["name"]: bytes_to_tensor(t, view[t["offset"]:t["offset"] + t["nbytes"]], device) for t in header["tensors"]}
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


# ----------------------------------------------------------------------------- roles
POLICIES = {
    # name: (messages sent before the destination may resume, messages sent in the background)
    "ours": ({"inflight", "meta"}, {"sink"}),            # refresh frozen until the true sink binds
    "ours_refresh": ({"inflight", "meta"}, {"sink"}),    # adaptive refresh left on; true sink overwrites at bind
    "full": ({"sink", "recent", "meta", "vae", "inflight"}, set()),
    "cold": (set(), set()),
    "replay": ({"seeds"}, set()),
}


def parse_sweep(s: str) -> list[tuple[str, float]]:
    out = []
    for item in s.split(","):
        pol, bw = item.split(":")
        out.append((pol, float(bw)))
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
    total_calls = args.migration_chunk + args.post_chunks
    needed = 1 + chunk + total_calls * chunk
    video = load_mp4_as_tensor(args.video_path, resize_hw=(args.height, args.width))
    reps = (needed + video.shape[1] - 1) // video.shape[1]
    if reps > 1:
        video = video.repeat(1, reps, 1, 1)
    video = video[:, :needed].to(torch.bfloat16).unsqueeze(0).pin_memory()
    prompt = TextDataset(args.prompt_file_path)[0]
    runner = sa.Runner(pm, video, prompt, args, device)
    return sa, runner, pm, pl, device


def run_source(args):
    import torch

    sa, runner, pm, pl, device = build_runtime(args)
    sink, fsl = pl.num_sink_tokens, pl.frame_seq_length
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.host, args.port))
    srv.listen(1)
    print(f"[source] listening on {args.host}:{args.port}", flush=True)
    conn, _ = srv.accept()
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    M = args.migration_chunk
    while True:
        hdr, _ = recv_msg(conn)
        if hdr["kind"] == "DONE":
            break
        assert hdr["kind"] == "PREP", hdr["kind"]
        policy, bw = hdr["policy"], float(hdr["bw_mbps"])
        print(f"[source] {policy} @ {bw:g} Mbps: running to M={M}", flush=True)
        session = runner.start()
        for c in range(M):
            runner.step(session, c)
        torch.cuda.synchronize(device)
        snap = sa.serialize_state(pl, pm, session)
        send_msg(conn, "PREPARED", {}, b"", None)
        hdr, _ = recv_msg(conn)
        assert hdr["kind"] == "READY", hdr["kind"]
        throttle = Throttle(bw * 1e6)
        fg, bg = POLICIES[policy]
        t0 = time.time()
        if policy == "replay":
            hist_end = max(1, hdr.get("last_refresh_call", -1) + 1)
            idx = list(range(0, runner.first)) + [runner.first + cc * runner.chunk + f for cc in list(range(0, hist_end)) + list(range(M - 3, M)) for f in range(runner.chunk)]
            frames = ((runner.video[0, :, idx].float().permute(1, 2, 3, 0) * 0.5 + 0.5).clamp(0, 1) * 255).to(torch.uint8).contiguous().numpy()
            send_msg(conn, "SEEDS", {"n_frames": int(frames.shape[0]), "hist_end": hist_end}, frames, throttle)
        else:
            for comp in sorted(fg):
                h, b = pack_component(snap, comp, sink, fsl)
                send_msg(conn, "STATE", {"fg": True, **h}, b, throttle)
        send_msg(conn, "GO", {"policy": policy, "t_go": time.time()}, b"", None)
        for comp in sorted(bg):
            h, b = pack_component(snap, comp, sink, fsl)
            send_msg(conn, "STATE", {"fg": False, **h}, b, throttle)
        send_msg(conn, "END", {"t_end": time.time(), "elapsed_s": time.time() - t0}, b"", None)
        del snap
        torch.cuda.empty_cache()
    conn.close()
    srv.close()


def run_dest(args):
    import torch

    sa, runner, pm, pl, device = build_runtime(args)
    sink, fsl = pl.num_sink_tokens, pl.frame_seq_length
    M, N = args.migration_chunk, args.post_chunks
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. bit-exact baseline on this GPU (same seeds -> same frames as the source would have produced)
    print("[dest] baseline run", flush=True)
    session = runner.start()
    baseline, chunk_times, sink_pos_hist = {}, [], {}
    for c in range(M + N):
        t0 = time.perf_counter()
        fr = runner.step(session, c)
        torch.cuda.synchronize(device)
        chunk_times.append(time.perf_counter() - t0)
        if fr is not None:
            baseline[c] = fr
        sink_pos_hist[c] = sa.slot_positions(pl)["sink_slot_pos"]
        runner.noise_hist[c] = float(session.noise_scale)
    service_s = float(np.median(chunk_times[M:]))
    refresh = [c for c in range(1, M + N) if sink_pos_hist[c] != sink_pos_hist[c - 1]]
    pre = [c for c in refresh if c < M]
    runner.last_refresh_call = pre[-1] if pre else -1
    print(f"[dest] baseline done; service time {service_s * 1e3:.0f} ms/chunk; refresh calls {refresh}", flush=True)

    sock = socket.create_connection((args.host, args.port))
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    results = []
    for policy, bw in parse_sweep(args.sweep):
        print(f"[dest] === {policy} @ {bw:g} Mbps ===", flush=True)
        send_msg(sock, "PREP", {"policy": policy, "bw_mbps": bw}, b"", None)
        hdr, _ = recv_msg(sock)
        assert hdr["kind"] == "PREPARED", hdr["kind"]
        # provisioning: allocate buffers on this GPU (not part of the handoff time)
        session = runner.fresh_destination()
        snap = sa.serialize_state(pl, pm, session)  # template with the right shapes; contents are overwritten
        for layer in snap["kv"]:
            layer["k"].zero_(); layer["v"].zero_()
        snap["have"] = set()
        torch.cuda.synchronize(device)
        bytes_fg = bytes_bg = 0
        rec = {"policy": policy, "bw_mbps": bw, "service_s": service_s, "events": [], "calls": []}
        t_mig = time.time()
        send_msg(sock, "READY", {"policy": policy, "bw_mbps": bw, "last_refresh_call": runner.last_refresh_call}, b"", None)

        # foreground messages until GO
        seeds = None
        while True:
            hdr, payload = recv_msg(sock)
            if hdr["kind"] == "GO":
                break
            if hdr["kind"] == "SEEDS":
                seeds = (hdr, payload)
            else:
                unpack_into_snapshot(hdr, payload, device, snap, sink, fsl)
            bytes_fg += len(payload)
            rec["events"].append({"t": time.time() - t_mig, "recv": hdr.get("comp", hdr["kind"]), "mb": len(payload) / MB})
        t_go = time.time()

        # apply the policy
        bound_call = None
        cfg_thr = float(getattr(pm.config, "adapt_sink_threshold", -1))
        if policy == "full":
            sa.restore_state(pl, pm, session, snap, set(sa.STATE_COMPONENTS))
        elif policy in ("ours", "ours_refresh"):
            sa.restore_state(pl, pm, session, snap, {"meta", "inflight"})
            if policy == "ours":
                for block in pl.generator.model.blocks:
                    block.self_attn.adapt_sink_thr = -1  # freeze promotions until the true sink binds
        elif policy == "cold":
            pass
        elif policy == "replay":
            session, ms, seed_bytes, replayed = runner.replay_restart(M, 3, True, True, True)
            rec["events"].append({"t": time.time() - t_mig, "replay_ms": ms, "replayed_calls": replayed})
        torch.cuda.synchronize(device)
        t_resume = time.time()

        # background receiver (END always arrives; sink only for ours)
        bg = {"sink": None, "end": None, "bytes": 0}

        def receiver():
            while True:
                hdr, payload = recv_msg(sock)
                if hdr["kind"] == "END":
                    bg["end"] = time.time(); break
                unpack_into_snapshot(hdr, payload, device, snap, sink, fsl)
                bg["bytes"] += len(payload)
                bg["sink"] = time.time()

        th = threading.Thread(target=receiver, daemon=True)
        th.start()

        # generate M..M+N-1, binding the sink at the first chunk boundary after it arrives
        if policy == "cold":
            session, frames0, ms = runner.restart_at(session, M)
            rec["events"].append({"t": time.time() - t_mig, "restart_ms": ms})
            lag = len(pl.denoising_step_list) - 1
            pending_cold = (M + lag, frames0)
        else:
            pending_cold = None
        frames_out = {}
        for c in range(M, M + N):
            if policy in ("ours", "ours_refresh") and bound_call is None and bg["sink"] is not None:
                # Atomic bind. The destination may have rewound/realigned RoPE positions since M
                # (t_refresh at call 48): re-rotate the transferred keys by the per-slot position delta.
                from models.wan.causal_model import _shift_temporal_rope

                freqs = pl.generator.model.freqs.to(device)
                shifted = 0
                for li, layer in enumerate(pl.kv_cache1):
                    k_x = snap["kv"][li]["k"][:, :sink * fsl]
                    v_x = snap["kv"][li]["v"][:, :sink * fsl]
                    pos_x = snap["sink_pos"][li]
                    for b in range(k_x.shape[0]):
                        for sidx in range(sink):
                            lo, hi = sidx * fsl, (sidx + 1) * fsl
                            kk = k_x[b, lo:hi]
                            if policy == "ours":
                                # frozen refresh: slot positions only moved by a t_refresh realign; follow it
                                delta = int(layer["pos"][b, sidx].item() - pos_x[b, sidx].item())
                                if delta != 0:
                                    kk = _shift_temporal_rope(kk, freqs, delta); shifted += 1
                            else:
                                # refresh was on: the slot may hold a promoted frame; take the true sink's
                                # position back verbatim (exact only if no realign happened since M)
                                layer["pos"][b, sidx] = pos_x[b, sidx]
                            layer["k"][b, lo:hi] = kk
                            layer["v"][b, lo:hi] = v_x[b, lo:hi]
                for block in pl.generator.model.blocks:
                    block.self_attn.adapt_sink_thr = cfg_thr
                bound_call = c
                rec["events"].append({"t": time.time() - t_mig, "bound_at_call": c, "slots_rerotated": shifted})
            if pending_cold is not None and c == M:
                fr = None
            else:
                fr = runner.step(session, c)
            if pending_cold is not None and c == pending_cold[0]:
                fr = pending_cold[1]
            torch.cuda.synchronize(device)
            t_out = time.time()
            ref = baseline.get(c)
            ps = None
            if fr is not None and ref is not None:
                ps = float(np.mean([sa.psnr(ref[f].astype(np.float32) / 255.0, fr[f].astype(np.float32) / 255.0) for f in range(min(ref.shape[0], fr.shape[0]))]))
            rec["calls"].append({"call": c, "rel": c - M, "t_out": t_out - t_mig, "psnr": ps, "missing": fr is None})
            frames_out[c] = fr
        th.join(timeout=600)
        rec.update({
            "t_go": t_go - t_mig, "t_resume": t_resume - t_mig,
            "t_first_out": next((x["t_out"] for x in rec["calls"] if not x["missing"]), None),
            "bytes_fg_mb": bytes_fg / MB, "bytes_bg_mb": bg["bytes"] / MB,
            "t_sink_arrived": (bg["sink"] - t_mig) if bg["sink"] else None,
            "bound_call": bound_call, "t_end": (bg["end"] - t_mig) if bg["end"] else None,
            "refresh_calls_baseline": refresh,
        })
        results.append(rec)
        with open(out_dir / f"proto_{policy}_{int(bw)}mbps.json", "w") as fh:
            json.dump(rec, fh, indent=1)
        tf = rec["t_first_out"] if rec["t_first_out"] is not None else float("nan")
        stall = tf - service_s
        late = [x["psnr"] for x in rec["calls"] if x["rel"] >= 16 and x["psnr"] is not None]
        print(f"[dest] {policy} @ {bw:g} Mbps: first output {tf:.2f} s (stall ~{stall:.2f} s), fg {bytes_fg / MB:.1f} MB, bg {bg['bytes'] / MB:.0f} MB, "
              f"bound at call {bound_call}, PSNR M+16.. {np.mean(late) if late else float('nan'):.1f} dB", flush=True)
        del snap
        torch.cuda.empty_cache()
    send_msg(sock, "DONE", {}, b"", None)
    sock.close()
    with open(out_dir / "proto_results.json", "w") as fh:
        json.dump(results, fh, indent=1)
    print(f"[dest] done -> {out_dir}")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--role", choices=["source", "dest"], required=True)
    p.add_argument("--host", type=str, default="127.0.0.1")
    p.add_argument("--port", type=int, default=29777)
    p.add_argument("--sweep", type=str, default="ours:1000,ours_refresh:1000,full:1000,cold:1000,replay:1000", help="policy:bw_mbps,...")
    p.add_argument("--config_path", type=str, default=str(REPO_ROOT / "configs/wan_causal_dmd_v2v.yaml"))
    p.add_argument("--checkpoint_folder", type=str, default=str(REPO_ROOT / "ckpts/wan_causal_dmd_v2v"))
    p.add_argument("--prompt_file_path", type=str, default=str(REPO_ROOT / "examples/prompt.txt"))
    p.add_argument("--video_path", type=str, default=str(REPO_ROOT / "examples/original.mp4"))
    p.add_argument("--output_folder", type=str, default=str(REPO_ROOT / "results/state_migration/proto"))
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
    p.add_argument("--out_dir", type=str, default=str(REPO_ROOT / "results/state_migration/proto"))
    return p.parse_args()


if __name__ == "__main__":
    a = parse_args()
    run_source(a) if a.role == "source" else run_dest(a)
