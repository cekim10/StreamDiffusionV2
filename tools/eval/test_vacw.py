#!/usr/bin/env python3
"""VACW v0 loopback validation (design `results/evaluation/osdi/expM2/vacw_v0_design.md`, frozen 9137bc9; Amendment 1).

Four fake nodes on 127.0.0.1 (no torch), A -> B -> C -> D, 100 Mbps emulated links, 64 MiB fake Sink = 16 fragments of
4 MiB, dry promotions at known calls: a bound fake owner changes 3 known fragments of its live Sink per promotion, so a
fresh snapshot S_k differs from the image O_k bound by exactly 3 x (promotions at O_k) fragments. Policies: split_va,
restart_fresh (fresh snapshots) and split (frozen, stale S_0), rho 0.5 (every owner binds before it is left) and rho 1
(the first owner may not be bound at the move: the S_k = S_{k-1} path).

Checks per run (harness faults, not hypotheses): run validity (W / R / N rules), I1 (no fragment sent under a superseded
manifest after the next snapshot became active; superseded flows cancelled), I2 / H1a (every bind's version is the
snapshot active at that time; a bind happens only after the whole digest verified), I3 / I4 (no verified-hash failure
other than stale-by-design rejections), I5 (the dry chain: dirty fragments of S_k == 3 x promotions at O_k, i.e. O_k
generated on exactly the image it bound; the final owner binds the last snapshot), I6 (split_va: holder-valid fragments
are delivered by holders, the capturing owner sends exactly the dirty ones), exposure accounting, restart_fresh byte
bound (the capturing owner sends S_k whole), split stale baseline (one snapshot, binds S_0). I7 (positions inside the
snapshot) is a property of the GPU Sink pack (ring/pos_sink tensors are part of the component) and is not exercised here.

    python tools/eval/test_vacw.py            # ~4 min; results under results/evaluation/_dryrun__vacw_lb_rho*/
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
from run_wrn import Ctx, vacw_args  # noqa: E402
from wrn_validity import run_validity_wrn  # noqa: E402

N_FRAGS, DIRTY_PER_PROMO = 16, 3
PROMOTE = "60,65,70,115,120,125,170,175"


def check(cond, msg, fails):
    print(("  [ok] " if cond else "  [FAIL] ") + msg)
    if not cond:
        fails.append(msg)


def manifest_at(hist, t):
    v = None
    for ti, ver in hist:
        if ti <= t:
            v = ver
    return v


def check_run(d: Path, fails: list):
    s = json.load(open(d / "summary.json"))
    pol = s["policy"]; v = s["vacw"]; val = s["validation"]
    print(f"- {d.name}")
    ok, bad = run_validity_wrn(s, d, dry=True)
    check(ok, f"valid under the W / R / N rules {bad}", fails)
    check(val["all_fragments_verified"] is True and val["sink_version_consistent"] and val["final_sink_digest_matches_source"] is True, "I3 / I4: every accepted fragment verified by hash; no non-stale rejection; final digest matches", fails)
    binds = v["binds"]
    check(bool(binds) and all(b["ok"] for b in binds), f"I2 / H1a: {len(binds)} binds, each of the snapshot active at bind time {[(b['node'], b['bound_version'][:6], b['intended_version'][:6]) for b in binds]}", fails)
    # node-side: a bind only after sink_verified ok of that version
    for lb in "BCD":
        ev = list(csv.DictReader(open(d / f"node_{lb}" / "events.csv", newline="")))
        for b in [e for e in ev if e["event"] == "sink_bind"]:
            det = json.loads(b["detail"]) if b.get("detail") else {}
            ver = det.get("sink_version")
            okv = any(e["event"] == "sink_verified" and (json.loads(e["detail"]).get("sink_version") == ver) and json.loads(e["detail"]).get("ok") and float(e["t_wall"]) <= float(b["t_wall"]) for e in ev)
            check(okv, f"I2 at {lb}: bind of {str(ver)[:6]} preceded by sink_verified ok of the same version", fails)
    hist = v["manifest_hist_rel"]
    rows = list(csv.DictReader(open(d / "fragments.csv", newline="")))
    sent = [r for r in rows if r["event"] == "sent"]
    bad_sent = [r for r in sent if r["sink_version"] != manifest_at(hist, float(r["t_rel"]))]
    check(not bad_sent, f"I1: no fragment sent under a superseded manifest after the next became active ({len(sent)} sends, {len(hist)} manifests)", fails)
    moves = s["moves"]; pm = v["per_move"]
    if pol in ("split_va", "restart_fresh"):
        check(v["enabled"] and v["n_snapshots"] == 1 + v["fresh_transitions"], f"snapshot count = 1 + fresh transitions ({v['n_snapshots']}, {v['fresh_transitions']})", fails)
        for m in pm:
            check(bool(m["fresh"]) == bool(m["was_bound"]), f"move {m['i']} {m['from']}->{m['to']}: fresh iff the leaving owner was bound (bound {m['was_bound']}, fresh {m['fresh']})", fails)
        promos = {lb: s["node_end"][lb].get("promotion_calls") or [] for lb in "ABCD"}
        for snap in v["snapshots"][1:]:
            exp = min(N_FRAGS, DIRTY_PER_PROMO * len(promos[snap["captured_by"]]))
            check(snap["dirty_frags"] == exp, f"I5 chain: S_{snap['k']} by {snap['captured_by']} differs from the image it bound by {snap['dirty_frags']} fragments (expected 3 x {len(promos[snap['captured_by']])} promotions = {exp})", fails)
        last = v["snapshots"][-1]
        check(binds[-1]["node"] == s["path"][-1] and binds[-1]["bound_version"] == last["sink_version"], f"I5: final owner bound the last snapshot S_{last['k']} ({last['captured_by']})", fails)
        fin = v["final_snapshot"]; b = v["bytes_sinks"]
        if pol == "split_va" and moves[-1].get("fresh"):
            dirty = last["dirty_frags"]
            check(abs(fin["available_verified_reuse"] - (N_FRAGS - dirty) / N_FRAGS) < 1e-9, f"available verified reuse at the final move = unchanged fragments held by the previous owner ({fin['available_verified_reuse']:.3f} = {N_FRAGS - dirty}/{N_FRAGS})", fails)
            check(abs(fin["realized_reuse"] - fin["available_verified_reuse"]) < 1e-9, f"I6: realized reuse = available ({fin['realized_reuse']:.3f}): every holder-valid fragment came from a holder", fails)
            check(abs(b["source_final_snapshot"] * N_FRAGS - dirty) < 1e-6, f"I6: the capturing owner sent exactly the dirty fragments ({b['source_final_snapshot'] * N_FRAGS:.1f} of {dirty})", fails)
            check(fin["content_reuse_potential"] >= fin["available_verified_reuse"] >= fin["realized_reuse"] - 1e-9, "reuse triple ordering potential >= available >= realized", fails)
        if pol == "restart_fresh":
            post = s["d0"]["source_bytes_post_move_sinks"]
            check(abs(post - 1.0) < 1e-9 and s["bytes"]["reused_from_non_source"] == 0 and val["restart_discarded_progress"] is True, f"restart_fresh: after the final move the source role sent S_K whole ({post:.2f} Sink; {b['source_total']:.2f} over the run), nothing reused", fails)
        print(f"    exposure: fresh transitions {v['fresh_transitions']} / {len(moves)} moves; stale rejections {v['rejected_stale']}; cross-version accepted {v['cross_version_accepted']}; "
              f"capture {[round(m['snapshot_capture_s'], 2) if m['snapshot_capture_s'] is not None else None for m in pm]} s; manifest wait {[round(m['manifest_wait_s'], 2) if m['manifest_wait_s'] is not None else None for m in pm]} s; "
              f"bind-ready {[round(m['bind_ready_s'], 2) if m['bind_ready_s'] is not None else None for m in pm]} s")
    else:
        check(not v["enabled"] and v["n_snapshots"] == 1 and all(b["bound_version"] == v["snapshots"][0]["sink_version"] for b in binds), f"split (stale baseline): one snapshot S_0, {len(binds)} binds of S_0", fails)
        check(v["rejected_stale"] == 0 and v["cross_version_accepted"] == 0, "split: no stale rejections / cross-version receipts (single manifest)", fails)
    return s


def unit_stale_receipt(fails: list):
    """Design 1.2 / I1 receiver and sender rules, which the A -> B -> C -> D loopback cannot reach (no flow is active toward
    an owner once it is bound, so no fragment of a superseded snapshot is ever in flight there): two in-process fake
    nodes; B's manifest is updated to an S_1 whose fragments 1 and 3 differ while A still sends S_0: B must accept 0 and 2
    (hash equal: cross-version receipt) and reject 1 and 3 as stale by hash; after A's own update, A must skip 1 and 3
    (stale at the sender) and send 0 and 2 only."""
    import threading
    import time
    import mobility_node as mn

    print("- unit: stale receipt / sender skip after a manifest update")
    out = ROOT / "results/evaluation/_dryrun__vacw_unit"
    shutil.rmtree(out, ignore_errors=True)
    nodes = {}
    for i, lb in enumerate("AB"):
        a = mn.parse_args(["--label", lb, "--bind", "127.0.0.1", "--ctl_port", str(29991 + 2 * i), "--data_port", str(29992 + 2 * i), "--mss", "0", "--dry_run", "--dry_sink_mb", "16"])
        n = mn.Node(a); n.send = lambda *x, **k: None   # no orchestrator: control messages dropped, events still logged
        n.cmd_run_begin({"run_id": "unit", "run_rel": "results/evaluation/_dryrun__vacw_unit", "session_id": "unit", "t0": None})
        nodes[lb] = n
    A, B = nodes["A"], nodes["B"]
    man0 = A.cmd_source_prep({"M": 30, "frag_bytes": 4 << 20})["manifest"]
    B.cmd_manifest({"manifest": man0})
    man1 = json.loads(json.dumps(man0)); man1["sink_version"] = "deadbeefdeadbeef"; man1["sink_digest"] = "deadbeef" * 8; man1["snapshot_k"] = 1
    for fid in (1, 3):
        man1["frags"][fid]["sha256"] = "11" * 32
    rp = B.cmd_manifest_update({"manifest": man1})
    check(rp["valid"] == [] and rp["n_stale"] == 0 and not rp["same"], f"B installed S_1 with nothing held {rp}", fails)
    A.cmd_flow_start({"flow_id": "f1", "dst": "B", "dst_host": "127.0.0.1", "dst_port": 29994, "frag_ids": [0, 1, 2, 3], "closed": True, "rate_bps": 0})
    A.flows["f1"]["thread"].join(30); time.sleep(0.5)
    ev = lambda n, name: [json.loads(r["detail"]) for r in csv.DictReader(open(n.run["dir"] / "events.csv", newline="")) if r["event"] == name]  # noqa: E731
    rej = ev(B, "fragment_rejected_hash"); acc = ev(B, "fragment_accepted_cross_version")
    check(B.run["have"] == {0, 2} and sorted(d["fragment_id"] for d in rej) == [1, 3] and all(d["reason"] == "hash_stale" for d in rej) and sorted(d["fragment_id"] for d in acc) == [0, 2],
          f"B accepted 0, 2 (hash equal to S_1, cross-version) and rejected 1, 3 as stale (have {sorted(B.run['have'])}, rejected {[d['fragment_id'] for d in rej]}, accepted {[d['fragment_id'] for d in acc]})", fails)
    check(len(ev(B, "flow_version_stale")) == 1 and not ev(B, "sink_version_mismatch"), "B logged the S_0 flow as stale, not as a version mismatch", fails)
    rp = A.cmd_manifest_update({"manifest": man1})
    check(rp["valid"] == [0, 2] and rp["n_stale"] == 2, f"A's holdings under S_1: valid 0, 2; stale 1, 3 {rp}", fails)
    A.cmd_flow_start({"flow_id": "f2", "dst": "B", "dst_host": "127.0.0.1", "dst_port": 29994, "frag_ids": [0, 1, 2, 3], "closed": True, "rate_bps": 0})
    A.flows["f2"]["thread"].join(30); time.sleep(0.5)
    sk = [d for d in ev(A, "flow_skip_not_held") if d["flow"] == "f2"]
    check(sorted(d["fragment_id"] for d in sk) == [1, 3] and all(d["stale"] for d in sk) and A.flows["f2"]["sent"] == {0, 2}, f"A skipped the stale 1, 3 and sent 0, 2 under S_1 (skipped {[d['fragment_id'] for d in sk]}, sent {sorted(A.flows['f2']['sent'])})", fails)
    check(B.run["have"] == {0, 2} and B.run["sink_verified"] is None, "B: 0, 2 were duplicates; S_1 still incomplete (no verify, no bind)", fails)
    for n in nodes.values():
        n.cmd_run_end({})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rhos", default="0.5,1")
    ap.add_argument("--unit_only", action="store_true")
    ap.add_argument("--keep", action="store_true", help="keep earlier loopback results (default: the loopback directories are removed first)")
    ap.add_argument("--py", default=os.environ.get("PY") or (str(ROOT / ".venv/bin/python") if (ROOT / ".venv/bin/python").exists() else sys.executable))
    a = ap.parse_args()
    c = Ctx(argparse.Namespace(dry=True, py=a.py, dry_promote=PROMOTE, wait_s=0, tag="", cells=""))
    fails = []
    unit_stale_receipt(fails)
    for rho in ([] if a.unit_only else a.rhos.split(",")):
        exp = f"_vacw_lb_rho{rho}"
        out = ROOT / "results/evaluation" / ("_dryrun_" + exp)
        if out.exists() and not a.keep:
            shutil.rmtree(out)
        rc = c.orch(exp, vacw_args(c, rho, reps="1") + ["--max_run_s", "150"], ["--sink_fp"], f"VACW loopback rho {rho}")
        if rc != 0:
            fails.append(f"orchestrator exit {rc} (rho {rho})")
        print(f"\n== rho {rho}")
        for d in sorted(out.glob("policy=*")):
            if (d / "summary.json").exists():
                check_run(d, fails)
            else:
                fails.append(f"{d.name}: no summary")
    print("\nALL PASS" if not fails else f"\nFAILURES ({len(fails)}):\n  " + "\n  ".join(fails))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
