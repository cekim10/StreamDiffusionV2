#!/usr/bin/env python3
"""LongLive live migration between two hosts (osdi/longlive/snapshot_prereg.md): exact window snapshot + catch-up
replay vs Full stop-and-copy. One session, one migration at call M, application-level shaping (tools/eval/common
Throttle) on the source -> destination link.

  snap   at M the source copies sink + window K / V (+ counters) to host memory and keeps serving; the snapshot and then
         every later call's output latents (the replay log) go to the destination. The destination imports the snapshot
         (cross-attention recomputed from the prompt), replays the log teacher-forced (context pass only; the VAE decoder
         is rebuilt from the last K_v logged blocks once the replay has caught up, while the source still serves), asks to
         switch when its backlog is <= 1 call again; the source stops after its current call, the destination replays
         the rest and generates the next call.
  full   at M the source stops and sends the whole state (sink, window, cross-attention, VAE cache, latent buffer); the
         destination imports it and generates call M.
  replay M1 (Continuity Replay) on LongLive (osdi/longlive/m1_prereg.md): the source sends the sink at M and keeps
         serving; the destination starts from the sink positioned at M - W and replays the logged calls M - W, ... (the
         W pre-trigger blocks, then every call the source serves) teacher-forced, context pass only, rebuilds the VAE
         decoder from the last K_v logged blocks once caught up, and switches as snap does. LongLive's sink is written by
         call 0 only, so it needs no synchronisation after M.
  recache LongLive-native: the source sends the sink at M and keeps serving; the destination asks to switch at once;
         at the switch the source sends its counters and latent buffer, the destination runs LongLive's KV recache and
         warms the VAE on the last block, then generates.

After the cutover the source keeps generating V calls in shadow (no output) and sends their latent and frame digests;
the destination compares its own (bit-exactness after the cutover). The source also sends a state fingerprint at the
switch call. Times on the destination's clock (offset from a ping exchange). The destination writes the JSON.

    dst host:  python tools/longlive/ll_migrate.py dst --port 29951 --method snap --out results/.../snap_p0_s0_r1.json
    src host:  python tools/longlive/ll_migrate.py src --peer elves-02:29951 --method snap --prompt_idx 0 --seed 0
"""

from __future__ import annotations

import argparse
import json
import queue
import socket
import statistics as st
import struct
import sys
import threading
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
import ll_runtime as llr  # noqa: E402
from common import Throttle  # noqa: E402

SNAP = ["sink_kv", "window_kv"]
SHIP = {"snap": SNAP, "replay": ["sink_kv"], "recache": ["sink_kv"]}   # full: FULL
LIVE = ("snap", "replay", "recache")   # the source keeps serving until the destination asks to switch
FULL = ["sink_kv", "window_kv", "crossattn_kv", "vae_decoder_cache", "latent_buffer"]
DT = {str(d): d for d in (torch.bfloat16, torch.float16, torch.float32, torch.int64, torch.uint8)}


# ------------------------------------------------------------------ framing: [8-byte header length][JSON header][payload]
def send_msg(sock, lock, kind, meta=None, payload=b"", throttle=None, chunk=1 << 20):
    h = json.dumps({"kind": kind, "n": len(payload), **(meta or {})}).encode()
    with lock:
        sock.sendall(struct.pack("!Q", len(h)) + h)
        mv = memoryview(payload)
        for i in range(0, len(mv), chunk):
            if throttle is not None:
                throttle.take(min(chunk, len(mv) - i))
            sock.sendall(mv[i:i + chunk])


def recv_exact(sock, n):
    buf = bytearray(n)
    mv, got = memoryview(buf), 0
    while got < n:
        k = sock.recv_into(mv[got:], min(n - got, 1 << 22))
        if k == 0:
            raise ConnectionError("peer closed")
        got += k
    return buf


def recv_msg(sock):
    (hl,) = struct.unpack("!Q", recv_exact(sock, 8))
    h = json.loads(bytes(recv_exact(sock, hl)))
    return h, (recv_exact(sock, h["n"]) if h["n"] else b"")


def tensor_bytes(t: torch.Tensor):
    return t.contiguous().view(-1).view(torch.uint8).numpy()


