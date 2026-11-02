#!/usr/bin/env python3
"""LongLive second-model gates (osdi/second_model_survey.md), one GPU, before any migration experiment.

gate0   feasibility on one L40S: per-call generate / decode time and FPS after warm-up, peak GPU memory, the session
        state inventory by component and OTTER role (durable / ephemeral / immediate), and the cost of one KV recache.
gate1   determinism and state completeness, all in one process:
          R     reference: calls 0..N-1, per-call latent and frame digests, a full state export before call M
          rep   a second fresh session, calls 0..N-1: equal to R call by call? (in-process determinism)
          full  a fresh session that imports R's full export and runs M..N-1: equal to R? (the export is the whole state)
          rc    LongLive-native reconstruction: import only the sink and the latent buffer (+ counters), KV recache,
                warm the VAE decoder on the last block, run M..N-1: PSNR vs R per call (a "P-sink + recache" baseline)
        The JSON keeps every digest so two hosts can be compared with `compare`.
compare A.json B.json   cross-host determinism: R's digests equal call by call?

    python tools/longlive/ll_gate.py gate0 --calls 60 --out results/evaluation/longlive/gate0_<host>.json
    python tools/longlive/ll_gate.py gate1 --calls 60 --at 30 --out results/evaluation/longlive/gate1_<host>.json
    python tools/longlive/ll_gate.py compare results/evaluation/longlive/gate1_A.json results/evaluation/longlive/gate1_B.json
"""

from __future__ import annotations

import argparse
import json
import math
import socket
import statistics as st
import subprocess
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ll_runtime as llr  # noqa: E402

DEFAULT_PROMPT = json.loads((llr.LL_DIR / "example/interactive_example.jsonl").read_text().splitlines()[0])["prompts"][0]


def psnr(a: torch.Tensor, b: torch.Tensor) -> float:
    mse = torch.mean((a.float() - b.float()) ** 2).item()
    return 99.0 if mse == 0 else 10 * math.log10(255.0 ** 2 / mse)


def env() -> dict:
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=llr.ROOT, capture_output=True, text=True).stdout.strip()
    except OSError:
        commit = None
    return {"host": socket.gethostname(), "commit": commit, "torch": torch.__version__,
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "cudnn_benchmark": torch.backends.cudnn.benchmark}


def run(sess: llr.LLSession, n_to: int, keep_frames_from: int | None = None, export_at: int | None = None):
    """Step the session until call n_to; per-call digests; optional frames (CPU) from a call on and one export."""
    rec, frames, snap = [], {}, None
    while sess.call < n_to:
        if export_at is not None and sess.call == export_at:
            snap = sess.export_state()
        o = sess.step()
        rec.append({"call": o["call"], "lat": llr.digest(o["latents"]), "frm": llr.digest(o["frames"]),
                    "n_frames": int(o["frames"].shape[0]), "t_gen_s": o["t_gen_s"], "t_dec_s": o["t_dec_s"]})
        if keep_frames_from is not None and o["call"] >= keep_frames_from:
            frames[o["call"]] = o["frames"].cpu()
    return rec, frames, snap


def gate0(a, model):
    torch.cuda.reset_peak_memory_stats() if torch.cuda.is_available() else None
    s = llr.LLSession(model, [a.prompt], seed=a.seed).start()
    rec, _, _ = run(s, a.calls)
    inv = s.inventory()
    model.sync(); import time; t0 = time.perf_counter()
    s.recache(); model.sync(); t_rc = time.perf_counter() - t0
    w = rec[a.warmup:]
    tot = sum(r["t_gen_s"] + r["t_dec_s"] for r in w)
    out = {"mode": "gate0", "env": env(), "args": vars(a), "calls": rec,
           "steady": {"calls": len(w), "frames": sum(r["n_frames"] for r in w), "fps": sum(r["n_frames"] for r in w) / tot,
                      "t_gen_ms_median": 1e3 * st.median(r["t_gen_s"] for r in w),
                      "t_dec_ms_median": 1e3 * st.median(r["t_dec_s"] for r in w),
                      "t_call_ms_median": 1e3 * st.median(r["t_gen_s"] + r["t_dec_s"] for r in w)},
           "recache_ms": 1e3 * t_rc,
           "peak_gpu_mb": torch.cuda.max_memory_allocated() / 2 ** 20 if torch.cuda.is_available() else None,
           "inventory": inv}
    sd = out["steady"]
    print(f"[gate0] {sd['calls']} calls after {a.warmup} warm-up: {sd['fps']:.2f} FPS, call {sd['t_call_ms_median']:.0f} ms "
          f"(generate {sd['t_gen_ms_median']:.0f}, decode {sd['t_dec_ms_median']:.0f}); recache {out['recache_ms']:.0f} ms; "
          f"peak {out['peak_gpu_mb']} MiB")
    for n, v in inv.items():
        if n != "_by_role":
            print(f"  {n:18s} {v['role']:9s} {v['bytes'] / 2 ** 20:9.1f} MiB")
    print("  by role (MiB): " + ", ".join(f"{r} {b / 2 ** 20:.1f}" for r, b in inv["_by_role"].items()))
    return out


