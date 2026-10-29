#!/usr/bin/env python3
"""M3-E0 (osdi/m3e0/preregistration.md): cross-version classification of the Sink fragments that abandoned destinations
hold, against the base the final (completed) migration needed. One GPU process per workload; analysis only.

For every run directory given, the run's base versions are read from its events: the boundary call c0 and the live
per-fragment SHA-256 prefixes of every task's base (`A:replay_base_sent`), and the fragments each destination held
hash-verified when its round 1 ended (`<dst>:replay_base`). The workload is then re-generated deterministically in this
process (same input, prompt and seed; the same calls as the source), the Sink serialization (`pack(snapshot, "sink")`,
the exact bytes the source fragments) is captured at every boundary c0, and every call's cache decisions between the
boundaries are recorded (refresh = a write into a Sink slot; realignment = a position shift of an unwritten Sink slot),
as in tools/eval/m1_sink_dirty.py (E4).

Reproduction check (measured): the offline fragment hashes of every version must equal the live ones (412 / 412);
otherwise the run's classification is reported as not reproduced and not used.

Per fragment of a held version v against the target base t (4 MiB fragments, block-level attribution):
  identical       hash-equal: usable as is (content-identical; validity by SHA-256 against t's manifest)
  shift_only      differs only in K blocks whose ordered RoPE shifts reproduce t bitwise, possibly plus the position
                  table: needs cross-version reconstruction (ordered shifts, as M2)
  refresh         overlaps a block refreshed in [v, t): needs new values from the source
  other           any other change (not explained by refresh or shift)
Strict same-version reuse is possible only when v == t (same boundary call); it is counted separately.

    python tools/eval/m3e0_crossversion.py --runs <run_dir>[,<run_dir>...] --video_path ... --prompt_file_path ... --seed 0
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p_ in (ROOT, ROOT / "tools", ROOT / "tools" / "eval"):
    if str(p_) not in sys.path:
        sys.path.insert(0, str(p_))

PRIO = ("refresh", "other", "shift_only")


def contiguous(header, bufs) -> bytearray:
    buf = bytearray(header["nbytes"]); mv = memoryview(buf)
    for t, b in zip(header["tensors"], bufs):
        mv[t["offset"]:t["offset"] + t["nbytes"]] = memoryview(b).cast("B")
    return buf


def run_versions(d: Path) -> dict:
    """Tasks in start order with their base boundary, live hashes, outcome and the destination's held fragments."""
    ev = []
    for r in csv.DictReader(open(d / "events.csv", newline="")):
        ev.append({"event": r["event"], **(json.loads(r["detail"]) if r["detail"] else {})})
    tasks = [{"id": e["id"], "src": e["src"], "dst": e["dst"]} for e in ev if e["event"] == "xb_task_start"]
    for t in tasks:
        b = next((e for e in ev if e["event"] == f"{t['src']}:replay_base_sent" and e.get("task") == t["id"]), None)
        h = next((e for e in ev if e["event"] == f"{t['dst']}:replay_base" and e.get("task") == t["id"]), None)
        t["c0"] = b and int(b["call"])
        t["hashes"] = b and b.get("sink_frag_hashes16")
        t["held"] = {int(fid): hh for fid, hh in (h or {}).get("sink_frag_hashes16_held", [])}
        t["base_verified"] = h and h.get("verified")
        t["cancelled"] = any(e["event"] == "xb_task_cancel" and e.get("task") == t["id"] for e in ev)
        t["done"] = any(e["event"] == "xb_task_done" and e.get("task") == t["id"] for e in ev)
    return {"run": d.name, "tasks": tasks}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", required=True, help="comma list of run directories (one workload)")
    ap.add_argument("--video_path", required=True); ap.add_argument("--prompt_file_path", required=True); ap.add_argument("--seed", default="0")
    ap.add_argument("--gpu_id", default="0"); ap.add_argument("--frag_bytes", type=int, default=4 << 20)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    import torch

    import m1_replay as mr
    import mobility_node as mn
    from models.wan.causal_model import _shift_temporal_rope
    from mobility_node import frag_table

    runs = [run_versions(Path(x)) for x in a.runs.split(",") if x]
    V = sorted({t["c0"] for R in runs for t in R["tasks"] if t["c0"] is not None})
    margs = mn.parse_args(["--label", "E0X", "--video_path", a.video_path, "--prompt_file_path", a.prompt_file_path, "--seed", a.seed, "--gpu_id", a.gpu_id,
                           "--migration_chunk", "30", "--post_chunks", "1500"])
    rt = mn.GpuRuntime(margs)
    pl, dev = rt.pl, rt.device
    sync = lambda: torch.cuda.synchronize(dev)  # noqa: E731
    S, fsl = rt.sink, rt.fsl
    rec = mr.Recorder(torch, pl, S, dev, sync, keep_slots=False)
    session = rt.session = rt.runner.start()
    snaps = {}   # c0 -> (header, bytes)

    def capture(c):
        ser = rt.serialize_live()
        h, b = rt.pack(ser, "sink")
        snaps[c] = (h, contiguous(h, b)); del b, ser

    for c in range(max(V)):
        if c in V:
            sync(); capture(c)
        if c >= min(V):
            rec.call, rec.active = c, True
        rt.runner.step(session, c)
        rec.call, rec.active = None, False
    sync(); capture(max(V))
    h0 = snaps[V[0]][0]
    T = {t["name"]: t for t in h0["tensors"]}
    shp = T["kv/0/k"]["shape"]
    rows_n, H, D = shp[0], shp[2], shp[3]
    blk = fsl * H * D * 2
    n_layers = len(pl.kv_cache1)
    freqs = pl.generator.model.freqs.to(dev)
    nbytes = len(snaps[V[0]][1])
    frags = frag_table(nbytes, a.frag_bytes)
    flen = [f["len"] for f in frags]

    def hashes16(B):
        mv = memoryview(B)
        return [hashlib.sha256(mv[f["off"]:f["off"] + f["len"]]).hexdigest()[:16] for f in frags]

    H16 = {c: hashes16(B) for c, (_, B) in snaps.items()}

    def classify(cv, ct):
        """Per-fragment category of version cv against target ct (cv <= ct)."""
        Bv, Bt = memoryview(snaps[cv][1]), memoryview(snaps[ct][1])
        hist = {}
        for c in range(cv, ct):
            e = rec.entries[c]
            for li, wrows in enumerate(e["written"]):
                pre, post = e["pre"]["pos"][li].tolist(), e["post"]["pos"][li].tolist()
                for b, w in enumerate(wrows):
                    for s in range(S):
                        hh = hist.setdefault((li, b, s), {"refresh": [], "shifts": []})
                        if w == s:
                            hh["refresh"].append(c)
                        elif post[b][s] != pre[b][s]:
                            hh["shifts"].append(int(post[b][s] - pre[b][s]))
        ranges, nblk = [], {"refresh": 0, "other": 0, "shift_only": 0, "unchanged": 0}
        for li in range(n_layers):
            for part in ("k", "v"):
                t = T[f"kv/{li}/{part}"]
                for b in range(rows_n):
                    for s in range(S):
                        lo = t["offset"] + (b * S + s) * blk; hi = lo + blk
                        if Bv[lo:hi] == Bt[lo:hi]:
                            nblk["unchanged"] += 1; continue
                        hh = hist.get((li, b, s), {"refresh": [], "shifts": []})
                        if hh["refresh"]:
                            cat = "refresh"
                        elif part == "k" and hh["shifts"]:
                            k0 = torch.frombuffer(bytearray(Bv[lo:hi]), dtype=torch.bfloat16).view(fsl, H, D).to(dev)
                            for dd in hh["shifts"]:
                                k0 = _shift_temporal_rope(k0, freqs, dd)
                            kt = torch.frombuffer(bytearray(Bt[lo:hi]), dtype=torch.bfloat16).view(fsl, H, D).to(dev)
                            cat = "shift_only" if torch.equal(k0, kt) else "other"
                        else:
                            cat = "other"
                        nblk[cat] += 1; ranges.append((lo, hi, cat))
            tp = T[f"ring/{li}/pos_sink"]
            if Bv[tp["offset"]:tp["offset"] + tp["nbytes"]] != Bt[tp["offset"]:tp["offset"] + tp["nbytes"]]:
                ranges.append((tp["offset"], tp["offset"] + tp["nbytes"], "position"))
        hv, ht = H16[cv], H16[ct]
        cats, unexplained = [], 0
        for i, f in enumerate(frags):
            if hv[i] == ht[i]:
                cats.append("identical"); continue
            lo, hi = f["off"], f["off"] + f["len"]
            cs = {c_ for r_lo, r_hi, c_ in ranges if r_lo < hi and r_hi > lo}
            if not cs:
                unexplained += 1; cats.append("other"); continue
            cats.append(next((p for p in PRIO if p in cs), "shift_only"))   # position-only changes are reconstructed with the shifts
        return cats, nblk, unexplained

    def tally(ids, cats):
        out = {k: {"fragments": 0, "bytes": 0} for k in ("identical", "shift_only", "refresh", "other")}
        for i in ids:
            out[cats[i]]["fragments"] += 1; out[cats[i]]["bytes"] += flen[i]
        return out

    res = {"host": platform.node(), "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
           "video": a.video_path, "seed": a.seed, "versions": V, "sink_bytes": nbytes, "n_fragments": len(frags), "block_bytes": blk, "runs": {}}
    for R in runs:
        tasks = R["tasks"]
        fin = next((t for t in reversed(tasks) if t["done"]), None)
        rr = {"tasks": [], "final_task": fin and fin["id"], "final_c0": fin and fin["c0"]}
        repro = all(t["hashes"] is None or H16[t["c0"]] == t["hashes"] for t in tasks if t["c0"] is not None)
        rr["reproduction"] = {t["id"]: (sum(x == y for x, y in zip(H16[t["c0"]], t["hashes"])) if t["hashes"] else None) for t in tasks if t["c0"] is not None}
        rr["reproduced_all"] = repro
        union = {k: set() for k in ("identical", "shift_only", "refresh", "other")}
        for t in tasks:
            if fin is None or t is fin or t["c0"] is None:
                continue
            ids = sorted(t["held"])
            held_ok = all(t["hashes"][i] == hh for i, hh in t["held"].items()) if t["hashes"] else None
            x = {"task": t["id"], "dst": t["dst"], "c0": t["c0"], "cancelled": t["cancelled"], "held_fragments": len(ids), "held_bytes": sum(flen[i] for i in ids),
                 "held_equal_live_base": held_ok, "strict_same_version": t["c0"] == fin["c0"]}
            if repro:
                cats, nblk, unexp = classify(t["c0"], fin["c0"])
                x["vs_final"] = tally(ids, cats); x["blocks_changed_vs_final"] = nblk; x["fragments_unexplained"] = unexp
                x["whole_base_vs_final"] = tally(range(len(frags)), cats)
                for i in ids:
                    union[cats[i]].add(i)
                nx = tasks[tasks.index(t) + 1] if tasks.index(t) + 1 < len(tasks) else None
                if nx is not None and nx["c0"] is not None and nx is not fin:
                    cn, _, _ = classify(t["c0"], nx["c0"])
                    x["vs_next"] = {"task": nx["id"], "c0": nx["c0"], **tally(ids, cn)}
            rr["tasks"].append(x)
        if repro and fin is not None:
            seen = set()
            u = {}
            for k in ("identical", "shift_only", "refresh", "other"):   # a fragment held by two holders counts once, in its best class
                ids = union[k] - seen; seen |= ids
                u[k] = {"fragments": len(ids), "bytes": sum(flen[i] for i in ids)}
            rr["union_over_abandoned_holders_vs_final"] = u
        res["runs"][R["run"]] = rr
        print(f"[E0X] {R['run'][:70]}: reproduced {repro}; " + "; ".join(f"{x['task']} c0 {x['c0']} held {x['held_fragments']}" + (f" -> {json.dumps({k: v['fragments'] for k, v in x['vs_final'].items()})}" if "vs_final" in x else "") for x in rr["tasks"]), flush=True)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=1, default=str))
    print(f"[E0X] wrote {a.out}")


if __name__ == "__main__":
    main()
