#!/usr/bin/env python3
"""Dry protocol test of M2 / E9 (versioned Sink state reuse) on an A -> B -> A path with precopy_replay: fixed switch
calls, retention at the first digest-equal switch, tracking on B, a delta base at the second migration (DELTAOK),
the fresh-base baseline, and the full-base fallback when the delta's digest disagrees (DELTANO).

    python tools/eval/test_m2_live.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
import test_xb as tx  # noqa: E402


def main():
    base = ["--path", "A,B,A", "--allow_return", "--xb_policy_settings", "precopy_replay@thr=16:rl=1", "--replay_window", "12", "--replay_lag", "1",
            "--replay_sink_sync", "--replay_switch_calls", "80,164", "--move_calls", "120"]   # dry nodes run at trigger 30: the dry base round takes ~30 calls
    for exp, extra, want_mode in (("_m2reuse_test", ["--replay_retain", "--replay_reuse"], "delta"), ("_m2base_test", [], "full"),
                                  ("_m2dmm_test", ["--replay_retain", "--replay_reuse", "--replay_delta_test_mismatch"], "full")):
        R = tx.run(exp, "precopy_replay", 1, "1e9", base + extra)
        d = R.get("precopy_replay")
        tx.check(d is not None, f"{exp}: run written")
        if d is None:
            continue
        s = json.load(open(d / "summary.json"))
        ev = tx.events(d)
        sws = s["switchovers"]
        tx.check(len(sws) == 2 and [x["dst"] for x in sws] == ["B", "A"] and [int(x["call"]) for x in sws] == [80, 164], f"{exp}: A->B at 80, B->A at 164 ({[(x['dst'], x['call']) for x in sws]})")
        sw = [e for e in ev if e["event"].endswith(":xb_precopy_switch")]
        tx.check(len(sw) == 2 and all(not e["detail"].get("switch_call_missed") for e in sw), f"{exp}: both switches at their planned calls")
        tx.check(all(e["detail"].get("verdict") == "SINKOK" for e in sw), f"{exp}: both cutovers digest-equal (SINKOK)")
        bs = [e for e in ev if e["event"] == "B:replay_base_sent"]
        tx.check(bool(bs) and bs[-1]["detail"].get("mode") == want_mode, f"{exp}: second migration base mode {bs and bs[-1]['detail'].get('mode')} (want {want_mode})")
        if "--replay_retain" in extra:
            tx.check(bool(sw[0]["detail"].get("retained")), f"{exp}: A retained its Sink version at the first switch")
            db = [e for e in ev if e["event"] == "A:replay_delta_base"]
            if want_mode == "delta":
                tx.check(bool(db) and db[-1]["detail"].get("accepted") is True, f"{exp}: A rebuilt the base from its retained Sink (DELTAOK)")
            else:
                tx.check(bool(db) and db[-1]["detail"].get("accepted") is False and bs[-1]["detail"].get("delta_verdict") == "DELTANO",
                         f"{exp}: delta rejected (DELTANO), full base sent instead")
        m = [r for r in tx.metrics(d)]
        a2 = [int(r["call"]) for r in m if r["owner"] == "A" and int(r["call"]) >= 164]
        b = [int(r["call"]) for r in m if r["owner"] == "B"]
        tx.check(bool(a2) and a2[0] == 164 and bool(b) and b[0] == 80 and b[-1] == 163, f"{exp}: B served 80..163, A resumed at 164")
    print("ALL PASS" if not tx.FAILS else f"FAILED: {tx.FAILS}")
    sys.exit(1 if tx.FAILS else 0)


if __name__ == "__main__":
    main()