def gate1(a, model):
    M, N = a.at, a.calls
    R = llr.LLSession(model, [a.prompt], seed=a.seed).start()
    rR, fR, snap = run(R, N, keep_frames_from=M, export_at=M)
    ckR = R.checksums()
    del R
    rep = llr.LLSession(model, [a.prompt], seed=a.seed).start()
    rRep, _, _ = run(rep, N)
    ckRep = rep.checksums()
    del rep
    full = llr.LLSession(model, [a.prompt], seed=a.seed).start().import_state(snap)
    rFull, _, _ = run(full, N)
    ckFull = full.checksums()
    del full
    rc = llr.LLSession(model, [a.prompt], seed=a.seed).start()
    rc.import_state({"counters": snap["counters"], "tensors": {k: snap["tensors"][k] for k in ("sink_kv", "latent_buffer")}})
    import time
    model.sync(); t0 = time.perf_counter()
    rc.recache(); rc.warm_decoder(); model.sync(); t_rc = time.perf_counter() - t0
    rRc, fRc, _ = run(rc, N, keep_frames_from=M)
    del rc
    eq = lambda x, y, key: all(p[key] == q[key] for p, q in zip(x, y)) and len(x) == len(y)  # noqa: E731
    out = {"mode": "gate1", "env": env(), "args": vars(a), "R": rR,
           "rep_equal": {"latents": eq(rR, rRep, "lat"), "frames": eq(rR, rRep, "frm"), "state": ckR == ckRep},
           "full_equal": {"latents": eq(rR[M:], rFull, "lat"), "frames": eq(rR[M:], rFull, "frm"), "state": ckR == ckFull},
           "recache": {"t_reconstruct_ms": 1e3 * t_rc, "psnr": {c: psnr(fRc[c], fR[c]) for c in sorted(fRc)},
                       "latents_equal_calls": [p["call"] for p, q in zip(rR[M:], rRc) if p["lat"] == q["lat"]]},
           "snapshot_bytes": {k: sum(llr.nbytes(t) for t in v) for k, v in snap["tensors"].items()}}
    ps = list(out["recache"]["psnr"].values())
    print(f"[gate1] rep == R: {out['rep_equal']}; full import at {M} == R: {out['full_equal']}")
    print(f"[gate1] recache at {M}: {out['recache']['t_reconstruct_ms']:.0f} ms; PSNR first {ps[0]:.1f}, "
          f"median {st.median(ps):.1f}, min {min(ps):.1f} dB over {len(ps)} calls")
    return out


def compare(a):
    x, y = (json.loads(Path(p).read_text()) for p in (a.a, a.b))
    same = [p["call"] for p, q in zip(x["R"], y["R"]) if p["lat"] == q["lat"] and p["frm"] == q["frm"]]
    first = next((p["call"] for p, q in zip(x["R"], y["R"]) if not (p["lat"] == q["lat"] and p["frm"] == q["frm"])), None)
    print(f"[compare] {x['env']['host']} vs {y['env']['host']}: {len(same)} / {min(len(x['R']), len(y['R']))} calls equal; "
          f"first difference: {first}")
    return {"equal_calls": len(same), "first_difference": first}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["gate0", "gate1", "compare"])
    ap.add_argument("a", nargs="?"); ap.add_argument("b", nargs="?")
    ap.add_argument("--calls", type=int, default=60)
    ap.add_argument("--warmup", type=int, default=5)
    ap.add_argument("--at", type=int, default=30)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    ap.add_argument("--config", default=str(llr.DEFAULT_CFG))
    ap.add_argument("--ckpt_dir", default=str(llr.CKPT_DIR))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.mode == "compare":
        compare(a); return
    torch.backends.cudnn.benchmark = False
    torch.set_grad_enabled(False)
    model = llr.load_model(a.config, "cuda", a.ckpt_dir)
    out = gate0(a, model) if a.mode == "gate0" else gate1(a, model)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(out, indent=1))
        print(f"[{a.mode}] -> {a.out}")


if __name__ == "__main__":
    main()
