#!/usr/bin/env python3
"""Task B: exact Sink block-change and fragment-reuse analysis from W1 block checksums (results/evaluation/expW_W1/*/w1_blocks.csv).

Per call c >= 1 and per block (layer, key in {k, v}, row, sink slot): changed iff its checksum differs from call c - 1.
Attribution per (layer, row, slot) at call c:
  refresh   K and V both changed and the slot's RoPE position changed to a value not equal to the common shift
  realign   K changed, V unchanged, and the slot's position moved by the same delta as every other moved slot of that row
  other     anything else (reported; should be rare)
Fragment reuse for delta in {1, 5, 10, 25, 50} calls: fraction of fragments unchanged over (c, c + delta], for
  (a) block-aligned fragments (one block = one 4,792,320 B fragment, 360 per Sink) and
  (b) the current 412 x 4 MiB table (a block maps to the fragments its byte range overlaps),
  each with and without realign-induced K changes (the latter = what canonicalized keys would give, IF they reconstruct
  correctly: see the rotation round-trip test in w1_summary.json["rope_roundtrip"]).

    python tools/eval/expb_reuse.py            # -> results/evaluation/osdi/expB_reuse.{json,md}
"""

from __future__ import annotations

import csv
import glob
import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NL, NS, NR, FSL, HD = 30, 3, 2, 1560, 1536
BLK = FSL * HD * 2
FRAG = 4 << 20
PER_LAYER = 2 * NR * NS * BLK + NR * NS * 8
N_FRAG412 = (NL * PER_LAYER + FRAG - 1) // FRAG
DELTAS = (1, 5, 10, 25, 50)
START = 30


def block_index(li, key, b, s):
    return ((li * 2 + (0 if key == "k" else 1)) * NR + b) * NS + s


