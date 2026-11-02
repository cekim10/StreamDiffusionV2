#!/usr/bin/env python3
"""Fig. 13 per-input table for the main text (user decision 2026-11-02: the paper has no appendix, so the per-input
detail is one small table). Reads osdi/fig13/fig13_results.json (fig13_report.py); OTTER conditions, rep 1.

Columns: input (sorted by Fig. 5 refresh intensity), conditions, schedule-divergence rate, first-call PSNR median,
W3 PSNR median [min-max], share W3 PSNR >= 40 dB, W3 tPSNR median, share of both >= 40 dB (the claim rule's F_P / F_T
per input).

    python3.11 tools/eval/fig13_table.py   # -> results/evaluation/osdi/fig13/fig13_table.{md,tex}
"""

import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "results/evaluation/osdi/fig13"
REFRESH = {"dog": 3.6, "bird": 3.6, "boxing": 8.2, "basketball": 9.1, "hockey": 16.4, "swimmer": 22.7, "train": 34.5, "audi": 53.6,
           "circus": 89.1, "bfly": 128.2}
NAME = {"dog": "Dog", "bird": "Bird", "boxing": "Boxing", "basketball": "Basketball", "hockey": "Hockey", "swimmer": "Swimmer",
        "train": "Train", "audi": "Audi", "circus": "Circus", "bfly": "Butterfly"}


def main():
    runs = [r for r in json.loads((D / "fig13_results.json").read_text())["runs"] if r["method"] == "otter" and r["rep"] in (1, None) and r["valid"]]
    rows = []
    for inp in sorted({r["input"] for r in runs}, key=lambda x: (REFRESH[x], x)):
        rs = [r for r in runs if r["input"] == inp]
        w3 = [r["W3"] for r in rs]
        rows.append({"input": inp, "refresh": REFRESH[inp], "n": len(rs), "div": sum(r["schedule_diverged"] for r in rs) / len(rs),
                     "first": st.median(r["first_psnr"] for r in rs), "w3": st.median(w3), "w3_min": min(w3), "w3_max": max(w3),
                     "fp": sum(x >= 40 for x in w3) / len(rs), "tw3": st.median(r["t_W3"] for r in rs),
                     "both": sum(r["W3"] >= 40 and r["t_W3"] >= 40 for r in rs) / len(rs)})
    allr = {"n": len(runs), "div": sum(r["schedule_diverged"] for r in runs) / len(runs), "first": st.median(r["first_psnr"] for r in runs),
            "w3": st.median(r["W3"] for r in runs), "w3_min": min(r["W3"] for r in runs), "w3_max": max(r["W3"] for r in runs),
            "fp": sum(r["W3"] >= 40 for r in runs) / len(runs), "tw3": st.median(r["t_W3"] for r in runs),
            "both": sum(r["W3"] >= 40 and r["t_W3"] >= 40 for r in runs) / len(runs)}
    pc = lambda x: f"{100 * x:.0f}"  # noqa: E731
    L = ["# Fig. 13 per-input table (OTTER, fixed cutover; measured)", "",
         "| input | refresh / 100 calls | conditions | schedule diverged (%) | first call (dB) | W3 PSNR median [min-max] (dB) | W3 >= 40 dB (%) | W3 tPSNR (dB) | both >= 40 dB (%) |",
         "|---|---|---|---|---|---|---|---|---|"]
    T = [r"\begin{tabular}{lrrrrrr}", r"\toprule",
         r"Input & Refresh & Diverged (\%) & First (dB) & W3 (dB) & W3 $\geq$ 40 dB (\%) & W3 tPSNR (dB) \\", r"\midrule"]
    for r in rows:
        L.append(f"| {NAME[r['input']]} | {r['refresh']:g} | {r['n']} | {pc(r['div'])} | {r['first']:.1f} | {r['w3']:.1f} [{r['w3_min']:.1f}-{r['w3_max']:.1f}] | "
                 f"{pc(r['fp'])} | {r['tw3']:.1f} | {pc(r['both'])} |")
        T.append(f"{NAME[r['input']]} & {r['refresh']:g} & {pc(r['div'])} & {r['first']:.1f} & {r['w3']:.1f} & {pc(r['fp'])} & {r['tw3']:.1f} \\\\")
    L.append(f"| **All** | | {allr['n']} | {pc(allr['div'])} | {allr['first']:.1f} | {allr['w3']:.1f} [{allr['w3_min']:.1f}-{allr['w3_max']:.1f}] | "
             f"{pc(allr['fp'])} | {allr['tw3']:.1f} | {pc(allr['both'])} |")
    T += [r"\midrule", f"All & & {pc(allr['div'])} & {allr['first']:.1f} & {allr['w3']:.1f} & {pc(allr['fp'])} & {allr['tw3']:.1f} \\\\",
          r"\bottomrule", r"\end{tabular}"]
    L += ["", "W3 = calls 25-100 after the cutover (median per condition); conditions = 15 cutover calls per input (seed 0: S 70-79, "
          "seed 1: S 70-78 step 2). 40 dB is an operational threshold, not a perceptual one."]
    (D / "fig13_table.md").write_text("\n".join(L) + "\n")
    (D / "fig13_table.tex").write_text("\n".join(T) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
