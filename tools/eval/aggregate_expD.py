#!/usr/bin/env python3
"""Experiment D aggregation: applies the frozen G1-G9 criteria to the run summaries exactly as specified in
results/evaluation/osdi/expD/aggregation_spec.md (written before any sweep data). Medians over valid reps; invalid runs
listed with reasons; criteria on fewer than 3 valid reps are NOT EVALUABLE.

    python tools/eval/aggregate_expD.py                      # results/evaluation/expD_*  -> osdi/expD/expD_results.{md,json}
    python tools/eval/aggregate_expD.py --prefix _dryrun_expD  # loopback protocol test of the aggregator
Also writes osdi/expD/expD_extra_reps.json (scenario A configurations whose TTFO or bind-ready IQR > 10 % of the median).
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from expD_validity import run_validity  # noqa: E402

EV = ROOT / "results/evaluation"
T_S, SHAPED = 14.05, 1000.0   # dry runs (loopback protocol test): 5.4 s and 100 Mbps


def label(s) -> str:
    pol, pp = s["policy"], ((s.get("d0") or {}).get("prepos") or {}).get("policy")
    if s.get("cold_destination"):
        return "OTTER cold destination"
    if pol == "split":
        return {None: "M1 + M2", "none": "M1 + M2 (no placement)", "top1": "M1 + M2 + top-1"}.get(pp, f"M1 + M2 + {pp}")
    if pol == "reuse_dyn":
        return {None: "OTTER event-driven", "none": "OTTER event-driven (no placement)", "top1": "Full OTTER", "oracle": "oracle"}.get(pp, f"OTTER event-driven + {pp}")
    return {"full": "Full migration", "cold": "Cold restart", "restart": "M1 only", "reuse_aware_in": "OTTER at moves"}.get(pol, pol)


def discarded_sinks(run: Path, s) -> float:
    ev = list(csv.DictReader(open(run / "events.csv")))
    bound = {e["event"].split(":")[0] for e in ev if e["event"].endswith(":sink_bind")}
    tot = sum(int(r["bytes"]) for r in csv.DictReader(open(run / "fragments.csv")) if r["event"] == "recv" and r["classification"] == "wasted" and r["dst"] not in bound)
    return tot / s["sink_bytes"]


def node_dups(run: Path) -> int:
    return sum(1 for f in run.glob("node_*/fragments.csv") for r in csv.DictReader(open(f)) if r["event"] == "recv" and r["ok"] == "False")


def fwd_evaluable(run: Path, s) -> bool:
    """G5 (d): every fragment the final owner verified has an orchestrator recv row naming its sender and checksum."""
    fin = s["path"][-1]
    rows = [r for r in csv.DictReader(open(run / "fragments.csv")) if r["event"] == "recv" and r["dst"] == fin and r["ok"] == "True"]
    return len({r["fragment_id"] for r in rows}) == s["n_frags"] and all(r["src"] for r in rows)


def record(run: Path, scen: str, dry: bool = False) -> dict | None:
    try:
        s = json.load(open(run / "summary.json"))
    except (OSError, ValueError):
        return {"run": run.name, "scenario": scen, "valid": False, "why": ["no summary.json (incomplete)"]}
    ok, why = run_validity(s, dry)
    L, F, z, c = s["latency_after_final_move_s"], s["final"], s["d0"], s["continuity"]
    pp = z.get("prepos") or {}
    top = max(pp["alloc_sinks"], key=pp["alloc_sinks"].get) if pp.get("alloc_sinks") else None
    rd = (F["rejoin_rel_s"] - F["first_bound_output_rel_s"]) if F.get("rejoin_rel_s") is not None and F.get("first_bound_output_rel_s") is not None else None
    peak = (s.get("gpu_peak_mem_mb") or {}).get(s["path"][-1], {}).get("peak_allocated_mb")
    return {"run": run.name, "scenario": scen, "valid": ok, "why": why, "label": label(s), "policy": s["policy"], "bw": s["bw_mbps"], "rho": s["rho"],
            "path": "".join(s["path"]), "ev": "_ev=" in s["run_id"], "ttfo": L.get("first_output"), "bind": L.get("continuity_ready"), "rejoin_delay": rd,
            "rejoin_calls": c.get("rejoin_calls_after_bind"), "src": z["source_bytes_total_sinks"], "pre": z["source_bytes_pre_move_sinks"], "post": z["source_bytes_post_move_sinks"],
            "fwd": z["holder_forwarded_sinks"], "x_dest": z["x_verified_at_move"].get(s["path"][-1]), "x_top": z["x_verified_at_move"].get(top) if top else None,
            "net_total": z.get("aggregate_network_sinks"), "discarded": discarded_sinks(run, s) if (run / "fragments.csv").exists() else None,
            "replans": z["n_replans"], "dups": s["bytes"]["duplicate"] + node_dups(run), "retained": z["verified_progress_retained"], "reused": z["verified_progress_reused"],
            "peak_dest_mb": peak, "fwd_evaluable": fwd_evaluable(run, s) if (run / "fragments.csv").exists() else False,
            "net_sessions": [float(x["t_r_s"]) if x.get("t_r_s") not in (None, "") else None for x in (s.get("hybrid") or {}).get("network_sessions", [])] or None,
            "psnr_after_rejoin": c.get("psnr_after_rejoin_mean")}


def med(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else None


def iqr(xs):
    xs = sorted(x for x in xs if x is not None)
    if len(xs) < 3:
        return None
    q = st.quantiles(xs, n=4, method="inclusive")
    return q[2] - q[0]


class Agg:
    def __init__(self, prefix, min_reps=3):
        self.prefix, self.min_reps = prefix, min_reps
        self.runs = []
        for d in sorted(EV.glob(prefix + "_*")):
            scen = d.name[len(prefix) + 1:]
            if scen not in ("A", "B", "C", "D", "E", "F", "G") and not scen.startswith("Agen_"):
                continue   # G9 is read separately; correctness tests and logs are not part of the sweep
            for r in sorted(d.glob("policy=*")):
                rec = record(r, scen, prefix.startswith("_dryrun"))
                if rec:
                    self.runs.append(rec)
        self.verdicts, self.tables = [], []

    def cfg(self, scen, **kw):
        """Valid reps of one configuration."""
        out = [r for r in self.runs if r["scenario"] == scen and r["valid"] and all(r.get(k) == v for k, v in kw.items())]
        return out

    def m(self, scen, key, **kw):
        reps = self.cfg(scen, **kw)
        return (med([r[key] for r in reps]) if len(reps) >= self.min_reps else None), len(reps)

    def verdict(self, name, ok, detail):
        v = "NOT EVALUABLE" if ok is None else ("SUPPORTED" if ok else "NOT SUPPORTED")
        self.verdicts.append({"criterion": name, "verdict": v, "detail": detail})

    def run(self, steady):
        fmt = lambda x: "-" if x is None else (f"{x:.3f}" if isinstance(x, float) else str(x))  # noqa: E731
        # G1, G2 (A)
        g1, g2 = [], []
        for bw in (SHAPED, 0.0):
            t, n = self.m("A", "ttfo", label="OTTER event-driven", bw=bw)
            g1.append((None if t is None else t <= 1.0, f"bw {bw or 'native'}: OTTER TTFO {fmt(t)} s (n={n}) <= 1.0"))
            rd, n1 = self.m("A", "rejoin_delay", label="OTTER event-driven", bw=bw)
            rc, _ = self.m("A", "rejoin_calls", label="OTTER event-driven", bw=bw)
            g2.append((None if rd is None or rc is None else (rd <= 6.0 and rc <= 8), f"bw {bw or 'native'}: rejoin {fmt(rd)} s, {fmt(rc)} calls (n={n1}) <= 6.0 s and <= 8"))
        tf, nf = self.m("A", "ttfo", label="Full migration", bw=SHAPED)
        to, _ = self.m("A", "ttfo", label="OTTER event-driven", bw=SHAPED)
        g1.append((None if tf is None or to is None else to <= 0.1 * tf, f"1 Gbps: OTTER {fmt(to)} s <= 0.1 x Full migration {fmt(tf)} s (n={nf})"))
        self.combine("G1", g1); self.combine("G2", g2)
        # G3 (B)
        for rho in (2.0, 4.0):
            parts = []
            s2, n2 = self.m("B", "src", label="M1 + M2", rho=rho); s1, n1 = self.m("B", "src", label="M1 only", rho=rho)
            parts.append((None if s2 is None or s1 is None else (s2 <= 1.10 and s1 >= 1.40), f"(a) source M1+M2 {fmt(s2)} <= 1.10, M1 only {fmt(s1)} >= 1.40 (n={n2},{n1})"))
            d2, _ = self.m("B", "discarded", label="M1 + M2", rho=rho); d1, _ = self.m("B", "discarded", label="M1 only", rho=rho)
            parts.append((None if d2 is None or d1 is None else (d2 <= 0.10 and d1 >= 0.40), f"(b) discarded M1+M2 {fmt(d2)} <= 0.10, M1 only {fmt(d1)} >= 0.40"))
            b2, _ = self.m("B", "bind", label="M1 + M2", rho=rho); b1, _ = self.m("B", "bind", label="M1 only", rho=rho)
            parts.append((None if b2 is None or b1 is None else abs(b2 - b1) <= 1.0, f"(c) bind-ready M1+M2 {fmt(b2)} vs M1 only {fmt(b1)} s, within 1.0 s"))
            self.combine(f"G3 rho {rho:g}", parts)
        # G4 (C), G5 (D)
        bo, no = self.m("C", "bind", label="Full OTTER"); bn, nn = self.m("C", "bind", label="M1 + M2 (no placement)"); x, _ = self.m("C", "x_dest", label="Full OTTER")
        self.verdict("G4", None if bo is None or bn is None or x is None else bo <= bn - 0.5 * x * T_S,
                     f"Full OTTER bind-ready {fmt(bo)} s (n={no}) <= no placement {fmt(bn)} s (n={nn}) - 0.5 x {fmt(x)} x {T_S} = {fmt(None if bn is None or x is None else bn - 0.5 * x * T_S)}")
        for lab in ("Full OTTER", "M1 + M2 + top-1"):
            b, n = self.m("D", "bind", label=lab); bn, _ = self.m("D", "bind", label="M1 + M2 (no placement)")
            src, _ = self.m("D", "src", label=lab); post, _ = self.m("D", "post", label=lab); fwd, _ = self.m("D", "fwd", label=lab); x, _ = self.m("D", "x_top", label=lab)
            evalb = all(r["fwd_evaluable"] for r in self.cfg("D", label=lab))
            parts = [(None if b is None or bn is None else abs(b - bn) <= 1.5, f"(a) bind-ready {fmt(b)} vs no placement {fmt(bn)} s, within 1.5 s (n={n})"),
                     (None if src is None else src <= 1.02, f"(b) B_source,total {fmt(src)} <= 1.02"),
                     (None if post is None or x is None else post <= (1 - x) + 0.02, f"(c) B_post {fmt(post)} <= (1 - x) + 0.02 with x {fmt(x)}"),
                     (None if fwd is None or x is None or not evalb else fwd >= 0.9 * x, f"(d) B_fwd {fmt(fwd)} >= 0.9 x {fmt(x)}" + ("" if evalb else " (not evaluable: receipts missing)"))]
            if lab == "Full OTTER":
                self.combine("G5", parts)
            else:
                self.tables.append(("G5 clauses for M1 + M2 + top-1 (reported, not judged)", [p[1] + f" -> {'pass' if p[0] else ('-' if p[0] is None else 'fail')}" for p in parts]))
        # G6 (E)
        b1, n1 = self.m("E", "bind", label="M1 only"); b2, n2 = self.m("E", "bind", label="M1 + M2"); b3, n3 = self.m("E", "bind", label="OTTER event-driven")
        self.verdict("G6", None if None in (b1, b2, b3) else (b2 <= b1 - 3.5 and b3 <= b1 - 3.5),
                     f"GPU session bind-ready M1+M2 {fmt(b2)} (n={n2}), OTTER event-driven {fmt(b3)} (n={n3}) <= M1 only {fmt(b1)} (n={n1}) - 3.5 s")
        # G7
        bd, nd = self.m("F", "bind", label="OTTER event-driven"); ba, na = self.m("F", "bind", label="OTTER at moves")
        rp, _ = self.m("F", "replans", label="OTTER event-driven"); du, _ = self.m("F", "dups", label="OTTER event-driven")
        parts = [(None if bd is None or ba is None else bd <= 0.5 * ba, f"F: event-driven {fmt(bd)} (n={nd}) <= 0.5 x at moves {fmt(ba)} (n={na}) s"),
                 (None if rp is None else rp <= 2, f"F: re-plans {fmt(rp)} <= 2 (reps {[r['replans'] for r in self.cfg('F', label='OTTER event-driven')]})"),
                 (None if du is None else du == 0, f"F: duplicates {fmt(du)} = 0")]
        for scen, kw in (("B", {"rho": 2.0}), ("B", {"rho": 4.0}), ("G", {})):
            r_, n_ = self.m(scen, "replans", label="OTTER event-driven", **kw)
            bd, _ = self.m(scen, "bind", label="OTTER event-driven", **kw); ba, _ = self.m(scen, "bind", label="OTTER at moves", **kw)
            tag = f"{scen}{' rho ' + format(kw['rho'], 'g') if kw else ''}"
            parts.append((None if r_ is None or bd is None or ba is None else (r_ == 0 and abs(bd - ba) <= 1.0),
                          f"{tag} (no change): re-plans {fmt(r_)} = 0 (reps {[r['replans'] for r in self.cfg(scen, label='OTTER event-driven', **kw)]}), bind-ready {fmt(bd)} vs {fmt(ba)} s within 1.0 s"))
        self.combine("G7", parts)
        # G8 (G)
        b1, n1 = self.m("G", "bind", label="M1 only")
        parts = []
        for lab in ("M1 + M2", "OTTER at moves", "OTTER event-driven"):
            b, n = self.m("G", "bind", label=lab)
            parts.append((None if b is None or b1 is None else b <= 0.6 * b1, f"{lab} {fmt(b)} (n={n}) <= 0.6 x M1 only {fmt(b1)} (n={n1}) s"))
        self.combine("G8", parts)
        # G9
        parts = []
        if steady:
            rel = steady["relative_difference"]; okv = steady.get("gpu0_idle_before") is not False and steady["reps"] >= self.min_reps and steady.get("identical_frames_rep1") is not False
            parts.append((abs(rel) <= 0.02 if okv else None, f"steady state: OTTER-enabled vs unmodified median chunk interval {rel * 100:+.2f} % (|.| <= 2 %), reps {steady['reps']}, identical frames {steady.get('identical_frames_rep1')}"))
        else:
            parts.append((None, "steady state: no expD_G9 run"))
        for bw in (SHAPED, 0.0):
            peaks = {lab: self.m("A", "peak_dest_mb", label=lab, bw=bw)[0] for lab in ("Full migration", "Cold restart", "M1 only", "OTTER event-driven")}
            vals = [v for v in peaks.values() if v is not None]
            spread = (max(vals) - min(vals)) / min(vals) if len(vals) == 4 and min(vals) > 0 else None   # 0 = no GPU (dry run)
            parts.append((None if spread is None else spread <= 0.01, f"bw {bw or 'native'}: destination peak memory_allocated {{{', '.join(f'{k}: {fmt(v and v / 1024)} GiB' for k, v in peaks.items())}}}, spread {fmt(spread)} <= 0.01"))
        self.combine("G9", parts)

    def combine(self, name, parts):
        oks = [p[0] for p in parts]
        v = None if any(o is None for o in oks) else all(oks)
        self.verdict(name, v, "; ".join(p[1] + ("" if p[0] is None else (" [pass]" if p[0] else " [fail]")) for p in parts))

    def extra_reps(self):
        out = []
        keyf = lambda r: (r["label"], r["bw"])  # noqa: E731
        groups = defaultdict(list)
        for r in self.runs:
            if r["scenario"] == "A" and r["valid"]:
                groups[keyf(r)].append(r)
        for (lab, bw), reps in groups.items():
            if len(reps) == 3:
                for k in ("ttfo", "bind"):
                    q, m_ = iqr([r[k] for r in reps]), med([r[k] for r in reps])
                    if q is not None and m_ and q > 0.10 * m_:
                        out.append({"label": lab, "bw": bw, "metric": k, "iqr": q, "median": m_}); break
        return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prefix", default="expD")
    ap.add_argument("--min_reps", type=int, default=3, help="valid reps needed per configuration (3 per the spec; lower only to test the aggregator on dry runs)")
    a = ap.parse_args()
    if a.min_reps != 3:
        assert a.prefix != "expD", "--min_reps other than 3 is for protocol tests only"
    global T_S, SHAPED
    if a.prefix.startswith("_dryrun"):
        T_S, SHAPED = 5.4, 100.0
    g = Agg(a.prefix, a.min_reps)
    sd = sorted((EV / f"{a.prefix}_G9").glob("steady_*/summary.json"))
    steady = json.load(open(sd[-1])) if sd else None
    g.run(steady)
    extra = g.extra_reps()
    out = Path(ROOT / "results/evaluation/osdi/expD"); out.mkdir(parents=True, exist_ok=True)
    tag = "" if a.prefix == "expD" else "_" + a.prefix.strip("_")
    lines = ["# Experiment D results", "", f"Aggregated by `tools/eval/aggregate_expD.py` per `aggregation_spec.md` from `results/evaluation/{a.prefix}_*`. Medians over valid reps.", "",
             "| criterion | verdict | detail |", "|---|---|---|"]
    lines += [f"| {v['criterion']} | **{v['verdict']}** | {v['detail']} |" for v in g.verdicts]
    for title, rows in g.tables:
        lines += ["", f"### {title}", ""] + [f"- {r}" for r in rows]
    lines += ["", "## Configurations (medians over valid reps)", "", "| scenario | configuration | bw | rho | valid / all | TTFO | bind-ready | rejoin (s / calls) | source | discarded | B_fwd | re-plans | dups |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    cfgs = defaultdict(list)
    for r in g.runs:
        if r.get("label"):
            cfgs[(r["scenario"], r["label"], r["bw"], r["rho"], r["path"], r["ev"])].append(r)
    f = lambda x: "-" if x is None else f"{x:.2f}"  # noqa: E731
    for (sc, lab, bw, rho, path, ev), rs in sorted(cfgs.items(), key=lambda kv: str(kv[0])):
        v = [r for r in rs if r["valid"]]
        lines.append(f"| {sc} | {lab}{' (' + path + ')' if path not in ('AB', 'ABCD') else ''}{' + cap event' if ev else ''} | {bw or 'native'} | {rho} | {len(v)} / {len(rs)} | {f(med([r['ttfo'] for r in v]))} | {f(med([r['bind'] for r in v]))} | "
                     f"{f(med([r['rejoin_delay'] for r in v]))} / {f(med([r['rejoin_calls'] for r in v]))} | {f(med([r['src'] for r in v]))} | {f(med([r['discarded'] for r in v]))} | {f(med([r['fwd'] for r in v]))} | {f(med([r['replans'] for r in v]))} | {f(med([r['dups'] for r in v]))} |")
    inv = [r for r in g.runs if not r["valid"]]
    lines += ["", f"## Invalid runs ({len(inv)}; excluded, kept, re-run)", ""] + [f"- `{r['scenario']}/{r['run']}`: {', '.join(r['why'])}" for r in inv]
    lines += ["", f"## Scenario A configurations needing reps 4-5 (IQR > 10 % of the median): {len(extra)}", ""] + [f"- {e}" for e in extra]
    (out / f"expD_results{tag}.md").write_text("\n".join(lines) + "\n")
    (out / f"expD_results{tag}.json").write_text(json.dumps({"verdicts": g.verdicts, "runs": g.runs, "steady": steady, "extra_reps": extra}, indent=1, default=str))
    (out / f"expD_extra_reps{tag}.json").write_text(json.dumps(extra, indent=1))
    print("\n".join(lines[:len(g.verdicts) + 6]))


if __name__ == "__main__":
    main()
