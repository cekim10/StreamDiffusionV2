#!/usr/bin/env python3
"""LongLive second-model gates (osdi/second_model_survey.md), one GPU, before any migration experiment.

gate0   feasibility on one L40S: per-call generate / decode time and FPS after warm-up, peak GPU memory, the session
        state inventory by component and OTTER role (durable / ephemeral / immediate), and the cost of one KV recache.
gate1   determinism and state completeness, all in one process:
          R     reference: calls 0..N-1, per-call latent and frame digests, a full state export before call M
          rep   a second fresh session, calls 0..N-1: equal to R call by call? (in-process determinism)
          full  a fresh session that imports R's full export and runs M..N-1: equal to R? (the export is the whole state)
          reconstruction of the state at M on a fresh session without the window / VAE cache, then calls M..N-1 vs R
          (time, window layers exact, VAE cache exact, PSNR per call, equal latents):
            recache      LongLive-native: sink + last local_attn_size latents, KV recache, VAE warmed on the last block
            replay_all   teacher-forced replay (context pass + decode per logged block) of calls 0..M-1 (exact)
            replay_wW    OTTER-style: sink, then teacher-forced replay of the last W calls (window rebuilt approximately)
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
    lats = []
    while sess.call < n_to:
        if export_at is not None and sess.call == export_at:
            snap = sess.export_state()
        o = sess.step()
        rec.append({"call": o["call"], "lat": llr.digest(o["latents"]), "frm": llr.digest(o["frames"]),
                    "n_frames": int(o["frames"].shape[0]), "t_gen_s": o["t_gen_s"], "t_dec_s": o["t_dec_s"]})
        if keep_frames_from is not None and o["call"] >= keep_frames_from:
            frames[o["call"]] = o["frames"].cpu()
        lats.append(o["latents"].cpu())
    run.latents = lats
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
    lats = run.latents   # R's output latents, calls 0..N-1 (the replay log)
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
    snapM = {k: snap["tensors"][k] for k in ("window_kv", "vae_decoder_cache")}
    import time

    def reconstruct(name, build):
        """Build a destination session at call M with `build`, time it, compare its state with R's at M, run to N."""
        s = llr.LLSession(model, [a.prompt], seed=a.seed).start()
        model.sync(); t0 = time.perf_counter()
        build(s)
        model.sync(); t_ms = 1e3 * (time.perf_counter() - t0)
        assert s.call == M, (name, s.call)
        got = s.export_state(["window_kv", "vae_decoder_cache"])["tensors"]
        win_eq = [bool(torch.equal(x, y)) for x, y in zip(got["window_kv"], snapM["window_kv"])]
        vae_eq = all((x is None and y is None) or (x is not None and y is not None and torch.equal(x, y))
                     for x, y in zip(got["vae_decoder_cache"], snapM["vae_decoder_cache"]))
        rX, fX, _ = run(s, N, keep_frames_from=M)
        ps = {c: psnr(fX[c], fR[c]) for c in sorted(fX)}
        r = {"t_reconstruct_ms": t_ms, "window_layers_exact": sum(win_eq[0::2]) if win_eq else 0, "layers": len(win_eq) // 2,
             "vae_cache_exact": vae_eq, "psnr": ps, "latents_equal_calls": [p["call"] for p, q in zip(rR[M:], rX) if p["lat"] == q["lat"]]}
        v = list(ps.values())
        print(f"[gate1] {name:12s} {t_ms:8.0f} ms; window exact {r['window_layers_exact']}/{r['layers']} layers, VAE cache exact "
              f"{vae_eq}; PSNR first {v[0]:.1f}, median {st.median(v):.1f}, min {min(v):.1f} dB; latents equal on "
              f"{len(r['latents_equal_calls'])}/{len(rX)} calls")
        return r

    sink, lb = snap["tensors"]["sink_kv"], snap["tensors"]["latent_buffer"]
    variants = {
        # LongLive-native: sink + last local_attn_size latents, KV recache, VAE decoder warmed on the last block
        "recache": lambda s: (s.import_state({"counters": snap["counters"], "tensors": {"sink_kv": sink, "latent_buffer": lb}}),
                              s.recache(), s.warm_decoder()),
        # teacher-forced replay of the whole log from call 0 (exact by construction; cost grows with M)
        "replay_all": lambda s: s.replay(lats[:M]),
    }
    for W in a.replay_windows:   # OTTER-style: the sink plus a replay of the last W calls
        if W <= M:
            variants[f"replay_w{W}"] = (lambda W: lambda s: s.from_sink(sink, call=M - W).replay(lats[M - W:M]))(W)
    recon = {name: reconstruct(name, b) for name, b in variants.items()}
    eq = lambda x, y, key: all(p[key] == q[key] for p, q in zip(x, y)) and len(x) == len(y)  # noqa: E731
    out = {"mode": "gate1", "env": env(), "args": vars(a), "R": rR,
           "rep_equal": {"latents": eq(rR, rRep, "lat"), "frames": eq(rR, rRep, "frm"), "state": ckR == ckRep},
           "full_equal": {"latents": eq(rR[M:], rFull, "lat"), "frames": eq(rR[M:], rFull, "frm"), "state": ckR == ckFull},
           "reconstruction": recon,
           "snapshot_bytes": {k: sum(llr.nbytes(t) for t in v) for k, v in snap["tensors"].items()},
           "replay_log_bytes_per_call": llr.nbytes(lats[0])}
    import hashlib
    out["R_chain"] = hashlib.blake2b("".join(r["lat"] + r["frm"] for r in rR).encode(), digest_size=8).hexdigest()
    print(f"[gate1] rep == R: {out['rep_equal']}; full import at {M} == R: {out['full_equal']}")
    print(f"[gate1] R chain {out['R_chain']} ({N} calls, seed {a.seed}; equal on two hosts = cross-host determinism)")
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
    ap.add_argument("--replay_windows", type=lambda s: [int(x) for x in s.split(",")], default=[3, 6, 12],
                    help="gate1: W of the sink + last-W-calls replay variants")
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
