#!/usr/bin/env python3
"""XB calibration (osdi/expXB/preregistration.md section 4): full grid table, selection rules 1-5, alternative min-gap
settings and the R-win W trade-off. Calibration runs are never evidence for XH1-XH5.

    python tools/eval/aggregate_xb_cal.py [--dry]      # -> results/evaluation/osdi/expXB/calibration_{grid.md,selection.json}

Rules as fixed in the draft:
 1 eligibility: valid run that passes its class check (P-full: all five component digests at the switchover and the
   first post-switchover call bit-exact; P-sink: Sink / in-flight / meta digests at the switchover; R-full: inputs
   bit-exact and the first post-resume call bit-exact; R-win: valid).
 2 P-full, P-sink, R-full: smallest TTFO-local; settings within 5 % of the smallest are tied; ties -> smallest delivery
   gap -> fewest remote-served chunks -> smaller threshold (R-full: lag) -> smaller round limit.
 3 R-win: among W whose terminal PSNR is within 1.0 dB of the best W, the smallest TTFO-local.
 4 alternative: the eligible setting with the smallest delivery gap (settings within 5 % of it tied; ties -> smallest
   TTFO-local -> fewest remote chunks -> smaller parameters); run in XB1 only where it differs from the selected one.
 5 jitter: a selected setting whose repeats differ from its first run by > 10 % in TTFO-local triggers re-calibration of
   that method with 3 runs per setting; then the per-setting median decides.
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
from xb_delivery import delivery_metrics, load_run  # noqa: E402
from xb_validity import run_validity_xb  # noqa: E402

METHODS = ("precopy_full", "precopy_sink", "recompute_full", "recompute_win")
LABEL = {"precopy_full": "P-full", "precopy_sink": "P-sink", "recompute_full": "R-full", "recompute_win": "R-win"}


def setting_of(pol, xp):
    if pol.startswith("precopy"):
        return f"thr={xp['threshold_mib']:g}:rl={xp['round_limit']}"
    if pol == "recompute_full":
        return f"lag={xp['lag']}:rl={xp['round_limit']}"
    return f"W={xp['W']}"


def sort_params(pol, setting):
    kv = dict(x.split("=") for x in setting.split(":"))
    return tuple(float(kv[k]) for k in (("thr", "rl") if pol.startswith("precopy") else ("lag", "rl") if pol == "recompute_full" else ("W",)))


def run_record(d: Path, dry: bool) -> dict:
    s, m, ev = load_run(d)
    pol = s["policy"]
    valid, why = run_validity_xb(s, d, dry=dry)
    D = delivery_metrics(s, m, ev)
    eq = D["output_equivalence"][-1] if D["output_equivalence"] else {}
    v = s["validation"]
    if pol == "precopy_full":
        sv = [e for e in ev if e["event"] == "xb_switch_verified"]
        comps = sv[-1].get("components_ok", {}) if sv else {}
        cls_ok = bool(comps) and set(comps) == {"inflight", "meta", "recent", "sink", "vae"} and all(comps.values()) and eq.get("first_call_match") is True
    elif pol == "precopy_sink":
        sv = [e for e in ev if e["event"] == "xb_switch_verified"]
        comps = sv[-1].get("components_ok", {}) if sv else {}
        cls_ok = bool(comps) and {"sink", "inflight", "meta"} <= set(comps) and all(comps.values())
    elif pol == "recompute_full":
        cls_ok = v.get("inputs_exact_at_switchovers") is True and eq.get("first_call_match") is True
    else:
        cls_ok = True
    rounds = [e for e in ev if e["event"] in ("xb_precopy_round", "xb_recompute_round")]
    sw = next((e for e in ev if e["event"] == "xb_precopy_switch"), {})
    fin = next((e for e in s.get("tasks", []) if e.get("outcome") == "switched"), {})
    est = D["remote_delivery_bytes_ESTIMATED"]
    inp = s.get("inputs") or {}
    return {"run": d.name, "policy": pol, "setting": setting_of(pol, s["xb_params"]), "rep": s.get("rep"), "valid": valid, "invalid_why": why, "class_ok": cls_ok,
            "eligible": valid and cls_ok, "ttfo_local_s": D["ttfo_local_final_s"], "delivery_gap_s": D["delivery_gap_s"], "remote_chunks": D["remote_chunks"],
            "remote_wall_s": D["remote_wall_s"], "est_bytes_crf23": est["crf23"], "est_bytes_crf28": est["crf28"],
            "rounds": len(rounds), "dirty_mib_per_round": [round((e.get("dirty_bytes") or 0) / 2 ** 20) for e in rounds if e["event"] == "xb_precopy_round"],
            "switch_reason": sw.get("reason") or fin.get("finish_reason"), "final_bytes_mib": round((sw.get("final_bytes") or 0) / 2 ** 20) if sw else None,
            "input_bytes_mib": round((inp.get("bytes_sent") or 0) / 2 ** 20) if inp else None, "input_raw_mib": round((inp.get("raw_bytes") or 0) / 2 ** 20) if inp else None,
            "out_eq": f"{eq.get('matching')}/{eq.get('checked')}" if eq else None, "first_call_match": eq.get("first_call_match"),
            "terminal_psnr": D["trajectory_final"]["terminal_median_psnr"], "first_ge35_idx": D["trajectory_final"]["first_ge35_idx"],
            "sustained10_idx": D["trajectory_final"]["sustained10_idx"], "rtt_ms": (s.get("rtt_measured_lan") or {}).get("A-B", {}).get("median_ms")}


def med(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else None


def per_setting(recs, use_median: bool):
    """setting -> representative record: rep 1 (or the median over reps if the method was re-calibrated, rule 5)."""
    by = defaultdict(list)
    for r in recs:
        by[r["setting"]].append(r)
    out = {}
    for k, rs in by.items():
        rs = sorted(rs, key=lambda r: r["rep"] or 0)
        if use_median:
            el = [r for r in rs if r["eligible"]]
            if not el:
                out[k] = {**rs[0], "eligible": False}; continue
            out[k] = {**el[0], "ttfo_local_s": med(r["ttfo_local_s"] for r in el), "delivery_gap_s": med(r["delivery_gap_s"] for r in el),
                      "remote_chunks": med(r["remote_chunks"] for r in el), "terminal_psnr": med(r["terminal_psnr"] for r in el), "n_reps": len(el)}
        else:
            r1 = next((r for r in rs if r["rep"] == 1), rs[0])
            out[k] = {**r1, "n_reps": 1}
    return out


def pick(pol, cands: dict, primary: str, secondary: str):
    el = {k: r for k, r in cands.items() if r["eligible"] and r[primary] is not None}
    if not el:
        return None
    best = min(r[primary] for r in el.values())
    tied = [k for k, r in el.items() if r[primary] <= 1.05 * best]
    return min(tied, key=lambda k: (el[k][secondary] if el[k][secondary] is not None else float("inf"), el[k]["remote_chunks"], sort_params(pol, k)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--exp", default="expXB_cal")
    a = ap.parse_args()
    root = ROOT / "results/evaluation" / (("_dryrun_" if a.dry else "") + a.exp)
    recs = [run_record(d, a.dry) for d in sorted(root.glob("policy=*")) if (d / "summary.json").exists()]
    out = ROOT / "results/evaluation/osdi/expXB"
    sel_path = out / ("_dryrun_calibration_selection.json" if a.dry else "calibration_selection.json")
    prev = json.loads(sel_path.read_text()) if sel_path.exists() else {}
    sel, L = {}, [f"# XB calibration grid{' (DRY RUN, not a result)' if a.dry else ''}", "",
                  "Setting: XB1 (A -> B, trigger chunk 30, 1 Gbps, dog, seed 0). Calibration runs are not evidence for XH1-XH5.",
                  "TTFO-local, delivery gap, remote-served chunks and RTT are measured. Delivery bytes are ESTIMATED (H.264 size of remotely served output; not transmitted).", ""]
    for pol in METHODS:
        rs = [r for r in recs if r["policy"] == pol]
        if not rs:
            continue
        nreps = defaultdict(int)
        for r in rs:
            nreps[r["setting"]] += 1
        recal = bool(prev.get(pol, {}).get("jitter_recalibrate")) and min(nreps.values()) >= 3
        reps = per_setting(rs, recal)
        if pol == "recompute_win":
            el = {k: r for k, r in reps.items() if r["eligible"] and r["terminal_psnr"] is not None}
            best_q = max((r["terminal_psnr"] for r in el.values()), default=None)
            ok = [k for k, r in el.items() if best_q is not None and r["terminal_psnr"] >= best_q - 1.0]
            chosen = min(ok, key=lambda k: (el[k]["ttfo_local_s"], sort_params(pol, k))) if ok else None
            alt = pick(pol, reps, "delivery_gap_s", "ttfo_local_s")
        else:
            chosen = pick(pol, reps, "ttfo_local_s", "delivery_gap_s")
            alt = pick(pol, reps, "delivery_gap_s", "ttfo_local_s")
        # rule 5: jitter of the selected setting's repeats vs its first run
        jitter = None
        if chosen:
            cr = sorted((r for r in rs if r["setting"] == chosen), key=lambda r: r["rep"] or 0)
            r1 = cr[0]["ttfo_local_s"] if cr else None
            reps_t = [r["ttfo_local_s"] for r in cr[1:] if r["ttfo_local_s"] is not None]
            if r1 and reps_t:
                jitter = max(abs(t - r1) / r1 for t in reps_t)
        sel[pol] = {"selected": chosen, "alternative_min_gap": alt, "alternative_differs": alt is not None and alt != chosen, "n_repeats_of_selected": len([r for r in rs if r["setting"] == chosen]) - 1 if chosen else 0,
                    "max_rel_jitter_ttfo": jitter, "jitter_recalibrate": bool(prev.get(pol, {}).get("jitter_recalibrate")) or (jitter is not None and jitter > 0.10),
                    "decided_by_median_over_reps": recal}
        L += [f"## {LABEL[pol]}: selected {chosen or 'NONE ELIGIBLE'}; alternative (min delivery gap) {alt}" + (" (differs: run in XB1, rule 4)" if sel[pol]["alternative_differs"] else ""), "",
              f"Jitter of the selected setting's repeats: {'-' if jitter is None else f'{100 * jitter:.1f} %'}" + (" -> re-calibration with 3 runs per setting (rule 5)" if sel[pol]["jitter_recalibrate"] else ""), "",
              "| setting | rep | valid | class check | TTFO-local (s) | delivery gap (s) | remote chunks | remote wall (s) | est. delivery CRF 23 / 28 (KB) | rounds | dirty MiB per round | switch / finish reason | inputs FFV1 / raw (MiB) | output equivalence | terminal PSNR | first >= 35 dB idx | sustained 10 idx |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        f = lambda x, n=2: "-" if x is None else (f"{x:.{n}f}" if isinstance(x, float) else str(x))  # noqa: E731
        for r in sorted(rs, key=lambda r: (sort_params(pol, r["setting"]), r["rep"] or 0)):
            L.append(f"| {r['setting']}{' **(selected)**' if r['setting'] == chosen else ''} | {r['rep']} | {r['valid']}{'' if r['valid'] else ' ' + '; '.join(r['invalid_why'])} | {r['class_ok']} | {f(r['ttfo_local_s'])} | {f(r['delivery_gap_s'])} | "
                     f"{r['remote_chunks']} | {f(r['remote_wall_s'], 1)} | {r['est_bytes_crf23'] // 1000} / {r['est_bytes_crf28'] // 1000} | {r['rounds']} | {r['dirty_mib_per_round'] or '-'} | {r['switch_reason']} | "
                     f"{f(r['input_bytes_mib'])} / {f(r['input_raw_mib'])} | {r['out_eq']} | {f(r['terminal_psnr'], 1)} | {f(r['first_ge35_idx'])} | {f(r['sustained10_idx'])} |")
        if pol == "recompute_win":
            L += ["", "R-win latency-quality trade-off (all W; rule 3 keeps W within 1.0 dB of the best terminal PSNR, then the smallest TTFO-local):", "",
                  "| W | TTFO-local (s) | delivery gap (s) | remote chunks | terminal PSNR (dB) | first >= 35 dB idx | sustained 10 idx |", "|---|---|---|---|---|---|---|"]
            for k in sorted(reps, key=lambda k: sort_params(pol, k)):
                r = reps[k]
                L.append(f"| {k[2:]} | {f(r['ttfo_local_s'])} | {f(r['delivery_gap_s'])} | {r['remote_chunks']} | {f(r['terminal_psnr'], 1)} | {f(r['first_ge35_idx'])} | {f(r['sustained10_idx'])} |")
        L.append("")
    rtts = [r["rtt_ms"] for r in recs if r["rtt_ms"] is not None]
    L += [f"Measured LAN RTT A-B (TCP echo, median per run): {'-' if not rtts else f'{min(rtts):.2f}-{max(rtts):.2f} ms'}; WAN / radio latency is not emulated or measured.",
          "", f"Runs: {len(recs)} ({sum(r['valid'] for r in recs)} valid, {sum(r['eligible'] for r in recs)} eligible)."]
    sel_path.write_text(json.dumps(sel, indent=1))
    (out / ("_dryrun_calibration_grid.md" if a.dry else "calibration_grid.md")).write_text("\n".join(L) + "\n")
    print("\n".join(L)); print(json.dumps(sel, indent=1))


if __name__ == "__main__":
    main()
