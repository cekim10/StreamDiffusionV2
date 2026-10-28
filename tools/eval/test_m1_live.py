#!/usr/bin/env python3
"""Dry protocol test of the M1 input-log replay policy (precopy_replay) against dry-run nodes (no torch): the Sink
pre-copy base, the ordered per-call log, the destination's shadow replay and acknowledgements, the switch only after
the replay caught up, no lost / duplicated / reordered calls, the post-run verification message, and the cutover
timing record of every pre-copy policy (precopy_replay, precopy_sink, precopy_full).

    python tools/eval/test_m1_live.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
import test_xb as tx  # noqa: E402


def main():
    settings = "precopy_replay@thr=16:rl=1;precopy_sink@thr=16:rl=1;precopy_full@thr=256:rl=10"
    R = tx.run("_m1live_test", "precopy_replay,precopy_sink,precopy_full", 1, "1e9",
               ["--xb_policy_settings", settings, "--replay_window", "12", "--replay_lag", "1", "--replay_verify"])
    tx.check(set(R) == {"precopy_replay", "precopy_sink", "precopy_full"}, f"three runs written ({sorted(R)})")
    for pol, d in R.items():
        s = json.load(open(d / "summary.json"))
        c = s.get("cutover") or {}
        tx.check(c.get("M") is not None and c.get("interruption_s") is not None and c.get("source_stop_to_first_output_s") is not None,
                 f"{pol}: cutover timing recorded (M {c.get('M')}, interruption {c.get('interruption_s')}, stop->first output {c.get('source_stop_to_first_output_s')})")
        tx.check(s["validation"].get("switchovers_verified") is True and s["validation"].get("n_switchovers") == 1, f"{pol}: one verified switchover")
        f = tx.first_after_switch(d, s)
        tx.check(f is not None, f"{pol}: destination generated after the switchover")
    if "precopy_replay" in R:
        d = R["precopy_replay"]
        s = json.load(open(d / "summary.json"))
        v, rp = s["validation"], s["replay"]
        for k in ("replay_base_verified", "replay_conditioning_equal", "replay_order_ok", "replay_post_meta_all_equal", "replay_meta_consistent_at_switch",
                  "replay_no_lost_or_duplicated_calls"):
            tx.check(v.get(k) is True, f"precopy_replay: {k}")
        # replay_source_unchanged_vs_reference: the fake runtime's source output is never the 99 dB marker (dry ref_match is
        # always False); on GPU it is the per-call frame digest against the reference, checked in the real run
        tx.check(v.get("replay_source_unchanged_vs_reference") is False, "precopy_replay: source reference check present (always False in dry runs by construction)")
        tx.check(v.get("replay_switch_refused") == 0 and v.get("replay_ready_timeout") is False, "precopy_replay: no refused switch, no readiness timeout")
        t = rp["timing"]
        tx.check(t["replayed_calls"] is not None and t["replayed_calls"] >= 12 and t["replayed_calls"] == t["M"] - t["c0"], f"precopy_replay: replayed every call c0..M-1, >= W (c0 {t['c0']}, M {t['M']}, {t['replayed_calls']})")
        tx.check(rp["bytes"]["log_calls"] == t["replayed_calls"] and rp["bytes"]["log_bytes"] > 0, f"precopy_replay: log calls sent = replayed ({rp['bytes']['log_calls']}), {rp['bytes']['log_bytes']} B")
        tx.check(rp["verify"] is not None and rp["verify"].get("recent_rel") is not None, "precopy_replay: post-run verification received")
        ev = tx.events(d)
        acks = [e for e in ev if e["event"] == "B:replay_applied"]
        tx.check([int(e["detail"]["call"]) for e in acks] == list(range(t["c0"], t["M"])), "precopy_replay: calls applied strictly in order")
        sw = [e for e in ev if e["event"] == "A:xb_precopy_switch"]
        tx.check(bool(sw) and sw[-1]["detail"].get("last_log") == t["M"] - 1, "precopy_replay: the last logged call is M - 1")
        rounds = [e for e in ev if e["event"] == "A:xb_precopy_round"]
        tx.check(len(rounds) >= 1 and float(sw[-1]["detail"].get("ready_wait_s") or 0) >= 0, f"precopy_replay: {len(rounds)} Sink round(s), ready wait {sw[-1]['detail'].get('ready_wait_s')}")
    print("ALL PASS" if not tx.FAILS else f"FAILED: {tx.FAILS}")
    sys.exit(1 if tx.FAILS else 0)


if __name__ == "__main__":
    main()
