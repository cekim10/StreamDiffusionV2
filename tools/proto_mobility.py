#!/usr/bin/env python3
"""Repeated mobility A -> B -> C (-> D ...) with per-segment continuity-state routing.

Execution moves A->B at t0 (READY) and then to the next edge every T_m seconds (checked at chunk
boundaries). The fast state (in-flight row + metadata, ~2.7 MB) always follows execution. The sink
(1.6 GB) is streamed as 30 per-layer segments and routed by policy:
    restart    : A streams to the current edge; on a move, abort and restart from segment 0 to the new edge
    relay      : A streams to B to completion; an edge forwards the sink to the current edge only once it
                 holds all segments (store-and-forward, T_ready(final) ~ n * T_s)
    relay_pipe : like relay but an edge forwards each segment as soon as it holds it (pipelined chain)
    split      : progress-preserving: on a move the old edge forwards the segments it already holds to the
                 new edge while A sends only the not-yet-delivered segments directly to the new edge
    direct     : oracle: A streams to the final edge from the start
Only the A->edge link is a real throttled TCP stream; edge->edge forwarding is emulated inside the
destination process with the same per-link bandwidth (sleep per segment). Each link is independent, so
two links into one edge (split) give it 2x ingress: the favorable case for split, stated in the output.
B, C, D are logical edges hosted by one destination process (one GPU); each move serializes the fast
state and restores it into freshly allocated buffers (provisioning excluded from timing).

Sweep items: policy:T_m[:hops]  (hops = number of edges after A; default 2 -> A->B->C).
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for p in (REPO_ROOT, REPO_ROOT / "tools"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np  # noqa: E402

from proto_handoff import MB, Throttle, build_runtime, pack_component, recv_msg, send_msg, tensor_to_bytes, unpack_into_snapshot  # noqa: E402
from sink_router import EDGE_NAMES, POLICIES, SinkRouter  # noqa: E402


# ----------------------------------------------------------------------------- per-layer sink framing
def pack_sink_layer(snap: dict, li: int, sink: int, fsl: int):
    layer = snap["kv"][li]
    mk, bk = tensor_to_bytes(layer["k"][:, :sink * fsl])
    mv, bv = tensor_to_bytes(layer["v"][:, :sink * fsl])
    mp, bp = tensor_to_bytes(snap["ring"][li]["pos"][:, :sink])
    header = {"layer": li, "tensors": [
        {"name": "k", "offset": 0, "nbytes": bk.nbytes, **mk},
        {"name": "v", "offset": bk.nbytes, "nbytes": bv.nbytes, **mv},
        {"name": "pos", "offset": bk.nbytes + bv.nbytes, "nbytes": bp.nbytes, **mp},
    ]}
    return header, [bk, bv, bp]


def unpack_sink_layer(header: dict, payload, device) -> dict:
    from proto_handoff import bytes_to_tensor

    view = memoryview(payload)
    return {x["name"]: bytes_to_tensor(x, view[x["offset"]:x["offset"] + x["nbytes"]], device) for x in header["tensors"]}


def parse_sweep(s: str):
    """policy:T_m[:hops[:ingress]] ; ingress = k (shared receive capacity k x link) or 'u' (unlimited, default)."""
    out = []
    for item in s.split(","):
        parts = item.split(":")
        hops = int(parts[2]) if len(parts) > 2 else 2
        ing = None if len(parts) < 4 or parts[3] in ("u", "unlim", "") else float(parts[3])
        out.append((parts[0], float(parts[1]), hops, ing))
    return out


# ----------------------------------------------------------------------------- source (edge A)
def run_source(args):
    import torch

    sa, runner, pm, pl, device = build_runtime(args)
    sink, fsl = pl.num_sink_tokens, pl.frame_seq_length
    L = int(pl.num_transformer_blocks)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.host, args.port)); srv.listen(1)
    print(f"[A] listening on {args.host}:{args.port}", flush=True)
    conn, _ = srv.accept()
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    M = args.migration_chunk

    ctl = {"lock": threading.Lock(), "queue": [], "done": False, "cur": "B", "moved": threading.Event()}

    def control_reader():
        while not ctl["done"]:
            try:
                hdr, _ = recv_msg(conn)
            except Exception:  # noqa: BLE001
                break
            if hdr["kind"] == "MOVED":
                ctl["cur"] = hdr["to"]; ctl["moved"].set()
            with ctl["lock"]:
                ctl["queue"].append(hdr)
            if hdr["kind"] == "DONE":
                ctl["done"] = True

    def wait_for(kind):
        while True:
            with ctl["lock"]:
                for i, h in enumerate(ctl["queue"]):
                    if h["kind"] == kind:
                        return ctl["queue"].pop(i)
            if ctl["done"]:
                return None
            time.sleep(0.005)

    threading.Thread(target=control_reader, daemon=True).start()

    def send_layer(snap, li, dest, throttle):
        h, b = pack_sink_layer(snap, li, sink, fsl)
        send_msg(conn, "SINK", {"dest": dest, "n_layers": L, **h}, b, throttle)
        return sum(x.nbytes for x in b)

    while True:
        hdr = wait_for("PREP")
        if hdr is None:
            break
        policy, tm, hops, bw = hdr["policy"], float(hdr["t_m"]), int(hdr["hops"]), float(hdr["bw_mbps"])
        final_edge = EDGE_NAMES[hops]
        print(f"[A] {policy} T_m={tm:g}s hops={hops} ingress={hdr.get('ingress')} @ {bw:g} Mbps: running to M={M}", flush=True)
        session = runner.start()
        for c in range(M):
            runner.step(session, c)
        torch.cuda.synchronize(device)
        snap = sa.serialize_state(pl, pm, session)
        ctl["cur"] = "B"; ctl["moved"].clear()
        send_msg(conn, "PREPARED", {}, b"", None)
        assert wait_for("READY") is not None
        throttle = Throttle(bw * 1e6)
        for comp in ("inflight", "meta"):
            h, b = pack_component(snap, comp, sink, fsl)
            send_msg(conn, "STATE", {"dest": "B", **h}, b, throttle)
        send_msg(conn, "GO", {"t_go": time.time()}, b"", None)
        log = {"policy": policy, "bytes_by_dest": {}, "events": []}

        def account(dest, n):
            log["bytes_by_dest"][dest] = log["bytes_by_dest"].get(dest, 0) + n

        if policy == "direct":
            for li in range(L):
                account(final_edge, send_layer(snap, li, final_edge, throttle))
        elif policy in ("relay", "relay_pipe"):
            for li in range(L):
                account("B", send_layer(snap, li, "B", throttle))
        elif policy == "restart":
            # the sink follows execution from the source; every move restarts from segment 0
            while True:
                dest = ctl["cur"]; ctl["moved"].clear()
                li = 0
                aborted = False
                while li < L:
                    if ctl["moved"].is_set():
                        aborted = True; break
                    account(dest, send_layer(snap, li, dest, throttle)); li += 1
                log["events"].append({"streamed_to": dest, "aborted_at_layer": li if aborted else None})
                if aborted:
                    continue
                if dest == final_edge:
                    break
                ctl["moved"].wait(timeout=300)  # execution will move again; then resend from scratch
                if ctl["cur"] == dest:
                    break
        elif policy == "split":
            # progress-preserving: never resend a segment that has already left A; just retarget the rest
            li = 0
            while li < L:
                dest = ctl["cur"]; ctl["moved"].clear()
                account(dest, send_layer(snap, li, dest, throttle)); li += 1
                if ctl["moved"].is_set():
                    log["events"].append({"retargeted_to": ctl["cur"], "next_layer": li})
        send_msg(conn, "END", {"t": time.time(), **log}, b"", None)
        del snap
        torch.cuda.empty_cache()
    conn.close(); srv.close()


# ----------------------------------------------------------------------------- destination (edges B, C, D, ...)
def bind_sink(pl, layers: dict, sink: int, fsl: int, device, cfg_thr: float) -> int:
    from models.wan.causal_model import _shift_temporal_rope

    freqs = pl.generator.model.freqs.to(device)
    shifted = 0
    for li, layer in enumerate(pl.kv_cache1):
        t = layers[li]
        for b in range(t["k"].shape[0]):
            for sidx in range(sink):
                lo, hi = sidx * fsl, (sidx + 1) * fsl
                kk = t["k"][b, lo:hi]
                delta = int(layer["pos"][b, sidx].item() - t["pos"][b, sidx].item())
                if delta != 0:
                    kk = _shift_temporal_rope(kk, freqs, delta); shifted += 1
                layer["k"][b, lo:hi] = kk
                layer["v"][b, lo:hi] = t["v"][b, lo:hi]
    for block in pl.generator.model.blocks:
        block.self_attn.adapt_sink_thr = cfg_thr
    return shifted


def run_dest(args):
    import torch

    sa, runner, pm, pl, device = build_runtime(args)
    sink, fsl = pl.num_sink_tokens, pl.frame_seq_length
    L = int(pl.num_transformer_blocks)
    M, N = args.migration_chunk, args.post_chunks
    out_dir = Path(args.out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    cfg_thr = float(getattr(pm.config, "adapt_sink_threshold", -1))

    print("[dest] baseline run", flush=True)
    session = runner.start()
    baseline, times = {}, []
    for c in range(M + N):
        t0 = time.perf_counter(); fr = runner.step(session, c); torch.cuda.synchronize(device); times.append(time.perf_counter() - t0)
        if fr is not None:
            baseline[c] = fr
        runner.noise_hist[c] = float(session.noise_scale)
    service_s = float(np.median(times[M:]))
    print(f"[dest] baseline done; S = {service_s * 1e3:.0f} ms", flush=True)

    sock = socket.create_connection((args.host, args.port))
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    results = []
    for policy, tm, hops, ingress in parse_sweep(args.sweep):
        bw = args.bw_mbps
        edges = [EDGE_NAMES[i] for i in range(1, hops + 1)]  # B, C, ...
        final_edge = edges[-1]
        print(f"[dest] === {policy} T_m={tm:g}s hops={hops} ingress={ingress or 'unlimited'} ({'->'.join(['A'] + edges)}) @ {bw:g} Mbps ===", flush=True)
        send_msg(sock, "PREP", {"policy": policy, "bw_mbps": bw, "t_m": tm, "hops": hops, "ingress": ingress}, b"", None)
        hdr, _ = recv_msg(sock); assert hdr["kind"] == "PREPARED"
        session = runner.fresh_destination()
        snap = sa.serialize_state(pl, pm, session)
        snap["have"] = set()
        torch.cuda.synchronize(device)

        rec = {"policy": policy, "t_m": tm, "hops": hops, "ingress_mult": ingress, "bw_mbps": bw, "service_s": service_s, "edges": edges,
               "events": [], "calls": [], "bytes": {"fast": 0}, "ready": {}, "moves": []}
        seg: dict[int, dict] = {}  # segment -> tensors (content identical wherever it is held)
        state = {"end": None}
        bound: dict[str, int] = {}
        t_mig = time.time()
        # validated routing model (tools/test_sink_router.py); forwarders sleep the emulated link time per segment
        seg_estimate = len(pl.denoising_step_list) * sink * fsl * pl.num_heads * 128 * 2 * 2  # k+v, bf16, all rows
        router = SinkRouter(policy, edges, L, seg_estimate, bw * 1e6, ingress_mult=ingress)
        send_msg(sock, "READY", {}, b"", None)
        while True:
            hdr, payload = recv_msg(sock)
            if hdr["kind"] == "GO":
                break
            unpack_into_snapshot(hdr, payload, device, snap, sink, fsl)
            rec["bytes"]["fast"] += len(payload)
        sa.restore_state(pl, pm, session, snap, {"meta", "inflight"})
        for block in pl.generator.model.blocks:
            block.self_attn.adapt_sink_thr = -1
        torch.cuda.synchronize(device)
        router.start()

        def receiver():
            while True:
                hdr, payload = recv_msg(sock)
                k = hdr["kind"]
                if k == "END":
                    state["end"] = hdr; break
                if k == "SINK":
                    # shared ingress: pace the source's flow through the target edge's capacity before it counts
                    # as delivered (the kernel buffer fills and TCP backpressure slows the sender accordingly)
                    router.source_take(hdr["dest"], len(payload))
                    seg[hdr["layer"]] = unpack_sink_layer(hdr, payload, device)
                    router.seg_bytes = len(payload)
                    router.deliver(hdr["dest"], hdr["layer"], len(payload))

        threading.Thread(target=receiver, daemon=True).start()

        for c in range(M, M + N):
            now = time.time() - t_mig
            # ---- mobility event: move to the next edge every T_m
            if router.idx < hops - 1 and now >= tm * (router.idx + 1):
                fast = sa.serialize_state(pl, pm, session)
                fast_bytes = sum(x.numel() * x.element_size() for x in (fast["pipeline"]["hidden_states"][:-1], fast["session"]["last_image"]))
                session = runner.fresh_destination()  # provisioning the next edge (excluded)
                sa.restore_state(pl, pm, session, fast, {"meta", "inflight"})
                for block in pl.generator.model.blocks:
                    block.self_attn.adapt_sink_thr = -1
                torch.cuda.synchronize(device)
                del fast
                with router.lock:
                    held_old = len(router.holders[router.node])
                old, new = router.move()
                rec["bytes"]["fast"] += fast_bytes
                rec["moves"].append({"t": time.time() - t_mig, "from": old, "to": new, "call": c,
                                     "old_held_segments": held_old, "old_bound": old in bound})
                send_msg(sock, "MOVED", {"to": new, "t": time.time()}, b"", None)
            node = router.node
            if node not in bound and router.ready(node):
                with router.lock:
                    layers = {li: seg[li] for li in router.holders[node]}
                shifted = bind_sink(pl, layers, sink, fsl, device, cfg_thr)
                bound[node] = c
                rec["ready"][node] = time.time() - t_mig
                rec["events"].append({"t": rec["ready"][node], "bound_at": node, "call": c, "slots_rerotated": shifted})
            fr = runner.step(session, c)
            torch.cuda.synchronize(device)
            ref = baseline.get(c)
            ps = float(np.mean([sa.psnr(ref[f].astype(np.float32) / 255.0, fr[f].astype(np.float32) / 255.0) for f in range(min(ref.shape[0], fr.shape[0]))])) if (fr is not None and ref is not None) else None
            bound_idx = max([edges.index(e) + 1 for e in bound] + [0])  # A = 0
            rec["calls"].append({"call": c, "rel": c - M, "t_out": time.time() - t_mig, "node": node, "psnr": ps,
                                 "missing": fr is None, "lag": (edges.index(node) + 1) - bound_idx})
        for _ in range(3000):  # the source may still be streaming (restart); wait for its END
            if state["end"] is not None:
                break
            time.sleep(0.1)
        router.finish()
        with router.lock:
            held = {e: len(router.holders[e]) for e in edges}
        rec["bytes"].update(router.bytes)
        src_by_dest = (state["end"] or {}).get("bytes_by_dest")
        rec.update({"t_ready_final": rec["ready"].get(final_edge), "bound_call": bound, "held_at_end": held,
                    "wasted_mb": router.wasted_bytes(final_edge, src_by_dest) / MB, "total_mb": sum(rec["bytes"].values()) / MB,
                    "source_log": state["end"],
                    "lag_mean": float(np.mean([x["lag"] for x in rec["calls"]])), "lag_max": int(max(x["lag"] for x in rec["calls"]))})
        results.append(rec)
        with open(out_dir / f"mob_{policy}_tm{tm:g}_h{hops}_i{ingress or 'u'}.json", "w") as fh:
            json.dump(rec, fh, indent=1)
        print(f"[dest] {policy} T_m={tm:g} hops={hops}: ready {rec['ready']}, bytes {{{', '.join(f'{k2} {v / MB:.0f}' for k2, v in rec['bytes'].items())}}} MB, "
              f"wasted {rec['wasted_mb']:.0f} MB, lag mean {rec['lag_mean']:.2f} max {rec['lag_max']}", flush=True)
        del snap, seg
        torch.cuda.empty_cache()
    send_msg(sock, "DONE", {}, b"", None)
    sock.close()
    with open(out_dir / "mobility_results.json", "w") as fh:
        json.dump(results, fh, indent=1)
    print(f"[dest] done -> {out_dir}")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--role", choices=["source", "dest"], required=True)
    p.add_argument("--host", type=str, default="127.0.0.1")
    p.add_argument("--port", type=int, default=29778)
    p.add_argument("--sweep", type=str, default="restart:2:3,relay:2:3,relay_pipe:2:3,split:2:3,direct:2:3", help="policy:T_m[:hops[:ingress]],... (ingress k = k x link shared receive capacity, u = unlimited)")
    p.add_argument("--bw_mbps", type=float, default=1000.0)
    p.add_argument("--config_path", type=str, default=str(REPO_ROOT / "configs/wan_causal_dmd_v2v.yaml"))
    p.add_argument("--checkpoint_folder", type=str, default=str(REPO_ROOT / "ckpts/wan_causal_dmd_v2v"))
    p.add_argument("--prompt_file_path", type=str, default=str(REPO_ROOT / "examples/prompt.txt"))
    p.add_argument("--video_path", type=str, default=str(REPO_ROOT / "examples/original.mp4"))
    p.add_argument("--output_folder", type=str, default=str(REPO_ROOT / "results/state_migration/mobility"))
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
    p.add_argument("--post_chunks", type=int, default=130)
    p.add_argument("--out_dir", type=str, default=str(REPO_ROOT / "results/state_migration/mobility"))
    return p.parse_args()


if __name__ == "__main__":
    a = parse_args()
    assert all(item.split(":")[0] in POLICIES for item in a.sweep.split(",")), f"policies must be in {POLICIES}"
    run_source(a) if a.role == "source" else run_dest(a)
