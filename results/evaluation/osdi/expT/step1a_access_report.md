# Experiment T, Step 1A: trace access and metadata verification (2026-10-17)

Frozen preregistration: `preregistration.md` v3.1, commit 2a781f8d (unchanged). Nothing was downloaded except public
web pages (index / summary / dataset pages); no trace file, no preprocessing, no experiment. "Documented" = stated on
an official page read on 2026-10-17; "requires inspection" = can only be settled by opening the data.

## MAWI samplepoint-F

| item | finding | source / status |
|---|---|---|
| organization | one trace per day, index per year, entries `YYYYMMDD1400.html` (one 2023 entry `...1359`) with a per-trace summary page | documented: https://mawi.wide.ad.jp/mawi/samplepoint-F/2022/ , `/2023/` |
| pre-July-2023 traces exist and are linked | e.g. `2022/202203151400.pcap.gz`, `2018/201806151400.pcap.gz`, `2023/202306301400.pcap.gz` (summary pages give an http download link on mawi.nezu.wide.ad.jp) | documented |
| gaps | e.g. 2022-11 lists only days 01-04; 2022-12 has no entries for days 01-13 and 22 | documented (index page) |
| format | pcap (tcpdump), gzip-compressed | documented (summary pages) |
| capture window | 14:00:00-14:15:00, TotalTime ~900 s | documented (summary pages) |
| snap length | CapLen 96 bytes (truncated payload) | documented |
| sizes | 2018-06-15: 2286.95 MB gz / 7559.09 MB; 2022-03-15: 2588.65 MB gz / 7508.95 MB; 2023-06-30: 4411.13 MB gz / 10916.01 MB | documented |
| average rate (summary) | 2018-06-15: 816.38 Mbps (stddev 140.96M); 2022-03-15: 676.82 Mbps (stddev 190.13M); 2023-06-30: 1044.50 Mbps (stddev 245.41M) | documented |
| bytes beyond the capture length | 2022-03-15 summary: total bytes 76,140,665,927 vs captured 5,827.71 MB, so per-packet wire lengths are recorded | documented numbers; that each record's original length is usable is **requires inspection** (standard pcap record header) |
| timestamp resolution | not stated; standard pcap is microsecond unless the file uses the nanosecond magic number | **requires inspection** (file header) |
| direction of each packet | not stated; the 96-byte capture includes the Ethernet header, so direction may be derivable from MAC addresses | **requires inspection** |
| link and capacity | FAQ: a 1 Gbps transit link in Tokyo to NTTC GIN (AS2914); since July/August 2023 also the 10 Gbps BBIX link | documented (FAQ, archive page); the summary pages do not describe the link |
| license / use | "You may use WIDE traffic data for only research purposes." "Actions that trespass upon users' privacy are prohibited."; addresses anonymized | documented (archive page, FAQ) |

## Lumos5G 1.0

| item | finding | source / status |
|---|---|---|
| access without interactive authentication | (1) IEEE DataPort https://ieee-dataport.org/node/3598: "Open Access" files "available ... upon login" (a free IEEE account; the page also mentions a subscription) -> **authentication required**. (2) The official project page https://networking.umn.edu/lumos5g links "Download (lumos5G-v1.0) Dataset" to Google Drive file `Lumos5G-v1.0.zip` (id 1spFuxOe5VFyWOHdeJsBeHPHbHiGidw22); the Drive view page loads without an access error, but whether it is public to anyone with the link is **not verified** (no download attempted) | documented / unverified |
| official download instructions (if authentication is required) | DataPort: sign in with a free IEEE account at https://ieee-dataport.org/node/3598 and download `Lumos5G-v1.0.zip` (1.53 MB). Alternative official link: the project page above -> "Download (lumos5G-v1.0) Dataset" (Google Drive). Stopped here for this part | documented |
| license | "Lumos5G 1.0 dataset is licensed under the Creative Commons Attribution 4.0 International License." (DataPort); the project page states no license | documented |
| size and format | `Lumos5G-v1.0.zip`, 1.53 MB, CSV in a zip | documented (DataPort) |
| content | the "Loop" area of the IMC'20 paper: a 1300 m loop near U.S. Bank Stadium, Minneapolis (mmWave 5G) | documented |
| `tower_id` | "Indicates the (anonymized) tower identifier." | documented; per-second availability, missing values, and whether it identifies a tower, a cell or a sector **require inspection** |
| timestamps | no wall-clock column; `seq_num` "acts like an index or a per-second timeline" within a run | documented |
| session / run identifiers | `run_num` "Indicates the run number"; several runs per trajectory and mobility mode; `mobility_mode` (walking / driving); `trajectory_direction` (CW / ACW; driving CW only) | documented; no date or measurement-session field is documented -> whether runs share a session **cannot be determined** from the documentation |
| other fields | `abstractSignalStr`, latitude, longitude, `movingSpeed` (m/s), `compassDirection`, `nrStatus`, LTE and NR signal metrics (some flagged unreliable), `Throughput` (iPerf 3.7, per second) | documented |
| number of runs, duration per run | not stated | **requires inspection** |

