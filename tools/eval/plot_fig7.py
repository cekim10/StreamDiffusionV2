#!/usr/bin/env python3
"""Figure 7: continuity timeline after a single physical handoff, drawn ONLY from the frozen Phase 1 (v3)
run directories under results/evaluation/single_handoff/policy=* (metrics.csv per chunk, events.csv).
No synthetic or interpolated samples: every plotted PSNR is a measured chunk; event markers are the
measured event timestamps, placed on the chunk axis between the measured output times of neighbouring chunks.

    python tools/eval/plot_fig7.py --bw 1000            # rep = the one with the median continuity-ready time
    python tools/eval/plot_fig7.py --bw native --rep 2
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

LABEL = {"full": "SDV2-FullMigration", "cold": "SDV2-Restart", "replay": "Replay", "ours": "Ours"}
COLOR = {"full": "#7f7f7f", "cold": "#d62728", "replay": "#ff7f0e", "ours": "#2ca02c"}
REJOIN_DB = 35.0  # criterion used by the harness (proto_handoff.py): first post-bind chunk with PSNR >= 35 dB
IDENTICAL = 99.0  # sentinel written by the harness for bit-identical chunks


def load_run(d: Path):
    s = json.load(open(d / "summary.json"))
    m = []
    for r in csv.DictReader(open(d / "metrics.csv")):
        m.append({"call": int(r["call"]), "rel": int(r["rel"]), "t_out_rel": float(r["t_out_rel"]), "psnr": float(r["psnr"]) if r["psnr"] else None,
                  "ssim": float(r["ssim"]) if r["ssim"] else None, "missing": r["missing"] == "True", "sink_bound": r["sink_bound"] == "True"})
    ev = {}
    for r in csv.DictReader(open(d / "events.csv")):
        det = json.loads(r["detail"]) if r["detail"] else {}
        key = r["event"] + (f":{det['comp']}" if r["event"] == "checksum" else "")
        if r["t_rel"] and key not in ev:
            ev[key] = (float(r["t_rel"]), det)
    return s, m, ev, (d / "git_commit.txt").read_text().strip()


def pick_runs(root: Path, bw: str, rep: str):
    runs = {}
    for pol in ("ours", "cold", "replay", "full"):
        dirs = sorted(root.glob(f"policy={pol}_bw={bw}_rep=*"))
        if not dirs:
            raise SystemExit(f"no runs for {pol} @ {bw}")
        if rep == "auto":
            if pol == "ours":
                cands = sorted(dirs, key=lambda d: json.load(open(d / "summary.json"))["continuity_ready_rel_s"])
                chosen = cands[len(cands) // 2]
                rep = str(json.load(open(chosen / "summary.json"))["rep"])
                dirs = [chosen]
            else:
                dirs = [d for d in dirs if f"_rep={rep}_" in d.name]
        else:
            dirs = [d for d in dirs if f"_rep={rep}_" in d.name]
        runs[pol] = (dirs[0],) + load_run(dirs[0])
    return runs, rep


def chunk_pos(t: float, m: list[dict], t_resume: float) -> float:
    """Place a measured time on the chunk axis: chunk r is produced during (t_out[r-1], t_out[r]]; chunk 0
    during (resume, t_out[0]]. Linear within the interval (position only, no data is created)."""
    rels = [r["rel"] for r in m]; ts = [r["t_out_rel"] for r in m]
    if t <= t_resume:
        return -1.0
    prev_t, prev_x = t_resume, -1.0
    for x, tt in zip(rels, ts):
        if t <= tt:
            return prev_x + (t - prev_t) / (tt - prev_t) * (x - prev_x)
        prev_t, prev_x = tt, x
    return rels[-1] + (t - ts[-1]) / (ts[-1] - ts[-2])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default="results/evaluation/single_handoff")
    ap.add_argument("--bw", default="1000", help="bandwidth tag as in the run dir (250, 500, 1000, 2500, 5000, native)")
    ap.add_argument("--rep", default="auto")
    ap.add_argument("--out", default="results/evaluation/continuity")
    ap.add_argument("--xmax", type=int, default=48, help="chunks after migration shown in panel (a)")
    a = ap.parse_args()
    root, out = Path(a.root), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    runs, rep = pick_runs(root, a.bw, a.rep)
    d_ours, s_ours, m_ours, ev_ours, commit = runs["ours"]
    M = int(json.load(open(d_ours / "config.json"))["migration_chunk"])
    bound = s_ours["bound_call"]; rejoin_calls = s_ours["rejoin_calls_after_bind"]
    x_bind = bound - M; x_rejoin = x_bind + rejoin_calls
    t_resume = ev_ours["resume"][0]
    t_rejoin = next(r["t_out_rel"] for r in m_ours if r["call"] == bound + rejoin_calls)
    t_bind_out = next(r["t_out_rel"] for r in m_ours if r["call"] == bound)
    events = [("GO (in-flight + metadata landed)", ev_ours["go"][0]), ("first output", ev_ours["first_output"][0]), ("Sink received", ev_ours["sink_ready"][0]),
              ("Sink verified", ev_ours["checksum:sink"][0]), ("Sink bound", ev_ours["sink_bind"][0]), (f"rejoin (>= {REJOIN_DB:g} dB)", t_rejoin)]
    ev_pos = {name: chunk_pos(t, m_ours, t_resume) for name, t in events}

    # ------------------------------------------------------------------ figure
    fig = plt.figure(figsize=(7.6, 5.6))
    gs = fig.add_gridspec(2, 1, height_ratios=[3.0, 1.9], hspace=0.5)
    ax = fig.add_subplot(gs[0]); bx = fig.add_subplot(gs[1])

    # (a) continuity over chunks
    ymin, ymax = 5.0, 50.0
    for pol in ("cold", "replay", "ours"):
        _, s, m, _, _ = runs[pol]
        xs = [r["rel"] for r in m if r["psnr"] is not None and r["rel"] <= a.xmax]
        ys = [r["psnr"] for r in m if r["psnr"] is not None and r["rel"] <= a.xmax]
        ax.plot(xs, ys, color=COLOR[pol], lw=1.4 if pol == "ours" else 1.1, marker="o" if pol == "ours" else None, ms=2.6, label=LABEL[pol], zorder=3 if pol == "ours" else 2)
        miss = [r["rel"] for r in m if r["missing"] and r["rel"] <= a.xmax]
        if miss:
            ax.plot(miss, [ymin + 3.6] * len(miss), marker="x", color=COLOR[pol], ls="none", ms=6, mew=1.5, zorder=4)
            ax.text(miss[0] + 0.5, ymin + 3.0, "no output (Restart)", fontsize=6.3, color=COLOR[pol], va="center")
    ax.axhline(REJOIN_DB, color="#444444", lw=0.7, ls="--")
    ax.text(a.xmax - 0.3, REJOIN_DB - 0.6, f"rejoin criterion ({REJOIN_DB:g} dB)", ha="right", va="top", fontsize=6.5, color="#444444")
    # phases of Ours
    x_first = ev_pos["first output"]
    ax.axvspan(x_first, x_bind, color="#fde2c8", alpha=0.55, lw=0, zorder=0)
    ax.axvspan(x_bind, x_rejoin, color="#d9f0d3", alpha=0.75, lw=0, zorder=0)
    ax.text((x_first + x_bind) / 2, ymax - 0.8, "continuity gap: Sink in flight,\ndestination runs its own valid stream", ha="center", va="top", fontsize=6.8, color="#8a4b08")
    ax.text((x_bind + x_rejoin) / 2, ymax - 0.8, "post-bind\nrecovery", ha="center", va="top", fontsize=6.8, color="#1b5e20")
    ax.text(x_rejoin + 0.6, ymax - 0.8, "on the original\ntrajectory", ha="left", va="top", fontsize=6.8, color="#1b5e20")
    ax.annotate("", xy=(a.xmax, ymin + 1.0), xytext=(x_first, ymin + 1.0), arrowprops=dict(arrowstyle="->", color="#2ca02c", lw=1.0))
    ax.text(x_first + 9.5, ymin + 1.4, "execution ready: output flows from chunk 0 onward", fontsize=6.8, color="#1b5e20", va="bottom")
    for name, x in ev_pos.items():
        ax.axvline(x, color="#2ca02c" if "Sink" in name or "rejoin" in name else "#555555", lw=0.7, ls=":" if "GO" in name else "-", zorder=1)
    # event labels: (text, x offset, y, ha)
    lab = [("GO", ev_pos["GO (in-flight + metadata landed)"] + 0.12, 12.5, "left"), ("first output", x_first + 0.25, 20.0, "left"),
           ("Sink received + verified", ev_pos["Sink received"] - 0.3, 32.3, "right"), ("bound", ev_pos["Sink bound"] + 0.3, 32.3, "left"),
           ("rejoin", x_rejoin + 0.3, 20.0, "left")]
    for txt, x, y, ha in lab:
        ax.text(x, y, txt, fontsize=6.5, color="#222222", va="bottom", ha=ha)
    _, s_full, m_full, ev_full, _ = runs["full"]
    ax.text(0.8, 44.5, f"{LABEL['full']}: no output for {ev_full['first_output'][0]:.1f} s while 6.2 GB transfers,\nthen bit-identical to the uninterrupted run (not drawable on this axis)",
            fontsize=6.5, color="#555555", ha="left", va="top")
    ax.set_xlim(-1.6, a.xmax); ax.set_ylim(ymin, ymax)
    ax.set_xlabel(f"chunks after migration (chunk 0 = first chunk produced on the destination; migration at chunk {M})", fontsize=8)
    ax.set_ylabel("PSNR vs uninterrupted\nsame-seed execution (dB)")
    ax.grid(True, lw=0.3, alpha=0.5)
    ax.legend(loc="lower left", bbox_to_anchor=(0.52, 0.03), frameon=True, framealpha=0.92, edgecolor="none", fontsize=7.2)
    bw_txt = "native 10 GbE" if a.bw == "native" else f"{a.bw} Mbps"
    ax.set_title(f"(a) Continuity after a physical handoff elves-01 \u2192 elves-02 ({bw_txt}, seed {s_ours['seed']}, k={s_ours['k']}, rep {rep})", fontsize=8.5, loc="left")

    # (b) latency decomposition (time since migration start, linear; FullMigration runs off the axis)
    t_go, t_first = ev_ours["go"][0], ev_ours["first_output"][0]
    t_srs, t_sr, t_sv, t_sb = ev_ours["sink_recv_start"][0], ev_ours["sink_ready"][0], ev_ours["checksum:sink"][0], ev_ours["sink_bind"][0]
    t_full = ev_full["first_output"][0]
    xmax_b = max(t_rejoin * 1.12, 2.0)
    y1, y2, y3, h = 1.0, 0.56, -0.25, 0.3
    bx.barh(y1, t_go, left=0, height=h, color="#9ecae1", lw=0, label="foreground fragment (in-flight rows + metadata, 2 MB)")
    bx.barh(y1, t_first - t_go, left=t_go, height=h, color="#2ca02c", lw=0, label="first chunk generated on the destination")
    bx.barh(y2, t_sr - t_srs, left=t_srs, height=h, color="#c7e9c0", lw=0, label="Sink (1.65 GB) in flight; generation continues")
    bx.barh(y2, t_sb - t_sr, left=t_sr, height=h, color="#74c476", lw=0, label="verify, wait for the chunk boundary, bind")
    bx.barh(y2, t_rejoin - t_sb, left=t_sb, height=h, color="#238b45", lw=0, label=f"post-bind recovery to >= {REJOIN_DB:g} dB")
    for t, yy in ((t_go, y1), (t_first, y1), (t_sr, y2), (t_sv, y2), (t_sb, y2), (t_rejoin, y2)):
        bx.plot([t], [yy], marker="|", color="black", ms=9, mew=1.1)
    bx.text(max(t_go - 0.1, 0.02), y1 + h / 2 + 0.04, f"GO\n{t_go:.2f} s", ha="left", va="bottom", fontsize=6.3)
    bx.text(t_first + 0.45, y1 + h / 2 + 0.04, f"first output\n{t_first:.2f} s", ha="left", va="bottom", fontsize=6.3)
    bx.text(t_sr - 0.15, y2 - h / 2 - 0.04, f"Sink received {t_sr:.2f} s\nverified {t_sv:.2f} s", ha="right", va="top", fontsize=6.3)
    bx.text(t_sb + 0.15, y2 - h / 2 - 0.04, f"bound\n{t_sb:.2f} s", ha="left", va="top", fontsize=6.3)
    bx.text(t_rejoin, y2 - h / 2 - 0.04, f"rejoin\n{t_rejoin:.2f} s", ha="center", va="top", fontsize=6.3)
    if t_full > xmax_b:
        bx.barh(y3, xmax_b, left=0, height=h, color="#bdbdbd", lw=0, label="FullMigration: 6.2 GB transfer, no output")
        bx.annotate("", xy=(xmax_b, y3), xytext=(xmax_b * 0.985, y3), arrowprops=dict(arrowstyle="-|>", color="#bdbdbd", lw=2.5, mutation_scale=16), annotation_clip=False)
        bx.text(xmax_b * 0.5, y3, f"transfer continues off-axis: first output at {t_full:.1f} s ({t_full / t_first:.0f}x Ours)", ha="center", va="center", fontsize=6.5, color="#333333")
    else:
        bx.barh(y3, ev_full["go"][0], left=0, height=h, color="#bdbdbd", lw=0, label="FullMigration: 6.2 GB transfer, no output")
        bx.barh(y3, t_full - ev_full["go"][0], left=ev_full["go"][0], height=h, color="#636363", lw=0, label="FullMigration: restore + first chunk")
        bx.text(t_full + 0.05, y3, f"first output {t_full:.2f} s", ha="left", va="center", fontsize=6.5)
    bx.set_xlim(0, xmax_b); bx.set_ylim(y3 - 0.3, y1 + 0.62)
    bx.set_yticks([(y1 + y2) / 2, y3]); bx.set_yticklabels(["Ours", "SDV2-\nFullMigration"], fontsize=7.5)
    bx.set_xlabel("time since migration start (s)", fontsize=8)
    bx.grid(True, axis="x", lw=0.3, alpha=0.5)
    bx.legend(loc="upper center", bbox_to_anchor=(0.5, -0.3), ncol=2, frameon=False, fontsize=6.3)
    bx.set_title(f"(b) Latency decomposition for Ours ({bw_txt}): execution handoff vs continuity handoff", fontsize=8.5, loc="left")
    fig.savefig(out / "fig7_continuity_timeline.pdf", bbox_inches="tight"); fig.savefig(out / "fig7_continuity_timeline.png", dpi=220, bbox_inches="tight")

    # ------------------------------------------------------------------ data + checks
    with open(out / "fig7_data.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["kind", "policy", "run_dir", "git_commit", "call", "rel_chunk", "t_rel_s", "psnr_db", "ssim", "missing", "sink_bound", "event", "chunk_pos"])
        for pol in ("ours", "cold", "replay", "full"):
            d, s, m, ev, c = runs[pol]
            for r in m:
                w.writerow(["chunk", pol, d.name, c, r["call"], r["rel"], f"{r['t_out_rel']:.4f}", "" if r["psnr"] is None else f"{r['psnr']:.4f}", "" if r["ssim"] is None else f"{r['ssim']:.4f}", r["missing"], r["sink_bound"], "", ""])
            for name, (t, det) in ev.items():
                w.writerow(["event", pol, d.name, c, "", "", f"{t:.4f}", "", "", "", "", name, f"{chunk_pos(t, m, ev['resume'][0]):.3f}" if pol == "ours" and "resume" in ev else ""])
    post = [r["psnr"] for r in m_ours if r["call"] >= bound and r["psnr"] is not None]
    post8 = [r["psnr"] for r in m_ours if r["call"] >= bound + 8 and r["psnr"] is not None]
    cold_max = max(r["psnr"] for r in runs["cold"][2] if r["psnr"] is not None)
    replay_max = max(r["psnr"] for r in runs["replay"][2] if r["psnr"] is not None)
    full_ok = all(r["psnr"] == IDENTICAL for r in m_full if r["psnr"] is not None) and not any(r["missing"] for r in m_full)
    print(f"selected: {d_ours.name}  (rep {rep}, migration chunk {M}, commit {commit})")
    for pol in ("cold", "replay", "full"):
        print(f"  {pol}: {runs[pol][0].name} (commit {runs[pol][4]})")
    print(f"events (s since migration start): " + ", ".join(f"{n}={t:.3f}" for n, t in events))
    print(f"event positions (chunks): " + ", ".join(f"{n}={x:.2f}" for n, x in ev_pos.items()))
    print(f"CHECK rejoin_calls_after_bind == 6: {rejoin_calls} -> {'OK' if rejoin_calls == 6 else 'FAIL'}")
    print(f"CHECK first chunk >= {REJOIN_DB} dB after bind: call {bound + rejoin_calls} (PSNR {next(r['psnr'] for r in m_ours if r['call'] == bound + rejoin_calls):.1f} dB); first output after bind at {t_bind_out:.2f} s")
    print(f"post-bind PSNR: calls {bound}..{bound + len(post) - 1}: min {min(post):.1f}, max {max(post):.1f} dB; from bind+8: min {min(post8):.1f}, max {max(post8):.1f}, mean {np.mean(post8):.1f} dB")
    print(f"pre-bind PSNR (Ours, continuity gap): min {min(r['psnr'] for r in m_ours if r['call'] < bound):.1f}, max {max(r['psnr'] for r in m_ours if r['call'] < bound):.1f} dB")
    print(f"CHECK Restart never reaches {REJOIN_DB} dB: max {cold_max:.1f} dB -> {'OK' if cold_max < REJOIN_DB else 'FAIL'};  Replay max {replay_max:.1f} dB -> {'never' if replay_max < REJOIN_DB else 'reaches'}")
    print(f"CHECK FullMigration identical for every chunk: {'OK' if full_ok else 'FAIL'}; first output {ev_full['first_output'][0]:.2f} s")
    print(f"CHECK all run dirs are top-level frozen v3 dirs: {'OK' if all(runs[p][0].parent == root for p in runs) else 'FAIL'}")
    # consistency across bandwidths (ours only; all reps)
    print("\nconsistency across bandwidths (Ours, every rep): bw rep bind_chunk rejoin_calls t_sink_ready t_bind t_rejoin psnr_gap_mean psnr_post8_mean")
    for bw in ("250", "500", "1000", "2500", "5000", "native"):
        for d in sorted(root.glob(f"policy=ours_bw={bw}_rep=*")):
            s, m, ev, _ = load_run(d)
            b = s["bound_call"]; rj = s["rejoin_calls_after_bind"]
            trj = next((r["t_out_rel"] for r in m if r["call"] == b + rj), float("nan")) if rj is not None else float("nan")
            gap = [r["psnr"] for r in m if r["call"] < b and r["psnr"] is not None]; p8 = [r["psnr"] for r in m if r["call"] >= b + 8 and r["psnr"] is not None]
            print(f"  {bw:>6} {s['rep']} {b - M:>3} {rj} {ev['sink_ready'][0]:7.2f} {ev['sink_bind'][0]:7.2f} {trj:7.2f} {np.mean(gap):6.1f} {np.mean(p8) if p8 else float('nan'):6.1f}")
    print(f"\n-> {out / 'fig7_continuity_timeline.png'}")


if __name__ == "__main__":
    main()
