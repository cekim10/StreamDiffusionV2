#!/usr/bin/env python3
"""Experiment W-AR (exploratory): center-band crop variants of the four preregistered LOVEU videos
(results/evaluation/osdi/expW/preregistration.md section 9). Rows 102-377 (276 x 480) of every frame, cut from the
decoded yuv420p planes and re-encoded losslessly (H.264, qp 0, yuv420p), so the variant equals the cropped source exactly
(checked: PSNR of the decoded variant against the cropped source frames). The originals are not touched; the output
directory must stay outside version control. The unchanged loader scales the 276 x 480 band to 480 x 832 uniformly.

    python -I tools/eval/expw_war_variant.py --src data/loveu_tgve_2023 --out data/loveu_tgve_2023/war
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import av
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TOP, H = 102, 276


def war_videos() -> list[dict]:
    """Within each frame-length group, sorted by motion score: positions floor((j + 0.5) n / 2), j = 0, 1."""
    sel = list(csv.DictReader(open(ROOT / "results/evaluation/osdi/expW/loveu_selection.csv", newline="")))
    out = []
    for frames in ("32", "128"):
        g = sorted((r for r in sel if r["frames"] == frames), key=lambda r: (float(r["motion_score"]), r["video_id"]))
        out += [g[math.floor((j + 0.5) * len(g) / 2)] for j in range(2)]
    return out


def crop_encode(src: Path, dst: Path) -> dict:
    with av.open(str(src)) as ic:
        st = ic.streams.video[0]
        rate = st.average_rate
        planes, rgb_ref = [], []
        for fr in ic.decode(st):
            y = fr.to_ndarray(format="yuv420p")   # (H*3/2, W): Y rows then U, V
            h, w = fr.height, fr.width
            Y = y[:h]; U = y[h:h + h // 4].reshape(h // 2, w // 2); V = y[h + h // 4:].reshape(h // 2, w // 2)
            planes.append((Y[TOP:TOP + H], U[TOP // 2:(TOP + H) // 2], V[TOP // 2:(TOP + H) // 2]))
            rgb_ref.append(fr.to_ndarray(format="rgb24")[TOP:TOP + H])
    with av.open(str(dst), "w") as oc:
        os_ = oc.add_stream("libx264", rate=rate)
        os_.width, os_.height, os_.pix_fmt = planes[0][0].shape[1], H, "yuv420p"
        os_.options = {"qp": "0", "preset": "veryslow"}
        for Y, U, V in planes:
            arr = np.concatenate([Y, U.reshape(-1, Y.shape[1]), V.reshape(-1, Y.shape[1])], axis=0)
            for pkt in os_.encode(av.VideoFrame.from_ndarray(arr, format="yuv420p")):
                oc.mux(pkt)
        for pkt in os_.encode():
            oc.mux(pkt)
    with av.open(str(dst)) as vc:
        dec = [f.to_ndarray(format="rgb24") for f in vc.decode(vc.streams.video[0])]
    mse = [float(np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2)) for a, b in zip(dec, rgb_ref)]
    psnr = [99.0 if m == 0 else 10 * math.log10(255 ** 2 / m) for m in mse]
    return {"frames_in": len(planes), "frames_out": len(dec), "size_out": [H, planes[0][0].shape[1]], "psnr_vs_cropped_min_db": min(psnr)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="prepared directory with the selected mp4s (expw_loveu.py prepare)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    rep = {}
    for r in war_videos():
        src = Path(a.src) / f"{r['video_id']}.mp4"
        dst = out / f"{r['video_id']}__war.mp4"
        rep[r["video_id"]] = {"prompt_type": r["prompt_type"], **crop_encode(src, dst)}
        print(r["video_id"], rep[r["video_id"]])
    (out / "war_variants.json").write_text(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
