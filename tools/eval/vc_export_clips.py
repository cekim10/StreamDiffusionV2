#!/usr/bin/env python3
"""Experiment VD-3 visual evidence (osdi/expVD3/preregistration.md section 5): blinded, randomized clips for the
user's inspection. Runs on the host that holds the frames; clips go to --clips_dir on that host's local disk and are
never committed (LOVEU clips are for internal inspection only and are never redistributed).

Per cell (unit x schedule): REF, frozen M1 (OT-x), TSin, DR2, DR2+TSin, TSinKC over [move - 16, bind + 20] (the
pre-move anchor, the whole Sink-less window, the bind and 20 calls after it), H.264 CRF 18 at 16 fps:
  - one clip per condition, named by a random code (no condition information in the name, the frames or the order);
  - one side-by-side grid per cell (3 x 2 tiles at half size, tile positions randomized, each tile labelled with its
    code);
  - markers identical in every clip of a cell (REF included): the move call's frames carry an "M" overlay and a yellow
    border, the bind call's frames a "B" overlay and a cyan border; the elapsed call index relative to the move is
    shown in a corner.
The code-to-condition key goes to <clips_dir>/sealed/vd3_blind_key.json (not opened before the inspection is
recorded); its SHA-256 is printed in the generated form so the key cannot be replaced afterwards. The presentation
order (cells shuffled, codes shuffled inside each cell) comes from --order_seed and is recorded in the form.

    python tools/eval/vc_export_clips.py --root results/evaluation/expVC --clips_dir /local/vd3_clips --order_seed 20261025
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

import vc_frames as vf  # noqa: E402
import vc_schedules as vs  # noqa: E402

INPUTS = ("dog", "train", "butterfly-feeding-slow-motion", "audi-snow-trail")
SHOWN = ("REF", "OT", "TSin", "DR2", "DR2+TSin", "TSinKC")
CONFIRM = {("train", 0), ("audi-snow-trail", 0), ("dog", 1), ("train", 1), ("butterfly-feeding-slow-motion", 1), ("audi-snow-trail", 1)}
REPO_INPUTS = ("dog", "train")   # repository clips; LOVEU inputs are inspected internally only
FIELDS = ("identity (kept / changed / unsure)", "appearance (kept / changed)", "color (no shift / shift)", "boundary at M (no visible jump / jump)",
          "Sink-less interval M..B (stable / drifts / breaks)", "new discontinuity at the exact Sink bind B (no visible jump / jump)", "notes")


def cond_id(name: str, x: str) -> str:
    return "REF" if name == "REF" else (f"OT-{x}" if name == "OT" else f"VD3{x}-{name}")


def mark(fr: np.ndarray, rel: int, event: str | None) -> np.ndarray:
    import cv2

    f = np.ascontiguousarray(fr.copy())
    h, w = f.shape[:2]
    if event:
        col = (255, 220, 0) if event == "M" else (0, 220, 255)
        t = max(4, w // 120)
        f[:t], f[-t:], f[:, :t], f[:, -t:] = col, col, col, col
        cv2.putText(f, event, (w // 2 - 20, h // 8), cv2.FONT_HERSHEY_SIMPLEX, max(0.8, w / 500), col, 3, cv2.LINE_AA)
    cv2.putText(f, f"{rel:+d}", (8, h - 10), cv2.FONT_HERSHEY_SIMPLEX, max(0.4, w / 1300), (255, 255, 255), 1, cv2.LINE_AA)
    return f


def encode(path: Path, frames: list[np.ndarray], fps=16):
    import av

    path.parent.mkdir(parents=True, exist_ok=True)
    h, w = frames[0].shape[:2]
    with av.open(str(path), "w", format="mp4") as c:
        s = c.add_stream("libx264", rate=fps); s.width, s.height, s.pix_fmt = w - w % 2, h - h % 2, "yuv420p"; s.options = {"crf": "18", "preset": "veryfast"}
        for fr in frames:
            for p in s.encode(av.VideoFrame.from_ndarray(np.ascontiguousarray(fr[:h - h % 2, :w - w % 2]), format="rgb24")):
                c.mux(p)
        for p in s.encode():
            c.mux(p)


def tile(fr: np.ndarray, code: str) -> np.ndarray:
    import cv2

    t = np.ascontiguousarray(fr[::2, ::2])
    cv2.putText(t, code, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    return t


def cell_frames(root: Path, unit: str, x: str, cond: dict, k: int) -> dict:
    m, b = cond["resets"][0], cond["binds"][-1]
    calls = list(range(m - 16, b + 21))
    out = {}
    for name in SHOWN:
        sp = root / unit / cond_id(name, x) / "summary.json"
        if not sp.exists():
            continue
        s = json.loads(sp.read_text())
        R = vf.read_calls(Path(s["frames"]), calls)
        seq = []
        for c in calls:
            for fr in R.get(c, []):
                seq.append(mark(fr, c - m, "M" if c == m else ("B" if c == b else None)))
        out[name] = seq
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(ROOT / "results/evaluation/expVC"))
    ap.add_argument("--clips_dir", required=True)
    ap.add_argument("--order_seed", type=int, required=True)
    ap.add_argument("--inputs", default=",".join(INPUTS))
    ap.add_argument("--seeds", default="0,1")
    ap.add_argument("--form", default=str(ROOT / "results/evaluation/osdi/expVD3/vd3_inspection_form.md"))
    a = ap.parse_args()
    root, clips = Path(a.root), Path(a.clips_dir)
    sched = json.loads((ROOT / "results/evaluation/osdi/expVC/vc_schedules.json").read_text())
    rng = random.Random(a.order_seed)
    cells = [(inp, int(sd), x) for inp in a.inputs.split(",") if inp for sd in a.seeds.split(",") if sd for x in ("1", "L")]
    cells = [c for c in cells if (root / f"{c[0]}_s{c[1]}" / "REF" / "summary.json").exists()]
    rng.shuffle(cells)
    key, form_cells, used = {}, [], set()
    for ci, (inp, sd, x) in enumerate(cells, 1):
        unit = f"{inp}_s{sd}"
        cond = next(c for c in vs.unit_sched(sched, unit)["conditions"] if c["id"] == f"OT-{x}")
        k = int(json.loads((root / unit / "REF" / "summary.json").read_text()).get("k", 2))
        F = cell_frames(root, unit, x, cond, k)
        names = [n for n in SHOWN if n in F]
        n_min = min(len(F[n]) for n in names)
        codes = []
        for n in names:
            while True:
                code = secrets.token_hex(3).upper()
                if code not in used:
                    used.add(code); break
            codes.append(code)
            key[code] = {"cell": f"{unit}|OT-{x}", "condition": cond_id(n, x), "name": n}
            encode(clips / f"cell{ci:02d}" / f"{code}.mp4", F[n][:n_min])
        order = list(range(len(names))); rng.shuffle(order)
        grid = []
        for i in range(n_min):
            tiles = [tile(F[names[j]][i], codes[j]) for j in order]
            while len(tiles) < 6:
                tiles.append(np.zeros_like(tiles[0]))
            grid.append(np.concatenate([np.concatenate(tiles[r * 3:(r + 1) * 3], 1) for r in range(2)], 0))
        encode(clips / f"cell{ci:02d}" / "grid.mp4", grid)
        pres = [codes[j] for j in order]
        form_cells.append({"cell": ci, "label": f"cell {ci:02d}" + (" (repository clip)" if inp in REPO_INPUTS else " (internal only: LOVEU, never redistributed)")
                           + (" - counterfactual: copied schedule" if (cond.get("counterfactual") or any(c.get("counterfactual") for c in vs.unit_sched(sched, unit)["conditions"]
                                                                                                           if c.get("vd3_of") == f"OT-{x}")) else ""), "codes": pres,
                           "move_rel": 0, "bind_rel": cond["binds"][-1] - cond["resets"][0], "frames": n_min})
    (clips / "sealed").mkdir(parents=True, exist_ok=True)
    kb = json.dumps({"order_seed": a.order_seed, "key": key}, indent=1, sort_keys=True).encode()
    (clips / "sealed" / "vd3_blind_key.json").write_bytes(kb)
    ksha = hashlib.sha256(kb).hexdigest()
    L = ["# VD-3 blinded inspection form (fill a copy as `vd3_inspection.md` and commit it BEFORE the aggregate verdicts are produced)", "",
         f"Key: `<clips_dir>/sealed/vd3_blind_key.json`, SHA-256 `{ksha}` (do not open before this form is recorded). Order seed {a.order_seed}. "
         "Clips in `<clips_dir>/cellNN/`: one file per code and `grid.mp4` (all codes of the cell side by side, positions randomized). "
         "Markers: yellow border + 'M' = the move call, cyan border + 'B' = the exact-bind call (present in every clip of the cell, including the uninterrupted one); "
         "the number in the corner is the call index relative to M. Answer for every code; 'unsure' is allowed for identity.", "",
         "STATUS: NOT RECORDED   <- change to `STATUS: RECORDED` when every row is filled", ""]
    for fc in form_cells:
        L += [f"## {fc['label']} (M at 0, B at +{fc['bind_rel']}; {fc['frames']} frames)", "",
              "| code | " + " | ".join(FIELDS) + " |", "|" + "---|" * (len(FIELDS) + 1)]
        L += [f"| {code} |" + " |" * len(FIELDS) for code in fc["codes"]]
        L.append("")
    Path(a.form).parent.mkdir(parents=True, exist_ok=True)
    Path(a.form).write_text("\n".join(L) + "\n")
    (clips / "vd3_inspection_form.md").write_text("\n".join(L) + "\n")
    print(f"[clips] {len(form_cells)} cells, {len(key)} clips -> {clips}; key sha256 {ksha}; form {a.form}")


if __name__ == "__main__":
    main()
