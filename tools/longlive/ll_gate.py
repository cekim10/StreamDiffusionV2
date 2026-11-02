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
ablate  state-component ablation at call M (osdi/longlive/ablation_prereg.md): which component's absence causes the
        sink + last-W replay loss. A fresh session gets a subset of R's exact state at M (the rest empty / cold /
        recomputed / replayed / perturbed), then calls M..N-1 are scored against R: per-call PSNR, reference-relative
        temporal PSNR (boundary = first frame after the cutover), latent relative error, window medians W1 k 1-8,
        W2 9-24, W3 25-100; the state at M vs R per component (per layer for the window). Cross-attention K / V is
        never shipped (recomputed from the prompt; checked against R after the first call).
compare A.json B.json   cross-host determinism: R's digests equal call by call?

    python tools/longlive/ll_gate.py gate0 --calls 60 --out results/evaluation/longlive/gate0_<host>.json
    python tools/longlive/ll_gate.py gate1 --calls 60 --at 30 --out results/evaluation/longlive/gate1_<host>.json
    python tools/longlive/ll_gate.py ablate --calls 220 --at 120 --seed 0 --prompt_idx 0 --out results/evaluation/osdi/longlive/ablate_p0_s0.json
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

PROMPTS = [json.loads(x)["prompts"][0] for x in (llr.LL_DIR / "example/interactive_example.jsonl").read_text().splitlines() if x.strip()]
DEFAULT_PROMPT = PROMPTS[0]


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


# Phase 1 state dependency diagnosis; Phase 2 reconstruction feasibility and sensitivity (run after Phase 1's sanity)
PHASES = {1: ["full", "sink_win_vae", "sink", "sink_win", "sink_vae", "w12", "w12_vaeX", "winX_vaeR12"],
          2: ["w24", "w48", "w96", "eps_win", "eps_vae", "eps_sink", "winX_vae1", "recache"]}   # run order = user priority
ABLATE = PHASES[1] + PHASES[2]
# components shipped to the destination per condition (+ replay log blocks), for the estimated 1 Gbps readiness screen
ALL = ["sink_kv", "window_kv", "crossattn_kv", "vae_decoder_cache", "latent_buffer"]
SHIPPED = {"full": (ALL, 0), "sink_win_vae": (["sink_kv", "window_kv", "vae_decoder_cache"], 0), "sink": (["sink_kv"], 0),
           "sink_win": (["sink_kv", "window_kv"], 0), "sink_vae": (["sink_kv", "vae_decoder_cache"], 0),
           "w12": (["sink_kv"], 12), "w12_vaeX": (["sink_kv", "vae_decoder_cache"], 12), "winX_vaeR12": (["sink_kv", "window_kv"], 12),
           "winX_vae1": (["sink_kv", "window_kv"], 1), "eps_win": (ALL, 0), "eps_vae": (ALL, 0), "eps_sink": (ALL, 0),
           "recache": (["sink_kv", "latent_buffer"], 0), "w24": (["sink_kv"], 24), "w48": (["sink_kv"], 48), "w96": (["sink_kv"], 96)}


def rel_err(xs, ys) -> float | None:
    """||x - y|| / ||y|| over a list of tensors; an entry missing in x (None, or the VAE's 'Rep' marker) counts as zero."""
    num = den = 0.0
    for x, y in zip(xs, ys):
        if not torch.is_tensor(y):
            continue
        y = y.float()
        d = y if not torch.is_tensor(x) else x.float().to(y.device) - y
        num += torch.sum(d ** 2).item(); den += torch.sum(y ** 2).item()
    return None if den == 0 else math.sqrt(num / den)


