#!/usr/bin/env python3
"""Judge the Experiment D focused correctness tests (results/evaluation/expD_correctness/) against conditions written
before the runs (results/evaluation/osdi/expD/correctness_conditions.md). Correctness only: these are not G1-G9
criteria and no Experiment D outcome is computed here. Writes results/evaluation/osdi/expD/correctness_check.md;
exits non-zero on any failure.

Every run: version events 0; duplicates 0 (orchestrator and node logs); NIC peaks <= 1.15 x the cap (1 Gbps; unshaped:
the 9.4 Gbps NIC); paced payload egress <= 1.05 x cap in every 10 s window (shaped runs); GPU 0 idle before the run; four distinct
hosts on one commit; stop reason not deadline / window_exhausted; per-move timing non-negative (resume <= first
output); the final owner keeps generating (>= min(8, tail_calls) chunks after the final move); NIC-measured egress of every node within [0.97, 1.12] x the bytes the run
accounts to it (fragments + execution state) when that is >= 100 MiB.
By capability:
  full      state digests of every component match; the Sink component's digest equals the source manifest's; every
            chunk after resume bit-exact (>= 99 dB); the completed transfer carries the whole packed state; a redirected
            (cancelled) transfer's partial state is discarded at its receiver; resume after the completing transfer ends
  cold      no Sink fragment, no execution state and no in-flight rows sent; a PSNR value for every produced chunk;
            first output within 3 chunks of the resume
  revisit   M1 only: the revisited owner held nothing on return and received again every fragment it had verified;
            progress-preserving policies: everything verified before leaving still held on return, nothing received
            again; Sink verified with the source digest and bound at the revisited owner; rejoin >= 35 dB
  hybrid    the GPU session restores (digest, bind, rejoin >= 35 dB); every network session restored at the final
            owner; combined source-A payload (GPU + network sessions) <= 1.05 x cap in every 10 s window; network
            sessions' paced egress valid; GPU session's median chunk time within 5 % of the node's baseline service time
  colddest  the destination process started after the trigger; reference frames available before the first output;
            TTFO from the trigger > runtime-ready time > process start >= 0; Sink verified with the source digest,
            bound, rejoin >= 35 dB
  fast M1-family runs (every non-full, non-cold run): all fragments verified, final Sink digest = source digest, rejoin >= 35 dB
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAP = 1000.0
DRY = False   # --dry: loopback protocol test (no NIC counters, one host): NIC and host checks skipped


def nic_tx_bytes(run: Path, lb: str, t0: float, t1: float) -> float | None:
    f = run / f"node_{lb}" / "network.csv"
    if not f.exists():
        return None
    rows = [r for r in csv.DictReader(open(f)) if r["net_tx_mbps"]]
    tot, prev = 0.0, None
    for r in rows:
        t = float(r["t_wall"])
        if prev is not None and t0 <= t <= t1:
            tot += float(r["net_tx_mbps"]) * 1e6 / 8 * (t - prev)
        prev = t
    return tot


def kind(s):
    rid = s["run_id"]
    if "_colddest" in rid:
        return "colddest"
    if "_hybrid=" in rid:
        return "hybrid"
    if s["policy"] in ("full", "cold"):
        return s["policy"]
    if s.get("revisit"):
        return "revisit"
    return "fast"


def check(run: Path):
    s = json.load(open(run / "summary.json"))
    v, z, c = s["validation"], s["d0"], s["continuity"]
    k = kind(s)
    cap = s["bw_mbps"] if s["bw_mbps"] > 0 else (CAP if DRY else 9400.0)   # unshaped: the physical NIC (Phase 0: ~9.4 Gbps)
    chk = {}
    chk["version events 0"] = z["version_events"] == 0
    node_dups = 0
    for f in run.glob("node_*/fragments.csv"):
        node_dups += sum(1 for r in csv.DictReader(open(f)) if r["event"] == "recv" and r["ok"] == "False")
    chk["duplicates 0"] = s["bytes"]["duplicate"] == 0 and node_dups == 0
    nic = [x for d in (v["nic_rx_peak_mbps_by_node"], v["nic_tx_peak_mbps_by_node"]) for x in d.values() if x is not None]
    if not DRY:
        chk["NIC <= 1.15 cap"] = bool(nic) and max(nic) <= 1.15 * cap
    chk["four hosts, one commit"] = (DRY or v["four_hosts_distinct"]) and v.get("nodes_same_commit") is True
    chk["stop reason"] = not str(v["stop_reason"]).startswith(("deadline", "window_exhausted"))
    if v.get("paced_egress_10s_within_cap") is not None:
        chk["paced egress 10 s <= 1.05 cap"] = v["paced_egress_10s_within_cap"]
    if not DRY:
        chk["GPU 0 idle before run"] = v.get("gpu0_idle_before_run") is True
    pm = s["per_move"]
    chk["per-move timing"] = all((m["resume_s"] is None or m["resume_s"] >= 0) and (m["first_output_s"] is None or (m["resume_s"] is not None and m["first_output_s"] >= m["resume_s"])) for m in pm)
    fin_rows = [r for r in csv.DictReader(open(run / "metrics.csv")) if r["owner"] == s["path"][-1] and float(r["t_out_rel"]) >= s["t_final_move_rel_s"] and r["missing"] == "False"]
    tail = json.load(open(run / "config.json"))["args"].get("tail_calls", 12)
    chk["final owner keeps generating"] = len(fin_rows) >= min(8, tail)
    # NIC-measured egress vs accounted bytes per node (fragments + execution state + in-flight rows)
    ev = list(csv.DictReader(open(run / "events.csv")))
    t0 = float(next(e for e in ev if e["event"] == "migration_start")["t_wall"])
    acc = defaultdict(float)
    for src_dst, b in s["bytes"]["by_link"].items():
        acc[src_dst.split("->")[0]] += b
    for x in s["execution_state"]["state_transfers"]:
        acc[x["src"]] += x.get("bytes") or 0
    for m in s["moves"]:
        acc[m["from"]] += m.get("fg_bytes") or 0
    ratios = {}
    if k != "hybrid" and not DRY:   # hybrid: the restore nodes share the NICs; checked on the combined source egress instead
        for lb, b in acc.items():
            if b >= 100 * 2**20:
                nb = nic_tx_bytes(run, lb, t0 - 2, t0 + 3600)
                ratios[lb] = None if nb is None else nb / b
        chk["NIC egress vs accounted"] = all(r is not None and 0.97 <= r <= 1.12 for r in ratios.values())
    es = s["execution_state"]
    if k == "full":
        done = [x for x in es["state_transfers"] if x.get("completed")]
        chk["state digests ok"] = v["full_state_digests_ok"] is True
        chk["Sink digest = manifest"] = v["final_sink_digest_matches_source"] is True
        chk["bit-exact after resume"] = v["full_bit_exact_after_resume"] is True
        chk["completed transfer = whole state"] = len(done) == 1 and done[0].get("bytes") == es["packed_state_bytes"] == done[0].get("state_bytes")
        cancelled = [x for x in es["state_transfers"] if not x.get("completed") and (x.get("bytes") or 0) >= 8 * 2**20]
        aborted = {json.loads(e["detail"]).get("xfer") for e in ev if e["event"].endswith(":full_recv_aborted")}
        chk["redirect discards partial state"] = all(x["xfer"] in aborted for x in cancelled) and not any(x["xfer"] in aborted for x in done)
        fin_pm = pm[-1]
        chk["resume after transfer end"] = fin_pm["resume_s"] is not None and fin_pm["state_transfer"] and fin_pm["resume_s"] >= (fin_pm["state_transfer"]["end_s"] or 0) - 0.5
    elif k == "cold":
        chk["no state sent"] = v["cold_no_state_transferred"] is True and s["bytes"]["total_sent"] == 0
        produced = [r for r in csv.DictReader(open(run / "metrics.csv")) if r["missing"] == "False" and float(r["t_out_rel"]) >= 0 and r["owner"] != "A"]
        chk["PSNR for every produced chunk"] = bool(produced) and all(r["psnr"] not in ("", "None") for r in produced)
        chk["first output within 3 chunks of resume"] = all(m["first_output_s"] is not None and m["first_output_s"] - m["resume_s"] <= 3 * 0.6 for m in pm)
    else:
        chk["all fragments verified"] = v["all_fragments_verified"] is True
        chk["final Sink digest = source"] = v["final_sink_digest_matches_source"] is True
        chk["rejoin >= 35 dB"] = (c.get("psnr_after_rejoin_mean") or 0) >= 35
    pp = z.get("prepos")
    if pp and pp.get("frags"):
        # (added 2026-10-17 after the testbed run, see correctness_conditions.md) placement fragments reach the candidates
        top = max(pp["alloc_sinks"], key=pp["alloc_sinks"].get)
        want = pp["frags"].get(top, 0)
        got = round(z["x_verified_at_move"].get(top, 0) * s["n_frags"])
        chk["placement delivered (allocation - max(2, 5 %) fragments)"] = want == 0 or got >= want - max(2, 0.05 * want)
    if k == "revisit":
        r = s["revisit"]
        if s["policy"] == "restart":
            chk["M1 only: nothing held on return"] = r["held_on_return_policy_view"] == 0 and r["verified_before_leaving_still_held_on_return"] in (0, 0.0)
            chk["M1 only: re-received"] = r["fragments_received_again_after_return"] >= round(r["verified_before_leaving"] * s["n_frags"]) - 1
        else:
            chk["preserved on return"] = r["verified_before_leaving_still_held_on_return"] == 1.0 and r["fragments_received_again_after_return"] == 0
    if k == "hybrid":
        h = s["hybrid"]; ns = h["network_summary"]
        chk["network sessions restored"] = ns["restored_sessions"] == h["n_network_sessions"] and all(x.get("t_r_s") not in (None, "") for x in h["network_sessions"])
        chk["network pacing valid"] = bool(ns["validation"].get("paced_egress_within_cap")) and bool(ns["validation"].get("all_fragments_verified"))
        bins = defaultdict(int)
        for r in csv.DictReader(open(run / "fragments.csv")):
            if r["event"] == "sent" and r["src"] == "A":
                bins[int(float(r["t_rel"]) // 10)] += int(r["bytes"])
        nd = next((ROOT / h["network_run_dir"]).glob("node_A/fragments.csv"), None)
        for r in csv.DictReader(open(nd)) if nd else []:
            if r["event"] == "sent":
                bins[int((float(r["t"]) - t0) // 10)] += int(r["bytes"])
        full_bins = [b for k_, b in bins.items() if k_ >= 0 and (k_ + 1) * 10 <= max(bins) * 10]
        chk["combined A payload <= 1.05 cap / 10 s"] = all(b * 8 / 10 / 1e6 <= 1.05 * cap for b in full_bins)
        svc = json.load(open(run / "host_info.json"))[s["path"][-1]]["hello"].get("service_s")
        chunk = sorted(float(r["chunk_s"]) for r in fin_rows if r["chunk_s"])
        chk["GPU chunk time unaffected (5 %)"] = bool(svc) and bool(chunk) and abs(chunk[len(chunk) // 2] - svc) <= 0.05 * svc
    if k == "colddest":
        cd = s["cold_destination"]
        chk["process started after trigger"] = cd["process_launch_s"] is not None and cd["process_launch_s"] >= 0 and cd["process_start_s"] >= 0
        chk["TTFO > runtime ready > process start"] = cd["ttfo_s"] > cd["runtime_ready_s"] > cd["process_start_s"]
        chk["reference from cache"] = DRY or str(cd.get("reference", "")).endswith(".npz")
    bad = [x for x, ok in chk.items() if not ok]
    row = f"| {k} | {s['policy']} | {s['run_id'][-15:]} | {len(chk) - len(bad)}/{len(chk)} | {'PASS' if not bad else 'FAIL: ' + '; '.join(bad)} |"
    return row, bad, {"run": run.name, "kind": k, "checks": chk, "nic_ratio": ratios}


def main():
    global DRY, CAP
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    if "--dry" in sys.argv:
        DRY, CAP = True, 100.0
    exp = args[0] if args else "expD_correctness"
    runs = sorted((ROOT / "results/evaluation" / exp).glob("policy=*"), key=lambda p: p.name[-15:])
    rows, fails, detail = [], [], []
    for r in runs:
        if not (r / "summary.json").exists():
            rows.append(f"| - | - | {r.name[-15:]} | - | INCOMPLETE (no summary.json) |"); fails.append(r.name); continue
        if "per_move" not in json.load(open(r / "summary.json")):
            continue   # written by the harness before the Experiment D capabilities (not a test of them)
        row, bad, det = check(r)
        rows.append(row); detail.append(det)
        if bad:
            fails.append(r.name)
    out = ["# Experiment D focused correctness - check", "", f"`{exp}`; conditions in the docstring of `tools/eval/check_expD_correctness.py` (written before the runs).", "",
           "| capability | policy | run | checks passed | verdict |", "|---|---|---|---|---|"] + rows + ["", f"{len(runs)} runs; {len(fails)} failing.", "",
           "Per-run checks:", "```", json.dumps(detail, indent=1, default=str), "```"]
    p = ROOT / "results/evaluation/osdi/expD" / f"correctness_check_{exp}.md"; p.parent.mkdir(parents=True, exist_ok=True); p.write_text("\n".join(out) + "\n")
    print("\n".join(out[:len(rows) + 8]))
    sys.exit(1 if fails or not runs else 0)


if __name__ == "__main__":
    main()
