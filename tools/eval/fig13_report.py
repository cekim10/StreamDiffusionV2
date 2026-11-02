#!/usr/bin/env python3
"""Fig. 13 (osdi/fig13/preregistration.md): output fidelity after a verified cutover. Applies the preregistered rules.

Per run (one migration A -> B; OTTER and P-sink switch at the fixed call S; Full is the exact control): validity, then
per destination call k = call - S + 1 (k = 1: B's first generated call; Full: k from B's first call) PSNR / SSIM vs the
reference and the reference-relative temporal PSNR (node --fidelity_log), window medians W1 = k 1-8, W2 = 9-24,
W3 = 25-100, first call, terminal (k 91-100), boundary tPSNR (first frame of k = 1); Sink: first k with a decision
divergence (a refresh queued or a cache slot written differently from the reference on any layer / row), a position
divergence (slot positions differ) and a content divergence (block checksums differ); the first decision divergence is
classified (dest_only: only the destination queued a refresh; ref_only; slot: both, different slots; write; realign)
with the reference's and the destination's min similarity there (threshold 0.2).

F13-H1  OTTER conditions with no schedule divergence (decision or position) by k = 100: >= 90 % have W3 PSNR >= 40 dB.
F13-H2  >= 80 % of first decision divergences are threshold crossings (dest_only / ref_only) whose reference margin
        |min sim - 0.2| is below the 10th percentile of that input's reference margins over calls 30-180.
F13-H3  across the 10 inputs: Spearman rho(Fig. 5 refresh intensity, OTTER schedule-divergence rate) >= 0.6.
F13-H4  W1 PSNR OTTER > P-sink at S = 74, seed 0, in >= 8 of 10 inputs.
Claim rule (section 7): reported shares F_P (W3 PSNR >= 40 dB) and F_T (W3 tPSNR >= 40 dB) over all OTTER conditions.

    python tools/eval/fig13_report.py            # -> results/evaluation/osdi/fig13/fig13_results.{json,md}
    python tools/eval/fig13_report.py --sanity   # per-run detail of whatever exists so far
    python tools/eval/fig13_report.py --prefix _dryrun_ --dry
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
from xb_validity import run_validity_xb  # noqa: E402

EVAL = ROOT / "results/evaluation"
OUT = EVAL / "osdi/fig13"
THR = 0.2   # adapt_sink_threshold (configs/wan_causal_dmd_v2v.yaml; models/wan/causal_model.py)
# Fig. 5 refresh intensity, refreshes per 100 calls, seed 0 (m123_figures.data.json fig5_inputs)
REFRESH = {"dog": 3.6, "bird": 3.6, "boxing": 8.2, "basketball": 9.1, "hockey": 16.4, "swimmer": 22.7, "train": 34.5, "audi": 53.6,
           "circus": 89.1, "bfly": 128.2}
INPUTS = tuple(sorted(REFRESH, key=lambda k: (REFRESH[k], k)))
S_SEED = {0: tuple(range(70, 80)), 1: (70, 72, 74, 76, 78)}
W1, W2, W3, TERM = (1, 8), (9, 24), (25, 100), (91, 100)
NAME = re.compile(r"^(?P<pre>_dryrun_)?expF13_(?P<inp>[a-z]+)_s(?P<seed>\d+)_(?:S(?P<S>\d+)|full)$")


def load(d: Path):
    s = json.load(open(d / "summary.json"))
    ev = []
    for r in csv.DictReader(open(d / "events.csv", newline="")):
        node, name = r["event"].split(":", 1) if ":" in r["event"] else ("", r["event"])
        ev.append({"node": node, "event": name, "t": float(r["t_wall"]), **(json.loads(r["detail"]) if r["detail"] else {})})
    m = list(csv.DictReader(open(d / "metrics.csv", newline="")))
    fr = {}
    for lb in ("A", "B"):
        p = d / f"node_{lb}" / "fidelity_record.json.gz"
        if p.exists():
            with gzip.open(p, "rt") as fh:
                fr[lb] = json.load(fh)
    return s, ev, m, fr


def first(ev, node, name, after=-1e18):
    return next((e for e in ev if e["node"] == node and e["event"] == name and e["t"] >= after), None)


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def wmed(series: dict, lo_hi) -> float | None:
    v = [series[k] for k in range(lo_hi[0], lo_hi[1] + 1) if series.get(k) is not None]
    return st.median(v) if v else None


def decision_divergence(own: dict, ref: dict, c_lo: int, c_hi: int):
    """First call in [c_lo, c_hi] where the queued refreshes / written slots / realignment of any (layer, row) differ from
    the reference, with the class and both min similarities of the first differing (layer, row)."""
    for c in range(c_lo, c_hi + 1):
        o, r = own.get(c), ref.get(c)
        if o is None or r is None:
            continue
        ro = {(x[0], x[1]): x for x in o}
        rr = {(x[0], x[1]): x for x in r}
        for key in sorted(set(ro) | set(rr)):
            a, b = ro.get(key), rr.get(key)   # [layer, row, n, min, arg, ins, w, ra]
            if a is None or b is None:
                continue
            if a[5] != b[5] or a[6] != b[6] or a[7] != b[7]:
                if a[5] != b[5]:
                    cls = "dest_only" if (a[5] and not b[5]) else "ref_only" if (b[5] and not a[5]) else "slot"
                elif a[6] != b[6]:
                    cls = "write"
                else:
                    cls = "realign"
                return {"call": c, "layer": key[0], "row": key[1], "class": cls, "sim_dest": a[3], "sim_ref": b[3],
                        "margin_ref": None if b[3] is None else abs(b[3] - THR), "margin_dest": None if a[3] is None else abs(a[3] - THR),
                        "dsim": None if (a[3] is None or b[3] is None) else abs(a[3] - b[3])}
    return None


def run_record(d: Path, dry: bool) -> dict | None:
    g = NAME.match(d.parent.name)
    if not g:
        return None
    inp, seed = g["inp"], int(g["seed"])
    s, ev, m, frec = load(d)
    pol = s.get("policy") or ("full" if "policy=full" in d.name else "")
    meth = {"precopy_replay": "otter", "precopy_sink": "psink", "full": "full"}.get(pol, pol)
    S = int(g["S"]) if g["S"] else None
    rep = int(re.search(r"_rep=(\d+)", d.name).group(1)) if re.search(r"_rep=(\d+)", d.name) else None
    if pol == "full":   # not an XB method: judged with the W / R / N rules, as in Fig. 7 (fig7_report.validity)
        from wrn_validity import run_validity_wrn
        ok, why = run_validity_wrn(s, d, dry=dry)
    else:
        ok, why = run_validity_xb(s, d, dry=dry)
    sw = first(ev, "A", "xb_precopy_switch")
    rowsB = sorted(((int(r["call"]), r) for r in m if r.get("owner") == "B" and r.get("psnr") not in ("", None)), key=lambda x: x[0])
    c1 = rowsB[0][0] if rowsB else None
    k0 = S if S is not None else c1   # k = call - k0 + 1
    ps = {c - k0 + 1: fnum(r["psnr"]) for c, r in rowsB} if k0 is not None else {}
    ss = {c - k0 + 1: fnum(r["ssim"]) for c, r in rowsB} if k0 is not None else {}
    own = {x["call"]: x for x in (frec.get("B") or {}).get("own", [])}
    refB = {x["call"]: x.get("refresh") for x in (frec.get("B") or {}).get("ref", [])}
    tp = {c - k0 + 1: st.median(x["tpsnr"]) for c, x in own.items() if x.get("tpsnr")} if k0 is not None else {}
    bound = own[k0]["tpsnr"][0] if (k0 in own and own[k0].get("tpsnr")) else None
    checks = {"valid_xb": ok, "B_calls_k1_100": all(ps.get(k) is not None for k in range(1, 101)), "fidelity_record": bool(own) or dry}
    if meth in ("otter", "psink"):
        checks["switch_at_S"] = bool(sw) and sw.get("call") == S and not sw.get("switch_call_missed")
    if meth == "otter":
        checks["SINKOK"] = bool(sw) and sw.get("verdict") == "SINKOK"
    if meth == "full":
        checks["bit_exact"] = all((r.get("ref_match") in ("True", "true", True)) or (fnum(r["psnr"]) or 0) >= 99 for _, r in rowsB) and bool(rowsB)
    hi = (k0 + 99) if k0 is not None else None
    dd = decision_divergence({c: x.get("refresh") or [] for c, x in own.items()}, refB, k0, hi) if (own and k0 is not None) else None
    pos_k = next((c - k0 + 1 for c in sorted(own) if k0 <= c <= hi and own[c].get("pos_diff")), None) if own and k0 else None
    blk_k = next((c - k0 + 1 for c in sorted(own) if k0 <= c <= hi and (own[c].get("n_blk_diff") or 0) > 0), None) if own and k0 else None
    rec = {"run": d.name, "exp": d.parent.name, "input": inp, "seed": seed, "S": S, "method": meth, "rep": rep, "valid": all(checks.values()), "checks": checks,
           "validity_why": why, "c0": (sw or {}).get("c0"), "replay_len": (S - sw["c0"]) if (sw and sw.get("c0") is not None and S) else None,
           "psnr": {str(k): v for k, v in ps.items()}, "tpsnr": {str(k): v for k, v in tp.items()},
           "first_psnr": ps.get(1), "W1": wmed(ps, W1), "W2": wmed(ps, W2), "W3": wmed(ps, W3), "term": wmed(ps, TERM),
           "ssim_W1": wmed(ss, W1), "ssim_W2": wmed(ss, W2), "ssim_W3": wmed(ss, W3),
           "t_W1": wmed(tp, W1), "t_W2": wmed(tp, W2), "t_W3": wmed(tp, W3), "t_boundary": bound,
           "div_decision": dd, "div_decision_k": None if dd is None else dd["call"] - k0 + 1, "div_position_k": pos_k, "div_content_k": blk_k,
           "schedule_diverged": (dd is not None) or (pos_k is not None)}
    rec["_refresh_ref"] = refB
    return rec


def ref_margins(recs, inp, seed=None):
    """|min sim - 0.2| of every (call 30-180, layer, row) of the reference logs of one input (one run per seed)."""
    out, seen = [], set()
    for r in recs:
        if r["input"] != inp or (seed is not None and r["seed"] != seed) or r["seed"] in seen or not r["_refresh_ref"]:
            continue
        seen.add(r["seed"])
        for c, lst in r["_refresh_ref"].items():
            if 30 <= int(c) <= 180:
                out += [abs(x[3] - THR) for x in (lst or []) if x[3] is not None]
    return out


def measured_refresh(recs, inp, seed):
    """Sink writes per 100 calls in the reference, calls 30-180 (slot < 3 = a Sink slot), one run of (input, seed)."""
    for r in recs:
        if r["input"] == inp and r["seed"] == seed and r["_refresh_ref"]:
            n = sum(1 for c, lst in r["_refresh_ref"].items() if 30 <= int(c) <= 180 for x in (lst or []) for w in x[6] if w < 3)
            return 100.0 * n / 151.0
    return None


def spearman(x, y):
    def rank(v):
        o = sorted(range(len(v)), key=lambda i: v[i]); rk = [0.0] * len(v); i = 0
        while i < len(o):
            j = i
            while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
                j += 1
            for t in range(i, j + 1):
                rk[o[t]] = (i + j) / 2
            i = j + 1
        return rk
    if len(x) < 3:
        return None
    rx, ry = rank(x), rank(y)
    mx, my = st.mean(rx), st.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return None if den == 0 else num / den


def same_series(a, b):
    ka = set(a["psnr"]) & set(b["psnr"])
    return bool(ka) and all(a["psnr"][k] == b["psnr"][k] for k in ka) and a["div_decision"] == b["div_decision"]


def analyze(recs, dry):
    ot = [r for r in recs if r["method"] == "otter" and r["rep"] == 1]
    rep2 = {(r["input"], r["seed"], r["S"]): r for r in recs if r["method"] == "otter" and r["rep"] == 2}
    full = {(r["input"], r["seed"]): r for r in recs if r["method"] == "full"}
    psk = {r["input"]: r for r in recs if r["method"] == "psink"}
    # evaluable inputs: Full control bit-exact for every seed run, and the repeat equal to rep 1
    evaluable, notes = {}, {}
    for inp in INPUTS:
        why = []
        for sd in (0, 1):
            f = full.get((inp, sd))
            if f is None or not f["valid"]:
                why.append(f"Full s{sd} missing / not exact")
        r1 = next((r for r in ot if r["input"] == inp and r["seed"] == 0 and r["S"] == 74), None)
        r2 = rep2.get((inp, 0, 74))
        if r1 is None or r2 is None or not same_series(r1, r2):
            why.append("repeat missing or differs")
        evaluable[inp] = not why or dry
        notes[inp] = why
    kept = [r for r in ot if r["valid"] and evaluable.get(r["input"])]
    und = [r for r in kept if not r["schedule_diverged"]]
    h1_share = (sum(1 for r in und if (r["W3"] or 0) >= 40) / len(und)) if und else None
    divs = [r["div_decision"] for r in kept if r["div_decision"] is not None]
    pct10 = {}
    for inp in INPUTS:
        mg = sorted(ref_margins(recs, inp))
        pct10[inp] = mg[int(0.1 * (len(mg) - 1))] if mg else None
    cross = [(r, r["div_decision"]) for r in kept if r["div_decision"] is not None]
    h2_hits = [1 for r, dv in cross if dv["class"] in ("dest_only", "ref_only") and dv["margin_ref"] is not None and pct10.get(r["input"]) is not None
               and dv["margin_ref"] < pct10[r["input"]]]
    h2_share = (len(h2_hits) / len(cross)) if cross else None
    rate = {inp: (sum(1 for r in kept if r["input"] == inp and r["schedule_diverged"]) / max(1, sum(1 for r in kept if r["input"] == inp)))
            for inp in INPUTS if any(r["input"] == inp for r in kept)}
    rho = spearman([REFRESH[i] for i in rate], [rate[i] for i in rate])
    # exploratory: near-threshold decision frequency (reference, |min sim - 0.2| < 0.02, calls 30-180) and measured refresh
    near = {inp: (lambda mg: (sum(1 for x in mg if x < 0.02) / len(mg)) if mg else None)(ref_margins(recs, inp)) for inp in rate}
    rho_near = spearman([near[i] for i in rate if near[i] is not None], [rate[i] for i in rate if near[i] is not None])
    meas = {inp: {sd: measured_refresh(recs, inp, sd) for sd in (0, 1)} for inp in INPUTS}
    s01 = [i for i in INPUTS if meas[i][0] is not None and meas[i][1] is not None]
    rho_seeds = spearman([meas[i][0] for i in s01], [meas[i][1] for i in s01])
    h4 = {}
    for inp in INPUTS:
        o = next((r for r in kept if r["input"] == inp and r["seed"] == 0 and r["S"] == 74), None)
        p = psk.get(inp)
        if o and p and p["valid"] and o["W1"] is not None and p["W1"] is not None:
            h4[inp] = (o["W1"], p["W1"])
    F_P = (sum(1 for r in kept if (r["W3"] or 0) >= 40) / len(kept)) if kept else None
    F_T = (sum(1 for r in kept if (r["t_W3"] or 0) >= 40) / len(kept)) if kept else None
    n_expected = sum(len(S_SEED[sd]) for sd in (0, 1)) * len([i for i in INPUTS if evaluable.get(i)])
    ver = {"evaluable_inputs": evaluable, "not_evaluable_why": notes, "n_otter_kept": len(kept), "n_otter_expected": n_expected,
           "F13_H1": {"n_undiverged": len(und), "share_W3_ge_40": h1_share, "holds": h1_share is not None and h1_share >= 0.90},
           "F13_H2": {"n_divergences": len(cross), "share": h2_share, "pct10_margin": pct10, "holds": h2_share is not None and h2_share >= 0.80,
                      "classes": {c: sum(1 for dv in divs if dv["class"] == c) for c in ("dest_only", "ref_only", "slot", "write", "realign")}},
           "F13_H3": {"rate": rate, "rho": rho, "holds": rho is not None and rho >= 0.6, "exploratory_near_threshold": near, "rho_near": rho_near,
                      "measured_refresh_per_100": meas, "rho_seed0_seed1_refresh": rho_seeds},
           "F13_H4": {"pairs": h4, "n_otter_higher": sum(1 for a, b in h4.values() if a > b), "holds": sum(1 for a, b in h4.values() if a > b) >= 8},
           "claim": {"F_P_W3_psnr_ge_40": F_P, "F_T_W3_tpsnr_ge_40": F_T, "schedule_divergence_share": (sum(1 for r in kept if r["schedule_diverged"]) / len(kept)) if kept else None}}
    return ver


def fmt(x, n=1):
    return "-" if x is None else f"{x:.{n}f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--sanity", action="store_true")
    a = ap.parse_args()
    recs = []
    for e in sorted(EVAL.glob(f"{a.prefix}expF13_*")):
        for d in sorted(e.iterdir()):
            if d.is_dir() and (d / "summary.json").exists():
                r = run_record(d, a.dry)
                if r:
                    recs.append(r)
    if a.sanity:
        for r in recs:
            dv = r["div_decision"]
            print(f"== {r['exp']} {r['method']} rep {r['rep']}: {'valid' if r['valid'] else 'INVALID'} {r['validity_why']}")
            print(f"   checks {r['checks']}")
            print(f"   c0 {r['c0']}, replay {r['replay_len']} calls; PSNR first {fmt(r['first_psnr'])}, W1 {fmt(r['W1'])}, W2 {fmt(r['W2'])}, W3 {fmt(r['W3'])}, "
                  f"terminal {fmt(r['term'])}; SSIM W3 {fmt(r['ssim_W3'], 3)}; tPSNR boundary {fmt(r['t_boundary'])}, W1 {fmt(r['t_W1'])}, W3 {fmt(r['t_W3'])}")
            print(f"   Sink divergence k: decision {r['div_decision_k']}, position {r['div_position_k']}, content {r['div_content_k']}; first decision {dv}")
        if not recs:
            print("no Fig. 13 runs found")
    ver = analyze(recs, a.dry)
    OUT.mkdir(parents=True, exist_ok=True)
    pub = [{k: v for k, v in r.items() if not k.startswith("_")} for r in recs]
    (OUT / f"{a.prefix}fig13_results.json").write_text(json.dumps({"verdicts": ver, "runs": pub}, indent=1, default=str))
    L = ["# Fig. 13 results", "", "Rules: `preregistration.md` (DRAFT until frozen). Quality isolation: every OTTER / P-sink run switches at the fixed call S.", "",
         f"F13-H1 {'SUPPORTED' if ver['F13_H1']['holds'] else 'NOT SUPPORTED'} (share {fmt(ver['F13_H1']['share_W3_ge_40'], 3)} of {ver['F13_H1']['n_undiverged']} undiverged); "
         f"F13-H2 {'SUPPORTED' if ver['F13_H2']['holds'] else 'NOT SUPPORTED'} (share {fmt(ver['F13_H2']['share'], 3)} of {ver['F13_H2']['n_divergences']}); "
         f"F13-H3 {'SUPPORTED' if ver['F13_H3']['holds'] else 'NOT SUPPORTED'} (rho {fmt(ver['F13_H3']['rho'], 2)}); "
         f"F13-H4 {'SUPPORTED' if ver['F13_H4']['holds'] else 'NOT SUPPORTED'} ({ver['F13_H4']['n_otter_higher']} / {len(ver['F13_H4']['pairs'])})", "",
         f"Claim rule: F_P = {fmt(ver['claim']['F_P_W3_psnr_ge_40'], 3)}, F_T = {fmt(ver['claim']['F_T_W3_tpsnr_ge_40'], 3)}, schedule divergence share "
         f"{fmt(ver['claim']['schedule_divergence_share'], 3)} (OTTER kept {ver['n_otter_kept']} / {ver['n_otter_expected']})", "",
         "| input | refresh / 100 | seed | S | method | valid | first | W1 | W2 | W3 | terminal | tPSNR bnd | tPSNR W3 | div k (dec / pos / cont) | first decision class |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(recs, key=lambda r: (REFRESH.get(r["input"], 0), r["input"], r["seed"], r["method"], r["S"] or 0, r["rep"] or 0)):
        dv = r["div_decision"]
        L.append(f"| {r['input']} | {REFRESH.get(r['input'])} | {r['seed']} | {r['S'] or '-'} | {r['method']}{'' if r['rep'] in (1, None) else ' r' + str(r['rep'])} | "
                 f"{'yes' if r['valid'] else 'NO'} | {fmt(r['first_psnr'])} | {fmt(r['W1'])} | {fmt(r['W2'])} | {fmt(r['W3'])} | {fmt(r['term'])} | "
                 f"{fmt(r['t_boundary'])} | {fmt(r['t_W3'])} | {r['div_decision_k'] or '-'} / {r['div_position_k'] or '-'} / {r['div_content_k'] or '-'} | "
                 f"{dv['class'] if dv else '-'} |")
    (OUT / f"{a.prefix}fig13_results.md").write_text("\n".join(L) + "\n")
    print("\n".join(L[:6]))


if __name__ == "__main__":
    main()
