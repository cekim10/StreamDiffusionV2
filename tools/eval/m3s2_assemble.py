#!/usr/bin/env python3
"""M3-S2 Phase A0 (osdi/m3s2/preregistration.md): offline exactness of mixed-version Sink reconstruction on one GPU.

One deterministic generation of a workload (same procedure as m3s0_dump_events.py). The M3 lineage history
(m3_path.LineageHistory with the frozen M2 tracker's detection rule, m3_path.gpu_track_events) is recorded after every
call from the first boundary on. At every boundary in --versions and --targets (state before that call) the K and V
of all 180 Sink entries are copied to host memory, and at every target the 360 Sink block checksums are taken
(GpuRuntime.sink_checksums, the digest the frozen protocol compares).

Checks (all bitwise):
  E  entry level, every (version v < target t) pair and every entry: if the history says the entry is valid (not
     refreshed in calls [v, t)), the entry at v with its ordered shifts of [v, t) applied (the same RoPE shift the
     frozen M2 reuse applies) must equal the entry at t (K and V, torch.equal). Entries the history calls refreshed are
     counted by whether their V actually changed.
  S  Sink level, after generation: for every target, Sinks assembled the way the M3 destination assembles them -
     (a) all reusable entries from one older version (each version), (b) per entry a random version among the
     boundaries <= t (5 seeds; an entry invalid at its drawn version is taken at t, as the protocol re-sends it),
     (c) the M3-S1 shape: the first 139 entries from the earliest version, the rest at t - are written into the live
     ring's Sink, shifted in place, and their 360 block checksums compared with the target's.
  N  negative controls (must be detected): a valid entry with nonzero shifts reused without its shifts; with the summed
     shift as one rotation (reported, M1 / M2 follow-up found it not bitwise); a refreshed entry reused as if valid.

    python tools/eval/m3s2_assemble.py --video_path examples/original.mp4 --prompt_file_path examples/prompt.txt --seed 0 \\
        --out results/evaluation/osdi/m3s2/a0_dog.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p_ in (ROOT, ROOT / "tools", ROOT / "tools" / "eval"):
    if str(p_) not in sys.path:
        sys.path.insert(0, str(p_))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video_path", required=True); ap.add_argument("--prompt_file_path", required=True); ap.add_argument("--seed", default="0")
    ap.add_argument("--gpu_id", default="0")
    ap.add_argument("--versions", default="30,43,56,68,81,100,120")
    ap.add_argument("--targets", default="56,81,100,120,140")
    ap.add_argument("--mixes", type=int, default=5)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    import torch

    import mobility_node as mn
    import m3_path as m3
    from models.wan.causal_model import _shift_temporal_rope

    margs = mn.parse_args(["--label", "A0", "--video_path", a.video_path, "--prompt_file_path", a.prompt_file_path, "--seed", a.seed, "--gpu_id", a.gpu_id,
                           "--migration_chunk", "30", "--post_chunks", "1500"])
    rt = mn.GpuRuntime(margs)
    pl, dev, fsl, S = rt.pl, rt.device, rt.fsl, rt.sink
    sync = lambda: torch.cuda.synchronize(dev)  # noqa: E731
    versions = sorted({int(x) for x in a.versions.split(",")})
    targets = sorted({int(x) for x in a.targets.split(",")})
    bounds = sorted(set(versions) | set(targets))
    geo = {}   # the KV cache exists only after the session's first call: geometry is read at the first boundary

    def entries_now():
        coords = geo["coords"]
        out = {}
        for e, (li, i, s) in enumerate(coords):
            out[e] = (pl.kv_cache1[li]["k"][i, s * fsl:(s + 1) * fsl].detach().to("cpu", copy=True), pl.kv_cache1[li]["v"][i, s * fsl:(s + 1) * fsl].detach().to("cpu", copy=True))
        return out

    session = rt.session = rt.runner.start()
    hist = m3.LineageHistory(bounds[0])
    last = None
    snaps, cks, pos_at = {}, {}, {}
    t_all = time.time()
    # per-entry serialization cost on this GPU (D2H + SHA-256), measured at the first boundary
    cost = None
    for c in range(targets[-1] + 1):
        if c in bounds and not geo:
            L_, rows_ = len(pl.kv_cache1), int(pl.kv_cache1[0]["k"].shape[0])
            geo.update({"L": L_, "rows": rows_, "N": L_ * rows_ * S, "coords": [m3.coords_of(e, rows_, S) for e in range(L_ * rows_ * S)]})
        if c in bounds:
            sync()
            L, rows, N, coords = geo["L"], geo["rows"], geo["N"], geo["coords"]
            snaps[c] = entries_now()
            if c in targets:
                ck = rt.sink_checksums(); ck.pop("s"); cks[c] = ck["blocks"]; pos_at[c] = ck["pos"]
            if cost is None:
                t0 = time.perf_counter()
                for e in range(N):
                    li, i, s = coords[e]
                    mk, bk = m3.tensor_to_bytes(pl.kv_cache1[li]["k"][i, s * fsl:(s + 1) * fsl]); mv, bv = m3.tensor_to_bytes(pl.kv_cache1[li]["v"][i, s * fsl:(s + 1) * fsl])
                    t1 = time.perf_counter()
                    m3.sha_parts([bk, bv])
                    if e == 0:
                        t_first = (t1 - t0, time.perf_counter() - t1)
                cost = {"all_entries_d2h_and_hash_s": time.perf_counter() - t0, "first_entry_d2h_s": t_first[0], "first_entry_hash_s": t_first[1], "entry_bytes": int(bk.nbytes + bv.nbytes)}
        if c == bounds[0]:
            last = m3.gpu_track_events(rt, None)[0]
        rt.runner.step(session, c); sync()
        if c >= bounds[0]:
            t0 = time.perf_counter()
            last, ref, sh = m3.gpu_track_events(rt, last)
            hist.record(c, ref, sh, time.perf_counter() - t0)
        if c % 20 == 0:
            print(f"[A0] call {c} ({time.time() - t_all:.0f} s)", flush=True)
    freqs = pl.generator.model.freqs.to(dev)

    def shifted(k_cpu, ds):
        k = k_cpu.to(dev)
        for d in ds:
            k = _shift_temporal_rope(k, freqs, int(d))
        return k

    # ---- E: entry level
    E = {"pairs": 0, "valid_entries": 0, "valid_exact": 0, "valid_mismatch": [], "refreshed_entries": 0, "refreshed_v_changed": 0, "refreshed_v_unchanged": [],
         "valid_with_shifts": 0, "neg_noshift_detected": 0, "neg_summed_equal": 0, "neg_refreshed_detected": 0}
    per_pair = []
    for t in targets:
        for v in [x for x in bounds if x < t]:
            E["pairs"] += 1; pv = {"v": v, "t": t, "valid": 0, "exact": 0, "refreshed": 0, "with_shifts": 0}
            for e in range(N):
                kv_v, kv_t = snaps[v][e], snaps[t][e]
                if hist.valid(e, v, t):
                    ds = hist.shifts_since(e, v, t)
                    k2 = shifted(kv_v[0], ds)
                    ok = bool(torch.equal(k2, kv_t[0].to(dev))) and bool(torch.equal(kv_v[1], kv_t[1]))
                    E["valid_entries"] += 1; pv["valid"] += 1
                    if ok:
                        E["valid_exact"] += 1; pv["exact"] += 1
                    elif len(E["valid_mismatch"]) < 40:
                        E["valid_mismatch"].append([v, t, e, len(ds)])
                    if any(ds):
                        E["valid_with_shifts"] += 1; pv["with_shifts"] += 1
                        E["neg_noshift_detected"] += int(not torch.equal(kv_v[0].to(dev), kv_t[0].to(dev)))
                        E["neg_summed_equal"] += int(bool(torch.equal(shifted(kv_v[0], [sum(ds)]), kv_t[0].to(dev))))
                else:
                    E["refreshed_entries"] += 1; pv["refreshed"] += 1
                    changed = not torch.equal(kv_v[1], kv_t[1])
                    E["refreshed_v_changed"] += int(changed)
                    if not changed and len(E["refreshed_v_unchanged"]) < 40:
                        E["refreshed_v_unchanged"].append([v, t, e])
                    E["neg_refreshed_detected"] += int(not (torch.equal(shifted(kv_v[0], hist.shifts_since(e, v, t)), kv_t[0].to(dev)) and torch.equal(kv_v[1], kv_t[1])))
            per_pair.append(pv)
    E["per_pair"] = per_pair

    # ---- S: Sink level, written into the live ring's Sink (generation has ended)
    def assemble_and_check(t, choice):
        """choice: entry -> version (t = taken at the target, i.e. re-sent by the source). Returns block mismatches."""
        for e, (li, i, s) in enumerate(coords):
            v = choice[e]
            k_c, v_c = snaps[v][e]
            pl.kv_cache1[li]["k"][i, s * fsl:(s + 1) * fsl] = k_c.to(dev)
            pl.kv_cache1[li]["v"][i, s * fsl:(s + 1) * fsl] = v_c.to(dev)
            if v != t:
                k = pl.kv_cache1[li]["k"]
                for d in hist.shifts_since(e, v, t):
                    k[i, s * fsl:(s + 1) * fsl] = _shift_temporal_rope(k[i, s * fsl:(s + 1) * fsl], freqs, int(d))
        sync()
        ck = rt.sink_checksums(); ck.pop("s")
        return [[ii // 2, "kv"[ii % 2], b, s_] for ii, layer in enumerate(ck["blocks"]) for b, row in enumerate(layer) for s_, x in enumerate(row) if x != cks[t][ii][b][s_]]

    rng = random.Random(20261029)
    Ssc = []
    for t in targets:
        olds = [x for x in bounds if x < t]
        scen = [("single", v, {e: (v if hist.valid(e, v, t) else t) for e in range(N)}) for v in olds]
        for m in range(a.mixes):
            ch = {}
            for e in range(N):
                v = rng.choice(olds + [t])
                ch[e] = v if (v == t or hist.valid(e, v, t)) else t
            scen.append(("mix", m, ch))
        v0 = olds[0]
        scen.append(("s1_shape", v0, {e: (v0 if (e < 139 and hist.valid(e, v0, t)) else t) for e in range(N)}))
        for kind, key, ch in scen:
            bad = assemble_and_check(t, ch)
            Ssc.append({"t": t, "kind": kind, "key": key, "reused": sum(1 for e in range(N) if ch[e] != t), "versions": len(set(ch.values())),
                        "shift_ops": sum(len(hist.shifts_since(e, ch[e], t)) for e in range(N) if ch[e] != t), "n_block_mismatch": len(bad), "mismatched": bad[:10]})
        # negative control at Sink level: one refreshed entry reused stale (if any) must be caught by the 360-block digest
        stale = next(((e, v) for v in olds for e in range(N) if not hist.valid(e, v, t)), None)
        if stale is not None:
            ch = {e: t for e in range(N)}; ch[stale[0]] = stale[1]
            bad = assemble_and_check(t, ch)
            Ssc.append({"t": t, "kind": "neg_stale_entry", "key": list(stale), "reused": 1, "versions": 2, "n_block_mismatch": len(bad), "mismatched": bad[:10]})
    good = [x for x in Ssc if not x["kind"].startswith("neg")]
    neg = [x for x in Ssc if x["kind"].startswith("neg")]
    res = {"host": platform.node(), "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
           "video": a.video_path, "prompt": a.prompt_file_path, "seed": a.seed, "versions": versions, "targets": targets, "n_entries": N, "layers": L, "rows": rows, "sink_slots": S,
           "history": hist.summary(), "serialization_cost": cost, "entry_level": E, "sink_level": Ssc,
           "verdict": {"E_valid_entries_all_exact": E["valid_mismatch"] == [] and E["valid_exact"] == E["valid_entries"],
                       "S_assemblies_all_exact": all(x["n_block_mismatch"] == 0 for x in good), "S_assemblies": len(good),
                       "S_max_versions_in_one_sink": max((x["versions"] for x in good), default=None),
                       "N_noshift_all_detected": E["neg_noshift_detected"] == E["valid_with_shifts"], "N_refreshed_all_detected": E["neg_refreshed_detected"] == E["refreshed_entries"],
                       "N_stale_sink_all_detected": all(x["n_block_mismatch"] > 0 for x in neg), "summed_shift_equal_fraction": E["neg_summed_equal"] / E["valid_with_shifts"] if E["valid_with_shifts"] else None},
           "wall_s": time.time() - t_all}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=1))
    print(json.dumps(res["verdict"], indent=1))
    print(f"[A0] entry level: {E['valid_exact']} / {E['valid_entries']} valid entries exact over {E['pairs']} (v, t) pairs; refreshed {E['refreshed_entries']} "
          f"(V changed {E['refreshed_v_changed']}); Sink level: {sum(x['n_block_mismatch'] == 0 for x in good)} / {len(good)} assemblies exact; wrote {a.out}")


if __name__ == "__main__":
    main()
