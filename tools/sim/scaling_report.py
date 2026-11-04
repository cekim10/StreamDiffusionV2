#!/usr/bin/env python3
"""E9 scalability extension (osdi/fig_cluster/scaling_protocol.md, DRAFT; not frozen): load scaling (grid "load") and
cluster-size scaling (grids "scale", "scale_g4"). Descriptive tables, medians over seeds (min-max in brackets for the
two headline metrics), plus the two gates the protocol requires before any table is read. SIMULATED results.

Gates:
  R0  every run of the new grid whose configuration and seed also exist in the FROZEN primary sweep
      (sweep_primary.json) is identical to it in every summary field (same model, same calibration).
  R1  2 sites (grid 1 x 2): OTTER == Unstaged in every summary field (no staging candidate by construction).

    python3.11 tools/sim/cluster_sim.py sweep --grid load      # then:
    python3.11 tools/sim/scaling_report.py --grid load
    python3.11 tools/sim/scaling_report.py --grid scale [--prefix _dry_]
"""

from __future__ import annotations

import argparse
import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/evaluation/osdi/fig_cluster"
LABEL = {"full": "Full", "pfull": "Llumnix", "rfull": "SLLM", "base": "Unstaged", "otter": "OTTER", "naive": "Replicate"}
ORDER = ("full", "pfull", "rfull", "base", "otter", "naive")
CFG_KEYS = ("E", "G", "N", "C_gbps", "M_gb", "dwell_s", "T_end", "T_warm", "life_s", "drain_per_site_h", "drain_s", "k_stage")
METRICS = [   # (key, label, function)
    ("stalled", "stalled s / session-h", lambda r: r.get("stalled_s_per_session_h", r["stall_frac"] * 3600)),
    ("local", "local share", lambda r: r["local_frac"]),
    ("remote", "remote share", lambda r: r["remote_frac"]),
    ("reach", "moves reaching local", lambda r: r["moves_reaching_local"]),
    ("delay", "time w/o local per move (s)", lambda r: r["no_local_after_move_s"].get("mean")),
    ("stage", "staging GB / session-h", lambda r: (r.get("bytes_per_session_h_gb") or {}).get("staging", 0.0)),
    ("bytes", "all GB / session-h", lambda r: sum((r.get("bytes_per_session_h_gb") or {}).values())),
    ("mem", "site mem mean / peak (GB)", None),
    ("util", "link util p50 / p99", None),
    ("blocked", "blocked starts", lambda r: r["blocked_starts"]),
    ("wall", "sim wall (s)", lambda r: r.get("wall_s")),
]


def key(r):
    return tuple(r["cfg"].get(k) for k in CFG_KEYS) + (r["seed"], r["method"])


def same(a, b):
    ks = [k for k in a if k not in ("wall_s", "cfg", "seed")]
    return all(json.dumps(a[k], sort_keys=True) == json.dumps(b.get(k), sort_keys=True) for k in ks)


