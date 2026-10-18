import csv, sys, statistics as st
from collections import defaultdict, Counter
rows = list(csv.DictReader(open(sys.argv[1])))
runs = defaultdict(list)
for r in rows: runs[r["run_num"]].append(r)
chg = Counter(); per_run = []
for rs in runs.values():
    rs.sort(key=lambda r: float(r["seq_num"]))
    per_run.append(len({r["tower_id"] for r in rs}))
    for a, b in zip(rs, rs[1:]):
        if a["tower_id"] != b["tower_id"]:
            chg[(a["nrStatus"] == "CONNECTED", b["nrStatus"] == "CONNECTED")] += 1
print("tower changes by (5G before, 5G after):", dict(chg))
print("distinct towers per run: min", min(per_run), "median", st.median(per_run), "max", max(per_run))
print("tower_id values:", sorted({r["tower_id"] for r in rows}, key=lambda x: float(x))[:30])
