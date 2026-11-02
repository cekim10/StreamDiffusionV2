#!/usr/bin/env python3
"""Loopback test of ll_migrate.py on the tiny random CPU model (test_ll_runtime.py): a destination and a source process
on 127.0.0.1, every method (snap, full, replay W8, recache), K_v = 12 (the preregistered value), a fast and a slow link (the slow one builds a replay backlog). Checks: the state at the
switch call is exact (fingerprints), every post-cutover call equals the source's shadow (latents and frames), frames
complete, snap switches after the trigger and replays the log, full switches at the trigger.

    python tools/longlive/test_ll_migrate.py
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FAILS = []


def chk(c, m):
    print(("  [ok] " if c else "  [FAIL] ") + m)
    c or FAILS.append(m)


def run(method, bw, port, k_vae=12, extra=()):
    out = Path(tempfile.mkdtemp()) / f"{method}.json"
    common = [*extra, "--method", method, "--tiny", "--at", "14", "--verify", "4", "--k_vae", str(k_vae), "--bw_mbps", str(bw), "--burst_bytes", "256", "--max_catchup_s", "15",
              "--prompt", "a boy on a lawn"]
    dst = subprocess.Popen([sys.executable, str(HERE / "ll_migrate.py"), "dst", "--port", str(port), "--out", str(out), *common])
    src = subprocess.Popen([sys.executable, str(HERE / "ll_migrate.py"), "src", "--peer", f"127.0.0.1:{port}", *common],
                           stdout=subprocess.DEVNULL)
    rd, rs = dst.wait(timeout=900), src.wait(timeout=900)
    chk(rd == 0 and rs == 0, f"{method} @ {bw} Mbps: both processes exit 0 ({rd}, {rs})")
    return json.loads(out.read_text()) if out.exists() else None


def main():
    byts = {}
    for method, bw, port, extra in (("snap", 100.0, 29961, ()), ("snap", 0.2, 29962, ()), ("full", 0.5, 29963, ()),
                                    ("replay", 0.5, 29964, ("--replay_w", "8")), ("recache", 0.5, 29965, ())):
        r = run(method, bw, port, extra=extra)
        if r is None:
            continue
        byts[method] = r["bytes_until_switch"]
        chk(len(r["psnr_vs_shadow"]) == 4 and r["max_output_gap_s"] is not None,
            f"{method} @ {bw}: per-call PSNR vs the shadow on 4 / 4 calls ({r['psnr_windows']}), max output gap {r['max_output_gap_s']:.2f} s")
        if method == "recache":
            chk(r["frames_complete"] and r["switch_call"] > 14 and r["recache_s"] is not None,
                f"recache: switched at {r['switch_call']}, recache {r['recache_s']:.2f} s, frames complete; state exact {r['state_exact']} (not required)")
            continue
        chk(r["state_exact"], f"{method} @ {bw}: state at the switch call exact (fingerprints)")
        chk(r["lat_equal_calls"] == 4 and r["frm_equal_calls"] >= 3, f"{method} @ {bw}: post-cutover latents 4 / 4 equal the shadow, "
            f"frames >= 3 / 4 with K_v = 12 (latents {r['lat_equal_calls']}, frames {r['frm_equal_calls']}, first call {r['first_call_psnr_vs_shadow']})")
        chk(r["frames_complete"], f"{method} @ {bw}: frames complete")
        if method == "replay":
            chk(r["replayed_calls"] == r["switch_call"] - 14 + 8, f"replay W8: replayed {r['replayed_calls']} calls (8 before the trigger + "
                f"{r['switch_call'] - 14} served meanwhile)")
        if method == "snap":
            chk(r["switch_call"] > 14 and r["replayed_calls"] == r["switch_call"] - 14 and r["switch_req_after_trigger_s"] is not None,
                f"snap @ {bw}: switched at {r['switch_call']} after the trigger, replayed {r['replayed_calls']} calls "
                f"({'forced: the CPU tiny model decodes about as fast as it generates' if r['switch_forced'] else 'caught up'})")
            chk(r["vae_rebuild_blocks"] == 12, f"snap @ {bw}: VAE rebuilt from {r['vae_rebuild_blocks']} logged blocks before the "
                f"switch ({r['vae_rebuild_s']:.2f} s), {r['replayed_with_decode']} replayed calls decoded after it")
        elif method == "full":
            chk(r["switch_call"] == 14 and r["replayed_calls"] == 0, "full: switch at the trigger, no replay")
        if bw <= 0.5 and method in ("snap", "full"):   # replay ships only the tiny sink: below one token-bucket burst
            chk(r["state_transfer_s"] > 0.2, f"{method} @ {bw}: shaped state transfer {r['state_transfer_s']:.2f} s")
    if "replay" in byts and "full" in byts:
        chk(byts["replay"] < byts["full"], f"bytes until the switch: replay {byts['replay']} < full {byts['full']}")
    print("ALL PASS" if not FAILS else f"FAILED: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
