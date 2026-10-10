#!/usr/bin/env python3
"""Aggregate the prompt/clip sweep (tools/run_prompt_sweep.sh) together with the earlier generalization grid, test the
state-asymmetry claims per run, and pick the Fig. 3 case by a rule fixed here BEFORE the sweep results existed.

Conditions (same seed, input, migration point M = chunk 30 as each run's own uninterrupted baseline; PSNR on
uncompressed frames, mean of the frames of each chunk):
    no_sink = ph_localrefresh          (durable state lost)
    no_eph  = xfer_sink+meta+inflight  (recent KV + VAE caches lost; Sink, metadata, in-flight rows kept)

Pre-registered criteria (committed before the sweep ran; do not tune after seeing results):
    D  durable divergence  : no_sink mean PSNR over M+16..end < 30 dB, and no chunk >= 35 dB after M+4
    E  ephemeral transient : no_eph reaches >= 35 dB, and its mean over the last 16 chunks of the window is >= 35 dB
    Runs that fail D or E are reported, never dropped; their refresh history (adaptive Sink refresh calls before M) is
    listed because the generalization grid showed refreshes stretch healing time.
Fig. 3 selection rule (sweep runs only, since the grid saved no frames): among runs satisfying D and E, take the one with
the largest gap mean(no_eph) - mean(no_sink) over M+16..end; ties go to the lower seed. The rule picks; a person may
override it only by writing a run directory into results/state_migration/prompt_sweep/FIG3_SELECTED, and the summary
records both the rule's pick and the override.

Outputs: results/state_migration/prompt_sweep/summary.{csv,md}; one appendix figure per clip
(figures/background/appendix/fig_state_loss_<clip>); one candidate Fig. 3 strip per sweep run
(figures/background/candidates/fig3_<run>), all at the Fig. 2b / Fig. 3 sizes and style.

    python tools/aggregate_prompt_sweep.py
"""

from __future__ import annotations

import csv
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import make_background_figures as bg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

SWEEP = ROOT / "results/state_migration/prompt_sweep"
GRID = ROOT / "results/state_migration/gen"
FIGS = ROOT / "results/state_migration/figures/background"
NO_SINK, NO_EPH = "ph_localrefresh", "xfer_sink+meta+inflight"
TAU, D_MAX = 35.0, 30.0
CHUNKS = [0, 4, 8, 16, 32]


def curve(run: Path, cfg: str) -> dict[int, float]:
    d: dict[int, list[float]] = {}
    for r in csv.DictReader(open(run / "ablation_raw.csv")):
        if r["config"] == cfg and r["psnr"] and int(r["rel_call"]) >= 0:
            d.setdefault(int(r["rel_call"]), []).append(float(r["psnr"]))
    return {k: st.mean(v) for k, v in sorted(d.items())}


def run_metrics(run: Path, source: str) -> dict | None:
    if not (run / "ablation_raw.csv").exists():
        return None
    ns, ep = curve(run, NO_SINK), curve(run, NO_EPH)
    if not ns or not ep:
        return None
    static = json.load(open(run / "ablation_static.json"))
    M = int(static["args"]["migration_chunk"])
    clip = Path(static["args"]["video_path"]).stem
    n = max(ns) + 1
    ns16 = [v for k, v in ns.items() if k >= 16]; ep16 = [v for k, v in ep.items() if k >= 16]
    eplast = [v for k, v in ep.items() if k >= n - 16]
    D = st.mean(ns16) < D_MAX and not any(v >= TAU for k, v in ns.items() if k > 4)
    first = next((k for k, v in ep.items() if v >= TAU), None)
    E = first is not None and st.mean(eplast) >= TAU
    refresh = [c for c in static.get("sink_refresh_calls", []) if 4 < c < M]  # call 4 = first fill
    return {"run": run.name, "source": source, "clip": clip, "seed": int(static["args"]["seed"]), "k": int(static["k"]), "window": n,
            "no_sink_mean16": st.mean(ns16), "no_sink_max_after4": max(v for k, v in ns.items() if k > 4),
            "no_eph_m0": ep[0], "no_eph_first35": first, "no_eph_mean16": st.mean(ep16), "no_eph_last16": st.mean(eplast),
            "gap16": st.mean(ep16) - st.mean(ns16), "D": D, "E": E, "refresh_before_M": refresh, "dir": run,
            "has_frames": (run / "videos" / f"{NO_EPH}.mp4").exists(), "curves": (ns, ep)}