## Feasibility issues found (reported per the frozen feasibility rule; no rule changed)

1. **MAWI candidate set is unbounded in the frozen text.** Section 3.2 admits "samplepoint-F traces before 2023-07-01"
   and section 3.3 stratifies by V "over all candidate capacity schedules", without a rule that limits or samples the
   days. The archive runs from 2006-07-01, i.e. several thousand daily traces of 2-4 GB compressed each (multi-terabyte
   in total), all of which would have to be processed to compute V over every candidate. Executing the rule as written
   is impractical; a bounded, seeded set of candidate days would be a change to the selection rule and needs the
   reviewer's decision (dated erratum or amendment), not mine.
2. **The 1 Gbps normalization may not hold.** The summary pages report average rates of 816 Mbps (2018-06-15), 677 Mbps
   (2022-03-15) and 1044.5 Mbps (2023-06-30), with stddev 141-245 Mbps, against a documented 1 Gbps transit link. Either
   the reported rate sums both directions (not documented) or the monitored capacity exceeded 1 Gbps before July 2023.
   If the per-direction utilization is high, u(t) = bytes x 8 / 1 Gbps would often exceed 0.95 and clamp to C_min,
   making residual capacity dominated by the floor; if the capacity changed, the normalization is wrong for those days.
   Per-direction rates require inspecting packet data (direction from MAC addresses, unverified).
3. **Lumos5G structure differs from the text's "run file".** The dataset is one CSV with a `run_num` column, not one
   file per run. The frozen text's "run file" would have to be read as "a `run_num` group" (a clarification for the
   reviewer). No session field is documented, so mobility clusters would fall back to runs (`run_num`), which may share
   a measurement day.
4. **Lumos5G size and diversity.** One 1300 m loop, an unknown number of runs; whether there are enough eligible
   windows (<= 3 sites in 120 s, >= 2 migrations, H = 3 s) and >= 3 mobility clusters per tertile is unknown until the
   data are inspected; mmWave tower changes along a short loop may also concentrate the windows in few runs.
5. **`tower_id` semantics** (tower vs cell vs sector; behaviour when not on 5G) are undocumented beyond
   "anonymized tower identifier".

## Small inspections that would settle the "requires inspection" items (need approval; nothing downloaded)

- Lumos5G: the 1.53 MB zip (Drive link, if public; otherwise the user's DataPort download): read the CSV header, count
  runs, check `tower_id` per second and missing values.
- MAWI: an HTTP range request of the first ~20 MB of one pre-July-2023 `.pcap.gz` (stream-decompressed) to read the pcap
  file header (timestamp resolution) and a few hundred thousand records (original lengths, Ethernet addresses for
  direction, per-direction rates over the first seconds). No full trace.

Sources: https://mawi.wide.ad.jp/mawi/ ; https://mawi.nezu.wide.ad.jp/mawi/faq.html ;
https://mawi.wide.ad.jp/mawi/samplepoint-F/2022/ ; https://mawi.wide.ad.jp/mawi/samplepoint-F/2023/ ;
https://mawi.wide.ad.jp/mawi/samplepoint-F/2022/202203151400.html ; https://mawi.wide.ad.jp/mawi/samplepoint-F/2023/202306301400.html ;
https://mawi.wide.ad.jp/mawi/samplepoint-F/2018/201806151400.html ; https://ieee-dataport.org/node/3598 ;
https://networking.umn.edu/lumos5g ; https://drive.google.com/file/d/1spFuxOe5VFyWOHdeJsBeHPHbHiGidw22/view
