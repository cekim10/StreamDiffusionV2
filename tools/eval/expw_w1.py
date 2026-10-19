#!/usr/bin/env python3
"""Experiment W, W1: Sink stability without migration (results/evaluation/osdi/expW/preregistration.md section 4).

One unit = (workload, seed): the unmodified pipeline for calls 0..329 on one GPU, through the SAME code path as a node's
reference baseline (tools/eval/mobility_node.GpuRuntime.baseline with --sink_fp), so W1 records are comparable with the
W2 references. Per call: output-frame digest, Sink value fingerprints (per layer and sink slot), sink-slot positions,
service time; offline: promotion flags and the call class from the loop arithmetic (tools/eval/expw_loop_audit.py).

    python tools/eval/expw_w1.py --workload dog --seed 0 --gpu_id 0
    python tools/eval/expw_w1.py --workload mbike-trick --seed 0 --loveu_dir data/loveu_tgve_2023
    python tools/eval/expw_w1.py --workload dog --seed 0 --dry_run          # CPU protocol test (fake runtime)

Output: results/evaluation/expW_W1/<workload>_s<seed>_<stamp>/ (w1_calls.csv, w1_summary.json).
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

from expw_loop_audit import ADJ, CHUNK, FIRST, cut_calls  # noqa: E402

REPO_CLIPS = {"dog": ("examples/original.mp4", "examples/prompt.txt"), "bird": ("examples/bird.mp4", "examples/bird_prompt.txt"),
              "boxing": ("examples/boxing.mp4", "examples/boxing_prompt.txt"), "train": ("examples/train.mp4", "examples/train_prompt.txt")}
WINDOWS = (6, 25, 52)
STAT_FROM = 30


def workload_paths(name: str, loveu_dir: str | None) -> tuple[Path, Path]:
    if name in REPO_CLIPS:
        v, p = REPO_CLIPS[name]
        return ROOT / v, ROOT / p
    sel = {r["video_id"]: r for r in csv.DictReader(open(ROOT / "results/evaluation/osdi/expW/loveu_selection.csv", newline=""))}
    if name not in sel:
        sys.exit(f"unknown workload {name}")
    d = Path(loveu_dir or ROOT / "data/loveu_tgve_2023")
    return d / f"{name}.mp4", d / f"{name}__{sel[name]['prompt_type']}.txt"


def frame_count(path: Path) -> int:
    import av

    with av.open(str(path)) as c:
        return sum(1 for _ in c.decode(c.streams.video[0]))


def call_classes(T: int, n: int) -> list[str]:
    cuts = set(cut_calls(T, n + 4))
    adj = {c + d for c in cuts for d in range(ADJ + 1)}
    out = []
    for c in range(n):
        if c in cuts:
            out.append("cut")
        elif c in adj:
            out.append("adjacent")
        elif FIRST + CHUNK * c + CHUNK - 1 < T:
            out.append("first_pass")
        else:
            out.append("repeated")
    return out


def analyse(rec: list[dict], classes: list[str]) -> dict:
    """Promotions by cause and P_w (as fed / within-clip), preregistration section 4."""
    n = len(rec)
    # W Amendment 1 (2026-10-19): the third sink slot is written at call 1 (2-step Stream Batch), so a promotion is counted
    # from call 2 on; the call-1 change is sink filling
    promo = [False, False] + [rec[c]["sink_vfp"] != rec[c - 1]["sink_vfp"] for c in range(2, n)]
    boundary = {c for c in range(n) if classes[c] in ("cut", "adjacent")}
    cnt = lambda pred: (sum(1 for c in range(n) if pred(c) and promo[c]), sum(1 for c in range(n) if pred(c)))  # noqa: E731
    fp_num, fp_den = cnt(lambda c: c >= 2 and classes[c] == "first_pass")
    rp_num, rp_den = cnt(lambda c: c >= STAT_FROM and classes[c] == "repeated")
    bd_num, bd_den = cnt(lambda c: c >= STAT_FROM and c in boundary)
    cuts = [c for c in range(STAT_FROM, n) if classes[c] == "cut"]
    cut_followed = sum(1 for c in cuts if any(promo[x] for x in range(c, min(n, c + ADJ + 1))))
    pw = {}
    for w in WINDOWS:
        starts = list(range(STAT_FROM, n - w))
        fed = [any(promo[x] for x in range(c, c + w + 1)) for c in starts]
        inside = [c for c in starts if not any(x in boundary for x in range(c, c + w + 1))]
        wc = [any(promo[x] for x in range(c, c + w + 1)) for c in inside]
        pw[str(w)] = {"as_fed": sum(fed) / len(fed) if fed else None, "as_fed_windows": len(fed),
                      "within_clip": (sum(wc) / len(wc)) if len(wc) >= 10 else None, "within_clip_windows": len(wc),
                      "within_clip_measurable": len(wc) >= 10}
    return {"promotion_calls": [c for c in range(n) if promo[c]],
            "first_pass_within_clip": {"promotions": fp_num, "calls": fp_den, "per_100": (100 * fp_num / fp_den) if fp_den >= 10 else None},
            "repeated_within_clip": {"promotions": rp_num, "calls": rp_den, "per_100": (100 * rp_num / rp_den) if rp_den else None},
            "boundary_associated": {"promotions": bd_num, "calls": bd_den, "cut_calls": len(cuts), "cuts_followed_by_promotion": cut_followed,
                                    "boundary_promotion_probability": (cut_followed / len(cuts)) if cuts else None},
            "P_w": pw, "stable_at_w": {w: {k: (v[k] <= 0.05 if v[k] is not None else None) for k in ("as_fed", "within_clip")} for w, v in pw.items()}}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workload", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--gpu_id", type=int, default=0)
    ap.add_argument("--calls", type=int, default=330)
    ap.add_argument("--loveu_dir", default=None)
    ap.add_argument("--video_path", default=None, help="override (W-AR variant file)")
    ap.add_argument("--tag", default="", help="suffix of the output directory (e.g. war)")
    ap.add_argument("--out_root", default=str(ROOT / "results/evaluation/expW_W1"))
    ap.add_argument("--dry_run", action="store_true")
    a = ap.parse_args()
    video, prompt = workload_paths(a.workload, a.loveu_dir)
    if a.video_path:
        video = Path(a.video_path)
    import mobility_node as mn

    margs = mn.parse_args(["--label", "W1", "--video_path", str(video), "--prompt_file_path", str(prompt), "--seed", str(a.seed), "--gpu_id", str(a.gpu_id),
                           "--migration_chunk", "0", "--post_chunks", str(a.calls), "--sink_fp"] + (["--dry_run", "--dry_service_s", "0.001"] if a.dry_run else []))
    T = 81 if a.dry_run and not video.exists() else frame_count(video)
    t0 = time.time()
    rt = mn.FakeRuntime(margs) if a.dry_run else mn.GpuRuntime(margs)
    rt.baseline(0, a.calls, keep_frames=False, write_ref=False)
    rec = rt.base_record
    classes = call_classes(T, a.calls)
    stats = analyse(rec, classes)
    out = Path(a.out_root) / f"{a.workload}_s{a.seed}{('_' + a.tag) if a.tag else ''}_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    out.mkdir(parents=True, exist_ok=True)
    promo = set(stats["promotion_calls"])
    with open(out / "w1_calls.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["call", "class", "promotion", "frame_digest", "service_s", "sink_slot_pos", "sink_vfp"])
        for r, cl in zip(rec, classes):
            w.writerow([r["call"], cl, r["call"] in promo, r["frame_digest"], f"{r['service_s']:.5f}", json.dumps(r["sink_slot_pos"]), json.dumps(r["sink_vfp"])])
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    meta = {"workload": a.workload, "seed": a.seed, "calls": a.calls, "video": str(video), "video_sha256": hashlib.sha256(video.read_bytes()).hexdigest() if video.exists() else None,
            "prompt_file": str(prompt), "prompt": prompt.read_text(encoding="utf-8").strip() if prompt.exists() else None, "T_frames": T,
            "commit": commit, "host": platform.node(), "gpu_id": a.gpu_id, "dry_run": a.dry_run, "elapsed_s": time.time() - t0,
            "versions": {} if a.dry_run else {"torch": rt.torch.__version__, "gpu": rt.torch.cuda.get_device_name(rt.device)},
            "n_fingerprint_values": len(rec[0]["sink_vfp"] or []), **stats}
    (out / "w1_summary.json").write_text(json.dumps(meta, indent=1))
    print(f"[W1] {a.workload} s{a.seed}: {len(stats['promotion_calls'])} promotions; P_25 as fed {stats['P_w']['25']['as_fed']}; -> {out}")


if __name__ == "__main__":
    main()
