#!/usr/bin/env python3
"""Experiment VD-3 Phase T (osdi/expVD3/preregistration.md, decisions of 2026-10-25): distributions for choosing the
restoration thresholds, from REF streams and frozen-M1 controls only. No threshold is chosen here; the GO / NO-GO
thresholds are fixed after these distributions are reviewed, before any candidate condition runs. Runs on the host
that holds the frames (REF frames of <input>_s0 and <input>_s1).

Per cell (input x seed x schedule; the anchor is the schedule's 16 pre-move calls, the span its control's span):
  primary comparison (defined, not computed here): candidate minus REF of the same seed at the same calls, same anchor
  natural REF variation:
    - REF's 10-call window statistic over the span (content: DINO similarity to the anchor; color: dE to the anchor;
      warp error e_R and frame difference d_R relative to their span median): P5 / P25 / P50 / P75 / P95 and P95 - P5
    - window-to-window change of REF at a 10-call lag (non-overlapping windows): P50 / P95 of |w(i + 10) - w(i)|
    - REF's own V1 over the span: P50 / P95 / P99 / max
    - REF's early-to-late change over the cell's Sink-less window calls (what R3 pairs against)
  measurement noise:
    - embedder recomputation: the same REF frames embedded twice; max |difference| of per-call and 10-call-window
      similarity (GPU nondeterminism of the metric itself)
    - emulation determinism: G1 (the emulated frozen-M1 OT-1 vs the real run) and the prefix digests (recorded by the
      emulator); reported from the unit's files
  sensitivity (not a threshold source): cross-seed difference of the same statistic over the same windows (REF seed 1
    vs REF seed 0), P50 / P95 of |difference|
  context (not a threshold source): the frozen-M1 control's paired deviations in the same units

    python tools/eval/vd3_phaseT.py --root results/evaluation/expVC [--embedder dino --device cuda:0]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for p_ in (ROOT, ROOT / "tools", ROOT / "tools" / "eval"):
    if str(p_) not in sys.path:
        sys.path.insert(0, str(p_))

import vc_frames as vf  # noqa: E402
import vc_metrics as vm  # noqa: E402
import vc_schedules as vs  # noqa: E402

INPUTS = ("dog", "train", "butterfly-feeding-slow-motion", "audi-snow-trail")
WIN = 10
CONFIRM = {("train", 0), ("audi-snow-trail", 0), ("dog", 1), ("train", 1), ("butterfly-feeding-slow-motion", 1), ("audi-snow-trail", 1)}
PCT = (5, 25, 50, 75, 95)


def wins(x: np.ndarray) -> np.ndarray:
    return np.array([np.nanmean(x[i:i + WIN]) for i in range(len(x) - WIN + 1)]) if len(x) >= WIN else np.array([])


def pct(x, ps=PCT) -> dict:
    x = np.asarray(x, dtype=float); x = x[~np.isnan(x)]
    return {f"P{p}": float(np.percentile(x, p)) for p in ps} | {"n": int(len(x))} if len(x) else {"n": 0}


def dist(w: np.ndarray) -> dict:
    d = pct(w)
    if d["n"]:
        d["P95-P5"] = d["P95"] - d["P5"]
        lag = np.abs(w[WIN:] - w[:-WIN]) if len(w) > WIN else np.array([])
        d["lag10_abs_change"] = pct(lag, (50, 95))
    return d


class RefStream:
    def __init__(self, unit: Path, emb: dict, calls: list[int], pre: set, k: int, twice: bool):
        s = json.loads((unit / "REF" / "summary.json").read_text())
        self.R = vf.read_calls(Path(s["frames"]), calls)
        self.cs = sorted(self.R)
        getI = vm.input_provider(s, bool(s.get("dry_run")), self.R[self.cs[0]].shape[1:3])
        self.name = next(iter(emb))
        S = vm.stream_series(self.R, vm.gray_quarter, emb, None)
        self.M = vm.series_metrics(S, self.cs, pre)
        self.lab = S["lab"]
        self.noise = None
        if twice:   # measurement noise of the embedder: embed the same frames again
            S2 = vm.stream_series(self.R, vm.gray_quarter, emb, None)
            M2 = vm.series_metrics(S2, self.cs, pre)
            a = np.array([self.M["v5a"][self.name][c] for c in self.cs]); b = np.array([M2["v5a"][self.name][c] for c in self.cs])
            self.noise = {"per_call_max_abs": float(np.nanmax(np.abs(a - b))), "window_max_abs": float(np.nanmax(np.abs(wins(a) - wins(b)))) if len(a) >= WIN else None}
        g = {c: vm.gray_quarter(self.R[c]) for c in self.cs}
        gi = {c: vm.gray_quarter(getI(c - (k - 1))) for c in self.cs}
        self.tr = vm.transitions(g, g, gi)
        self.e = {}; self.d = {}
        for t in self.tr:
            if t["eR"] is not None:
                self.e.setdefault(t["call"], []).append(t["eR"])
            if t["dR"] is not None:
                self.d.setdefault(t["call"], []).append(t["dR"])
        self.v1 = vm.ref_spike_distribution(self.tr)

    def series(self, key: str, calls: list[int]) -> np.ndarray:
        if key == "dino":
            return np.array([self.M["v5a"][self.name].get(c, np.nan) for c in calls])
        if key == "dE":
            return np.array([self.M["v4_pre"].get(c, np.nan) for c in calls])
        src = self.e if key == "E" else self.d
        return np.array([np.mean(src[c]) if src.get(c) else np.nan for c in calls])


def control_context(unit: Path, x: str) -> dict:
    mp = unit / "metrics.json"
    if not mp.exists():
        return {"available": False}
    cm = json.loads(mp.read_text())["conditions"].get(f"OT-{x}")
    if cm is None:
        return {"available": False}
    pc, sl = cm["per_call"], cm["sinkless_calls"]
    sv = lambda k, cs: np.array([np.nan if pc[str(c)].get(k) is None else pc[str(c)][k] for c in cs if str(c) in pc])  # noqa: E731
    key = "v5a_dino" if any("v5a_dino" in v for v in pc.values()) else next(k for k in next(iter(pc.values())) if k.startswith("v5a_") and not k.startswith("v5a_vbench") and not k.endswith("_ref"))
    ev = {e["kind"]: e for e in cm["events"]}
    w = cm["windows"].get("sinkless") or {}
    early, late = sl[:8], sl[-8:]
    X = (np.nanmean(sv(key, early)) - np.nanmean(sv(key, late))) - (np.nanmean(sv(key + "_ref", early)) - np.nanmean(sv(key + "_ref", late)))
    return {"available": True, "D_c": float(np.nanmean(sv(key, sl) - sv(key + "_ref", sl))), "C_c": float(np.nanmean(sv("v4_pre", sl) - sv("v4_pre_ref", sl))),
            "dE_cross": w.get("v4_window_to_ref"), "E": w.get("E_ratio"), "motion": w.get("motion_ratio"), "X_late": float(X),
            "v1_reset": (ev.get("reset") or {}).get("spike"), "v1_bind": (ev.get("bind") or {}).get("spike")}


def determinism(unit: Path) -> dict:
    out = {}
    for name in sorted(Path(ROOT / "results/evaluation/osdi/expVC").glob(f"*checks_{unit.name.rsplit('_s', 1)[0]}*.json")):
        try:
            g = json.loads(name.read_text()).get("G1")
            if g:
                out[name.stem] = {"pass": g.get("pass"), "condition": g.get("condition", "OT-L"), "max_abs_dpsnr": g.get("max_abs_dpsnr")}
        except (ValueError, OSError):
            pass
    pref = {}
    for d in unit.iterdir():
        if (d / "summary.json").exists():
            v = json.loads((d / "summary.json").read_text()).get("prefix_identical_to_reference")
            if v is not None:
                pref[d.name] = v
    out["prefix_identical_to_reference"] = {"all": all(pref.values()) if pref else None, "n": len(pref)}
    return out


def cell(root: Path, inp: str, sd: int, x: str, emb: dict, sched: dict, cache: dict) -> dict:
    unit = root / f"{inp}_s{sd}"
    ctrl = next(c for c in vs.unit_sched(sched, unit.name)["conditions"] if c["id"] == f"OT-{x}")
    m, b = ctrl["resets"][0], ctrl["binds"][-1]
    pre = set(range(m - vm.PRE, m))
    calls = list(range(ctrl["frames_from"], ctrl["frames_to"] + 1))
    k = int(json.loads((unit / "REF" / "summary.json").read_text()).get("k", 2))
    key = (inp, sd, m)
    if key not in cache:
        cache[key] = RefStream(unit, emb, calls, pre, k, twice=(x == "1"))
    R = cache[key]
    post = [c for c in R.cs if c >= m]
    sl = [c for c in post if c < b]
    nat = {}
    for st in ("dino", "dE", "E", "motion"):
        w = wins(R.series(st, post))
        if st in ("E", "motion"):
            med = np.nanmedian(w); w = w / med - 1 if med else w
        nat[st] = dist(w)
    ser = R.series("dino", sl)
    nat["early_to_late_dino"] = float(np.nanmean(ser[:8]) - np.nanmean(ser[-8:])) if len(ser) >= 16 else None
    nat["V1"] = pct(R.v1, (50, 95, 99)) | {"max": float(np.max(R.v1)) if R.v1 else None}
    other = (inp, 1 - sd, m)
    sens = None
    o_unit = root / f"{inp}_s{1 - sd}"
    if (o_unit / "REF" / "summary.json").exists():
        if other not in cache:
            cache[other] = RefStream(o_unit, emb, calls, pre, k, twice=(x == "1"))
        O = cache[other]
        common = [c for c in post if c in O.cs]
        sens = {}
        for st in ("dino", "dE"):
            sens[st] = pct(np.abs(wins(R.series(st, common)) - wins(O.series(st, common))), (50, 95))
        for st in ("E", "motion"):
            r = wins(O.series(st, common)) / wins(R.series(st, common))
            sens[st] = pct(np.abs(r - 1), (50, 95))
        sens["dE_cross_window"] = pct([vm.de2000(np.mean([R.lab[c] for c in common[i:i + WIN]], 0), np.mean([O.lab[c] for c in common[i:i + WIN]], 0))
                                       for i in range(len(common) - WIN + 1)], (50, 95))
    return {"input": inp, "seed": sd, "schedule": f"OT-{x}", "confirmation": (inp, sd) in CONFIRM, "counterfactual": bool(ctrl.get("counterfactual")) or any(
                c.get("counterfactual") for c in vs.unit_sched(sched, unit.name)["conditions"] if c.get("vd3_of") == f"OT-{x}"),
            "move": m, "bind": b, "anchor": [m - vm.PRE, m - 1], "span": [ctrl["frames_from"], ctrl["frames_to"]], "embedder": R.name,
            "natural_ref_variation": nat, "measurement_noise": {"embedder_recompute": R.noise, "emulation": determinism(unit)},
            "sensitivity_cross_seed": sens, "context_frozen_m1": control_context(unit, x)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(ROOT / "results/evaluation/expVC"))
    ap.add_argument("--embedder", default="dino")
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--inputs", default=",".join(INPUTS))
    ap.add_argument("--out", default=None)
    ap.add_argument("--dry", action="store_true", help="synthetic units: output named _dryrun_")
    a = ap.parse_args()
    root = Path(a.root)
    dry = a.dry or "_dryrun_" in str(root)
    emb = vm.make_embedders(a.embedder, a.device)
    sched = json.loads((ROOT / "results/evaluation/osdi/expVC/vc_schedules.json").read_text())
    cells, cache = {}, {}
    f = lambda v, n=3: "-" if v is None else f"{v:.{n}f}"  # noqa: E731
    L = ["# VD-3 Phase T: distributions for the restoration thresholds (REF streams and frozen-M1 controls only; no threshold chosen)", "",
         "Primary comparison: candidate minus REF of the same seed at the same calls, same pre-move anchor. Natural variation and measurement noise "
         "below are the candidates for its thresholds; the cross-seed difference is sensitivity only; frozen M1 is context only.", "",
         "| cell | conf. | REF V1 P95 / P99 / max | DINO window P5-P95 width (lag-10 change P95) | dE window width (lag-10 P95) | e_R rel. width | d_R rel. width | "
         "REF early-late DINO | embedder noise (call / window max) | cross-seed DINO P95 | cross-seed dE P95 | frozen M1: D_c / C_c / V1 reset / X late |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for inp in [x for x in a.inputs.split(",") if x]:
        for sd in (0, 1):
            if not (root / f"{inp}_s{sd}" / "REF" / "summary.json").exists():
                continue
            for x in ("1", "L"):
                c = cell(root, inp, sd, x, emb, sched, cache)
                cells[f"{inp}_s{sd}|OT-{x}"] = c
                n, s_, ctx = c["natural_ref_variation"], c["sensitivity_cross_seed"] or {}, c["context_frozen_m1"]
                nz = c["measurement_noise"]["embedder_recompute"] or {}
                L.append(f"| {inp}_s{sd} OT-{x}{' (copied)' if c['counterfactual'] else ''} | {'Y' if c['confirmation'] else '-'} | "
                         f"{f(n['V1'].get('P95'), 2)} / {f(n['V1'].get('P99'), 2)} / {f(n['V1'].get('max'), 2)} | "
                         f"{f(n['dino'].get('P95-P5'))} ({f(n['dino'].get('lag10_abs_change', {}).get('P95'))}) | {f(n['dE'].get('P95-P5'), 2)} ({f(n['dE'].get('lag10_abs_change', {}).get('P95'), 2)}) | "
                         f"{f(n['E'].get('P95-P5'), 2)} | {f(n['motion'].get('P95-P5'), 2)} | {f(n['early_to_late_dino'])} | {f(nz.get('per_call_max_abs'), 5)} / {f(nz.get('window_max_abs'), 5)} | "
                         f"{f((s_.get('dino') or {}).get('P95'))} | {f((s_.get('dE') or {}).get('P95'), 2)} | "
                         + (f"{f(ctx['D_c'])} / {f(ctx['C_c'], 2)} / {f(ctx['v1_reset'], 2)} / {f(ctx['X_late'])} |" if ctx.get("available") else "- |"))
    L += ["", "Emulation determinism per unit (G1 and prefix digests): see the JSON (`measurement_noise.emulation`)."]
    out = Path(a.out or ROOT / "results/evaluation/osdi/expVD3" / ("_dryrun_vd3_phaseT" if dry else "vd3_phaseT"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps({"cells": cells}, indent=1, default=float)); out.with_suffix(".md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
