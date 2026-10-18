import csv, sys, statistics as st
from collections import defaultdict, Counter
rows = list(csv.DictReader(open(sys.argv[1])))
print("rows", len(rows), "columns", len(rows[0]))
key = lambda r: (r["run_num"], r["mobility_mode"], r["trajectory_direction"])
by_run_num = defaultdict(set)
for r in rows: by_run_num[r["run_num"]].add((r["mobility_mode"], r["trajectory_direction"]))
print("distinct run_num", len(by_run_num), "run_num values reused across mode/direction:", sum(1 for v in by_run_num.values() if len(v) > 1))
runs = defaultdict(list)
for r in rows: runs[key(r)].append(r)
print("runs (run_num, mode, direction):", len(runs), Counter((k[1], k[2]) for k in runs))
tow_missing = sum(1 for r in rows if r["tower_id"] in ("", "nan", "NaN", "None"))
print("tower_id missing rows", tow_missing, "distinct tower_id", len({r["tower_id"] for r in rows}))
lens, gaps, dups = [], 0, 0
for k, rs in runs.items():
    seq = [float(r["seq_num"]) for r in rs]
    lens.append(len(rs))
    gaps += sum(1 for a, b in zip(seq, seq[1:]) if b - a != 1)
    dups += len(seq) - len(set(seq))
print("run length (rows): min", min(lens), "median", st.median(lens), "max", max(lens), "| non-unit seq steps", gaps, "dup seq", dups)
print("nrStatus", Counter(r["nrStatus"] for r in rows).most_common(5))
