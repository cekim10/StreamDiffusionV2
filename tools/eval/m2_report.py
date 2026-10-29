#!/usr/bin/env python3
"""E9 report (osdi/m1_continuity/e9_plan.md): per run (baseline, m2) and per migration (1: A -> B, 2: B -> A) the base
mode and bytes, readiness, interruption, reconstruction, digests, fallbacks, tracking and retention, continuity, and the
equivalence checks between the two runs.

    python tools/eval/m2_report.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/evaluation/osdi/m1_continuity"


ROOTS = {}


def load(name):
    d = sorted((Path(ROOTS[name]) if name in ROOTS else ROOT / f"results/evaluation/expM2E9_{name}").glob("policy=*"))
    if not d:
        return None
    d = d[-1]
    ev = []
    for r in csv.DictReader(open(d / "events.csv", newline="")):
        ev.append({"t": float(r["t_rel"]) if r["t_rel"] not in ("", None) else None, "event": r["event"], **(json.loads(r["detail"]) if r["detail"] else {})})
    mt = list(csv.DictReader(open(d / "metrics.csv", newline="")))
    return {"dir": d, "summary": json.load(open(d / "summary.json")), "ev": ev, "mt": mt}


def migration(R, k):
    src, dst = (("A", "B") if k == 1 else ("B", "A"))
    ev, mt = R["ev"], R["mt"]
    first = lambda name, after=-1e9: next((e for e in ev if e["event"] == name and (e["t"] or -1e9) >= after), None)  # noqa: E731
    starts = [e for e in ev if e["event"] == "xb_task_start"]
    t0 = starts[k - 1]["t"] if len(starts) >= k else None
    sw = first(f"{src}:xb_precopy_switch", t0 or 0)
    M = int(sw["call"]) if sw else None
    base_sent = first(f"{src}:replay_base_sent", t0 or 0)
    rb = first(f"{dst}:replay_base", t0 or 0) or None
    rdb = first(f"{dst}:replay_delta_base", t0 or 0) or None
    ready = first(f"{src}:replay_ready", t0 or 0)
    ssc = first(f"{dst}:sink_sync_check", t0 or 0)
    res = first(f"{dst}:resume", t0 or 0)
    fo = first(f"{dst}:first_output", t0 or 0)
    rounds = [e for e in ev if e["event"] == f"{src}:xb_precopy_round" and (e["t"] or 0) >= (t0 or 0) and (sw is None or e["t"] <= sw["t"])]
    src_t = [float(m["t_out_rel"]) for m in mt if m["owner"] == src and M is not None and int(m["call"]) < M and (k == 1 or int(m["call"]) >= 64)]
    base_t = (rdb["t"] if (rdb and rdb.get("accepted")) else (rb["t"] if rb else None))
    out = {"src": src, "dst": dst, "M": M, "planned": sw and sw.get("switch_call_planned"), "missed": sw and sw.get("switch_call_missed"),
           "base_mode": base_sent and base_sent.get("mode"), "base_bytes": base_sent and base_sent.get("bytes"), "base_fallback_reason": base_sent and base_sent.get("fallback_reason"),
           "delta": None if not base_sent or base_sent.get("delta_entries") is None else {k_: base_sent.get(k_) for k_ in ("delta_entries", "delta_shifts", "delta_value_bytes", "delta_verdict", "delta_verdict_wait_s", "tracked_calls", "track_s")},
           "delta_rebuild": None if not rdb else {k_: rdb.get(k_) for k_ in ("accepted", "digest_equal", "n_block_mismatch", "positions_equal", "retained_h2d_s", "rebuild_s", "digest_s", "total_s", "mismatched_blocks")},
           "round_bytes": [e.get("dirty_bytes") for e in rounds], "log_bytes": sw and sw.get("log_bytes"), "patch_bytes": sw and sw.get("patch_bytes"), "patches": sw and sw.get("patches"),
           "final_bytes": sw and sw.get("final_bytes"), "cutover_verdict": sw and sw.get("verdict"), "cutover_digest_equal": ssc and ssc.get("match"),
           "fallback_bytes": sw and sw.get("fallback_bytes"), "retained": sw and sw.get("retained"), "retained_bytes": sw and sw.get("retained_bytes"), "retain_s": sw and sw.get("retain_s"),
           "t_task_start": t0, "base_ready_s": None if base_t is None or t0 is None else base_t - t0, "readiness_s": None if not ready or t0 is None else ready["t"] - t0,
           "ready_call": ready and ready.get("call"), "ready_wait_s": sw and sw.get("ready_wait_s"),
           "interruption_s": None if not fo or not src_t else fo["t"] - max(src_t), "stop_to_first_output_s": None if not (fo and sw) else fo["t"] - (sw["t"] - float(sw.get("stop_to_sent_s") or 0)),
           "restore_s": res and res.get("restore_s"), "dr2_s": res and res.get("dr2_s"), "n_replayed": res and res.get("n_replayed"), "tracking_started": res and res.get("tracking_version")}
    out["total_bytes"] = sum(int(x or 0) for x in out["round_bytes"]) + int(out["log_bytes"] or 0) + int(out["final_bytes"] or 0)
    return out


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", default=None); ap.add_argument("--m2", default=None); ap.add_argument("--out", default=str(OUT / "e9_report.json"))
    args = ap.parse_args()
    if args.baseline:
        ROOTS["baseline"] = args.baseline
    if args.m2:
        ROOTS["m2"] = args.m2
    rep = {}
    for name in ("baseline", "m2"):
        R = load(name)
        if R is None:
            rep[name] = {"error": "run missing"}; continue
        v = R["summary"]["validation"]
        rep[name] = {"run": R["dir"].name, "validation": {k: v[k] for k in v if k != "gpu0_before_run"}, "migrations": [migration(R, 1), migration(R, 2)]}
        for k in (1, 2):
            f = OUT / f"e9_metrics_{name}_mig{k}.json"
            if f.exists():
                m = next(iter(json.load(open(f))["runs"].values()))
                rep[name]["migrations"][k - 1]["continuity"] = {x: m.get(x) for x in ("M", "rules", "v1_reset", "v1_reset_ref_same_call", "D_c", "C_c", "warp_excess", "frame_diff_ratio", "stores")}
        rep[name]["psnr_B"] = {int(m["call"]): m["psnr"] for m in R["mt"] if m["owner"] == "B"}
    if "psnr_B" in rep.get("baseline", {}) and "psnr_B" in rep.get("m2", {}):
        a, b = rep["baseline"]["psnr_B"], rep["m2"]["psnr_B"]
        common = sorted(set(a) & set(b))
        rep["equivalence"] = {"B_calls_compared": len(common), "B_psnr_equal_every_call": all(a[c] == b[c] for c in common)}
    for name in ("baseline", "m2"):
        rep.get(name, {}).pop("psnr_B", None)
    Path(args.out).write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps(rep, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
