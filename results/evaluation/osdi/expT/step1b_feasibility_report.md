# Experiment T, Step 1B: feasibility inspection (2026-10-17)

Frozen preregistration v3.1 (2a781f8d), Experiment D and M3: unchanged. No OTTER run, no harness or preprocessing
code, no full MAWI download. Downloads: the public Lumos5G archive (1.53 MB) and the first 20 MiB of one MAWI capture
(HTTP range request), both kept outside the repository (scratch space) and read with isolated scripts
(`step1b_inspection_scripts/`). Nothing in the downloaded files was treated as instructions.

## B. Lumos5G 1.0 (inspected)

- **Access:** the official project page's Google Drive link returned the archive without authentication (HTTP 200,
  1,604,062 B = 1.53 MiB, SHA-256 1ea8770b3090735f987d4ef7b248188de7c667bf6be5716e4891daf9e8d331e8). The archive holds
  `LICENSE` ("licensed under the Creative Commons Attribution 4.0 International License"), `README.md` (column
  descriptions as on IEEE DataPort) and one CSV (`Lumos5G-v1.0.csv`, 8,480,348 B, 68,118 rows, 19 columns).
- **Schema (verified in the file):** `run_num, seq_num, abstractSignalStr, latitude, longitude, movingSpeed,
  compassDirection, nrStatus, lte_rssi, lte_rsrp, lte_rsrq, lte_rssnr, nr_ssRsrp, nr_ssRsrq, nr_ssSinr, Throughput,
  mobility_mode, trajectory_direction, tower_id`.
- **Runs:** 118 distinct `run_num` values, each with one mobility mode and direction (driving CW 46, walking ACW 38,
  walking CW 34); `seq_num` is contiguous in every run (no gap, no duplicate); run length 181-800 s, median 785.5 s.
- **`tower_id`:** 24 distinct values (1-24), no missing value; 2-15 distinct towers per run (median 9).
  **Semantics risk confirmed:** of 1,298 `tower_id` changes, none occurs while the UE stays 5G-connected
  (CONNECTED -> CONNECTED: 0); 842 occur as the UE leaves 5G and 454 while it is not on 5G. The identifier therefore
  does not record handovers between 5G cells, and "tower handover" in this trace means a change of the reported tower
  around and outside 5G coverage. This is a data property, recorded here; the frozen rule (a handover = a change of
  `tower_id`) is not changed.
- **Clusters:** no session or date field exists; per the frozen fallback, a mobility cluster is a run (`run_num`).
  Reading the frozen "run file" as "a `run_num` group" is a clarification for the reviewer (the dataset has one CSV).
- **Eligibility under the frozen rules** (section 3.1: rank by first appearance per run, site = floor(rank / k),
  migration at t + H after an H-second dwell, never backdated; 120 s windows starting where the site is stable for H s;
  eligible = <= 3 distinct sites and >= 2 migrations after the first move):

| (k, H) | candidate windows | eligible | non-overlapping eligible | runs (clusters) with an eligible window | windows excluded for > 3 sites | median inter-migration in eligible windows | mobility tertile cuts |
|---|---|---|---|---|---|---|---|
| (1, 3 s) primary | 51,092 | 11,027 (21.6 %) | 226 | 85 of 118 (23 driving) | 9,792 | 40.0 s | 33.5 / 46.0 s |
| (2, 3 s) | 52,301 | 10,273 (19.6 %) | 173 | 83 | 3,235 | 39 s | 31 / 46 s |
| (4, 3 s) | 53,076 | 8,031 (15.1 %) | 114 | 67 | 154 | 37 s | 29 / 45 s |
| (1, 0 s) | 53,958 | 11,245 (20.8 %) | 236 | 88 | 14,196 | 35.5 s | 25 / 43 s |
| (1, 10 s) | 45,791 | 9,263 (20.2 %) | 203 | 81 | 4,270 | 46 s | 41.5 / 50 s |

  The selection needs 18 primary windows (2 per cell, at most one per run per cell), 6 for NC1, 3 more per high-V pair
  for block C, 9 per sensitivity condition, and >= 3 clusters per tertile: all within these counts. The other windows are
  excluded either for > 3 sites (selection effect towards less dispersed mobility, as preregistered) or for < 2
  migrations (the median candidate window has 1 migration).
- **Observation relevant to interpretation (no rule changed):** eligible windows move every ~33-46 s (median 40 s),
  while a Sink takes ~14 s to restore at 1 Gbps (T_s = 14.05 s), i.e. rho = T_s / T_m ~ 0.3-0.4: restorations usually
  finish before the next migration unless residual capacity is low. Effects that need rho >= 1 (Experiment D's repeated
  scenarios) will arise only through capacity variability.

## C. MAWI samplepoint-F (first 20 MiB of 2022-03-15 14:00, inspected)

- **Range requests:** supported (`Accept-Ranges: bytes`; full file 2,714,401,242 B); HTTP 206 with exactly 20,971,520 B
  (SHA-256 fd6870d8f2c7573ccc47301e669d5a7af2c0f62af862a66d9b44da5498ea471e). The compressed prefix decompressed to
  60.8 MB; only the 845,886 complete records (6.99 s) were used.
- **Format:** classic pcap, little-endian magic d4c3b2a1, version 2.4 -> **microsecond timestamps**; linktype 1
  (Ethernet); header snaplen 96 (one record had a larger captured length, 526 B).
- **Lengths:** every record carries the original (wire) length: captured length median 54 B, original length median
  335 B, maximum 8,754 B; 1.16 % of records exceed a standard 1,518 B Ethernet frame (jumbo frames or capture offload;
  the wire-length sum per second is unaffected, per-packet counts would be).
- **Ordering:** 304 backward timestamp steps (0.04 %), the largest 6 microseconds, none across a 1 s boundary: per-second
  binning is unaffected.
- **Direction:** **identifiable.** Two Ethernet (source, destination) MAC pairs carry 100 % of the packets apart from 3
  IPv6-multicast frames (one pair in each direction of a router-to-router link). EtherTypes: IPv4 95.7 %, IPv6 4.3 %.
- **Per-direction wire rates in the first decoded seconds** (descriptive only): 337-638 Mbps in one direction and
  184-295 Mbps in the other. No link capacity is inferred from these numbers; they only show that per-direction series
  can be computed. (They are consistent with the summary page's 676.82 Mbps being a sum over both directions, which the
  page does not state; this remains unverified.)
- **Sizes for planning:** pre-July-2023 compressed captures read so far are 2.3-4.4 GB each.

## Feasibility status

| item | status |
|---|---|
| Lumos5G access, schema, runs, tower IDs, missing values | resolved (public; clean; documented above) |
| eligible windows and clusters under frozen rules | sufficient for every block (primary 226 non-overlapping windows, 85 clusters) |
| `tower_id` meaning | **open risk, confirmed**: changes only outside / at loss of 5G |
| "run file" vs `run_num` group; clusters = runs | clarification needed (reviewer) |
| MAWI timestamp resolution, wire lengths, direction | resolved (microsecond; wire length per record; two MAC pairs) |
| MAWI 1 Gbps normalization | unresolved by design; per-direction series are computable; clamping frequency will be measured after download |
| MAWI candidate dates (frozen text unbounded) | Amendment A1 draft (`amendment_A1_draft.md`) |
