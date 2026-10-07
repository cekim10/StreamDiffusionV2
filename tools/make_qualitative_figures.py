#!/usr/bin/env python3
"""Qualitative frame strips around the migration boundary, from the saved videos of the bit-exact
mechanism run (results/state_migration/mechanism/videos, frames from the migration chunk onward, 4 frames/chunk).

fig2a_qualitative : Baseline / No sink / Ephemeral state lost        (Background, pairs with the Fig. 2 curves)
figE_qualitative  : Baseline / No durable state / Ours (late binding) (Evaluation: migration -> gap -> rebind)
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import imageio.v3 as iio
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
VID = ROOT / "results/state_migration/mechanism/videos"
FPC = 4  # frames per chunk


def load(name: str) -> np.ndarray:
    return iio.imread(VID / f"{name}.mp4", plugin="pyav")  # [T, H, W, 3] uint8


def psnr(a: np.ndarray, b: np.ndarray) -> float:
    mse = float(np.mean((a.astype(np.float32) / 255 - b.astype(np.float32) / 255) ** 2))
    return 99.0 if mse == 0 else 10 * math.log10(1 / mse)


def strip(rows: list[tuple[str, str, str]], chunks: list[int], out: Path, title: str, arrival: int | None = None,
          frame_in_chunk: int = 3, crop=None):
    """rows: (label, video name, note). chunks: chunk offsets after migration to show."""
    base = load(rows[0][1])
    vids = {name: load(name) for _, name, _ in rows}
    ncol = len(chunks)
    fig, axes = plt.subplots(len(rows), ncol, figsize=(1.25 * ncol + 0.9, 0.78 * len(rows) + 0.55), gridspec_kw={"wspace": 0.04, "hspace": 0.22})
    for r, (label, name, note) in enumerate(rows):
        v = vids[name]
        for c, ch in enumerate(chunks):
            ax = axes[r, c]
            fi = ch * FPC + frame_in_chunk
            fr = v[min(fi, len(v) - 1)]
            ref = base[min(fi, len(base) - 1)]
            if crop:
                y0, y1, x0, x1 = crop; fr = fr[y0:y1, x0:x1]; ref = ref[y0:y1, x0:x1]
            ax.imshow(fr); ax.set_xticks([]); ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_visible(False)
            if r == 0:
                ax.set_title(f"M+{ch}", fontsize=7.5, pad=2)
            if r > 0:
                p = psnr(ref, fr)
                ax.text(0.03, 0.04, f"{p:.0f} dB", transform=ax.transAxes, fontsize=6.5, color="white", va="bottom",
                        bbox=dict(boxstyle="round,pad=0.15", fc="black", alpha=0.55, ec="none"))
            if c == 0:
                ax.text(-0.06, 0.5, label, transform=ax.transAxes, ha="right", va="center", fontsize=7.5, weight="bold")
                if note:
                    ax.text(-0.06, 0.08, note, transform=ax.transAxes, ha="right", va="center", fontsize=6.2, color="#555555")
    if arrival is not None and arrival in chunks:
        c = chunks.index(arrival)
        for r in range(len(rows)):
            axes[r, c].add_patch(plt.Rectangle((0, 0), 1, 1, transform=axes[r, c].transAxes, fill=False, ec="#2ca02c", lw=2.0))
    fig.suptitle(title, fontsize=8, x=0.02, ha="left", y=0.995)
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight", dpi=200); fig.savefig(out.with_suffix(".png"), bbox_inches="tight", dpi=200)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=str, default=str(ROOT / "results/state_migration/figures"))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    chunks = [0, 1, 2, 4, 8, 16, 32]
    strip([("Uninterrupted", "baseline", ""),
           ("No sink KV", "ph_localrefresh", "plausible, different"),
           ("Ephemeral lost", "xfer_sink+meta", "recent KV, VAE, in-flight")],
          chunks, out / "fig2a_qualitative", "Frames after migration (chunk M+k, last frame of each chunk); PSNR to the uninterrupted frame")
    strip([("Uninterrupted", "baseline", ""),
           ("No durable state", "xfer_meta", "never rejoins"),
           ("Ours: late binding", "ph_zero_16", "sink arrives at M+16")],
          [0, 2, 4, 8, 12, 16, 20, 24, 32], out / "figE_qualitative",
          "Migration -> temporary gap -> rebind: the true sink arrives at M+16 (green box) and the stream rejoins the original trajectory", arrival=16)
    print(f"-> {out}")


if __name__ == "__main__":
    main()