def frag412(li, key, b, s):
    base = li * PER_LAYER + (0 if key == "k" else NR * NS * BLK) + b * NS * BLK + s * BLK
    return set(range(base // FRAG, (base + BLK - 1) // FRAG + 1))


def analyse(path: Path) -> dict:
    rows = list(csv.DictReader(open(path, newline="")))
    cks = [json.loads(r["blocks"]) for r in rows]
    pos = [json.loads(r["pos_all"]) for r in rows]   # [layer][row][slot]
    n = len(rows)
    per_call = []   # per call: {"refresh": set of (li,b,s), "realign": set, "other": set, "changed_blocks": set of block idx}
    for c in range(1, n):
        ref, rea, oth, changed = set(), set(), set(), set()
        for li in range(NL):
            for b in range(NR):
                moved = {s: pos[c][li][b][s] - pos[c - 1][li][b][s] for s in range(len(pos[c][li][b])) if pos[c][li][b][s] != pos[c - 1][li][b][s] and pos[c - 1][li][b][s] > -(1 << 29)}
                deltas = [d for s, d in moved.items() if s >= NS]   # recent slots define the realign shift
                common = statistics_mode(deltas) if deltas else None
                for s in range(NS):
                    kc = cks[c][block_index(li, "k", b, s)] != cks[c - 1][block_index(li, "k", b, s)]
                    vc = cks[c][block_index(li, "v", b, s)] != cks[c - 1][block_index(li, "v", b, s)]
                    if kc:
                        changed.add(block_index(li, "k", b, s))
                    if vc:
                        changed.add(block_index(li, "v", b, s))
                    if not (kc or vc):
                        continue
                    if kc and not vc and s in moved and common is not None and moved[s] == common:
                        rea.add((li, b, s))
                    elif kc and vc:
                        ref.add((li, b, s))
                    else:
                        oth.add((li, b, s))
        per_call.append({"call": c, "refresh": ref, "realign": rea, "other": oth, "changed": changed})
    # realign-only K changes (what canonicalized keys would avoid)
    realign_blocks = [{block_index(li, "k", b, s) for (li, b, s) in pc["realign"]} for pc in per_call]
    out = {"calls": n, "promotions_by_cause": {"refresh": sum(len(pc["refresh"]) for pc in per_call if pc["call"] >= START),
                                              "realign": sum(len(pc["realign"]) for pc in per_call if pc["call"] >= START),
                                              "other": sum(len(pc["other"]) for pc in per_call if pc["call"] >= START)},
           "realign_calls": [pc["call"] for pc in per_call if pc["realign"]][:20], "reuse": {}}
    for d in DELTAS:
        f360, f360_nr, f412, f412_nr = [], [], [], []
        for c in range(START, n - d):
            ch = set().union(*(per_call[t - 1]["changed"] for t in range(c + 1, c + d + 1)))
            rl = set().union(*(realign_blocks[t - 1] for t in range(c + 1, c + d + 1)))
            ch_nr = ch - rl
            f360.append(1 - len(ch) / (NL * 2 * NR * NS)); f360_nr.append(1 - len(ch_nr) / (NL * 2 * NR * NS))
            fr = set(); fr_nr = set()
            for idx in ch:
                li, rest = divmod(idx, 2 * NR * NS); key = "k" if rest < NR * NS else "v"; b, s = divmod(rest % (NR * NS), NS)
                fr |= frag412(li, key, b, s)
                if idx in ch_nr:
                    fr_nr |= frag412(li, key, b, s)
            f412.append(1 - len(fr) / N_FRAG412); f412_nr.append(1 - len(fr_nr) / N_FRAG412)
        if not f360:
            out["reuse"][d] = None; continue
        out["reuse"][d] = {"block_aligned_mean": st.mean(f360), "block_aligned_min": min(f360), "block_aligned_norealign_mean": st.mean(f360_nr),
                           "frag412_mean": st.mean(f412), "frag412_min": min(f412), "frag412_norealign_mean": st.mean(f412_nr),
                           "dirty_bytes_mean": (1 - st.mean(f360)) * NL * 2 * NR * NS * BLK, "update_mbps_mean": (1 - st.mean(f360)) * NL * 2 * NR * NS * BLK * 8 / (d * 0.556) / 1e6}
    return out


def statistics_mode(xs):
    return max(set(xs), key=xs.count)


def main():
    res = {}
    for p in sorted(glob.glob(str(ROOT / "results/evaluation/expW_B/*/w1_blocks.csv"))):
        name = Path(p).parent.name.rsplit("_2", 1)[0]
        s = json.load(open(Path(p).parent / "w1_summary.json"))
        res[name] = {**analyse(Path(p)), "rope_roundtrip": s.get("rope_roundtrip")}
    out = ROOT / "results/evaluation/osdi/expB_reuse.json"
    out.write_text(json.dumps(res, indent=1))
    L = ["# Task B: exact Sink block changes and fragment reuse (W1 block checksums; measured)", "",
         "| unit | refresh / realign / other (calls 30-329) | " + " | ".join(f"reuse d={d}: blk / blk-noRL / 412 / 412-noRL" for d in DELTAS) + " | update Mbps d=25 |", "|---|---|" + "---|" * (len(DELTAS) + 1)]
    for name, r in res.items():
        pb = r["promotions_by_cause"]
        L.append(f"| {name} | {pb['refresh']} / {pb['realign']} / {pb['other']} | " + " | ".join(
            f"{r['reuse'][d]['block_aligned_mean']:.3f} / {r['reuse'][d]['block_aligned_norealign_mean']:.3f} / {r['reuse'][d]['frag412_mean']:.3f} / {r['reuse'][d]['frag412_norealign_mean']:.3f}" for d in DELTAS)
            + f" | {r['reuse'][25]['update_mbps_mean']:.0f} |" if all(r['reuse'][d] for d in DELTAS) else f"| {name} | {pb['refresh']} / {pb['realign']} / {pb['other']} | (too few calls) |")
    if res:
        L += ["", "RoPE round-trip (bf16 keys rotated +d then -d, vs the original): " + "; ".join(f"{n}: {r['rope_roundtrip']}" for n, r in list(res.items())[:3])]
    (ROOT / "results/evaluation/osdi/expB_reuse.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
