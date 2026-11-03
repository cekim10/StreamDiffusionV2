#!/usr/bin/env python3
"""Fig. 13d frame strips (osdi/fig13/strip_protocol.md). Strip runs only extract frames: they add nothing to the 150
fidelity conditions (fig13_results.json) and are never read by fig13_report.py.

select  the strip conditions by the rule fixed before any frame is seen: per non-LOVEU input (dog, train; Fig. 13 D8:
        no LOVEU frames in figures), the condition with the median W3 PSNR of its 15 OTTER conditions (rank 8 of 15,
        sorted by W3, seed, S) and the one with the lowest W3. Prints the conditions the runner hard-codes.
check   each strip run (expF13D_<input>_s<seed>_S<S>, roles swapped: B = elves-01, where the frames are written) against
        its sweep run: valid, and the per-call PSNR series and the Sink decision equal (fig13_report.same_series, the
        repeat test). A strip run that differs is not used.
plot    reference vs OTTER, last frame of each listed call after the cutover (k = 1, 2, 4, 8, 25, 50) and the call
        before it (k = 0, the source's last served call = the reference), one figure per condition. Run on elves-01.

    elves-01:  python tools/eval/fig13_strip.py select
    elves-01:  python tools/eval/fig13_strip.py check
    elves-01:  python tools/eval/fig13_strip.py plot
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
import fig13_report as fr  # noqa: E402

EVAL = ROOT / "results/evaluation"
OUT = EVAL / "osdi/fig13"
DUMPS = OUT / "_dumps"          # --dump_frames root on the destination (elves-01 in the strip runs)
INPUTS = ("dog", "train")
KS = (0, 1, 2, 4, 8, 25, 50)
STRIP_NAME = re.compile(fr.NAME.pattern.replace("expF13_", "expF13D_"))


def select():
    runs = [r for r in json.loads((OUT / "fig13_results.json").read_text())["runs"]
            if r["method"] == "otter" and r["rep"] in (1, None) and r["valid"] and r["input"] in INPUTS]
    out = []
    for inp in INPUTS:
        rs = sorted((r for r in runs if r["input"] == inp), key=lambda r: (r["W3"], r["seed"], r["S"]))
        assert len(rs) == 15, (inp, len(rs))
        for role, r in (("median", rs[len(rs) // 2]), ("lowest", rs[0])):
            out.append({"input": inp, "role": role, "seed": r["seed"], "S": r["S"], "W3": r["W3"], "diverged": r["schedule_diverged"],
                        "sweep_run": f"{r['exp']}/{r['run']}"})
    for c in out:
        print(f"{c['input']:5s} {c['role']:6s} seed {c['seed']} S {c['S']}: W3 {c['W3']:.1f} dB, schedule diverged {c['diverged']} ({c['sweep_run']})")
    return out


def strip_record(d: Path):
    pat = fr.NAME
    fr.NAME = STRIP_NAME
    try:
        return fr.run_record(d, dry=False)
    finally:
        fr.NAME = pat


def check():
    ok_all, res = True, []
    for c in select():
        exp = f"expF13D_{c['input']}_s{c['seed']}_S{c['S']}"
        ds = sorted((EVAL / exp).glob("policy=*"))
        sw = fr.run_record(EVAL / c["sweep_run"], dry=False)
        st = strip_record(ds[-1]) if ds else None
        same = bool(st) and st["valid"] and fr.same_series(st, sw)
        ok_all &= same
        rid = json.loads((ds[-1] / "summary.json").read_text())["run_id"] if ds else None
        res.append({**c, "strip_run": ds[-1].name if ds else None, "run_id": rid, "valid": st and st["valid"], "equal_to_sweep": same})
        print(f"{exp}: {'equal to its sweep run' if same else 'NOT USABLE'} ({ds[-1].name if ds else 'missing'})")
    (OUT / "strip_check.json").write_text(json.dumps(res, indent=1))
    print(f"[strip] {'all strip runs equal their sweep runs' if ok_all else 'some strip runs are not usable'}")
    return res


def plot():
    import matplotlib.pyplot as plt
    import vc_frames as vf
    from plot_fig7_migration import configure

    configure()
    chk = {(r["input"], r["seed"], r["S"]): r for r in json.loads((OUT / "strip_check.json").read_text())}
    for (inp, seed, S), r in chk.items():
        if not r["equal_to_sweep"]:
            print(f"skip {inp} s{seed} S{S}: not equal to its sweep run")
            continue
        root = DUMPS / r["run_id"]   # the destination's dump directory (mobility_node: <--dump_frames>/<run id>/OUT_B, REF_B)
        outd, refd = root / "OUT_B", root / "REF_B"
        calls = [S - 1 + k for k in KS]   # k = 0 is the source's last served call (S - 1); k >= 1 the destination's
        ref, out = vf.read_calls(refd, calls), vf.read_calls(outd, calls)
        fig, axs = plt.subplots(2, len(KS), figsize=(7.7, 2.6), gridspec_kw={"wspace": 0.03, "hspace": 0.05})
        for j, (k, c) in enumerate(zip(KS, calls)):
            for i, (lab, src) in enumerate((("Ref.", ref), ("OTTER", ref if k == 0 else out))):
                ax = axs[i, j]
                ax.imshow(src[c][-1]); ax.set_xticks([]); ax.set_yticks([])
                if j == 0:
                    ax.set_ylabel(lab, fontsize=19)
                if i == 0:
                    ax.set_title(f"k = {k}", fontsize=19)
        name = OUT / "figures" / f"fig13d_strip_{inp}_s{seed}_S{S}_{r['role']}"
        fig.savefig(name.with_suffix(".png"), dpi=300, bbox_inches="tight"); fig.savefig(name.with_suffix(".pdf"), bbox_inches="tight")
        plt.close(fig)
        print(f"  {name.relative_to(ROOT)}.{{pdf,png}}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["select", "check", "plot"])
    a = ap.parse_args()
    {"select": select, "check": check, "plot": plot}[a.mode]()


if __name__ == "__main__":
    main()
