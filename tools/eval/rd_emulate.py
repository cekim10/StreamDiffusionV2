#!/usr/bin/env python3
"""Experiment RD: in-place M1 emulation on one GPU (results/evaluation/osdi/expRD/preregistration.md, frozen f850072).

One process = one workload: the uninterrupted reference (GpuRuntime.baseline, the node's reference path), then every
condition of the phase from call 0. An M1 reset before call t runs the real destination path in-process:
serialize_live -> pack inflight + meta (fast-path bytes) [+ pack the Sink when an episode opens] -> release ->
provision (fresh destination session) -> unpack -> restore_fast (refresh frozen). A bind before call b unpacks the
withheld Sink bytes and calls bind() (RoPE re-rotation). Within an episode the withheld Sink is packed once and never
re-serialized from the Sink-less session (asserted by SHA-256).

    python tools/eval/rd_emulate.py --workload dog --phase 1 --gpu_id 0
    python tools/eval/rd_emulate.py --workload dog --phase 1 --dry_run       # CPU schedule test (fake runtime)

Output: <out_root>/<workload>_s<seed>/<condition id>_<stamp>/{calls.csv, summary.json}.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p_ in (ROOT, ROOT / "tools", ROOT / "tools" / "eval"):
    if str(p_) not in sys.path:
        sys.path.insert(0, str(p_))

import rd_metrics as rm  # noqa: E402
import rd_schedule as rs  # noqa: E402


def payload_of(header: dict, bufs) -> bytearray:
    """The bytes a receiver gets for one packed component (offsets as in the header; same layout as the wire)."""
    buf = bytearray(header["nbytes"]); mv = memoryview(buf)
    for t, b in zip(header["tensors"], bufs):
        mv[t["offset"]:t["offset"] + t["nbytes"]] = memoryview(b).cast("B")
    return buf


def sha(b) -> str:
    return hashlib.sha256(memoryview(b)).hexdigest()


def run_condition(rt, cond: dict, base_record: list, dry: bool, metrics_on: bool) -> tuple[list[dict], dict]:
    resets, binds = set(cond["resets"]), set(cond["binds"])
    t1 = min(cond["resets"])
    sinkless = set(rs.sinkless_calls(cond))
    rows, log = [], []
    withheld = None      # (header, payload, sha, packed_at)
    trigger = None
    bound_sha = []
    seq = []             # no-reference metric frames
    keep_from = t1 - 9
    prefix_ok = True
    missing_after = []
    if dry:
        rt.provision(); rt.bound = True   # the fake runtime starts as an uninterrupted (bound) session
    else:
        rt.session = rt.runner.start()
    t_run = time.time()
    for c in range(cond["end"] + 1):
        event = []
        if c in resets:
            t0 = time.perf_counter()
            snap = rt.serialize_live()
            fast = [rt.pack(snap, comp) for comp in ("inflight", "meta")]
            if withheld is None:
                if cond["sink_source"] == "trigger" and trigger is not None:
                    withheld = trigger
                    log.append({"call": c, "op": "episode_open", "sink": "trigger", "sha": trigger[2][:16]})
                else:
                    h, bufs = rt.pack(snap, "sink")
                    pl = payload_of(h, bufs)
                    withheld = (h, pl, sha(pl), c)
                    trigger = trigger or withheld
                    log.append({"call": c, "op": "episode_open", "sink": "packed", "sha": withheld[2][:16]})
            else:
                log.append({"call": c, "op": "reset_inside_episode", "sink": "kept", "sha": withheld[2][:16]})   # never re-serialized
            fast_pl = [(dict(h), payload_of(h, bufs)) for h, bufs in fast]
            del snap, fast
            rt.release(); rt.provision()
            for h, pl in fast_pl:
                rt.unpack(dict(h), pl)
            rt.restore_fast()
            event.append("reset"); log[-1]["reset_s"] = time.perf_counter() - t0
        if c in binds:
            assert withheld is not None, f"bind at {c} without a withheld Sink"
            h, pl, s_, at = withheld
            assert sha(pl) == s_, "withheld Sink bytes changed"
            t0 = time.perf_counter()
            rt.unpack(dict(h), pl)
            shifted = rt.bind()
            bound_sha.append({"call": c, "sha": s_, "packed_at": at})
            log.append({"call": c, "op": "bind", "sha": s_[:16], "packed_at": at, "slots_rerotated": shifted, "bind_s": time.perf_counter() - t0})
            withheld = None
            event.append("bind")
        produced, ps, ss, dt, pos = rt.step(c)
        fr = getattr(rt, "last_frames", None)
        if c < t1 and not dry and fr is not None:
            import mobility_node as mn
            if mn.frame_digest(fr) != base_record[c]["frame_digest"]:
                prefix_ok = False
        if c >= t1 and not produced:
            missing_after.append(c)
        phase = "prefix" if c < t1 else ("sinkless" if c in sinkless else "bound")
        rows.append({"call": c, "phase": phase, "event": "+".join(event), "psnr": ps, "ssim": ss, "produced": produced, "chunk_s": dt, "sink_slot_pos": json.dumps(pos)})
        if metrics_on and fr is not None and c >= keep_from:
            ref = rt.base.get(c); inp = rt.runner.input_frames_for_output_call(c)
            if ref is not None and inp is not None:
                n = min(len(fr), len(ref), len(inp))
                seq.append({"call": c, "O": rm.small_gray(fr[:n]), "R": rm.small_gray(ref[:n]), "I": rm.small_gray(inp[:n])})
    psnr = {r["call"]: r["psnr"] for r in rows}
    b = cond["binds"][-1]
    nr = None
    if metrics_on and seq:
        windows = {"sinkless": sinkless, "post_bind_20": set(range(b, b + 20)), "terminal_10": set(range(b + 90, b + 100))}
        events = [("reset", c) for c in cond["resets"]] + [("bind", c) for c in cond["binds"]]
        nr = rm.no_reference(seq, windows, events)
    # reference Sink changes between the first reset and the final bind (W method: value fingerprint changes, from call 2)
    vfp = [r.get("sink_vfp") for r in base_record]
    rvc = [c for c in range(max(2, t1 + 1), b + 1) if c < len(vfp) and vfp[c] is not None and vfp[c] != vfp[c - 1]]
    episodes_ok = all((bs["packed_at"] in cond["resets"]) for bs in bound_sha)
    if cond["structure"] == "r3c":
        episodes_ok = episodes_ok and bound_sha[-1]["packed_at"] == t1 and sum(1 for l in log if l["op"] == "episode_open" and l["sink"] == "packed") == 1
    summary = {"condition": cond, "t_first_reset": t1, "final_bind": b, "sinkless_calls": len(sinkless), "events": log, "bound_sink": bound_sha,
               "withheld_rule_ok": episodes_ok, "prefix_identical_to_reference": None if dry else prefix_ok,
               "missing_calls_after_first_reset": missing_after, "realized_resets": [r["call"] for r in rows if "reset" in r["event"]],
               "realized_binds": [r["call"] for r in rows if "bind" in r["event"]],
               "trajectory": rm.trajectory(psnr, b), "gap_psnr": rm.gap_psnr(psnr, sorted(sinkless)), "reference_sink_changes": rvc,
               "no_reference": nr, "elapsed_s": time.time() - t_run}
    summary["valid"] = bool(episodes_ok and (dry or prefix_ok) and not missing_after and summary["realized_resets"] == cond["resets"] and summary["realized_binds"] == cond["binds"])
    rt.release()
    return rows, summary


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workload", required=True)
    ap.add_argument("--seed", type=int, default=rs.SEED)
    ap.add_argument("--phase", choices=["0", "1", "x"], required=True, help="x = RD-X replays given with --replay_json")
    ap.add_argument("--replay_json", default="", help="RD-X: JSON list of replay conditions (realized schedules of real runs)")
    ap.add_argument("--only", default="", help="comma list of condition ids (re-runs)")
    ap.add_argument("--gpu_id", type=int, default=0)
    ap.add_argument("--loveu_dir", default=None)
    ap.add_argument("--out_root", default=None)
    ap.add_argument("--dry_run", action="store_true")
    ap.add_argument("--no_metrics", action="store_true", help="skip the section 5.2 metrics (dry runs)")
    ap.add_argument("--dry_promote_calls", default="", help="dry run only: calls at which a bound fake Sink changes (tests fresh vs withheld vs trigger Sinks)")
    a = ap.parse_args()
    if a.phase == "x":
        conds = [dict(c, workload=a.workload, seed=a.seed) for c in json.loads(a.replay_json)]
    else:
        conds = rs.phase0(a.workload) if a.phase == "0" else rs.phase1(a.workload)
    if a.only:
        keep = set(a.only.split(",")); conds = [c for c in conds if c["id"] in keep]
    if not conds:
        print(f"[RD] {a.workload}: no phase-{a.phase} condition", flush=True); return
    for c in conds:
        bad = rs.validate(c)
        assert not bad, (c["id"], bad)
    out_root = Path(a.out_root or ROOT / f"results/evaluation/{'_dryrun_' if a.dry_run else ''}expRD_phase{a.phase}")
    metrics_on = not (a.no_metrics or a.dry_run)
    if metrics_on:
        import cv2  # noqa: F401  (frozen D4: OpenCV Farneback; fail before the model loads if missing)
    from expw_w1 import workload_paths
    import mobility_node as mn

    video, prompt = workload_paths(a.workload, a.loveu_dir)
    N = max(c["end"] for c in conds) + 1
    margs = mn.parse_args(["--label", "RD", "--video_path", str(video), "--prompt_file_path", str(prompt), "--seed", str(a.seed), "--gpu_id", str(a.gpu_id),
                           "--migration_chunk", "0", "--post_chunks", str(N), "--sink_fp"] + (["--dry_run", "--dry_service_s", "0.0005", "--dry_sink_mb", "4", "--dry_promote_calls", a.dry_promote_calls] if a.dry_run else []))
    rt = mn.FakeRuntime(margs) if a.dry_run else mn.GpuRuntime(margs)
    t0 = time.time()
    rt.baseline(0, N, keep_frames=True, write_ref=False)
    base_record = rt.base_record
    t_base = time.time() - t0
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    unit = out_root / f"{a.workload}_s{a.seed}"
    for cond in conds:
        rows, summ = run_condition(rt, cond, base_record, a.dry_run, metrics_on)
        d = unit / f"{cond['id']}_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "calls.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader()
            for r in rows:
                w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in r.items()})
        summ.update({"workload": a.workload, "seed": a.seed, "phase": a.phase, "commit": commit, "host": platform.node(), "gpu_id": a.gpu_id, "dry_run": a.dry_run,
                     "baseline_s": t_base, "video": str(video), "prompt_file": str(prompt),
                     "versions": {} if a.dry_run else {"torch": rt.torch.__version__, "gpu": rt.torch.cuda.get_device_name(rt.device)}})
        (d / "summary.json").write_text(json.dumps(summ, indent=1, default=str))
        T = summ["trajectory"]
        print(f"[RD] {a.workload} {cond['id']}: valid {summ['valid']}, T {T['T'] and round(T['T'], 2)} dB, crossed {T['crossed']}, sustained {T['sustained']}, "
              f"gap {summ['gap_psnr'] and round(summ['gap_psnr'], 1)} dB, {summ['elapsed_s']:.0f} s", flush=True)


if __name__ == "__main__":
    main()