def perturb_(ts, eps: float, seed: int, stats: dict) -> None:
    """In place: every element times (1 + eps * random sign), rounded back to the tensor's dtype (bf16). Not exactly one
    ulp for every value: `stats` gets the elements actually changed and the realized relative error."""
    changed = total = 0
    num = den = 0.0
    for i, t in enumerate(ts):
        if not torch.is_tensor(t):
            continue
        g = torch.Generator(device=t.device); g.manual_seed(seed * 1000 + i)
        sign = torch.randint(0, 2, t.shape, generator=g, device=t.device).to(torch.float32) * 2 - 1
        old = t.float()
        t.copy_((old * (1 + eps * sign)).to(t.dtype))
        changed += int((t.float() != old).sum().item()); total += t.numel()
        num += torch.sum((t.float() - old) ** 2).item(); den += torch.sum(old ** 2).item()
    stats.update({"eps": eps, "elements_changed": changed, "elements": total, "changed_fraction": changed / max(1, total),
                  "realized_rel_err": math.sqrt(num / den) if den else None})


def windows(v: dict) -> dict:
    """Window medians over k (1-based calls after the cutover)."""
    def med(lo, hi):
        xs = [x for k, x in v.items() if lo <= k <= hi]
        return st.median(xs) if xs else None
    return {"first": v.get(1), "W1": med(1, 8), "W2": med(9, 24), "W3": med(25, 100), "min": min(v.values()) if v else None}


def tdiff(prev: torch.Tensor, fr: torch.Tensor) -> torch.Tensor:
    """Frame-to-frame differences of a call's frames [T, H, W, 3] uint8, the first against `prev` (last frame before)."""
    x = torch.cat([prev[None].to(fr.device), fr]).to(torch.int16)
    return (x[1:] - x[:-1]).float()


