"""Apply the frozen Experiment T v3.1 section 3.1 rules (read-only analysis of the trace, no OTTER run)."""
import csv, sys, statistics as st
from collections import defaultdict
W = 120
rows = list(csv.DictReader(open(sys.argv[1])))
runs = defaultdict(list)
for r in rows:
    runs[r["run_num"]].append(r)
meta = {k: (v[0]["mobility_mode"], v[0]["trajectory_direction"]) for k, v in runs.items()}

def sites_of(rs, k):
    rank, out = {}, []
    for r in sorted(rs, key=lambda r: float(r["seq_num"])):
        t = r["tower_id"]
        if t not in rank:
            rank[t] = len(rank)
        out.append(rank[t] // k)
    return out

def windows(site, H):
    n, res = len(site), []
    for w in range(0, n - W):
        if any(site[w + j] != site[w] for j in range(H + 1)) or w + H >= n:
            continue   # the window starts where the site is stable for H seconds
        cur, moves, visited = site[w], [w], [site[w]]
        t = w + 1
        while t < w + W:
            if site[t] != cur and site[t] != site[t - 1] or (site[t] != cur and H == 0):
                s = site[t]
                if t + H < n and all(site[t + j] == s for j in range(H + 1)) and t + H <= w + W:
                    moves.append(t + H); cur = s; visited.append(s)
                    t = t + H + 1; continue
            t += 1
        n_sites = len(set(visited)); n_mig = len(moves) - 1
        gaps = [b - a for a, b in zip(moves, moves[1:])]
        res.append({"w": w, "sites": n_sites, "mig": n_mig, "eligible": n_sites <= 3 and n_mig >= 2,
                    "med_inter": st.median(gaps) if gaps else None, "revisit": len(visited) > n_sites})
    return res

for k, H in [(1, 3), (2, 3), (4, 3), (1, 0), (1, 10)]:
    allw, el, el_runs, nonover, el_mode = 0, 0, set(), 0, defaultdict(int)
    med, revis, migr_all = [], 0, []
    for rn, rs in runs.items():
        ws = windows(sites_of(rs, k), H)
        allw += len(ws)
        last_end = -1
        for x in ws:
            migr_all.append(x["mig"])
            if x["eligible"]:
                el += 1; el_runs.add(rn); el_mode[meta[rn][0]] += 1; med.append(x["med_inter"]); revis += x["revisit"]
                if x["w"] > last_end:
                    nonover += 1; last_end = x["w"] + W - 1
    over3 = sum(1 for rn, rs in runs.items() for x in windows(sites_of(rs, k), H) if x["sites"] > 3)
    q = st.quantiles(med, n=3) if len(med) >= 3 else None
    print(f"k={k} H={H}: candidate windows {allw}, eligible {el} ({100*el/max(1,allw):.1f} %), non-overlapping eligible {nonover}, "
          f"runs with an eligible window {len(el_runs)} of {len(runs)} (driving {sum(1 for r in el_runs if meta[r][0]=='driving')}), "
          f"windows with >3 sites {over3}, eligible with a revisit {revis}, median inter-migration of eligible windows "
          f"{st.median(med) if med else None} s, tertile cuts {q}, migrations/window median (all) {st.median(migr_all)}")
