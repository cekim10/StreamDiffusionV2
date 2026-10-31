# Fig. 9 preregistration: why live replay (M1) (RQ3)

**Status: FROZEN (2026-10-31), before any Fig. 9 run and before the 9a re-analysis of the Fig. 7 runs.** DRAFT 1 was
7dcb39e2. Decisions D1-D6 by the user (2026-10-31), section 10. Plan: `osdi/eval_plan/plan.md` (Fig. 9, RQ3, P1).
Labels: [V] verified in code or earlier records, [H] hypothesis / expectation, [R] recommendation.

**Framing (user).** Fig. 9 is a **design breakdown (mechanism analysis) of M1**, not a strict single-component ablation
ladder: the steps differ in more than one component (section 3). Text and caption say "design breakdown".

Roles: Fig. 7 = OTTER vs external baselines (end to end); Fig. 8 = continuity and native performance; **Fig. 9 = why
M1 works: what conventional pre-copy cannot do, and what each part of M1 contributes**; Fig. 10 = M2; Fig. 11 = M3.

## 1. Questions and messages

RQ3: how does replay-based live migration overcome the limits of conventional state transfer?

- **9a, convergence.** Does iterative pre-copy converge? Message to test: pre-copy of the whole state does not converge
  (the recent state changes every call), while pre-copy of the Sink alone does, because the Sink changes rarely.
- **9b, the M1 ladder.** Starting from "wait for the Sink", add one M1 part at a time. Message to test: each part
  removes a specific cost (the Sink-transfer stall, the stop-and-copy of the dirty Sink, the loss of the recent state),
  and only full M1 has both a short gap and a rebuilt recent state.

Out of scope: M2 / M3 (one migration only, as Fig. 7); bandwidth (Fig. 12); quality beyond the switch window (Fig. 13).

## 2. Facts this protocol rests on

| fact | source | tag |
|---|---|---|
| State composition: Sink 1.73 GB (180 entries, 360 blocks), full state 6.46 GB (6.02 GiB), the rest (recent KV, VAE caches, in-flight rows) changes every call. | Fig. 7 bytes; state ablation | [V] |
| Pre-copy loop (`_precopy`): each round snapshots the scope (`full` = all components, `sink` = the Sink only) at a chunk boundary on the source and sends the 4 MiB fragments whose SHA-256 changed; per round `xb_precopy_round` records `dirty_bytes`, `snapshot_s`, `send_s`. Stop at `threshold`, `round_limit` or `no_shrink` (< 10 % shrink). | `mobility_node.py` `_precopy` | [V] code |
| Per-round `dirty_bytes` is a total over components; the split of a P-full round into Sink / other is not logged. | same | [V] code |
| **P-sink** (`precopy_sink`): Sink pre-copy while A serves; at the switch A stops and sends the dirty Sink plus in-flight rows and metadata; B restores metadata and in-flight rows, **the recent KV and VAE caches start at zero** (`restore_fast`), binds the Sink and resumes. | `_precopy`, `_xb_switch`, `restore_fast` | [V] code |
| **Wait-for-Sink** (`split_wait`): the older M1-fast path. A stops at the trigger and hands over in-flight rows and metadata; B generates nothing until the whole Sink has arrived and is bound (recent state starts at zero). It is not in the pre-copy family and does not use the input log. | `mobility_orchestrate.py` POLICY_LABEL, node `wait_sink`; `test_xb` check "no Sink-less generation at B" | [V] code |
| **OTTER without Sink sync** (`precopy_replay` without `--replay_sink_sync`, = M1 E3): Sink base + per-call input log, shadow replay at B; at the switch A resends the dirty Sink. | `_precopy` (`final_comps`) | [V] code |
| **OTTER** (Fig. 7 flags): as above plus refresh patches in the log and a Sink digest at the switch (SINKOK, no resend; SINKNO -> resend). | same; E5 / E6 | [V] |
| OTTER records the replay and verification costs per run: `replay_caught_up` (`replay_s_median`, `replay_s_total`, `n_applied`, patches applied), `sink_sync_check` (`ck_s`, mismatching blocks), `resume` (`restore_s`, `dr2_s`), `xb_precopy_switch` (`ready_wait_s`, `sink_ck_s`, `verdict_wait_s`, `log_bytes`, `patch_bytes`, `final_bytes`, `stop_to_sent_s`). | Fig. 7 run events | [V] |
| Fig. 7 runs (commit 00f2dd92): harness changes since then are the Fig. 8 per-call `track_ms` timing column only (6badbbea). | git log | [V] |

**Numbers seen before this draft (disclosed; rules using them are not blind).**
- Fig. 7 / 8a: P-full dirty rounds 4.5-5.7 GB (Fig. 7 report), 10 stalls per P-full run (8a); OTTER gap 1.63 / 1.59 s,
  TTFO-local 23.3 / 24.6 s, bytes 1.76 / 2.24 GB.
