#!/usr/bin/env python3
"""Fig. 2b / Fig. 3 same-run selection (rule fixed before the runs, 2026-10-20).

Runs: results/state_migration/fig23_same_run/<case>_s<seed>_k2 (tools/run_prompt_sweep.sh with all five loss conditions).
Per run, the pre-registered prompt-sweep criteria (tools/aggregate_prompt_sweep.py, unchanged):
    D  no Sink KV: mean PSNR over M+16..end < 30 dB and no chunk >= 35 dB after M+4
    E  no recent KV + VAE caches: reaches >= 35 dB and its last-16-chunk mean >= 35 dB
Selection: among the case's runs satisfying D and E, the largest gap mean(no_eph) - mean(no_sink) over M+16..end; ties
go to the lower seed. Every run is reported; none is dropped. Writes summary.md and SELECTED (the chosen run directory),
which tools/make_background_figures.py uses for both Fig. 2b and Fig. 3.

    python tools/select_fig23_run.py --case dragonC_dog
"""

from __future__ import annotations

import argparse
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from aggregate_prompt_sweep import curve, run_metrics  # noqa: E402

BASE = ROOT / "results/state_migration/fig23_same_run"
CONDS = [("drop_inflight", "no in-flight rows"), ("drop_kv_recent", "no recent KV"), ("drop_vae_all", "no VAE caches"),
         ("xfer_sink+meta+inflight", "no recent KV + VAE"), ("ph_localrefresh", "no Sink KV")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    a = ap.parse_args()
    runs = sorted(BASE.glob(f"{a.case}_s*_k2"))
    rows = [m for m in (run_metrics(r, "fig23") for r in runs) if m]
    L = [f"# Fig. 2b / 3 same-run case {a.case}", "", "Criteria and rule: tools/select_fig23_run.py (fixed before the runs).", "",
         "| run | D | E | gap M+16.. (dB) | " + " | ".join(f"{lab}: mean M+16.. / last 16" for _, lab in CONDS) + " | no-eph first >= 35 |",
         "|---|---|---|---|" + "---|" * len(CONDS) + "---|"]
    for m in rows:
        cells = []
        for cfg, _ in CONDS:
            c = curve(m["dir"], cfg)
            if not c:
                cells.append("-"); continue
            n = max(c) + 1
            cells.append(f"{st.mean([v for k, v in c.items() if k >= 16]):.1f} / {st.mean([v for k, v in c.items() if k >= n - 16]):.1f}")
        L.append(f"| {m['run']} | {m['D']} | {m['E']} | {m['gap16']:.1f} | " + " | ".join(cells) + f" | M+{m['no_eph_first35']} |")
    ok = [m for m in rows if m["D"] and m["E"]]
    gaps = [m["gap16"] for m in rows]
    L += ["", f"D in {sum(m['D'] for m in rows)} / {len(rows)}, E in {sum(m['E'] for m in rows)} / {len(rows)}; gap median {st.median(gaps):.1f} dB, range {min(gaps):.1f}-{max(gaps):.1f}" if rows else "no runs"]
    if ok:
        pick = sorted(ok, key=lambda m: (-m["gap16"], m["seed"]))[0]
        (BASE / "SELECTED").write_text(str(pick["dir"].relative_to(ROOT)) + "\n")
        L.append(f"Selected (rule): {pick['run']} (gap {pick['gap16']:.1f} dB)")
    else:
        L.append("No run satisfies D and E: nothing selected; Fig. 2b / 3 keep their previous source.")
    (BASE / f"summary_{a.case}.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