def ablate(a, model):
    import time

    M, N = a.at, a.calls
    prompt = a.prompt
    R = llr.LLSession(model, [prompt], seed=a.seed).start()
    rR, fR, snap = run(R, N, keep_frames_from=M - 1, export_at=M)
    lats = run.latents
    del R
    T, C = snap["tensors"], snap["counters"]
    sink, win, vae, lb = T["sink_kv"], T["window_kv"], T["vae_decoder_cache"], T["latent_buffer"]
    W = {n: (lambda n: lambda s: s.from_sink(sink, call=M - n).replay(lats[M - n:M]))(n) for n in (12, 24, 48, 96) if n <= M}
    exact = lambda names: lambda s: s.import_state({"counters": C, "tensors": {n: T[n] for n in names}}).reset_crossattn()  # noqa: E731
    builds = {
        "full": lambda s: s.import_state(snap),
        "sink_win_vae": exact(["sink_kv", "window_kv", "vae_decoder_cache"]),
        "sink": lambda s: s.from_sink(sink, call=M),
        "sink_win": exact(["sink_kv", "window_kv"]),
        "sink_vae": lambda s: s.from_sink(sink, call=M).import_state({"tensors": {"vae_decoder_cache": vae}}),
        "w12": W.get(12),
        "w12_vaeX": (lambda s: (W[12](s), s.import_state({"tensors": {"vae_decoder_cache": vae}}))) if 12 in W else None,
        "winX_vaeR12": lambda s: exact(["sink_kv", "window_kv"])(s).warm_decoder_from(lats[max(0, M - 12):M]),
        "winX_vae1": lambda s: exact(["sink_kv", "window_kv"])(s).warm_decoder_from(lats[M - 1:M]),
        "eps_win": lambda s: (s.import_state(snap), perturb_(s.components()["window_kv"][1], a.eps, 1, pst)),
        "eps_vae": lambda s: (s.import_state(snap), perturb_(s.components()["vae_decoder_cache"][1], a.eps, 2, pst)),
        "eps_sink": lambda s: (s.import_state(snap), perturb_(s.components()["sink_kv"][1], a.eps, 3, pst)),
        "recache": lambda s: (s.import_state({"counters": C, "tensors": {"sink_kv": sink, "latent_buffer": lb}}), s.recache(), s.warm_decoder()),
        "w24": W.get(24), "w48": W.get(48), "w96": W.get(96),
    }
    sbytes = {k: sum(llr.nbytes(t) for t in v if t is not None) for k, v in T.items()}
    log_b = llr.nbytes(lats[0])
    out = {"mode": "ablate", "env": env(), "args": vars(a), "R": rR, "conditions": {}, "snapshot_bytes": sbytes,
           "replay_log_bytes_per_call": log_b}
    pst = {}
    for name in a.conditions:
        b = builds.get(name)
        if b is None:
            print(f"[ablate] {name}: skipped (W > M or unknown)")
            continue
        pst.clear()
        s = llr.LLSession(model, [prompt], seed=a.seed).start()
        model.sync(); t0 = time.perf_counter()
        b(s)
        model.sync(); t_ms = 1e3 * (time.perf_counter() - t0)
        assert s.call == M, (name, s.call)
        got = s.export_state(["sink_kv", "window_kv", "vae_decoder_cache"])["tensors"]
        L = len(win) // 2
        wl = [{"exact": bool(torch.equal(got["window_kv"][2 * i], win[2 * i]) and torch.equal(got["window_kv"][2 * i + 1], win[2 * i + 1])),
               "rel_err": rel_err(got["window_kv"][2 * i:2 * i + 2], win[2 * i:2 * i + 2])} for i in range(L)]
        vx = len(got["vae_decoder_cache"]) == len(vae) and all(torch.equal(x, y) if torch.is_tensor(x) and torch.is_tensor(y) else x == y
                                                                for x, y in zip(got["vae_decoder_cache"], vae))
        state = {"sink_exact": all(torch.equal(x, y) for x, y in zip(got["sink_kv"], sink)), "sink_rel_err": rel_err(got["sink_kv"], sink),
                 "window_layers_exact": sum(w["exact"] for w in wl), "layers": L, "window_rel_err": rel_err(got["window_kv"], win),
                 "window_per_layer": wl, "vae_exact": vx, "vae_rel_err": rel_err(got["vae_decoder_cache"], vae)}
        ps, ps_al, tp, le, leq, missing, expected = {}, {}, {}, {}, 0, 0, 0
        prev_d, prev_r = fR[M - 1][-1], fR[M - 1][-1]
        xattn_exact = None
        for k in range(1, N - M + 1):
            o = s.step()
            c = o["call"]
            if k == 1:
                xattn_exact = all(torch.equal(xa[kk], T["crossattn_kv"][2 * i + j].to(xa[kk].device))
                                  for i, xa in enumerate(s.xattn) for j, kk in enumerate(("k", "v")))
            fd, fr = o["frames"], fR[c].to(o["frames"].device)
            expected += fr.shape[0]
            if fd.shape[0] < fr.shape[0]:   # a cold VAE decoder restarts: its first latent frame decodes to 1 frame, not 4
                n_miss = fr.shape[0] - fd.shape[0]
                missing += n_miss
                ps_al[k] = psnr(fd, fr[-fd.shape[0]:])   # diagnostic only: aligned to the reference's last frames
                fd = torch.cat([prev_d[None].to(fd.device).expand(n_miss, *fd.shape[1:]), fd])   # scored as held frames
            ps[k] = psnr(fd, fr)
            tp[k] = psnr(tdiff(prev_d, fd), tdiff(prev_r, fr))
            prev_d, prev_r = fd[-1], fr[-1]
            le[k] = rel_err([o["latents"]], [lats[c]])
            leq += int(llr.digest(o["latents"]) == rR[c]["lat"])
        comps, n_log = SHIPPED[name]
        shipped = sum(sbytes[cn] for cn in comps) + n_log * log_b
        r = {"t_build_ms": t_ms, "state_at_M": state, "xattn_recomputed_exact": xattn_exact, "psnr": ps, "psnr_aligned_diag": ps_al,
             "tpsnr": tp, "latent_rel_err": le, "latents_equal_calls": leq, "scored_calls": N - M,
             "frames_expected": expected, "frames_missing": missing, "frames_complete": missing == 0,
             "psnr_windows": windows(ps), "tpsnr_windows": windows(tp), "t_boundary": tp.get(1),
             "perturbation": dict(pst) or None, "shipped": {"components": comps, "replay_log_calls": n_log, "bytes": shipped},
             "est_ready_s_1gbps": shipped * 8 / 1e9 + t_ms / 1e3}   # estimated screen: transfer at 1 Gbps + build
        out["conditions"][name] = r
        pw = r["psnr_windows"]
        f = lambda x: "-" if x is None else f"{x:.1f}"  # noqa: E731
        print(f"[ablate] {name:13s} build {t_ms:7.0f} ms; window exact {state['window_layers_exact']:2d}/{L} (rel {state['window_rel_err'] or 0:.2e}), "
              f"VAE exact {vx} (rel {state['vae_rel_err'] or 0:.2e}); PSNR first {f(pw['first'])} W1 {f(pw['W1'])} W2 {f(pw['W2'])} "
              f"W3 {f(pw['W3'])} min {f(pw['min'])}; tPSNR bnd {f(r['t_boundary'])} W3 {f(r['tpsnr_windows']['W3'])}; "
              f"latent rel err k1 {le[1]:.1e} k{N - M} {le[N - M]:.1e}; equal {leq}/{N - M}; frames {expected - missing}/{expected}; "
              f"shipped {shipped / 2 ** 30:.2f} GiB, est. ready @1 Gbps {r['est_ready_s_1gbps']:.1f} s"
              + (f"; perturbed {pst['changed_fraction']:.3f} of elements, rel {pst['realized_rel_err']:.2e}" if pst else ""), flush=True)
        del s
        if a.out:   # partial results survive a crash
            Path(a.out).parent.mkdir(parents=True, exist_ok=True)
            Path(a.out).write_text(json.dumps(out, indent=1))
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
    ap.add_argument("mode", choices=["gate0", "gate1", "ablate", "compare"])
    ap.add_argument("a", nargs="?"); ap.add_argument("b", nargs="?")
    ap.add_argument("--calls", type=int, default=60)
    ap.add_argument("--warmup", type=int, default=5)
    ap.add_argument("--at", type=int, default=30)
    ap.add_argument("--replay_windows", type=lambda s: [int(x) for x in s.split(",")], default=[3, 6, 12],
                    help="gate1: W of the sink + last-W-calls replay variants")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--prompt", default=None, help="default: first prompt of interactive_example.jsonl set --prompt_idx")
    ap.add_argument("--prompt_idx", type=int, default=0)
    ap.add_argument("--conditions", type=lambda s: s.split(","), default=None, help="ablate: conditions in order (default: --phase)")
    ap.add_argument("--phase", type=int, choices=[1, 2], default=1, help="ablate: condition set of osdi/longlive/ablation_prereg.md")
    ap.add_argument("--eps", type=float, default=2.0 ** -8, help="ablate: relative perturbation of the eps_* conditions")
    ap.add_argument("--config", default=str(llr.DEFAULT_CFG))
    ap.add_argument("--ckpt_dir", default=str(llr.CKPT_DIR))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.prompt is None:
        a.prompt = PROMPTS[a.prompt_idx]
    if a.conditions is None:
        a.conditions = PHASES[a.phase]
    if a.mode == "compare":
        compare(a); return
    torch.backends.cudnn.benchmark = False
    torch.set_grad_enabled(False)
    model = llr.load_model(a.config, "cuda", a.ckpt_dir)
    out = {"gate0": gate0, "gate1": gate1, "ablate": ablate}[a.mode](a, model)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(out, indent=1))
        print(f"[{a.mode}] -> {a.out}")


if __name__ == "__main__":
    main()
