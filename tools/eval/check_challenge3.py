#!/usr/bin/env python3
"""Post-hoc check of the paper's Challenge 3 numbers against the frozen Experiment N runs (results/evaluation/expN_cell*);
exploratory analysis of existing traces, not a preregistered test. Output: osdi/expN/challenge3_check.md (written by hand from it)."""
import json, glob, csv, statistics as st
R = "results/evaluation"
def runs(cell, pol):
    return sorted(glob.glob(f"{R}/expN_cell{cell}/policy={pol}_bw*"))
def lat(d):
    s = json.load(open(d + "/summary.json")); L = s["latency_after_final_move_s"]
    return {"bind": L["sink_bind"], "verified": L["sink_verified"], "received": L["sink_received"], "src": s["d0"]["source_bytes_total_sinks"], "replans": s["d0"]["n_replans"]}
print("== latency definitions (median over reps) by cell / policy")
for cell in (1, 7, 8, 9, 10):
    for pol in ("reuse_aware_in", "split", "reuse_dyn"):
        rr = [lat(d) for d in runs(cell, pol)]
        if not rr: continue
        m = {k: st.median([r[k] for r in rr]) for k in rr[0]}
        print(f"cell {cell:2d} {pol:15s} n={len(rr)} bind {m['bind']:.2f} verified {m['verified']:.2f} received {m['received']:.2f} src {m['src']:.3f} replans {[r['replans'] for r in rr]}  per-rep bind {[round(r['bind'],2) for r in rr]}")
print("\n== cell 10 reuse_dyn re-plans")
for d in runs(10, "reuse_dyn"):
    s = json.load(open(d + "/summary.json")); rp = s["d0"]["replans"]; cap = s["d0"]["cap_changes"][0][0]; tmove = s["t_final_move_rel_s"]
    t_done = s["final"]["sink_complete_rel_s"]
    dT = [r["dT_s"] for r in rp]
    before = [r for r in rp if r["t_s"] < cap]
    # fragments verified at C per provider (orchestrator fragments.csv)
    rec = [r for r in csv.DictReader(open(d + "/fragments.csv")) if r["event"] == "recv" and r["dst"] == "C" and r["ok"] == "True" and r["dup"] == "False"]
    rec = [(float(r["t_rel"]), r["src"], int(r["bytes"])) for r in rec]
    def rate(t0, t1, src=None):
        b = sum(x[2] for x in rec if t0 <= x[0] < t1 and (src is None or x[1] == src))
        return b * 8 / (t1 - t0) / 1e6
    rows = []
    for r in rp:
        if r["t_s"] < cap: continue
        t = r["t_s"]; mr = r["measured_rate_mbps"]
        slow = min(mr, key=mr.get)
        long_ = rate(t - 10, t, slow)
        tot2 = rate(t - 2, t)
        rows.append({"t": t - tmove, "eta_cur": r["eta_cur_s"], "eta_new": r["eta_new_s"], "actual_left": t_done - t, "slow": slow, "meas": mr[slow], "long10": long_, "total_2s": tot2, "rates": mr})
    print(f"\n{d.split('/')[-1][:60]}  replans {len(rp)}, before cap change {len(before)} (t_after_move {[round(r['t_s']-tmove,2) for r in before]}), cap change at +{cap-tmove:.2f} s")
    print(f"   predicted dT range {min(dT):.1f} .. {max(dT):.1f} s; sum {sum(dT):.0f} s; B_source {s['d0']['source_bytes_total_sinks']:.3f}")
    ratios = [x["eta_cur"] / x["actual_left"] for x in rows]
    lr = [x["long10"] / x["meas"] for x in rows if x["meas"] > 0]
    print(f"   eta_cur / actual remaining: median {st.median(ratios):.2f}, range {min(ratios):.2f}..{max(ratios):.2f}")
    print(f"   slowest provider: 10 s mean rate / measured 2 s rate: median {st.median(lr):.2f}, range {min(lr):.2f}..{max(lr):.2f}")
    print(f"   total verified ingress in the 2 s before each re-plan (Mbps): median {st.median([x['total_2s'] for x in rows]):.1f}, range {min(x['total_2s'] for x in rows):.1f}..{max(x['total_2s'] for x in rows):.1f}")
    print("   measured rates seen:", sorted({round(v, 1) for x in rows for v in x['rates'].values()}))

print("\n== dip coincidence: provider that sets eta_cur (max bytes_left / rate) vs its 10 s mean")
tot = dip = 0; ratios_dip = []; ratios_nodip = []
for d in runs(10, "reuse_dyn"):
    s = json.load(open(d + "/summary.json")); rp = s["d0"]["replans"]; cap = s["d0"]["cap_changes"][0][0]; t_done = s["final"]["sink_complete_rel_s"]
    rec = [(float(r["t_rel"]), r["src"], int(r["bytes"])) for r in csv.DictReader(open(d + "/fragments.csv")) if r["event"] == "recv" and r["dst"] == "C" and r["ok"] == "True" and r["dup"] == "False"]
    rate = lambda t0, t1, src: sum(x[2] for x in rec if t0 <= x[0] < t1 and x[1] == src) * 8 / (t1 - t0) / 1e6
    for r in rp:
        if r["t_s"] < cap: continue
        mr = r["measured_rate_mbps"]; p = r["from"]   # the re-plan moves fragments away from the provider that set eta_cur
        tot += 1
        l10 = rate(r["t_s"] - 10, r["t_s"], p)
        isdip = mr.get(p, 0) > 0 and l10 / mr[p] >= 1.5
        dip += isdip
        (ratios_dip if isdip else ratios_nodip).append(r["eta_cur_s"] / (t_done - r["t_s"]))
print(f"post-change re-plans {tot}; the provider being drained had a 2 s rate >= 1.5x below its 10 s mean in {dip} ({100*dip/tot:.0f} %)")
print(f"eta_cur / actual remaining: with dip median {st.median(ratios_dip):.2f} (n {len(ratios_dip)}), without dip median {st.median(ratios_nodip) if ratios_nodip else None} (n {len(ratios_nodip)})")