def from_bytes(buf, dtype, shape):
    return torch.frombuffer(buf, dtype=torch.uint8).view(DT[dtype]).reshape(shape)


class Sender(threading.Thread):
    """Source -> destination: every queued message goes through one token bucket (the migration link)."""

    def __init__(self, sock, bw_bps, burst_bytes=1 << 20):
        super().__init__(daemon=True)
        self.sock, self.lock, self.q = sock, threading.Lock(), queue.Queue()
        self.throttle = Throttle(bw_bps, burst_bytes) if bw_bps > 0 else None
        self.chunk = min(1 << 20, burst_bytes)
        self.sent_bytes, self.t_marks, self.byte_marks = 0, {}, {}

    def put(self, kind, meta=None, payload=b"", mark=None):
        self.q.put((kind, meta, payload, mark))

    def run(self):
        while True:
            kind, meta, payload, mark = self.q.get()
            if kind is None:
                return
            send_msg(self.sock, self.lock, kind, meta, payload, self.throttle, self.chunk)
            self.sent_bytes += len(payload)
            if mark:
                self.t_marks[mark] = time.time()
                self.byte_marks[mark] = self.sent_bytes


def queue_state(snd: Sender, snap: dict, kind: str):
    """Snapshot as one META message (counters, tensor list) followed by one TENSOR message per tensor."""
    ents = []
    for name, ts in snap["tensors"].items():
        for i, t in enumerate(ts):
            ents.append({"name": name, "i": i, "dtype": str(t.dtype), "shape": list(t.shape)} if torch.is_tensor(t)
                        else {"name": name, "i": i, "value": t})
    snd.put(kind, {"counters": snap["counters"], "entries": ents})
    last = None
    for name, ts in snap["tensors"].items():
        for i, t in enumerate(ts):
            if torch.is_tensor(t):
                last = (name, i)
                snd.put("TENSOR", {"name": name, "i": i}, tensor_bytes(t))
    snd.put("STATE_END", {}, mark=f"{kind.lower()}_sent")
    return last


def model_for(a):
    if a.tiny:
        import test_ll_runtime as T
        return T.tiny_model()
    return llr.load_model(a.config, "cuda", a.ckpt_dir)


def frame_digest(fr):
    return llr.digest(fr) if fr is not None else None