def appendix_figure(clip: str, rows: list[dict]):
    """One panel per clip at the Fig. 2b size and style: every seed's no_sink (red) and no_eph (blue) curve."""
    fig = plt.figure(figsize=bg.FIG2A_SIZE)
    ax = fig.add_axes(bg.FIG2A_AXES)
    n = max(r["window"] for r in rows)
    for r in rows:
        ns, ep = r["curves"]
        ax.plot(list(ns), list(ns.values()), color=bg.C_DUR, lw=2.0, alpha=0.9)
        ax.plot(list(ep), list(ep.values()), color=bg.C_EPH, lw=2.0, ls="--", alpha=0.9)
    ax.axhline(TAU, color=bg.BLACK, lw=1.0, ls=":")
    bg._in_label(ax, n - 1.5, 13.0, "No Sink KV", bg.F2_ANNOT, ha="right", va="center", color=bg.C_DUR, weight="bold")
    bg._in_label(ax, n - 1.5, 51.5, "No recent KV + VAE caches", bg.F2_ANNOT, ha="right", va="top", color=bg.C_EPH, weight="bold")
    ax.set_xlim(0, n - 1); ax.set_ylim(8, 54); ax.set_yticks([10, 20, 30, 40, 50])
    bg._fig2a_axis(ax, "Chunks After Migration")
    ax.set_ylabel("PSNR (dB)", fontsize=bg.F2_LABEL)
    ax.tick_params(axis="y", length=5)
    bg.save(fig, FIGS / "appendix" / f"fig_state_loss_{clip}", tight=False)


def main():
    bg.configure_matplotlib()
    rows = []
    for d in sorted(SWEEP.glob("*_s*_k*")):
        m = run_metrics(d, "sweep")
        if m:
            rows.append(m)
    for d in sorted(GRID.glob("*")):
        m = run_metrics(d, "grid")
        if m:
            rows.append(m)
    if not rows:
        print("no runs found"); return
    # selection (sweep runs with frames only)
    eligible = [r for r in rows if r["source"] == "sweep" and r["has_frames"] and r["D"] and r["E"]]
    pick = max(eligible, key=lambda r: (r["gap16"], -r["seed"])) if eligible else None
    override = (SWEEP / "FIG3_SELECTED").read_text().strip() if (SWEEP / "FIG3_SELECTED").exists() else None
    # tables
    SWEEP.mkdir(parents=True, exist_ok=True)
    cols = ["source", "run", "clip", "seed", "k", "window", "no_sink_mean16", "no_sink_max_after4", "no_eph_m0", "no_eph_first35",
            "no_eph_mean16", "no_eph_last16", "gap16", "D", "E", "refresh_before_M"]
    with open(SWEEP / "summary.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(cols)
        for r in rows:
            w.writerow([f"{r[c]:.2f}" if isinstance(r[c], float) else r[c] for c in cols])
    f = lambda v: f"{v:.1f}" if isinstance(v, float) else str(v)  # noqa: E731
    lines = ["# Prompt/clip sweep: does the state asymmetry reproduce?", "",
             f"Criteria (fixed in tools/aggregate_prompt_sweep.py before the sweep ran): D = no-Sink mean over M+16.. < {D_MAX:g} dB and no chunk >= {TAU:g} dB after M+4; "
             f"E = no-ephemeral reaches >= {TAU:g} dB and its last-16-chunk mean >= {TAU:g} dB.", "",
             "| source | run | clip | seed | k | window | no Sink mean M+16.. | no Sink max after M+4 | no eph. M+0 | no eph. first >= 35 | no eph. mean M+16.. | no eph. last 16 | gap | D | E | refreshes before M |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append("| " + " | ".join(f(r[c]) for c in cols) + " |")
    nD = sum(r["D"] for r in rows); nE = sum(r["E"] for r in rows)
    lines += ["", f"D holds in {nD}/{len(rows)} runs, E in {nE}/{len(rows)} runs."]
    lines += ["", f"Fig. 3 rule pick: {pick['run'] if pick else 'none (no sweep run with frames satisfies D and E)'}"
              + (f" (gap {pick['gap16']:.1f} dB)" if pick else ""),
              f"Manual override (FIG3_SELECTED): {override or 'none'}"]
    (SWEEP / "summary.md").write_text("\n".join(lines) + "\n")
    # the rule's pick is what Fig. 3 uses unless a person overrides it (FIG3_SELECTED)
    rule_file = SWEEP / "FIG3_RULE_PICK"
    if pick:
        rule_file.write_text(str(pick["dir"].relative_to(ROOT)) + "\n")
    elif rule_file.exists():
        rule_file.unlink()
    print("\n".join(lines))
    # appendix figures: sweep runs per clip if present, else the grid's k=2 runs
    for clip in sorted({r["clip"] for r in rows}):
        rs = [r for r in rows if r["clip"] == clip and r["source"] == "sweep"] or [r for r in rows if r["clip"] == clip and r["k"] == 2]
        if rs:
            appendix_figure(clip, rs)
    # candidate strips for every sweep run with frames (reproducing or not; the summary says which)
    for r in rows:
        if r["source"] == "sweep" and r["has_frames"]:
            prompt = (ROOT / "examples" / Path(json.load(open(r["dir"] / "ablation_static.json"))["args"]["prompt_file_path"]).name).read_text().strip()
            bg.frames_strip(r["dir"], bg.ROWS_EPHEMERAL, CHUNKS, prompt, FIGS / "candidates" / f"fig3_{r['run']}")


if __name__ == "__main__":
    main()
