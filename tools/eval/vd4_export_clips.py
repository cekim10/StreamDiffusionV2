#!/usr/bin/env python3
"""Experiment VD-4 blinded clips for one inspection session (osdi/expVD4/preregistration.md section 6). Reuses VD-3's
clip functions (`vc_export_clips.mark / encode / tile`); VD-3's exporter, key and form are not touched.

Per cell of the session: REF, B0 (every session: its own false-positive baseline) and the session's conditions, over
[move - 16, bind + 20], random codes, randomized cell order and grid positions, identical M / B markers in every clip.
Key: <clips_dir>/sealed/vd4_<session>_blind_key.json (SHA-256 printed in the form; not opened before the form is
recorded). Form: results/evaluation/osdi/expVD4/vd4_inspection_form_<session>.md.

    python tools/eval/vd4_export_clips.py --session stage1 --names DR,D,R,A1 --cells <unit|OT-x,...> --clips_dir /local/vd4_clips/stage1 --order_seed N
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

FIELDS = ("identity (kept / changed / unsure)", "appearance drift M..B (none / drift)", "color (no shift / shift)",
          "boundary jump at M (no visible jump / jump)", "flicker / jitter M..B (none / flicker)", "motion consistency M..B (natural / unnatural)",
          "new discontinuity at the exact Sink bind B (no visible jump / jump)", "notes")
OUT = ROOT / "results/evaluation/osdi/expVD4"


def cond_id(name: str, x: str) -> str:
    return "REF" if name == "REF" else f"VD4{x}-{name}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(ROOT / "results/evaluation/expVC"))
    ap.add_argument("--session", required=True)
    ap.add_argument("--names", required=True, help="the session's conditions besides REF and B0 (at most 4)")
    ap.add_argument("--cells", required=True, help="comma list of <unit>|OT-<x>")
    ap.add_argument("--clips_dir", required=True)
    ap.add_argument("--order_seed", type=int, required=True)
    ap.add_argument("--form", default=None)
    a = ap.parse_args()
    names = ["REF", "B0"] + [n for n in a.names.split(",") if n and n not in ("REF", "B0")]
    assert len(names) <= 6, "a grid holds six clips"
    root, clips = Path(a.root), Path(a.clips_dir)
    sched = json.loads((ROOT / "results/evaluation/osdi/expVC/vc_schedules.json").read_text())
    rng = random.Random(a.order_seed)
    cells = [tuple(c.split("|")) for c in a.cells.split(",") if c]
    rng.shuffle(cells)
    key, form_cells, used = {}, [], set()
    for ci, (unit, ot) in enumerate(cells, 1):
        x = ot.split("-")[1]
        cond = next(c for c in vs.unit_sched(sched, unit)["conditions"] if c["id"] == ot)
        m, b = cond["resets"][0], cond["binds"][-1]
        calls = list(range(m - 16, b + 21))
        F = {}
        for n in names:
            sp = root / unit / cond_id(n, x) / "summary.json"
            if not sp.exists():
                continue
            R = vf.read_calls(Path(json.loads(sp.read_text())["frames"]), calls)
            F[n] = [ve.mark(fr, c - m, "M" if c == m else ("B" if c == b else None)) for c in calls for fr in R.get(c, [])]
        present = [n for n in names if n in F]
        n_min = min(len(F[n]) for n in present)
        codes = []
        for n in present:
            while True:
                code = secrets.token_hex(3).upper()
                if code not in used:
                    used.add(code); break
            codes.append(code)
            key[code] = {"cell": f"{unit}|{ot}", "condition": cond_id(n, x), "name": n}
            ve.encode(clips / f"cell{ci:02d}" / f"{code}.mp4", F[n][:n_min])
        order = list(range(len(present))); rng.shuffle(order)
        grid = []
        for i in range(n_min):
            tiles = [ve.tile(F[present[j]][i], codes[j]) for j in order]
            while len(tiles) < 6:
                tiles.append(np.zeros_like(tiles[0]))
            grid.append(np.concatenate([np.concatenate(tiles[r * 3:(r + 1) * 3], 1) for r in range(2)], 0))
        ve.encode(clips / f"cell{ci:02d}" / "grid.mp4", grid)
        inp = unit.rsplit("_s", 1)[0]
        cf = any(c.get("counterfactual") for c in vs.unit_sched(sched, unit)["conditions"] if c.get("vd4_of") == ot)
        form_cells.append({"label": f"cell {ci:02d}" + (" (repository clip)" if inp in ve.REPO_INPUTS else " (internal only: LOVEU, never redistributed)")
                           + (" - counterfactual: copied schedule" if cf else ""), "codes": [codes[j] for j in order], "bind_rel": b - m, "frames": n_min})
    (clips / "sealed").mkdir(parents=True, exist_ok=True)
    kb = json.dumps({"session": a.session, "order_seed": a.order_seed, "key": key}, indent=1, sort_keys=True).encode()
    kname = f"vd4_{a.session}_blind_key.json"
    (clips / "sealed" / kname).write_bytes(kb)
    ksha = hashlib.sha256(kb).hexdigest()
    L = [f"# VD-4 blinded inspection form, session {a.session} (fill a copy as `vd4_inspection_{a.session}.md` and commit it BEFORE the key is opened)", "",
         f"Key: `<clips_dir>/sealed/{kname}`, SHA-256 `{ksha}` (do not open before this form is recorded). Order seed {a.order_seed}. "
         "Clips in `<clips_dir>/cellNN/`: one file per code and `grid.mp4`. Markers: yellow border + 'M' = the move call, cyan border + 'B' = the exact-bind "
         "call (in every clip, including the uninterrupted one); the corner number is the call index relative to M. Use the listed words exactly; "
         "'unsure' only for identity.", "", "STATUS: NOT RECORDED   <- change to `STATUS: RECORDED` when every row is filled", ""]
    for fc in form_cells:
        L += [f"## {fc['label']} (M at 0, B at +{fc['bind_rel']}; {fc['frames']} frames)", "",
              "| code | " + " | ".join(FIELDS) + " |", "|" + "---|" * (len(FIELDS) + 1)]
        L += [f"| {code} |" + " |" * len(FIELDS) for code in fc["codes"]]
        L.append("")
    form = Path(a.form or OUT / f"vd4_inspection_form_{a.session}.md")
    form.parent.mkdir(parents=True, exist_ok=True)
    form.write_text("\n".join(L) + "\n")
    (clips / form.name).write_text("\n".join(L) + "\n")
    print(f"[clips] session {a.session}: {len(form_cells)} cells, {len(key)} clips -> {clips}; key sha256 {ksha}; form {form}")


if __name__ == "__main__":
    main()