# ------------------------------------------------------------------ source
def source(a, model):
    host, port = a.peer.rsplit(":", 1)
    t_end = time.time() + 300
    while True:
        try:
            sock = socket.create_connection((host, int(port)), timeout=10); break
        except OSError:
            if time.time() > t_end:
                raise
            time.sleep(1)
    sock.settimeout(None)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    lock = threading.Lock()
    for _ in range(a.pings):   # clock: answer the destination's pings
        h, _ = recv_msg(sock)
        send_msg(sock, lock, "PONG", {"t_dst": h["t_dst"], "t_src": time.time()})
    snd = Sender(sock, a.bw_mbps * 1e6, a.burst_bytes)
    snd.lock = lock
    snd.start()
    ctl = queue.Queue()

    def ctl_recv():
        try:
            while True:
                h, _ = recv_msg(sock)
                ctl.put(h)
        except (ConnectionError, OSError):
            return
    threading.Thread(target=ctl_recv, daemon=True).start()

    s = llr.LLSession(model, [a.prompt], seed=a.seed).start()
    calls = []

    def step():
        o = s.step()
        model.sync()
        t = time.time()
        calls.append({"call": o["call"], "t_done": t, "t_gen_s": o["t_gen_s"], "t_dec_s": o["t_dec_s"]})
        return o, t

    # the last pre-trigger output latents the destination needs: K_v (VAE rebuild); replay: max(W, K_v) (replay start)
    npre = {"snap": a.k_vae, "replay": max(a.replay_w, a.k_vae)}.get(a.method, 0)
    pre = {}
    while s.call < a.at:
        o, _ = step()
        if npre:
            pre[o["call"]] = o["latents"].cpu()
            pre.pop(o["call"] - npre, None)
    t_trigger = time.time()
    t_last = calls[-1]["t_done"]
    t0 = time.time()
    snap = s.export_state(SHIP.get(a.method, FULL))
    stall_s = time.time() - t0
    queue_state(snd, snap, "STATE")
    del snap
    for c in sorted(pre):
        snd.put("LOG", {"call": c, "pre": True}, tensor_bytes(pre[c]))
    if a.method in LIVE:
        switch = None
        while switch is None:
            try:
                h = ctl.get_nowait()
                if h["kind"] == "SWITCH_REQ":
                    switch = h
                    break
            except queue.Empty:
                pass
            o, t = step()
            t_last = t
            snd.put("LOG", {"call": o["call"], "t_done": t, "src_next": s.call},
                    tensor_bytes(o["latents"].cpu()) if a.method != "recache" else b"")
    s_call = s.call
    if a.method == "recache":   # what LongLive's recache needs at the switch call: counters and the latent buffer
        queue_state(snd, s.export_state(["latent_buffer"]), "STOPSTATE")
    snd.put("STOP", {"s": s_call, "t_last_frame": t_last, "t_trigger": t_trigger}, mark="stop_sent")
    snd.put("STATE_FP", {"fp": s.fingerprint()})
    for v in range(a.verify):   # shadow: the source's continuation, never served; its frames for the per-call PSNR
        o = s.step()
        fr = o["frames"].cpu()
        snd.put("SHADOW", {"call": o["call"], "lat": llr.digest(o["latents"]), "frm": frame_digest(o["frames"]),
                           "n_frames": int(fr.shape[0]), "shape": list(fr.shape)}, tensor_bytes(fr))
    snd.put("DONE", {"calls": calls, "stall_export_s": stall_s, "t_marks": snd.t_marks, "byte_marks": snd.byte_marks,
                     "env": env(a), "sent_bytes_before_done": snd.sent_bytes})
    snd.put(None)
    snd.join()
    while True:   # the destination's BYE (read by ctl_recv: one reader per socket)
        try:
            if ctl.get(timeout=600)["kind"] == "BYE":
                break
        except queue.Empty:
            break
    sock.close()


