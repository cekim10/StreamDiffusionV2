"""Delivery accounting for Experiment XB (osdi/expXB/preregistration.md sections 2 and 2.1).

Per run, from the delivered-chunk log (orchestrator metrics: call, owner, t_out_rel relative to the trigger) and the
user's edge over time (trigger: edges[1]; each move: its `to`):

- TTFO-local per move: from the move (trigger for the first) until the user's current edge delivers its first chunk;
  None (censored) if it delivers none before the next move or the end of the run.
- delivery gap: the longest interval with no chunk delivered from any host, from the trigger to the last delivered chunk.
- remote serving: chunks delivered by a host other than the user's current edge; their content time (4 frames at 16 fps
  per chunk) and wall time (per stretch: from the edge change to the stretch's last remote chunk).
- ESTIMATED remote delivery bytes: the H.264 CRF 23 (reported) and CRF 28 (sensitivity) sizes of the remotely served
  chunks, encoded live by the serving node (`xb_delivery_enc` events). The output stream is not transmitted on the
  testbed, so these are estimates; they are kept apart from the MEASURED transmitted bytes (state, inputs).
- measured LAN RTT between the hosts (summary `rtt_measured_lan`); WAN / radio latency is not emulated or measured.
- output equivalence: per owner after its switchover, how many delivered calls match the reference bit for bit.
- trajectory: PSNR after the final switchover (first call >= 35 dB, sustained 10 calls, terminal median of the last 10).
"""

from __future__ import annotations

import csv
import json
import statistics as st
from pathlib import Path

CHUNK_CONTENT_S = 4 / 16
REJOIN_DB = 35.0


def _f(v):
    try:
        return None if v in (None, "", "None") else float(v)
    except (TypeError, ValueError):
        return None


def _b(v):
    return True if v in (True, "True", "true") else False if v in (False, "False", "false") else None


def load_run(run_dir: Path | str):
    """(summary, metrics rows, node events) of a run directory, in the orchestrator's in-memory shapes."""
    d = Path(run_dir)
    s = json.load(open(d / "summary.json"))
    m = list(csv.DictReader(open(d / "metrics.csv", newline="")))
    ev = []
    for r in csv.DictReader(open(d / "events.csv", newline="")):
        if ":" in r["event"]:
            node, name = r["event"].split(":", 1)
            ev.append({"node": node, "event": name, "t": float(r["t_wall"]), **(json.loads(r["detail"]) if r["detail"] else {})})
    return s, m, ev


