# Experiment T - Amendment A1 (DRAFT, 2026-10-17, not adopted): MAWI date sampling and candidate capacity schedules

Applies to the frozen preregistration v3.1 (2a781f8d), sections 3.2-3.3, which admit "samplepoint-F traces before
2023-07-01" and stratify V "over all candidate capacity schedules" without bounding the dates or defining the
candidates. A1 bounds and defines them. It does not change any hypothesis, threshold, metric, eligibility rule, the
residual-capacity formula or C_min. Dates are chosen without looking at throughput, variability, size or any expected
performance. Written before any MAWI capture beyond a 20 MiB format check (2022-03-15, not part of the sampling) was
read.

## A1.1 How many dates the frozen design needs

- One capture covers ~900 s. A1 takes **7 non-overlapping 120 s windows** at offsets 0, 120, ..., 720 s from the first
  complete second (840 s), in **2 directions**: 14 window-directions per date.
- A capacity schedule uses 7 window-directions (A egress; B, C, D egress and ingress) and, following "preferring
  distinct MAWI days", A1 requires the 7 to come from **7 distinct dates** (so >= 7 dates are needed in any case).
- Schedules used by the design: block P 18 (C, NC2, V and G use P's pairs), block GC 1, block S 5 conditions x 9 = 45
  (re-derived per condition): **64 schedules if no window-direction is reused anywhere**, i.e. 448 window-directions
  = 32 dates. Stratification needs enough candidates per V tertile for P (6), GC (<= 1) and S (5 x 3 = 15): 22 per
  tertile, >= 66 candidates, **33 dates**.
- **A1 proposes N = 34 dates** (476 window-directions -> 68 candidate schedules, ~22.7 per tertile), so that no
  window-direction is used twice in the whole study. Download volume ~ 34 x 2.3-4.4 GB = ~80-150 GB compressed.
  Smaller alternative for the review: if S and GC may reuse schedules already drawn for P (a different block and
  condition, never within a block), 18 schedules suffice and N = 16 (one per calendar year is then possible), ~35-70 GB.

## A1.2 Date selection (deterministic, seed 20261017)

1. **Population:** every samplepoint-F trace listed on the official yearly index pages
   (`https://mawi.wide.ad.jp/mawi/samplepoint-F/<year>/`) with a date from 2006-07-01 to 2023-06-30, one entry per date
   (if a date lists more than one capture, the entry whose start time is closest to 14:00). The list is built from the
   index pages alone and committed (date, file name) before any capture is downloaded.
2. **Order:** sort the population by date; shuffle it with Python `random.Random(20261017).shuffle`.
3. **Acceptance in permutation order** until N dates are accepted. A date is accepted only if all integrity checks
   pass; none of them looks at throughput, variability or file size:
   - the summary page and the `.pcap.gz` are reachable (HTTP 200, retried 3 times over 24 h);
   - the file decompresses completely without a gzip error;
   - pcap header valid, linktype 1 (Ethernet);
   - captured span >= 840 s from the first complete second;
   - exactly two Ethernet (source, destination) MAC pairs, one per direction, carry >= 99 % of the packets
     (directions identifiable).
4. **Replacement rule:** a date that fails any check is recorded with the failing check and replaced by the next date
   in the same permutation; no other replacement, no re-shuffle, no manual choice. All accepted and rejected dates are
   reported.

## A1.3 Window-directions and candidate schedules

1. Per accepted date: per-second wire bytes per direction (frozen section 3.2: u(t) = bytes x 8 / 1 Gbps;
   available(t) = max(C (1 - u(t)), C_min)); 7 windows x 2 directions. Direction labels: the MAC pair with the
   lexicographically smaller source address is "d0", the other "d1" (labels only; roles are assigned in step 3).
2. **Candidate schedules:** shuffle all window-directions with `random.Random(20261017)`; fill schedules of 7
   greedily in that order, skipping a window-direction whose date is already in the current schedule (it goes to the
   next schedule that lacks its date); stop when no complete schedule can be formed; leftovers are discarded and
   counted. These are "all candidate capacity schedules" of frozen section 3.3; V and L are computed for each and the
   V tertiles are taken over all of them.
3. **Roles inside a schedule:** its 7 window-directions are assigned to (A egress, B egress, B ingress, C egress,
   C ingress, D egress, D ingress) by a seeded shuffle (`random.Random(20261017 + schedule index)`).
4. **Use:** blocks draw schedules by the frozen section 3.3 rules in the order P, GC, S (k = 2, k = 4, H = 0 s,
   H = 10 s, C_min = 10 Mbps); a schedule is used by at most one pair in the study (N = 34). If a stratum runs out, the
   shortfall is reported as a feasibility issue; no reuse without review.

## A1.4 What A1 does not change

Hypotheses T1-T3, T5, T6 and their thresholds; the exploratory section 9; mobility rules and eligibility; the
residual-capacity formula, C = 1 Gbps normalization and C_min; validity; analysis. The open question of whether 1 Gbps
is the right per-direction normalization for every sampled date is not settled by A1: clamped seconds per date and
direction are reported (frozen R3) and, if they dominate, raised as a feasibility issue.

## For the review

1. N = 34 (no window reuse) or N = 16 (schedule reuse across blocks).
2. The integrity checks and the replacement rule.
3. The clarification "run file" = `run_num` group for Lumos5G (from Step 1B), if it is to be recorded with A1.