# ------------------------------------------------------------------ destination
def destination(a, model):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", a.port)); srv.listen(1)
    sock, peer = srv.accept()
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    lock = threading.Lock()
    best = None
    for _ in range(a.pings):
        t1 = time.time()
        send_msg(sock, lock, "PING", {"t_dst": t1})
        h, _ = recv_msg(sock)
        t2 = time.time()
        if best is None or t2 - t1 < best[0]:
            best = (t2 - t1, h["t_src"] - (t1 + t2) / 2)
    rtt, off = best   # src clock = dst clock + off

    def to_dst(t_src):
        return t_src - off

    inbox = queue.Queue()

    def recv_loop():
        st_meta, tensors = None, {}
        try:
            while True:
                h, payload = recv_msg(sock)
                k = h["kind"]
                if k in ("STATE", "STOPSTATE"):
                    st_meta = h
                    tensors = {}
                elif k == "TENSOR":
                    e = next(x for x in st_meta["entries"] if x["name"] == h["name"] and x["i"] == h["i"])
                    tensors[(h["name"], h["i"])] = from_bytes(payload, e["dtype"], e["shape"])
                elif k == "STATE_END":
                    out = {}
                    for e in st_meta["entries"]:
                        out.setdefault(e["name"], []).append(tensors.get((e["name"], e["i"]), e.get("value")))
                    inbox.put(({"kind": st_meta["kind"], "t": time.time()}, {"counters": st_meta["counters"], "tensors": out}))
                elif k == "LOG":
                    inbox.put((dict(h, t=time.time()), from_bytes(payload, "torch.bfloat16", [1, model.F, *model.latent]).clone()
                               if h["n"] else None))
                elif k == "SHADOW" and h["n"]:
                    inbox.put((dict(h, t=time.time()), from_bytes(payload, "torch.uint8", h["shape"]).clone()))
                else:
                    inbox.put((dict(h, t=time.time()), None))
                    if k == "DONE":
                        return
        except (ConnectionError, OSError) as exc:
            inbox.put(({"kind": "ERROR", "err": repr(exc), "t": time.time()}, None))

    threading.Thread(target=recv_loop, daemon=True).start()
    ev, logs, shadow, stop, fp_src, done, shadow_frames, stopstate = {}, {}, {}, None, None, None, {}, [None]
    latest_next = None

    def pump(block=True):
        nonlocal stop, fp_src, done, latest_next
        try:
            h, x = inbox.get(block=block, timeout=600 if block else None)
        except queue.Empty:
            return None
        k = h["kind"]
        if k == "STOPSTATE":
            stopstate[0] = x
        elif k == "LOG":
            if x is not None:
                logs[h["call"]] = x
            if not h.get("pre"):
                latest_next = h["src_next"]
                ev.setdefault("first_log_t", h["t"])
        elif k == "STOP":
            stop = h
        elif k == "STATE_FP":
            fp_src = h["fp"]
        elif k == "SHADOW":
            shadow[h["call"]] = h
            if x is not None:
                shadow_frames[h["call"]] = x
        elif k == "DONE":
            done = h
        elif k == "ERROR":
            raise RuntimeError(h["err"])
        return h, x

    while True:   # the state
        r = pump()
        if r and r[0]["kind"] == "STATE":
            ev["state_recv_t"], snapshot = r[0]["t"], r[1]
            break
    t0 = time.time()
    s = llr.LLSession(model, [a.prompt], seed=a.seed).start()
    M = snapshot["counters"]["call"]
    if a.method == "replay":   # the sink positioned at M - W: empty window, cold VAE, cross-attention from the prompt
        s.from_sink(snapshot["tensors"]["sink_kv"], call=M - a.replay_w)
    elif a.method != "recache":
        s.import_state(snapshot)
    if a.method == "snap":
        s.reset_crossattn()
    model.sync()
    ev["import_s"] = time.time() - t0
    replay_log, vae_ready, decoded, switch_sent = [], False, 0, False
    if a.method in ("snap", "replay"):
        # 1. replay the log context-only (no decode) until the backlog is <= 1 call; 2. rebuild the VAE decoder from the
        # last k_vae logged blocks (pre-trigger + replayed) while the source still serves; 3. replay the calls made
        # meanwhile with decode (the decoder stays in step); 4. caught up again: ask to switch. The decoder rebuild is
        # thus never inside the delivery gap.
        while True:
            while True:   # drain without blocking
                if pump(block=False) is None:
                    break
            nxt = s.call
            caught_up = latest_next is not None and latest_next - nxt <= 1
            if not switch_sent and time.time() - ev["state_recv_t"] > a.max_catchup_s:   # not converging: switch anyway
                send_msg(sock, lock, "SWITCH_REQ", {"at_call": nxt, "t": time.time(), "forced": True})
                switch_sent, ev["switch_req_t"], ev["switch_forced"] = True, time.time(), True
                if not vae_ready:   # rebuild the decoder now; the remaining calls are replayed with decode
                    caught_up = True
            if caught_up and not vae_ready:
                blocks = [logs[c] for c in range(max(0, nxt - a.k_vae), nxt) if c in logs]
                t1 = time.time()
                s.warm_decoder_from(blocks)
                model.sync()
                ev["vae_rebuild_s"], ev["vae_rebuild_blocks"], vae_ready = time.time() - t1, len(blocks), True
                continue
            if nxt in logs:
                t1 = time.time()
                s.replay([logs[nxt]], decode=vae_ready)
                model.sync()
                decoded += int(vae_ready)
                replay_log.append({"call": nxt, "t": time.time(), "dt_s": time.time() - t1, "decoded": vae_ready,
                                   "backlog": None if latest_next is None else latest_next - s.call})
                continue
            if stop is not None and s.call >= stop["s"]:
                break
            if vae_ready and caught_up and not switch_sent:
                send_msg(sock, lock, "SWITCH_REQ", {"at_call": s.call, "t": time.time(), "forced": False})
                switch_sent, ev["switch_req_t"], ev["switch_forced"] = True, time.time(), False
            pump(block=True)
    elif a.method == "recache":
        send_msg(sock, lock, "SWITCH_REQ", {"at_call": M, "t": time.time(), "forced": False})
        ev["switch_req_t"], ev["switch_forced"] = time.time(), False
        while stop is None or stopstate[0] is None:
            pump()
        t1 = time.time()
        st2 = stopstate[0]
        s.import_state({"counters": st2["counters"], "tensors": {"sink_kv": snapshot["tensors"]["sink_kv"],
                                                                 "latent_buffer": st2["tensors"]["latent_buffer"]}})
        s.recache(); s.warm_decoder()
        model.sync()
        ev["recache_s"] = time.time() - t1
    else:
        while stop is None:
            pump()
    model.sync()
    ev["ready_t"] = time.time()   # the state at the switch call is complete on the destination
    fp_dst = s.fingerprint()
    outs = []
    first_frames, dest_frames = None, {}
    for v in range(a.verify):   # call s .. s + verify - 1, the calls the source ran in shadow
        o = s.step()
        model.sync()
        dest_frames[o["call"]] = o["frames"].cpu()
        if v == 0:
            first_frames = dest_frames[o["call"]]
        outs.append({"call": o["call"], "t_done": time.time(), "lat": llr.digest(o["latents"]), "frm": frame_digest(o["frames"]),
                     "n_frames": int(o["frames"].shape[0])})
    while done is None:
        pump()
    send_msg(sock, lock, "BYE")
    while fp_src is None:
        pump()
    t_trigger = to_dst(stop["t_trigger"])
    first = outs[0]
    cmp = [{"call": o["call"], "lat_equal": shadow.get(o["call"], {}).get("lat") == o["lat"],
            "frm_equal": shadow.get(o["call"], {}).get("frm") == o["frm"], "n_frames": o["n_frames"]} for o in outs]
    src_calls = done["calls"]
    before = [c["t_done"] for c in src_calls if c["call"] < a.at][-21:]
    iv_before = st.median([y - x for x, y in zip(before, before[1:])])
    t_state_sent = done["t_marks"].get("state_sent")
    during = [c["t_done"] for c in src_calls if c["call"] >= a.at and (t_state_sent is None or c["t_done"] <= t_state_sent)]
    iv_during = st.median([y - x for x, y in zip(during, during[1:])]) if len(during) > 2 else None
    import ll_gate
    sf = shadow_frames.get(first["call"])
    first_psnr = ll_gate.psnr(first_frames, sf) if sf is not None and sf.shape == first_frames.shape else None
    ps = {}   # k = 1.. after the switch: PSNR vs the source's shadow (frames held if the destination delivered fewer)
    for k, o in enumerate(outs, 1):
        fd, fr = dest_frames[o["call"]], shadow_frames.get(o["call"])
        if fr is None:
            continue
        if fd.shape[0] < fr.shape[0]:
            fd = torch.cat([fd[:1].expand(fr.shape[0] - fd.shape[0], *fd.shape[1:]), fd])
        ps[k] = ll_gate.psnr(fd, fr)
    served = sorted([to_dst(c["t_done"]) for c in done["calls"] if a.at - 5 <= c["call"] < stop["s"]] +
                    [o["t_done"] for o in outs[:5]])
    max_gap = max(y - x for x, y in zip(served, served[1:])) if len(served) > 1 else None
    res = {"mode": "ll_migrate", "method": a.method, "args": vars(a), "env_dst": env(a), "env_src": done["env"],
           "clock": {"rtt_s": rtt, "offset_s": off},
           "switch_call": stop["s"], "trigger_call": a.at,
           "state_exact": fp_src == fp_dst,
           "post_cutover": cmp, "lat_equal_calls": sum(c["lat_equal"] for c in cmp), "frm_equal_calls": sum(c["frm_equal"] for c in cmp),
           "first_call_psnr_vs_shadow": first_psnr, "psnr_vs_shadow": ps, "psnr_windows": ll_gate.windows(ps),
           "max_output_gap_s": max_gap, "recache_s": ev.get("recache_s"),
           "bytes_until_switch": done["byte_marks"].get("stop_sent"),
           "frames_complete": all(c["n_frames"] == 4 * model.F for c in cmp),
           "readiness_s": ev["ready_t"] - t_trigger, "ttfo_s": first["t_done"] - t_trigger,
           "delivery_gap_s": first["t_done"] - to_dst(stop["t_last_frame"]),
           "src_call_interval_s": {"before": iv_before, "during_state_send": iv_during},
           "src_export_stall_s": done["stall_export_s"],
           "state_transfer_s": ev["state_recv_t"] - t_trigger, "import_s": ev["import_s"],
           "replayed_calls": len(replay_log), "vae_rebuild_blocks": ev.get("vae_rebuild_blocks"), "vae_rebuild_s": ev.get("vae_rebuild_s"),
           "replayed_with_decode": decoded,
           "switch_forced": ev.get("switch_forced", False),
           "switch_req_after_trigger_s": (ev["switch_req_t"] - t_trigger) if "switch_req_t" in ev else None,
           "bytes_sent": done["sent_bytes_before_done"], "replay": replay_log}
    print(f"[ll_migrate] {a.method}: switch at call {stop['s']} (trigger {a.at}); state exact {res['state_exact']}; post-cutover "
          f"latents {res['lat_equal_calls']}/{len(cmp)}, frames {res['frm_equal_calls']}/{len(cmp)} (first call "
          f"{'-' if first_psnr is None else f'{first_psnr:.1f}'} dB), complete {res['frames_complete']}; "
          f"readiness {res['readiness_s']:.2f} s, TTFO {res['ttfo_s']:.2f} s, gap {res['delivery_gap_s']:.2f} s "
          f"(source call interval {iv_before:.2f} s); state transfer {res['state_transfer_s']:.2f} s, export stall "
          f"{res['src_export_stall_s']:.2f} s; replayed {len(replay_log)} calls ({decoded} with decode), VAE rebuilt from "
          f"{ev.get('vae_rebuild_blocks')} blocks in {ev.get('vae_rebuild_s') or 0:.2f} s; "
          f"{res['bytes_sent'] / 2 ** 30:.2f} GiB", flush=True)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(res, indent=1))
        print(f"[ll_migrate] -> {a.out}")
    sock.close(); srv.close()
    return res