def delivery_metrics(s: dict, metrics: list[dict], node_events: list[dict]) -> dict:
    path = s["path"]
    changes = [(0.0, path[1])] + [(float(mv["t_req"]), mv["to"]) for mv in s.get("moves", []) if mv.get("i", 1) > 1 and mv.get("t_req") is not None]
    changes.sort()

    def edge_at(t):
        e = changes[0][1]
        for tc, to in changes:
            if t >= tc:
                e = to
        return e

    rows = sorted(({"call": int(r["call"]), "owner": r["owner"], "t": _f(r["t_out_rel"]), "psnr": _f(r.get("psnr")), "ref_match": _b(r.get("ref_match"))}
                   for r in metrics if _f(r.get("t_out_rel")) is not None and str(r.get("missing")) not in ("True", "true")), key=lambda x: x["t"])
    rows = [r for r in rows if r["t"] >= 0]
    for r in rows:
        r["edge"] = edge_at(r["t"]); r["remote"] = r["owner"] != r["edge"]
    t_end = rows[-1]["t"] if rows else None
    # TTFO-local per edge change
    ttfo = []
    for i, (tc, to) in enumerate(changes):
        nxt = changes[i + 1][0] if i + 1 < len(changes) else float("inf")
        first = next((r for r in rows if r["owner"] == to and tc <= r["t"] < nxt), None)
        ttfo.append({"edge": to, "t_change": tc, "ttfo_local_s": None if first is None else first["t"] - tc, "first_call": None if first is None else first["call"]})
    # delivery gap
    ts = [0.0] + [r["t"] for r in rows]
    gaps = [b - a for a, b in zip(ts, ts[1:])]
    gap_i = max(range(len(gaps)), key=lambda i: gaps[i]) if gaps else None
    # remote serving and estimated bytes
    enc = {(e["node"], int(e["call"])): e for e in node_events if e.get("event") == "xb_delivery_enc"}
    remote = [r for r in rows if r["remote"]]
    stretches, cur = [], None
    for r in rows:
        if r["remote"]:
            key = (r["owner"], r["edge"])
            if cur is None or cur["key"] != key:
                tc = max(t for t, _ in changes if t <= r["t"])
                cur = {"key": key, "serving": r["owner"], "edge": r["edge"], "t_start": tc, "t_last": r["t"], "chunks": 0}
                stretches.append(cur)
            cur["t_last"] = r["t"]; cur["chunks"] += 1
        else:
            cur = None
    est = {"crf23": 0, "crf28": 0}
    unenc = 0
    for r in remote:
        e = enc.get((r["owner"], r["call"]))
        if e is None:
            unenc += 1; continue
        est["crf23"] += int(e.get("bytes_crf23") or 0); est["crf28"] += int(e.get("bytes_crf28") or 0)
    # output equivalence per ownership after a switchover / resume
    resumes = [e for e in node_events if e.get("event") == "resume"]
    equiv = []
    for e in resumes:
        rs = [r for r in rows if r["owner"] == e["node"] and r["call"] >= int(e.get("call") or 0)]
        known = [r for r in rs if r["ref_match"] is not None]
        equiv.append({"node": e["node"], "resume_call": e.get("call"), "mode": e.get("mode"), "calls": len(rs), "checked": len(known),
                      "matching": sum(1 for r in known if r["ref_match"]), "first_call_match": rs[0]["ref_match"] if rs else None,
                      "first_mismatch_call": next((r["call"] for r in known if not r["ref_match"]), None)})
    # trajectory after the final edge's first chunk
    fin = path[-1]
    fr = [r for r in rows if r["owner"] == fin and r["t"] >= changes[-1][0]]
    ps = [r["psnr"] for r in fr if r["psnr"] is not None]
    cross = next((i for i, p in enumerate(ps) if p >= REJOIN_DB), None)
    sus = next((i for i in range(len(ps) - 9) if all(p >= REJOIN_DB for p in ps[i:i + 10])), None)
    enc_s = [float(e.get("enc_s") or 0) for e in node_events if e.get("event") == "xb_delivery_enc"]
    return {
        "ttfo_local": ttfo, "ttfo_local_final_s": ttfo[-1]["ttfo_local_s"] if ttfo else None,
        "delivery_gap_s": max(gaps) if gaps else None, "delivery_gap_at_s": ts[gap_i] if gap_i is not None else None,
        "delivered_chunks": len(rows), "t_last_delivery_s": t_end,
        "remote_chunks": len(remote), "remote_content_s": len(remote) * CHUNK_CONTENT_S, "remote_wall_s": sum(x["t_last"] - x["t_start"] for x in stretches),
        "remote_stretches": [{k: v for k, v in x.items() if k != "key"} for x in stretches],
        "remote_delivery_bytes_ESTIMATED": {**est, "remote_chunks_not_encoded": unenc, "note": "H.264 encoded size of remotely served output; not transmitted on the testbed"},
        "delivery_encode_cpu_s": sum(enc_s),
        "rtt_measured_lan": s.get("rtt_measured_lan"),
        "output_equivalence": equiv,
        "trajectory_final": {"edge": fin, "calls": len(ps), "first_ge35_idx": cross, "sustained10_idx": sus,
                             "terminal_median_psnr": st.median(ps[-10:]) if len(ps) >= 10 else None, "median_psnr": st.median(ps) if ps else None},
    }
