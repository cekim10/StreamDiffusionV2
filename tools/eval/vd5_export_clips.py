#!/usr/bin/env python3
"""Experiment VD-5 blinded inspection material (osdi/expVD5/preregistration.md section 6). Reuses VD-3's clip
functions (`vc_export_clips.mark / encode / tile`); the VD-3 / VD-4 exporters, keys and forms are not touched.

Block A (single clips, fully blinded; inspected and committed first): per visual cell REF, V0, B0, R, S3, RS3 over
[move - 16, bind + 20] with random codes, randomized cell order and grid positions, identical M / B markers; plus a
seventh group of four repeats (B0 and R of two cells, chosen by the order seed) under fresh codes.
Block B (paired comparisons; opened only after block A is committed): per visual cell the pairs RS3 vs R and RS3 vs
S3, plus two catch trials (REF's own frames vs V0), each one video [LEFT | REFERENCE | RIGHT] with random sides and
random trial order.
Key: <clips_dir>/sealed/vd5_blind_key.json (SHA-256 printed in both forms; not opened before both are recorded).
Forms: results/evaluation/osdi/expVD5/vd5_inspection_form_A.md and _B.md.

    python tools/eval/vd5_export_clips.py --cells <unit|OT-x,...> --clips_dir /local/vd5_clips --order_seed N
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import secrets
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for p_ in (ROOT, ROOT / "tools", ROOT / "tools" / "eval"):
    if str(p_) not in sys.path:
        sys.path.insert(0, str(p_))

import vc_export_clips as ve  # noqa: E402
import vc_frames as vf  # noqa: E402
import vc_schedules as vs  # noqa: E402

OUT = ROOT / "results/evaluation/osdi/expVD5"
NAMES = ("REF", "V0", "B0", "R", "S3", "RS3")
FIELDS_A = ("boundary jump at M (none / mild / strong)", "motion reversal M..M+8 (none / reversed / unclear)", "content / appearance change M..B (none / change)",
            "identity M..B (kept / changed / unsure)", "color change M..B (none / shift)", "flicker / temporal instability M..B (none / flicker)",
            "new discontinuity at B (none / jump)", "notes")
FIELDS_B = ("less visible discontinuity at M (left / right / no difference)", "closer to the reference over M..B: content, color, motion (left / right / no difference)", "notes")
PAIRS = (("RS3", "R"), ("RS3", "S3"))
N_REPEAT_CELLS, N_CATCH = 2, 2


def cond_id(name: str, x: str) -> str:
    return {"REF": "REF", "RS3": f"VD5{x}-RS3"}.get(name, f"VD4{x}-{name}")


def new_code(used: set) -> str:
    while True:
        code = secrets.token_hex(3).upper()
        if code not in used:
            used.add(code)
            return code


def pad_grid(tiles: list, cols: int = 3, rows: int = 2) -> np.ndarray:
    tiles = list(tiles)
    while len(tiles) < cols * rows:
        tiles.append(np.zeros_like(tiles[0]))
    return np.concatenate([np.concatenate(tiles[r * cols:(r + 1) * cols], 1) for r in range(rows)], 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(ROOT / "results/evaluation/expVC"))
    ap.add_argument("--cells", required=True, help="comma list of <unit>|OT-<x> (the six visual cells)")
    ap.add_argument("--clips_dir", required=True)
    ap.add_argument("--order_seed", type=int, required=True)
    ap.add_argument("--form_a", default=None)
    ap.add_argument("--form_b", default=None)
    a = ap.parse_args()
    root, clips = Path(a.root), Path(a.clips_dir)
    sched = json.loads((ROOT / "results/evaluation/osdi/expVC/vc_schedules.json").read_text())
    rng = random.Random(a.order_seed)
    cells = [tuple(c.split("|")) for c in a.cells.split(",") if c]
    rng.shuffle(cells)
    used, key_a, key_b, groups = set(), {}, {}, []
    F = {}   # (cell, name) -> marked frames
    meta = {}
    for unit, ot in cells:
        x = ot.split("-")[1]
        cond = next(c for c in vs.unit_sched(sched, unit)["conditions"] if c["id"] == ot)
        m, b = cond["resets"][0], cond["binds"][-1]
        calls = list(range(m - 16, b + 21))
        for n in NAMES:
            sp = root / unit / cond_id(n, x) / "summary.json"
            if not sp.exists():
                sys.exit(f"[vd5 clips] missing run {unit}/{cond_id(n, x)}")
            R = vf.read_calls(Path(json.loads(sp.read_text())["frames"]), calls)
            F[(f"{unit}|{ot}", n)] = [ve.mark(fr, c - m, "M" if c == m else ("B" if c == b else None)) for c in calls for fr in R.get(c, [])]
        inp = unit.rsplit("_s", 1)[0]
        meta[f"{unit}|{ot}"] = {"bind_rel": b - m, "repo": inp in ve.REPO_INPUTS}
    # ---- block A: six cell groups
    for gi, (unit, ot) in enumerate(cells, 1):
        cell = f"{unit}|{ot}"
        n_min = min(len(F[(cell, n)]) for n in NAMES)
        codes = []
        for n in NAMES:
            code = new_code(used); codes.append(code)
            key_a[code] = {"cell": cell, "condition": cond_id(n, ot.split("-")[1]), "name": n, "repeat": False}
            ve.encode(clips / "blockA" / f"group{gi:02d}" / f"{code}.mp4", F[(cell, n)][:n_min])
        order = list(range(len(NAMES))); rng.shuffle(order)
        ve.encode(clips / "blockA" / f"group{gi:02d}" / "grid.mp4", [pad_grid([ve.tile(F[(cell, NAMES[j])][i], codes[j]) for j in order]) for i in range(n_min)])
        groups.append({"label": f"group {gi:02d}: one cell" + (" (repository clip)" if meta[cell]["repo"] else " (internal only: LOVEU, never redistributed)"),
                       "head": f"M at 0, B at +{meta[cell]['bind_rel']}; {n_min} frames", "codes": [codes[j] for j in order]})
    # ---- block A: the repeats (B0 and R of two cells, fresh codes, mixed into one group)
    rep_cells = rng.sample([f"{u}|{o}" for u, o in cells], N_REPEAT_CELLS)
    reps = [(c_, n) for c_ in rep_cells for n in ("B0", "R")]
    rng.shuffle(reps)
    gi = len(cells) + 1
    rcodes = []
    for c_, n in reps:
        code = new_code(used); rcodes.append(code)
        key_a[code] = {"cell": c_, "condition": cond_id(n, c_.split("|")[1].split("-")[1]), "name": n, "repeat": True}
        ve.encode(clips / "blockA" / f"group{gi:02d}" / f"{code}.mp4", F[(c_, n)])
    n_min = min(len(F[r]) for r in reps)
    ve.encode(clips / "blockA" / f"group{gi:02d}" / "grid.mp4", [pad_grid([ve.tile(F[r][i], c) for r, c in zip(reps, rcodes)]) for i in range(n_min)])
    groups.append({"label": f"group {gi:02d}: four clips from the cells above, in random order (internal only: may contain LOVEU clips)",
                   "head": "each clip carries its own M / B markers; rate each clip on its own", "codes": rcodes})
    # ---- block B: paired comparisons with the labelled reference
    trials = [(f"{u}|{o}", p, "pair") for u, o in cells for p in PAIRS]
    trials += [(c_, ("REF", "V0"), "catch") for c_ in rng.sample([f"{u}|{o}" for u, o in cells], N_CATCH)]
    rng.shuffle(trials)
    for ti, (c_, (n1, n2), kind) in enumerate(trials, 1):
        left, right = (n1, n2) if rng.random() < 0.5 else (n2, n1)
        n_min = min(len(F[(c_, n)]) for n in (left, right, "REF"))
        frames = [np.concatenate([ve.tile(F[(c_, left)][i], "LEFT"), ve.tile(F[(c_, "REF")][i], "REFERENCE"), ve.tile(F[(c_, right)][i], "RIGHT")], 1) for i in range(n_min)]
        tid = f"T{ti:02d}"
        ve.encode(clips / "blockB" / f"{tid}.mp4", frames)
        key_b[tid] = {"cell": c_, "left": left, "right": right, "kind": kind}
    (clips / "sealed").mkdir(parents=True, exist_ok=True)
    kb = json.dumps({"order_seed": a.order_seed, "block_a": key_a, "block_b": key_b}, indent=1, sort_keys=True).encode()
    (clips / "sealed" / "vd5_blind_key.json").write_bytes(kb)
    ksha = hashlib.sha256(kb).hexdigest()
    common = (f"Key: `<clips_dir>/sealed/vd5_blind_key.json`, SHA-256 `{ksha}` (do not open before BOTH forms are recorded and committed). "
              f"Order seed {a.order_seed}. Markers: yellow border + 'M' = the move call, cyan border + 'B' = the exact-bind call; the corner number is the call "
              "index relative to M. Use the listed words exactly.")
    LA = ["# VD-5 blinded inspection, block A: single clips (fill a copy as `vd5_inspection_A.md`, commit it BEFORE opening block B)", "", common,
          "Clips in `<clips_dir>/blockA/groupNN/`: one file per code and `grid.mp4`. A jump at M is `mild` or `strong` whenever one is visible; "
          "`unclear` only for motion reversal, `unsure` only for identity.", "", "STATUS: NOT RECORDED   <- change to `STATUS: RECORDED` when every row is filled", ""]
    for g in groups:
        LA += [f"## {g['label']} ({g['head']})", "", "| code | " + " | ".join(FIELDS_A) + " |", "|" + "---|" * (len(FIELDS_A) + 1)]
        LA += [f"| {code} |" + " |" * len(FIELDS_A) for code in g["codes"]] + [""]
    LB = ["# VD-5 blinded inspection, block B: paired comparisons (open only after block A is committed; fill a copy as `vd5_inspection_B.md`)", "", common,
          "Videos in `<clips_dir>/blockB/TNN.mp4`: LEFT and RIGHT are two coded outputs of one cell, REFERENCE (middle) is the uninterrupted stream of that cell. "
          "Answer each question with `left`, `right` or `no difference`.", "", "STATUS: NOT RECORDED   <- change to `STATUS: RECORDED` when every row is filled", "",
          "| trial | " + " | ".join(FIELDS_B) + " |", "|" + "---|" * (len(FIELDS_B) + 1)]
    LB += [f"| {tid} |" + " |" * len(FIELDS_B) for tid in key_b] + [""]
    fa, fb = Path(a.form_a or OUT / "vd5_inspection_form_A.md"), Path(a.form_b or OUT / "vd5_inspection_form_B.md")
    for f_, L in ((fa, LA), (fb, LB)):
        f_.parent.mkdir(parents=True, exist_ok=True)
        f_.write_text("\n".join(L) + "\n")
        (clips / f_.name).write_text("\n".join(L) + "\n")
    print(f"[vd5 clips] block A {len(key_a)} clips in {len(groups)} groups, block B {len(key_b)} trials -> {clips}; key sha256 {ksha}; forms {fa}, {fb}")


if __name__ == "__main__":
    main()