def env(a):
    return {"host": socket.gethostname(), "commit": (llr.ROOT / ".git").exists() and _commit(), "torch": torch.__version__,
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}


def _commit():
    import subprocess
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=llr.ROOT, capture_output=True, text=True).stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("role", choices=["src", "dst"])
    ap.add_argument("--method", choices=["snap", "full", "replay", "recache"], required=True)
    ap.add_argument("--peer", default=None, help="src: destination host:port")
    ap.add_argument("--port", type=int, default=29951, help="dst: listen port")
    ap.add_argument("--at", type=int, default=120, help="trigger call M")
    ap.add_argument("--verify", type=int, default=20, help="post-cutover calls compared with the source's shadow")
    ap.add_argument("--replay_w", type=int, default=96, help="replay: calls replayed before the trigger (from the sink at M - W)")
    ap.add_argument("--k_vae", type=int, default=12, help="snap: logged blocks decoded to rebuild the VAE decoder cache")
    ap.add_argument("--bw_mbps", type=float, default=1000.0)
    ap.add_argument("--max_catchup_s", type=float, default=300.0, help="snap: switch anyway this long after the state arrived")
    ap.add_argument("--pings", type=int, default=9)
    ap.add_argument("--burst_bytes", type=int, default=1 << 20, help="token bucket burst (tests: small, so a tiny state is shaped)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--prompt_idx", type=int, default=0)
    ap.add_argument("--prompt", default=None)
    ap.add_argument("--config", default=str(llr.DEFAULT_CFG))
    ap.add_argument("--ckpt_dir", default=str(llr.CKPT_DIR))
    ap.add_argument("--tiny", action="store_true", help="tiny random CPU model (tests)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.prompt is None:
        import ll_gate
        a.prompt = ll_gate.PROMPTS[a.prompt_idx]
    torch.backends.cudnn.benchmark = False
    torch.set_grad_enabled(False)
    model = model_for(a)
    (source if a.role == "src" else destination)(a, model)


if __name__ == "__main__":
    main()