- One Fig. 7 OTTER run (dog rep 2), read to find the event names: 32 calls replayed at 0.12 s each (3.9 s total), 2
  patches (19.2 MB), Sink check 0.06 s, verdict wait 0.18 s, DR-2 0.52 s, 3.2 MB at the switch.
- Older commits, other settings (XB1, 3 reps; M1 E3-E6, single runs): Wait-for-Sink gap = TTFO-local 15.0 s, 1.73 GB,
  terminal PSNR 47.3 dog / 36.2 bfly; P-sink `thr=16:rl=1` gap 8.1 / 9.6 s, TTFO-local 25.1 / 26.5 s, terminal 49.4 /
  34.0 dB; XB calibration P-sink `thr=256:rl=6` TTFO-local 28.7 s, gap 2.2 s (dog), ALT runs reached the threshold
  (dog and bfly); E3 OTTER without Sink sync 8.80 s (final dirty Sink 730 MB), with Sink sync (E5 / E6) 1.56-1.64 s.

## 3. Conditions (one harness, Fig. 7 setting: A -> B at call 30, 1 Gbps, `--hops 1 --tm 1e9`, Fig. 7 horizon)

| step | label | policy / flags | Sink | recent state at B | new runs |
|---|---|---|---|---|---|
| 0 | Wait-for-Sink | `split_wait` | sent after the stop, exact at bind | zero, refills | 10 |
| 1 | P-sink | `precopy_sink@thr=256:rl=10` (D1) | pre-copied while A serves; dirty rest at the stop | zero, refills | 10 |
| 2 | OTTER w/o Sink sync | `precopy_replay@thr=16:rl=1`, `--replay_window 12 --replay_lag 1` | base + resend of the dirty Sink at the stop | rebuilt by replay | 10 |
| 3 | OTTER | Fig. 7 OTTER flags | base + patches; digest at the stop | rebuilt by replay | 0 (Fig. 7 runs, D4) |
| ref. | P-full | Fig. 7 `precopy_full@thr=256:rl=10` | whole state pre-copied | exact | 0 (Fig. 7 runs; 9a only) |

Workloads dog (Low-refresh) and butterfly (High-refresh), seed 0; 5 valid reps per cell; reps interleaved across
steps 0-2. New runs: 30 (estimate [H] ~17 min each from Fig. 8: ~9 h).

## 4. Panel 9a: dirty state per pre-copy round (P-full: re-analysis; P-sink: new runs)

Per run: the sequence of `dirty_bytes` of every pre-copy round, then the stop-and-copy bytes at the switch, in GB and as
a fraction of the scope's size (= round 1, which sends every fragment of the scope); the switch reason. OTTER is not
drawn in 9a (one base round only). The logic carried to 9b: Sink-only pre-copy converging does not complete a migration,
because the recent state is not transferred.

**F9-H1 (Sink-only pre-copy converges).** P-sink stops by the threshold (`reason = threshold`) in >= 4 / 5 runs of each
workload. Predictions [H] (not blind, section 2): P-sink yes on both; P-full stops by `no_shrink` / `round_limit`
with every round >= 50 % of the full state (descriptive, already seen).

## 5. Panel 9b: the M1 ladder (delivery gap, readiness, fidelity at the switch, cost)

