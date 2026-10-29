#!/usr/bin/env python3
"""M3-S0 (osdi/m3s0/preregistration.md): per-call Sink lineage table of one workload, for the offline staging simulator.

Deterministic re-generation of the workload in one process (same input, prompt, seed and calls as the M3-E0 source A,
whose live fragment hashes the same procedure reproduced 412 / 412 in `m3e0_crossversion.py`). For every call c in
[c_lo, c_hi] it records the cache decisions of that call (refresh = a write into a Sink slot; realignment = a position
shift of an unwritten Sink slot), and after the call the 360 per-block int64 checksums of the Sink and (optionally) the
412 per-fragment SHA-256 prefixes of the Sink serialization. The checksums are ground truth for the lineage rule the
simulator applies: a V block is unchanged between s and t iff its entry was not refreshed in (s, t]; a K block is
unchanged iff additionally not shifted. Data extraction only: nothing in the migration path runs.

    python tools/eval/m3s0_dump_events.py --video_path ... --prompt_file_path ... --seed 0 --c_lo 25 --c_hi 140 --out osdi/m3s0/events_dog.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p_ in (ROOT, ROOT / "tools", ROOT / "tools" / "eval"):
    if str(p_) not in sys.path:
        sys.path.insert(0, str(p_))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video_path", required=True); ap.add_argument("--prompt_file_path", required=True); ap.add_argument("--seed", default="0")
    ap.add_argument("--gpu_id", default="0"); ap.add_argument("--c_lo", type=int, default=25); ap.add_argument("--c_hi", type=int, default=140)
    ap.add_argument("--no_hashes", action="store_true", help="skip the per-call fragment hashes (saves ~1.2 s per call)")
    ap.add_argument("--frag_bytes", type=int, default=4 << 20)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    import torch

    import m1_replay as mr
    import mobility_node as mn
    from mobility_node import frag_table

    margs = mn.parse_args(["--label", "S0D", "--video_path", a.video_path, "--prompt_file_path", a.prompt_file_path, "--seed", a.seed, "--gpu_id", a.gpu_id,
                           "--migration_chunk", "30", "--post_chunks", "1500"])
    rt = mn.GpuRuntime(margs)
    pl, dev = rt.pl, rt.device
    sync = lambda: torch.cuda.synchronize(dev)  # noqa: E731
    S = rt.sink
    rec = mr.Recorder(torch, pl, S, dev, sync, keep_slots=False)
    session = rt.session = rt.runner.start()
    refresh, shifts, block_ck, frag16, gen_s = {}, {}, {}, {}, {}
    frags = None
    t_all = time.time()
    for c in range(a.c_hi + 1):
        rec.call, rec.active = c, c >= a.c_lo
        t0 = time.time(); rt.runner.step(session, c); sync(); gen_s[c] = time.time() - t0
        rec.call, rec.active = None, False
        if c < a.c_lo:
            continue
        e = rec.entries[c]
        rf, sh = [], []
        for li, rows in enumerate(e["written"]):
            pre, post = e["pre"]["pos"][li].tolist(), e["post"]["pos"][li].tolist()
            for b, w in enumerate(rows):
                for s in range(S):
                    if w == s:
                        rf.append([li, b, s])
                    elif post[b][s] != pre[b][s]:
                        sh.append([li, b, s, int(post[b][s] - pre[b][s])])
        refresh[c], shifts[c] = rf, sh
        ck = rt.sink_checksums(); ck.pop("s")
        block_ck[c] = ck["blocks"]    # [layer*2 + (0 K | 1 V)][row][slot]
        if not a.no_hashes:
            ser = rt.serialize_live(); h, bufs = rt.pack(ser, "sink")
            buf = bytearray(h["nbytes"]); mv = memoryview(buf)
            for t, b in zip(h["tensors"], bufs):
                mv[t["offset"]:t["offset"] + t["nbytes"]] = memoryview(b).cast("B")
            frags = frags or frag_table(len(buf), a.frag_bytes)
            frag16[c] = [hashlib.sha256(mv[f["off"]:f["off"] + f["len"]]).hexdigest()[:16] for f in frags]
            del buf, mv, bufs, ser
        rec.entries.pop(c, None)
        if c % 10 == 0:
            print(f"[S0D] call {c}: {len(rf)} refresh, {len(sh)} shifts ({time.time() - t_all:.0f} s)", flush=True)
    # consistency of the lineage rule against the checksums, over every (s, t) pair with s < t
    calls = sorted(refresh)
    L = len(pl.kv_cache1)
    n_pairs = n_ok = 0
    bad = []
    for i, s in enumerate(calls):
        rf_acc, sh_acc = set(), set()
        for t in calls[i + 1:]:
            rf_acc |= {tuple(x) for x in refresh[t]}; sh_acc |= {tuple(x[:3]) for x in shifts[t]}
            for li in range(L):
                for b in range(len(block_ck[s][0])):
                    for sl in range(S):
                        key = (li, b, sl)
                        v_eq = block_ck[s][2 * li + 1][b][sl] == block_ck[t][2 * li + 1][b][sl]
                        k_eq = block_ck[s][2 * li][b][sl] == block_ck[t][2 * li][b][sl]
                        pv = (key not in rf_acc) == v_eq
                        pk = (key not in rf_acc and key not in sh_acc) == k_eq
                        n_pairs += 2; n_ok += pv + pk
                        if not (pv and pk) and len(bad) < 20:
                            bad.append([s, t, li, b, sl, "V" if not pv else "K"])
    res = {"host": platform.node(), "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
           "video": a.video_path, "prompt": a.prompt_file_path, "seed": a.seed, "c_lo": a.c_lo, "c_hi": a.c_hi, "sink_slots": S, "layers": L,
           "rows": len(block_ck[calls[0]][0]), "n_entries": L * len(block_ck[calls[0]][0]) * S, "block_bytes": rt.fsl * pl.kv_cache1[0]["k"].shape[2] * pl.kv_cache1[0]["k"].shape[3] * 2,
           "gen_s_median": sorted(gen_s.values())[len(gen_s) // 2], "refresh": refresh, "shifts": shifts, "block_ck": block_ck, "frag16": frag16,
           "n_fragments": len(frags) if frags else None,
           "lineage_rule_check": {"block_pairs": n_pairs, "consistent": n_ok, "fraction": n_ok / n_pairs if n_pairs else None, "first_inconsistent": bad}}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res))
    print(f"[S0D] lineage rule consistent on {n_ok} / {n_pairs} block pairs; wrote {a.out}")


if __name__ == "__main__":
    main()
