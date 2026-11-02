#!/usr/bin/env python3
"""Loopback test of ll_migrate.py on the tiny random CPU model (test_ll_runtime.py): a destination and a source process
on 127.0.0.1, both methods, K_v = 12 (the preregistered value), a fast and a slow link (the slow one builds a replay backlog). Checks: the state at the
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


def run(method, bw, port, k_vae=12):
    out = Path(tempfile.mkdtemp()) / f"{method}.json"
    common = ["--method", method, "--tiny", "--at", "14", "--verify", "4", "--k_vae", str(k_vae), "--bw_mbps", str(bw), "--burst_bytes", "256", "--max_catchup_s", "15",
              "--prompt", "a boy on a lawn"]
    dst = subprocess.Popen([sys.executable, str(HERE / "ll_migrate.py"), "dst", "--port", str(port), "--out", str(out), *common])
    src = subprocess.Popen([sys.executable, str(HERE / "ll_migrate.py"), "src", "--peer", f"127.0.0.1:{port}", *common],
                           stdout=subprocess.DEVNULL)
    rd, rs = dst.wait(timeout=900), src.wait(timeout=900)
    chk(rd == 0 and rs == 0, f"{method} @ {bw} Mbps: both processes exit 0 ({rd}, {rs})")
    return json.loads(out.read_text()) if out.exists() else None


def main():
    for method, bw, port in (("snap", 100.0, 29961), ("snap", 0.2, 29962), ("full", 0.5, 29963)):
        r = run(method, bw, port)
        if r is None:
            continue
        chk(r["state_exact"], f"{method} @ {bw}: state at the switch call exact (fingerprints)")
        chk(r["lat_equal_calls"] == 4 and r["frm_equal_calls"] >= 3, f"{method} @ {bw}: post-cutover latents 4 / 4 equal the shadow, "
            f"frames >= 3 / 4 with K_v = 12 (latents {r['lat_equal_calls']}, frames {r['frm_equal_calls']}, first call {r['first_call_psnr_vs_shadow']})")
        chk(r["frames_complete"], f"{method} @ {bw}: frames complete")
        if method == "snap":
            chk(r["switch_call"] > 14 and r["replayed_calls"] == r["switch_call"] - 14 and r["switch_req_after_trigger_s"] is not None,
                f"snap @ {bw}: switched at {r['switch_call']} after the trigger, replayed {r['replayed_calls']} calls "
                f"({'forced: the CPU tiny model decodes about as fast as it generates' if r['switch_forced'] else 'caught up'})")
            chk(r["vae_rebuild_blocks"] == 12, f"snap @ {bw}: VAE rebuilt from {r['vae_rebuild_blocks']} logged blocks before the "
                f"switch ({r['vae_rebuild_s']:.2f} s), {r['replayed_with_decode']} replayed calls decoded after it")
        else:
            chk(r["switch_call"] == 14 and r["replayed_calls"] == 0, "full: switch at the trigger, no replay")
        if bw <= 0.5:
            chk(r["state_transfer_s"] > 0.2, f"{method} @ {bw}: shaped state transfer {r['state_transfer_s']:.2f} s")
    print("ALL PASS" if not FAILS else f"FAILED: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
