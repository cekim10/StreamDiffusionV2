# Experiment T - Amendment A1 (DRAFT v2, 2026-10-17, not adopted): MAWI date sampling, candidate capacity schedules, Lumos5G run unit

Applies to the frozen preregistration v3.1 (2a781f8d), sections 3.1-3.3. Bounds and defines what the frozen text leaves
open; does not change any hypothesis, threshold, metric, eligibility rule, the residual-capacity formula, the 1 Gbps
normalization or C_min. Dates are chosen without looking at throughput, variability, file size or expected
performance. Written before any MAWI capture was read beyond a 20 MiB format check of 2022-03-15 (which is not part of
the sampling). v1 of this draft (31ea9d8) proposed N = 34 without reuse; superseded by the review (N = 16 with reuse).

## A1.1 Date budget and allocation feasibility check

- One capture covers ~900 s; A1 takes 7 non-overlapping 120 s windows at offsets 0, 120, ..., 720 s from the first
  complete second, in 2 directions: **14 window-directions per date**. A capacity schedule uses 7 window-directions
  from 7 distinct dates (frozen "preferring distinct MAWI days").
- **Provisional budget N = 16 dates** (224 window-directions -> up to 32 candidate schedules). Expected volume
  ~16 x 2.3-4.4 GB = ~35-70 GB compressed.
- **Deterministic feasibility check (after the candidates are built, A1.3):** every V tertile must contain >= 6
  candidate schedules (block P needs 2 pairs per cell x 3 mobility tertiles = 6 per V tertile, each a different
  schedule), the middle tertile must additionally have >= 1 schedule not used by block G's middle-tertile pair (block GC),
  and every V tertile must contain >= 3 schedules for each block-S condition (reuse across blocks allowed, A1.4). If the
  check fails, the next date in the permutation (A1.2) is accepted (subject to the same checks), the candidates are
  rebuilt by the same deterministic procedure, and the check is repeated, up to N = 24. If it still fails, the shortfall
  is reported as a feasibility issue; nothing else changes.

## A1.2 Date selection (seed 20261017)

1. **Population:** every samplepoint-F trace listed on the official yearly index pages
   (`https://mawi.wide.ad.jp/mawi/samplepoint-F/<year>/`) dated 2006-07-01 to 2023-06-30, one entry per date (if a date
   lists more than one capture, the one whose start time is closest to 14:00). Built from the index pages alone and
   committed (date, file name) before any capture is downloaded.
2. **Order:** sort by date; shuffle with Python `random.Random(20261017).shuffle`.
3. **Acceptance in permutation order** until the budget (A1.1) is met. Checks are in three separate classes:
   - **Integrity failures (the date is replaced):** summary page or `.pcap.gz` unreachable after 3 attempts over 24 h;
     gzip decompression error; invalid pcap header or a linktype other than 1 (Ethernet); captured span < 840 s from the
     first complete second.
   - **Direction-mapping failures (the date is replaced):** the capture cannot be split into the two directions of one
     link, defined as: the two Ethernet (source, destination) MAC pairs that carry the most wire bytes are each other's
     reverse, and together carry >= 99.9 % of the capture's wire bytes.
   - **Descriptive anomalies (recorded, never a reason to replace):** backward timestamp steps; captured lengths above
     the header snaplen; frames longer than 1,518 B; frames outside the two pairs (e.g. multicast); per-second gaps;
     clamped seconds (frozen R3).
4. **Replacement rule:** a date with an integrity or direction-mapping failure is replaced by the next date in the same
   permutation; no re-shuffle, no manual choice. All accepted and replaced dates are reported with the failing check.

**Why the direction threshold is 99.9 % of wire bytes** (reconsidering v1's 99 % of packets): what matters for u(t) is
bytes, not packets; bytes outside the two pairs are not attributed to a direction and are excluded, so the threshold
bounds that exclusion. At the summary-page rates (hundreds of Mbps to ~1 Gbps over both directions) 0.1 % is at most
~1-1.5 Mbps on average, small against the 1 Gbps normalization and C_min = 50 Mbps. In the inspected 20 MiB prefix the
two pairs carried every frame except 3 IPv6-multicast frames out of 845,886, so a link in the expected configuration
passes with a wide margin, while a capture carrying a substantial third flow of traffic (another link or a changed
monitoring setup) fails and is replaced rather than mis-attributed. The excluded bytes are reported per date.

## A1.3 Window-directions and candidate schedules

1. Per accepted date: per-second wire bytes per direction (frozen section 3.2: u(t) = bytes x 8 / 1 Gbps; available(t)
   = max(C (1 - u(t)), C_min)); 7 windows x 2 directions. Direction labels: the MAC pair with the lexicographically
   smaller source address is "d0", the other "d1" (labels only).
2. **Candidate schedules ("all candidate capacity schedules" of frozen 3.3):** shuffle all window-directions with
   `random.Random(20261017)`; fill schedules of 7 greedily in that order, deferring a window-direction whose date is
   already in the current schedule to the next schedule that lacks its date; stop when no complete schedule can be
   formed; leftovers are counted and discarded. V and L are computed for every candidate; the V tertiles are taken over
   all of them.
3. **Roles in a schedule:** its 7 window-directions are assigned to (A egress, B egress, B ingress, C egress, C ingress,
   D egress, D ingress) by `random.Random(20261017 + schedule index)`.

## A1.4 Reuse across blocks and independence

- **Permitted:** a candidate schedule (and so its windows) may be used by block P, by block GC and by any block-S
  condition. **Not permitted:** using a schedule twice within one block (each pair of a block has its own schedule).
  Blocks C, NC2, V and G use P's pairs as frozen.
- **Not independent:** a schedule used in two blocks is one capacity observation, not two. Comparisons between a
  sensitivity condition and the primary on shared schedules are paired comparisons and are reported as such; no
  analysis pools P and S runs as independent samples. Within block P, schedules share dates (each date contributes to
  several schedules): in addition to the frozen mobility-cluster aggregation, the report gives the number of distinct
  dates per V tertile and a descriptive leave-one-date-out range of the tertile medians of R_p and dS_p. The frozen
  decision rules are unchanged.

## A1.5 Lumos5G run unit (clarification of frozen 3.1)

The released dataset is one CSV (`Lumos5G-v1.0.csv`) with a `run_num` column (118 distinct values, each with one
mobility mode and direction, contiguous per-second `seq_num`). Wherever the frozen text says "run file", it means **one
`run_num` group** of that CSV; since no session or date field exists, the mobility cluster is the `run_num` group (the
frozen fallback).

## A1.6 What A1 does not change

Hypotheses T1-T3, T5, T6 and thresholds; exploratory section 9; mobility rules and eligibility; the residual-capacity
formula, the 1 Gbps normalization and C_min; validity; analysis. Whether 1 Gbps is the right per-direction
normalization for every sampled date is not settled by A1; clamped seconds are reported per date and direction and, if
they dominate, raised as a feasibility issue.