Metrics per run (Fig. 7 definitions): **delivery gap** (longest delivery interval after the trigger), **TTFO-local**
(trigger -> first output generated at B), total stall (Fig. 8 rule: intervals > 1.5 x T_ref), transferred bytes,
**fidelity at the switch** (PSNR vs the uninterrupted reference over B's first 24 calls: median and min; terminal),
and for OTTER steps the cost breakdown of section 2 (replay, patches, verification, DR-2, wait).

**F9-H2 (gap ladder).** median gap(OTTER) < median gap of each of Wait-for-Sink, P-sink, OTTER w/o Sink sync, both
workloads. Predictions [H]: Wait-for-Sink ~15 s, OTTER w/o sync ~8-9 s, P-sink ~2-3 s, OTTER ~1.6 s.

**F9-H3 (recent state matters at the switch).** median over runs of the median PSNR of B's first 24 calls:
OTTER >= P-sink and OTTER >= Wait-for-Sink, both workloads. Prediction [H]: holds (zeroed recent state); not
measured under the current commit. Not guaranteed: OTTER's replayed recent state is not bit-exact with the
uninterrupted reference, and the adaptive Sink refresh can change the later trajectory (Fig. 7 butterfly analysis). If
H3 fails, the result is reported as is, nothing is changed, and it is carried into Fig. 13.

**Descriptive.** TTFO-local per step (Wait-for-Sink is expected to reach local service earlier than OTTER, [H] ~15 vs
~23 s; reported as is); bytes; total stall; OTTER cost breakdown; P-full and Full from Fig. 7 as references.

## 6. Statistics

Per cell: median and IQR over valid reps (5 required, else NOT EVALUABLE). Every rep shown.

## 7. Validity and state correctness (C1, as each method claims it)

- All runs: the validity the XB aggregation applied to each policy (`aggregate_xb.run_record`): `run_validity_xb` for the
  pre-copy family, the W / R / N validity (`run_validity_wrn`) for Wait-for-Sink; one commit on A-D, GPU 0 idle before
  the set.
- Wait-for-Sink: Sink digest at bind equals the source's; no B generation before the bind.
- P-sink: the switchover's component digests (Sink, in-flight, metadata) verified.
- OTTER w/o Sink sync: base verified, replay order / no lost or duplicated calls, switchover components verified.
- OTTER: the Fig. 7 C1 (SINKOK or verified fallback, 0 / 360 Sink blocks mismatching, ...).
- A failing run is excluded and listed with its reason; no rerun unless a harness defect is found (Fig. 7 precedent).

## 8. Procedure and tools

Tools: `tools/eval/run_fig9.sh preflight | first | rest | dry`, `tools/eval/fig9_report.py` (9a, 9b, C1 per step, OTTER
cost; `--sanity`), `tools/eval/plot_fig9.py`. No harness code changed for Fig. 9.

1. Regression and dry run, then this freeze is committed with the tools. Done: `test_xb` ALL PASS (87), `test_m1_live` ALL
   PASS (sequentially); `run_fig9.sh dry` rc 0: on both workloads each new step completes and is valid with every C1
   check passing (Wait-for-Sink: no generation before the bind; P-sink: switch reason threshold; OTTER w/o Sink sync:
   Sink resent and verified); the report reads the Fig. 7 dry OTTER / P-full runs; verdicts NOT EVALUABLE (1 rep).
2. elves-01: `d0_remote.py pull` on all hosts, `run_fig9.sh preflight`.
3. `run_fig9.sh first` (dog P-sink rep 1) + `fig9_report.py --sanity`; counted if it meets section 7.
4. `run_fig9.sh rest` (29 runs; reps interleaved across steps and workloads).
5. `fig9_report.py` (the rules as written), `plot_fig9.py`.

## 9. Plot specification (user: three subfigures)

Style: Fig. 7 (EC-LLM e3; OTTER blue, the other steps gray; Low-refresh solid, High-refresh hatched).
- **(a) Dirty state per pre-copy round** (one panel per workload; dog in the body, butterfly may go to the appendix):
  x = pre-copy round, y = dirty bytes (GB, log, limits cover every point); P-full and P-sink, the run with the median
  number of rounds thick, the other reps thin; the stop-and-copy as an open marker after the last round; 256 MiB dashed.
- **(b) Maximum output gap** per step (4 steps x 2 workloads): bar = median, whisker = IQR, dots = reps, value printed;
  y log unless the medians span < 1 decade (the Fig. 7 rule).
- **(c) Post-migration PSNR**: the per-run median PSNR of B's first 24 calls, same layout, linear.
- TTFO-local, bytes and the OTTER cost breakdown are given as numbers in the text (D6), not as figures.

## 10. Decisions (user, 2026-10-31)

| | decision | reason (user) |
|---|---|---|
| D1 | P-sink `thr=256:rl=10` | Sink-only convergence under the same rule as P-full |
| D2 | Wait-for-Sink included (`split_wait`, older M1-fast path, disclosed) | the effect of overlapping transfer with generation |
| D3 | OTTER w/o Sink sync included | the contribution of the Sink synchronization |
| D4 | the 10 Fig. 7 OTTER runs reused | same setting; no needless reruns |
| D5 | F9-H1-H3 kept | each mechanism's effect tested |
| D6 | cost breakdown as a table in the text | the figure stays on the main results |

E3 (8.80 s) and E5 / E6 (1.56-1.64 s) are earlier settings: never quoted as Fig. 9 results.

## 11. What Fig. 9 must not claim

- That P-sink or Wait-for-Sink are external systems: they are internal ablations in OTTER's harness.
- "Equivalent correctness" across steps: the recent state differs by step (zero vs replayed); only the Sink is exact.
- That OTTER has the shortest TTFO-local among all methods (Wait-for-Sink is expected to be shorter).
- Convergence beyond 1 Gbps, two workloads and one migration.
- A strict one-component-per-step ablation (it is a design breakdown).
- That OTTER's recent state is exact (it is replayed, not bit-exact; H3 is reported whatever its outcome).
