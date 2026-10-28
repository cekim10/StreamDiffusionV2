# E6 record: robustness validation of the M1 mechanism (2026-10-28)

**Sources.**
- Runs: `results/evaluation/expM1E6_*` (pushed cda21c38), at commit 7d5d0ec7.
- Continuity metrics: `e6_metrics_*.json`, computed on host B (merged from f29fd94c).
- Plan: `e6_plan.md`.

**Setup.** Every case uses E5's protocol and settings: host A to host B, 1 Gbps, trigger at call 30, Replay-12, Sink
synchronization on. There is one run per case, so this is a functional validation, not a distribution.

**Validity.** Every run had GPU 0 idle on both hosts at the start, and both hosts ran the same commit.

## 1. Workload generalization

| | train s0 | butterfly s1 (refresh-heavy) | audi s1 | dog s1 (E5) |
|---|---|---|---|---|
| cross-host Sink digest | equal, 0 / 360 blocks | equal | equal | equal |
| fallback | no | no | no | no |
| refresh patches (calls with patches) | 19 (13), 182 MB | 54 (26), 518 MB | 10 (9), 96 MB | 2 (2), 19 MB |
| patch slot check / sent = applied / order | all yes | all yes | all yes | all yes |
| calls replayed (c0 -> M) | 33 (31 -> 64) | 34 (31 -> 65) | 32 (31 -> 63) | 33 |
| replay per call / source call interval | 0.123 / 0.570 s | 0.121 / 0.570 s | 0.120 / 0.568 s | 0.120 / 0.566 s |
| readiness wait (source still serving) / replay wait at the switch | 4.32 s / 0.00002 s | 4.75 s / 0.00002 s | 4.24 s / 0.00002 s | 4.27 s / 0.00002 s |
| user-visible interruption | 1.56 s | 1.57 s | 1.64 s | 1.56 s |
| trigger to the destination's first output | 23.96 s | 24.89 s | 23.29 s | 23.65 s |
| bytes at the switch | 3.2 MB | 3.2 MB | 3.2 MB | 3.2 MB |
| bytes before the switch (Sink base + log incl. patches) | 1.92 GB | 2.26 GB | 1.84 GB | 1.76 GB |
| post-run recent-KV error (K / V) | 0.61 % / 1.59 % | 0.62 % / 1.55 % | 0.59 % / 1.33 % | 0.53 % / 1.18 % |
| P1: V1 at M (REF at that call; REF P99) | pass 1.67 (0.92; 6.49) | pass 0.29 (0.28; 1.25) | pass 2.13 (0.62; 3.22) | pass 1.94 (1.03; 3.91) |
| P2a / P2b | pass / pass | pass / pass | pass / pass | pass / fail |
| E2 oracle at OT-1 (S3 / RS3 / Replay-12: P1 P2a P2b P3) | yyyy / yyyy / yyyy | yyyy / yyyy / yyyy | yyyy / yyyy / yyyy | yyny / yyny / yyny |

- The live P1 / P2 outcomes equal the oracle's on all four units. dog s1's P2b failure is the residual outside the KV
  ring that every oracle condition shows.
- Readiness waits happen while the source keeps serving, so they are not user-visible.
- Shadow-window log rates:

| | log rate | log share of the 1 Gbps link |
|---|---|---|
| butterfly | 15.6 MB per call (about 220 Mbps) | about 22 % |
| train | 5.9 MB per call | |
| audi | 3.4 MB per call | |
| dog | 1.0 MB per call | |

## 2. Real GPU fallback (dog s1; one bit of the destination's shadow Sink flipped before its digest)

| check | result |
|---|---|
| detection | the digest reported exactly the perturbed block, (layer 15, K, row 0, slot 1), and nothing else; verdict SINKNO |
| fallback | the source resent the dirty Sink fragments, 726,992,288 B: the same dirty set as E3 / E4, bytewise |
| fallback Sink | passed its digest |
| state after the bind | the destination's Sink digest equals the source's: it resumed from the exact Sink |
| resume and order | resumed at M = 63; order, patches (2 / 2) and metadata checks all hold |
| continuity | P1 pass (V1 1.55, P99 3.91), P2a pass, P2b fail (as dog s1 everywhere) |
| interruption | 9.31 s: E3's 8.80 s plus the digest and verdict round trip |
| bytes at the switch | 730 MB |

The fallback is correct and costs what E3 costs. It is taken only when the digest disagrees.

## 3. Latency and bandwidth overhead (against E3 replay / M1)

- **Interruption** is 1.56-1.64 s on every workload, against 8.80 s (E3 replay) and 8.05 s (M1). DR-2 (0.52 s) and the
  first destination call (about 0.74 s) are most of it.
- **Bytes at the switch** are 3.2 MB on every workload, against 730 MB.
- **Shadow-window bytes** grow with the refresh rate: 19-518 MB of patches. On butterfly the total transfer is 2.26 GB,
  against E3's 2.47 GB (E3 replay).
- **Source** per-call service is unchanged (0.566-0.570 s). The patch device-to-host copies and the Sink digest take
  0.065 s.
- **Destination** GPU is busy about 21 % of each source call interval during the shadow.

## 4. Limitations that remain before M1 can be called complete

1. **Coverage.**
   - One run per case, one host pair (identical GPUs and software), one bandwidth (1 Gbps), one trigger point.
   - Cross-host bitwise determinism is shown only for A and B. On heterogeneous GPUs the digest would force the
     fallback (about 9.3 s).
2. **Patch traffic is unbounded in the window length.** Patches cost 9.58 MB per refreshed entry and accumulate over
   the shadow. On butterfly that is 518 MB in 34 calls. At lower bandwidth the base takes longer and the window grows,
   so a long window on a refresh-heavy input could send more patch bytes than one Sink resend (1.73 GB). The window is
   bounded only by the readiness rule. This was not optimized, as instructed.
3. **Predicted moves only.** The protocol needs lead time for the base and the catch-up: about 23-25 s at 1 Gbps here.
   An unpredicted move would need the emergency path (Replay-3, not evaluated) or M1's late bind.
4. **Remaining interruption.** DR-2 and the first call are now the floor, about 1.3 s of the 1.56 s.
5. **Recent KV is approximate by design** (0.5-0.6 % K error). Its effect is bounded on these units by P1 / P2 equal to
   the oracle's. dog s1's P2b residual sits outside the KV ring.
6. **The digest is an int64 weighted checksum, not a cryptographic hash.** It is adequate for numerical drift but not
   for adversarial changes.
