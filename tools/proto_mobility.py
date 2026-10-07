#!/usr/bin/env python3
"""Repeated mobility A -> B -> C with a single-destination sink policy.

Independent variable: mobility interval T_m vs sink transfer time T_s (1.6 GB at --bw_mbps).
Execution moves A->B at t0 (READY) and B->C at t0 + T_m (checked at chunk boundaries). The fast
state (in-flight + metadata, ~2.7 MB) always follows execution. The 1.6 GB sink follows one policy:
    restart : stream A->B; on B->C abort it and stream A->C from the first layer (bytes to B wasted)
    relay   : stream A->B to completion, then B->C over an emulated link of the same bandwidth
    direct  : oracle; A streams the sink to C from the start, B only gets the fast state
B and C are logical edges hosted by one destination process (one GPU): B's state is serialized and
restored into freshly allocated C buffers (provisioning excluded from timing).

Usage: tools/run_mobility.sh (launches both roles). Results: results/state_migration/mobility/.
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


def unpack_sink_layer(header: dict, payload, device, buf: dict):
    from proto_handoff import bytes_to_tensor

    view = memoryview(payload)
    t = {x["name"]: bytes_to_tensor(x, view[x["offset"]:x["offset"] + x["nbytes"]], device) for x in header["tensors"]}
    buf["layers"][header["layer"]] = t


# ----------------------------------------------------------------------------- source (edge A)
def run_source(args):
    import torch

    sa, runner, pm, pl, device = build_runtime(args)
    sink, fsl = pl.num_sink_tokens, pl.frame_seq_length
    L = len(pl.kv_cache1)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.host, args.port)); srv.listen(1)
    print(f"[A] listening on {args.host}:{args.port}", flush=True)
    conn, _ = srv.accept()
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    M = args.migration_chunk

    control = {"moved": threading.Event(), "done": False, "lock": threading.Lock(), "queue": []}

    def control_reader():
        while not control["done"]:
            try:
                hdr, _ = recv_msg(conn)
            except Exception:  # noqa: BLE001
                break
            with control["lock"]:
                control["queue"].append(hdr)
            if hdr["kind"] == "MOVED":
                control["moved"].set()
            if hdr["kind"] == "DONE":
                control["done"] = True

    def wait_for(kind):
        while True:
            with control["lock"]:
                for i, h in enumerate(control["queue"]):
                    if h["kind"] == kind:
                        return control["queue"].pop(i)
            if control["done"]:
                return None
            time.sleep(0.005)

    threading.Thread(target=control_reader, daemon=True).start()

    def stream_sink(snap, dest: str, throttle: Throttle, abort: threading.Event | None):
        sent = 0
        for li in range(L):
            if abort is not None and abort.is_set():
                send_msg(conn, "SINK_ABORT", {"dest": dest, "layers_sent": li}, b"", None)
                return sent, False, li
            h, b = pack_sink_layer(snap, li, sink, fsl)
            send_msg(conn, "SINK", {"dest": dest, "n_layers": L, **h}, b, throttle)
            sent += sum(x.nbytes for x in b)
        send_msg(conn, "SINK_END", {"dest": dest, "t": time.time()}, b"", None)
        return sent, True, L

    while True:
        hdr = wait_for("PREP")
        if hdr is None:
            break
        policy, bw, tm = hdr["policy"], float(hdr["bw_mbps"]), float(hdr["t_m"])
        print(f"[A] {policy} T_m={tm:g}s @ {bw:g} Mbps: running to M={M}", flush=True)
        session = runner.start()
        for c in range(M):
            runner.step(session, c)
        torch.cuda.synchronize(device)
        snap = sa.serialize_state(pl, pm, session)
        control["moved"].clear()
        send_msg(conn, "PREPARED", {}, b"", None)
        assert wait_for("READY") is not None
        throttle = Throttle(bw * 1e6)
        for comp in ("inflight", "meta"):
            h, b = pack_component(snap, comp, sink, fsl)
            send_msg(conn, "STATE", {"dest": "B", **h}, b, throttle)
        send_msg(conn, "GO", {"t_go": time.time()}, b"", None)
        log = {"policy": policy, "bytes_AB": 0, "bytes_AC": 0, "aborted_at_layer": None}
        if policy == "restart":
            # naive: the sink always streams from the source to wherever execution currently is
            sent, done, layers = stream_sink(snap, "B", throttle, control["moved"])
            log["bytes_AB"] = sent
            if not done:
                log["aborted_at_layer"] = layers
            else:
                control["moved"].wait(timeout=120)  # execution will move at T_m; then C needs its own copy
            sent2, _, _ = stream_sink(snap, "C", throttle, None)
            log["bytes_AC"] = sent2
        elif policy == "relay":
            sent, _, _ = stream_sink(snap, "B", throttle, None)
            log["bytes_AB"] = sent
        elif policy == "direct":
            sent, _, _ = stream_sink(snap, "C", throttle, None)
            log["bytes_AC"] = sent
        send_msg(conn, "END", {"t": time.time(), **log}, b"", None)
        del snap
        torch.cuda.empty_cache()
    conn.close(); srv.close()


# ----------------------------------------------------------------------------- destination (edges B then C)
def bind_sink(pl, buf: dict, sink: int, fsl: int, device, cfg_thr: float) -> int:
    from models.wan.causal_model import _shift_temporal_rope

    freqs = pl.generator.model.freqs.to(device)
    shifted = 0
    for li, layer in enumerate(pl.kv_cache1):
        t = buf["layers"][li]
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
    L = len(pl.kv_cache1)
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
    for item in args.sweep.split(","):
        policy, tm = item.split(":"); tm = float(tm); bw = args.bw_mbps
        print(f"[dest] === {policy} T_m={tm:g}s @ {bw:g} Mbps ===", flush=True)
        send_msg(sock, "PREP", {"policy": policy, "bw_mbps": bw, "t_m": tm}, b"", None)
        hdr, _ = recv_msg(sock); assert hdr["kind"] == "PREPARED"
        session = runner.fresh_destination()
        snap = sa.serialize_state(pl, pm, session)
        for layer in snap["kv"]:
            layer["k"].zero_(); layer["v"].zero_()
        snap["have"] = set()
        torch.cuda.synchronize(device)

        rec = {"policy": policy, "t_m": tm, "bw_mbps": bw, "service_s": service_s, "events": [], "calls": [],
               "bytes": {"AB": 0, "AC": 0, "BC": 0, "fast_AB": 0, "fast_BC": 0}}
        bufs = {"B": {"layers": {}, "complete": None, "bytes": 0}, "C": {"layers": {}, "complete": None, "bytes": 0}}
        state = {"node": "B", "t_move": None, "end": None, "relay_started": False}
        lock = threading.Lock()
        t_mig = time.time()
        send_msg(sock, "READY", {}, b"", None)
        while True:
            hdr, payload = recv_msg(sock)
            if hdr["kind"] == "GO":
                break
            unpack_into_snapshot(hdr, payload, device, snap, sink, fsl)
            rec["bytes"]["fast_AB"] += len(payload)
        sa.restore_state(pl, pm, session, snap, {"meta", "inflight"})
        for block in pl.generator.model.blocks:
            block.self_attn.adapt_sink_thr = -1
        torch.cuda.synchronize(device)

        def relay_BC():
            """B forwards its complete sink to C over an emulated link of the same bandwidth."""
            nbytes = bufs["B"]["bytes"]
            t_link = nbytes * 8 / (bw * 1e6)
            rec["events"].append({"t": time.time() - t_mig, "relay_start": True, "mb": nbytes / MB, "link_s": t_link})
            time.sleep(t_link)
            with lock:
                bufs["C"]["layers"] = dict(bufs["B"]["layers"]); bufs["C"]["bytes"] = nbytes
                bufs["C"]["complete"] = time.time(); rec["bytes"]["BC"] += nbytes

        def receiver():
            while True:
                hdr, payload = recv_msg(sock)
                k = hdr["kind"]
                if k == "END":
                    state["end"] = hdr; break
                if k == "SINK":
                    dest = hdr["dest"]
                    with lock:
                        unpack_sink_layer(hdr, payload, device, bufs[dest])
                        bufs[dest]["bytes"] += len(payload); rec["bytes"]["A" + dest] += len(payload)
                elif k == "SINK_END":
                    dest = hdr["dest"]
                    with lock:
                        bufs[dest]["complete"] = time.time()
                    rec["events"].append({"t": time.time() - t_mig, "sink_complete_at": dest})
                    if policy == "relay" and dest == "B" and state["node"] == "C" and not state["relay_started"]:
                        state["relay_started"] = True
                        threading.Thread(target=relay_BC, daemon=True).start()
                elif k == "SINK_ABORT":
                    rec["events"].append({"t": time.time() - t_mig, "sink_abort": hdr["dest"], "layers_sent": hdr["layers_sent"]})

        th = threading.Thread(target=receiver, daemon=True); th.start()

        bound = {"B": None, "C": None}
        for c in range(M, M + N):
            now = time.time() - t_mig
            # ---- B -> C mobility event
            if state["node"] == "B" and now >= tm:
                fast = sa.serialize_state(pl, pm, session)
                fast_bytes = sum(x.numel() * x.element_size() for x in (fast["pipeline"]["hidden_states"][:-1], fast["session"]["last_image"]))  # in-flight + last_image; ring metadata is KB
                session = runner.fresh_destination()  # provisioning C (excluded)
                sa.restore_state(pl, pm, session, fast, {"meta", "inflight"})
                for block in pl.generator.model.blocks:
                    block.self_attn.adapt_sink_thr = -1
                torch.cuda.synchronize(device)
                del fast
                state["node"] = "C"; state["t_move"] = time.time() - t_mig
                rec["bytes"]["fast_BC"] += fast_bytes
                rec["events"].append({"t": state["t_move"], "moved": "C", "call": c, "B_bound": bound["B"] is not None,
                                      "B_sink_mb_so_far": bufs["B"]["bytes"] / MB})
                send_msg(sock, "MOVED", {"to": "C", "t": time.time()}, b"", None)
                with lock:
                    if policy == "restart":
                        bufs["B"]["layers"] = {}  # obsolete: whatever arrived is wasted
                    if policy == "relay" and bufs["B"]["complete"] is not None and not state["relay_started"]:
                        state["relay_started"] = True
                        threading.Thread(target=relay_BC, daemon=True).start()
            # ---- bind at the current node when its sink is complete
            node = state["node"]
            with lock:
                ready = bufs[node]["complete"] is not None and len(bufs[node]["layers"]) == L
            if ready and bound[node] is None:
                shifted = bind_sink(pl, bufs[node], sink, fsl, device, cfg_thr)
                bound[node] = c
                rec["events"].append({"t": time.time() - t_mig, "bound_at": node, "call": c, "slots_rerotated": shifted})
            fr = runner.step(session, c)
            torch.cuda.synchronize(device)
            ref = baseline.get(c)
            ps = float(np.mean([sa.psnr(ref[f].astype(np.float32) / 255.0, fr[f].astype(np.float32) / 255.0) for f in range(min(ref.shape[0], fr.shape[0]))])) if (fr is not None and ref is not None) else None
            rec["calls"].append({"call": c, "rel": c - M, "t_out": time.time() - t_mig, "node": node, "psnr": ps, "missing": fr is None})
        th.join(timeout=900)
        rec.update({"t_move": state["t_move"], "bound_call": bound, "source_log": state["end"],
                    "t_ready_B": next((e["t"] for e in rec["events"] if e.get("bound_at") == "B"), None),
                    "t_ready_C": next((e["t"] for e in rec["events"] if e.get("bound_at") == "C"), None),
                    "wasted_mb": (bufs["B"]["bytes"] / MB if (policy == "restart") else 0.0) if state["t_move"] is not None else 0.0,
                    "total_mb": sum(rec["bytes"].values()) / MB})
        results.append(rec)
        with open(out_dir / f"mob_{policy}_tm{tm:g}.json", "w") as fh:
            json.dump(rec, fh, indent=1)
        trc = rec["t_ready_C"]
        print(f"[dest] {policy} T_m={tm:g}: moved at {state['t_move']:.1f}s, ready_B {rec['t_ready_B']}, ready_C {trc}, "
              f"bytes {{AB {rec['bytes']['AB'] / MB:.0f}, AC {rec['bytes']['AC'] / MB:.0f}, BC {rec['bytes']['BC'] / MB:.0f}}} MB, wasted {rec['wasted_mb']:.0f} MB", flush=True)
        del snap, bufs
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
    p.add_argument("--sweep", type=str, default="restart:1,restart:2,restart:4,restart:8,restart:16,relay:1,relay:2,relay:4,relay:8,relay:16,direct:1,direct:2,direct:4,direct:8,direct:16",
                   help="policy:T_m_seconds,...")
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
    p.add_argument("--post_chunks", type=int, default=90)
    p.add_argument("--out_dir", type=str, default=str(REPO_ROOT / "results/state_migration/mobility"))
    return p.parse_args()


if __name__ == "__main__":
    a = parse_args()
    run_source(a) if a.role == "source" else run_dest(a)