def med(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else None


def f(x, d=1):
    return "-" if x is None else f"{x:.{d}f}"


def cells(runs, ckeys):
    out = {}
    for r in runs:
        out.setdefault(tuple(r["cfg"][k] for k in ckeys), {}).setdefault(r["method"], []).append(r)
    return dict(sorted(out.items()))


def table(runs, ckeys, clabel):
    L = []
    for c, by in cells(runs, ckeys).items():
        L += ["", f"**{clabel(c)}**", "",
              "| method | " + " | ".join(m[1] for m in METRICS) + " |", "|---" * (len(METRICS) + 1) + "|"]
        for m in ORDER:
            rs = by.get(m)
            if not rs:
                continue
            row = []
            for k, _, fn in METRICS:
                if k == "mem":
                    row.append(f"{f(med([r['mem_site_mean_gb'] for r in rs]))} / {f(med([r['mem_site_peak_gb'] for r in rs]))}")
                elif k == "util":
                    row.append(f"{f(med([r['link_util_p50'] for r in rs]), 2)} / {f(med([r['link_util_p99'] for r in rs]), 2)}")
                elif k in ("stalled", "local"):
                    xs = [fn(r) for r in rs]
                    d = 1 if k == "stalled" else 3
                    row.append(f"{f(med(xs), d)} [{f(min(xs), d)}-{f(max(xs), d)}]")
                else:
                    row.append(f(med([fn(r) for r in rs]), 3 if k in ("remote", "reach") else 1 if k != "blocked" else 0))
            L.append(f"| {LABEL[m]} | " + " | ".join(row) + " |")
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", default="load", choices=["load", "scale", "scale_g4"])
    ap.add_argument("--prefix", default="")
    a = ap.parse_args()
    d = json.loads((OUT / f"{a.prefix}sweep_{a.grid}.json").read_text())
    runs = d["runs"]
    frozen = {key(r): r for r in json.loads((OUT / "sweep_primary.json").read_text())["runs"]}
    shared = [r for r in runs if key(r) in frozen]
    r0 = [key(r) for r in shared if not same(r, frozen[key(r)])]
    two = {(r["seed"], r["cfg"]["N"], r["cfg"]["G"]): r for r in runs if r["cfg"]["E"] == 2 and r["method"] == "otter"}
    r1_pairs = [(two[(r["seed"], r["cfg"]["N"], r["cfg"]["G"])], r) for r in runs if r["cfg"]["E"] == 2 and r["method"] == "base"
                and (r["seed"], r["cfg"]["N"], r["cfg"]["G"]) in two]
    r1_bad = sum(1 for o, b in r1_pairs if not same({k: v for k, v in o.items() if k != "method"}, {k: v for k, v in b.items() if k != "method"}))
    L = [f"# E9 scalability extension: grid `{a.grid}` (PRELIMINARY SIMULATION - Sink delta beyond 240 calls extrapolated; descriptive only, G3)", "",
         f"Runs {len(runs)}; medians over seeds {sorted({r['seed'] for r in runs})}, [min-max] for stalled seconds and local share. "
         "Same model and calibration as the frozen primary sweep; delta bytes beyond 240 calls are extrapolated (D5) and the "
         "store is the idealized [A11] store unless stated otherwise.", "",
         f"- **R0** (shared points identical to the frozen primary sweep): {len(shared)} shared runs, {len(r0)} different -> "
         f"{'PASS' if not r0 else 'FAIL'}" + ("" if shared else " (no shared points in this grid)"),
         f"- **R1** (2 sites: OTTER == Unstaged): {len(r1_pairs)} pairs, {r1_bad} different -> "
         f"{'PASS' if not r1_bad else 'FAIL'}" + ("" if r1_pairs else " (no 2-site points in this grid)")]
    # L-D1 / S-D1 (descriptive counts, G3): cells where OTTER's median stalled s / session-h < each external baseline's,
    # with the local shares next to it (a baseline served mostly remotely stalls little)
    ckeys = ("C_gbps", "N") if a.grid == "load" else ("E", "G", "N")
    rows, held = [], 0
    for c, by in cells(runs, ckeys).items():
        ms = {m: med([METRICS[0][2](r) for r in by[m]]) for m in by}
        ls = {m: med([r["local_frac"] for r in by[m]]) for m in by}
        lose = [LABEL[b] for b in ("full", "pfull", "rfull") if b in ms and not ms["otter"] < ms[b]]
        held += not lose
        rows.append(f"| {c} | {f(ms['otter'])} / {f(100 * ls['otter'])} % | " + " | ".join(f"{f(ms[b])} / {f(100 * ls[b])} %" for b in ("full", "pfull", "rfull"))
                    + f" | {'yes' if not lose else 'no (' + ', '.join(lose) + ')'} |")
    L += ["", f"**{'L' if a.grid == 'load' else 'S'}-D1 (descriptive, not a hypothesis):** OTTER's median stalled s / session-h below each of Full, "
          f"Llumnix, SLLM in {held} / {len(rows)} cells.", "",
          f"| cell {ckeys} | OTTER stalled / local | Full | Llumnix | SLLM | below all three |", "|---|---|---|---|---|---|"] + rows
    if a.grid == "load":
        L += ["", "## L: load scaling (128 GPUs = 16 sites x 8; N sessions; sessions per GPU = N / 128)"]
        L += table(runs, ("C_gbps", "N"), lambda c: f"C {c[0]:g} Gbps, N {c[1]} ({c[1] / 128:.3f} per GPU)")
    else:
        L += ["", f"## S: cluster-size scaling ({'8' if a.grid == 'scale' else '4'} GPUs per site; sessions per GPU fixed)"]
        L += table(runs, ("E", "G", "N"), lambda c: f"{c[0] * c[1]} GPUs = {c[0]} sites x {c[1]}, N {c[2]} ({c[2] / (c[0] * c[1]):.2f} per GPU)")
    p = OUT / f"{a.prefix}scaling_{a.grid}.md"
    p.write_text("\n".join(L) + "\n")
    (OUT / f"{a.prefix}scaling_{a.grid}.json").write_text(json.dumps({"grid": a.grid, "R0": {"shared": len(shared), "different": len(r0)},
                                                                       "R1": {"pairs": len(r1_pairs), "different": r1_bad}}, indent=1))
    print("\n".join(L[:8]))
    print(f"-> {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
