# E9 record: first end-to-end M2, Versioned Sink State Reuse, A -> B -> A (2026-10-28)

## Sources

- Runs: `results/evaluation/expM2E9_{baseline,m2}` (pushed 7e63b204), at commit 519df864.
- Continuity: `e9_metrics_*.json`, computed on host B (merged from ca2fc9f4).
- Report: `e9_report.json` (`tools/eval/m2_report.py`).
- Plan: `e9_plan.md`.
- Setup: dog s1, 1 Gbps, Replay-12 with Sink synchronization, switches planned at calls 64 and 164 (both runs switched
  exactly there), second trigger at call 120.
- One run per arm, so this is a functional validation.

## 1. Validity and equivalence

- **Validation flags:** every one holds in both runs. That covers order, metadata, patches and both cutovers digest-equal
  (SINKOK). No readiness timeout, no refused switch, no fallback of any kind.
- **Equivalent source states:** B's outputs over calls 64 .. 163 are identical in the two runs, call for call (100
  calls). The second migration therefore starts from the same B state at the same call in both arms.
- **Identical results:** A's continuity after the second migration is identical between the arms to every printed
  digit (section 4). This is consistent with an exact Sink in both and the same replayed log.

## 2. Second migration (B -> A)

| | baseline: M1 fresh base | M2: delta base from A's retained Sink |
|---|---|---|
| base bytes | 1,727.6 MB | **21.6 MB** (80x less) |
| total bytes of the migration (base + log incl. patches + switch) | 1,756.8 MB | **50.7 MB** (35x less) |
| trigger to base ready on A | 18.30 s | **2.46 s** |
| trigger to replay ready (destination readiness) | 22.17 s (call 154) | **8.74 s** (call 134) |
| user-visible interruption | 1.54 s | 1.41 s |
| switch call | 164 (planned) | 164 (planned) |

**Delta content:**
- 2 refreshed entries, sent as their latest exact K / V (19.2 MB);
- 73 ordered shifts (realignments at 93 / 94);
- the metadata;
- the Sink digest.

No intermediate refresh values were sent. B tracked 59 calls in 0.021 s, 0.35 ms per call.

**Reconstruction on A:**
- the retained Sink host -> GPU in 0.083 s;
- shifts and entries in 0.021 s;
- the digest in 0.063 s;
- 0.34 s from the delta base's arrival to the verdict;
- DELTAOK at the base boundary: 360 / 360 blocks and positions equal to B's Sink.

**Cross-host Sink equality:** at the base (the rebuilt Sink against B's at call ~121) and at the cutover (SINKOK at 164).

**Remaining readiness:** M2's readiness is now bounded by the Replay-12 rule. The replay must apply 12 calls after the
base boundary: 6.3 s of waiting after the base was ready. The 2.46 s to the base includes the provisioning of A, the
wait for the base boundary and the verdict round trip.

## 3. First migration (A -> B) is unaffected

| | baseline | M2 |
|---|---|---|
| switch call | 64 | 64 |
| base / total bytes | 1,727.6 / 1,776.8 MB | 1,727.6 / 1,776.8 MB |
| readiness | 21.49 s | 21.42 s |
| interruption | 1.55 s | 1.54 s |
| continuity (P1 / P2a / P2b) | pass / pass / fail | identical |

Retention on A took 0.99 s after the cutover, while B was already serving, so it is off the critical path.

## 4. Continuity (VD-3 frozen rules, dog_s1 OT-1 thresholds, REF P99 3.91, window [M, M + 24))

| migration | P1: V1 at M (REF at that call) | P2a | P2b | baseline vs M2 |
|---|---|---|---|---|
| 1 (A -> B, call 64) | pass, 1.934 (1.027) | pass | fail (warp excess 0.283, frame-difference ratio 1.105) | identical |
| 2 (B -> A, call 164) | pass, 1.321 (0.827) | pass | pass (0.237, 1.089) | identical |

Notes:
- Migration 1's P2b failure is dog s1's known residual, which sits outside the KV ring.
- Migration 2 is measured on B's actual outputs before 164 and A's from 164.
- Its frames were dumped to call 220, which covers the window.

## 5. Resource overhead

- **Retained Sink:** 1.73 GB of host memory per retaining host. In this run A retained at the first switch and B at the
  second, so 1.73 GB on each.
- **Tracking:** 0.35 ms per call on the owner.
- **Delta-base path:** one host -> GPU copy of the retained Sink (0.08 s).

## 6. Remaining limitations

1. **Coverage.** One workload (2 refreshes in the interval), one interval (100 calls), one host pair, one bandwidth,
   one run per arm. E8 showed the delta grows with distinct refreshed entries (butterfly: 393 MB for 100 calls). That is
   not yet measured end to end.
2. **Fallbacks are not exercised on GPU.** The delta-base fallback (version mismatch or digest mismatch, DELTANO) is
   tested only on dry nodes. The cutover fallback was tested on GPU in E6.
3. **Retention policy is undefined.** It is one version per host, kept until the run ends, at 1.73 GB of host memory
   each. There is no eviction rule and no limit on how many sessions or versions are retained.
4. **Version scope.** Reuse requires the destination to hold exactly the version the source tracks. That is the last
   cutover between them. Paths like A -> B -> C -> A, where the tracked version is not A's, fall back to the full base.
5. **Readiness floor.** About 6 s at 1 Gbps comes from the Replay-12 window, not from the Sink.
6. **Inherited from M1:** predicted moves only, a cross-host determinism assumption guarded by the digests, and the
   interruption floor (DR-2 plus the first call).

## 7. Is M2 ready for broader evaluation?

**Yes.** The end-to-end protocol works on real hosts:
- exact reconstruction with digest verification at the base and the cutover;
- 35x less traffic for the returning migration;
- readiness from 22.2 s to 8.7 s;
- no continuity cost: results identical to the fresh-base baseline;
- the first migration unaffected.

Two things are needed before claims beyond this case:
- the refresh-heavy workload (butterfly) and a longer interval end to end;
- a GPU test of the delta-base fallback.

A retention policy is a design question for the broader M2.
