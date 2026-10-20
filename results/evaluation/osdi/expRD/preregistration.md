# Experiment RD - visual recovery diagnosis: preregistration (2026-10-20)

Status: **FROZEN** (freeze record `../expRD_freeze.md`). Draft 4c5aa5e revised before the freeze with the user's
decisions D1-D5 (section 11) and six clarifications (r3e interpretation, withheld-Sink preservation in r3c, meaning of
d = 0, Phase 1 run count 100, unchanged hypotheses / thresholds / rules, Phase 0 gate 5 / 5). Nothing implemented or run
at the freeze. Frozen results (ExpD, W / R / N, V, A, B, VACW) are used only as prior evidence and as fidelity targets;
none is modified.

## 1. Question

After a migration, OTTER resumes generation without the attention Sink and binds the Sink later. After one move at
1 Gbps the stream crosses back to the uninterrupted reference in 39 / 40 inputs (sustained in 31 / 40; W2); after three
moves butterfly-feeding-slow-motion never crosses back under any policy (0 / 18; VACW). **Is failure to recover the
reference trajectory primarily associated with (1) the duration of Sink-less generation, (2) repeated resets of the
recent KV / VAE state, or (3) their interaction?**

Facts that make the question non-trivial (prior evidence, not data of this experiment):
- butterfly s0: W2 one move, trigger call 34, bind call 58 (24 Sink-less calls): crosses 35 dB, never sustains;
  Experiment A native, bind ~4 calls after the trigger: sustains; VACW rho 1, resets at calls 30 / 54 / 77, bind 101
  (71 Sink-less calls, 3 resets): never crosses; VACW rho 0.5, resets 30 / 77 / 123, binds 54 / 100-103 / 147-150
  (three episodes of ~24 Sink-less calls separated by ~23 bound calls): never crosses, with a stale or a fresh Sink.
- dog s0 crosses in every one of these schedules.

So both a contiguous long Sink-less window and repeated short episodes are associated with failure on butterfly; the
two real schedules differ in duration, structure and Sink version at once. RD separates them on one GPU.

## 2. Method: single-GPU in-place M1 emulation

One process, one L40S, the real StreamDiffusionV2 runtime of `tools/eval/mobility_node.py` (`GpuRuntime`). An
**M1 reset at call t** executes, in-process and through the same functions a real destination uses, the sequence of a
move whose destination has no Sink:
1. stop at the chunk boundary before call t; `serialize_live()` (the leaving owner's serialization);
2. pack `inflight` and `meta` with `pack_component` (same bytes as the fast path; no network);
3. release the session and `provision()` a fresh destination session on the same GPU (fresh KV ring with zeroed sink
   and recent regions, fresh VAE caches: the real destination's "reconstruction");
4. `unpack` the packed fast-path components and `restore_fast()` (restores meta and in-flight rows; refresh frozen,
   `adapt_sink_thr = -1`);
5. generate from call t on.

A **bind at call b** unpacks the packed Sink component of the chosen snapshot and calls `bind()` (`bind_sink_into_live`,
RoPE re-rotation to the live positions, refresh re-enabled), exactly as `_become_owner` / `_generate` do.

The Sink snapshot rebound at b is, by default, the **withheld Sink**: the Sink packed at the reset that opened the
current Sink-less episode (the session's own Sink at that moment). For a contiguous window this is also the trigger
snapshot, so freshness does not vary within Phase 1. **Within one Sink-less episode the withheld Sink is packed once,
at the episode's first reset, and kept as host bytes until its bind; a later reset inside the same episode (r3c) never
packs a Sink from the intermediate Sink-less session** (whose Sink region is zero), exactly as in VACW rho 1, where
the Sink restored at D is the one packed at the trigger. The runner asserts this (the bound payload's SHA-256 equals the
one packed at the episode's first reset). (Phase 0 additionally replays the stale variant: the trigger snapshot rebound
in every episode, as frozen `split` does at rho 0.5.)

What the emulation removes: network transfer and its timing jitter (calls of reset and bind are exact), separate
processes and hosts, concurrent transfer threads, the warm-destination provisioning before the trigger (here done at
the reset; not timed). What it keeps: every byte and every function of the M1 state path. Its fidelity is tested
against real runs before it is used (Phase 0) and after (Phase 2); it is not assumed.

## 3. Factors and exact schedules

Notation: d = total Sink-less calls before the final bind b; resets R = {t_1, ...}; binds B = {..., b}.

### 3.1 Sink-less duration d
{0, 10, 25, 50, 75, 100} calls under r1 (d = 10 added by D1); {25, 50, 75, 100} under r3c; {0, 75} under r3e.
**d = 0 is "immediate Sink bind after an M1 reset"**: the Sink is rebound at the reset call itself (the real case of a
Sink already verified at the destination when execution arrives), while the recent KV and VAE state are reset. It is
not uninterrupted execution and is never described as such; the uninterrupted run is the PSNR reference.

### 3.2 Reset structure (the reset count never changes d)

| structure | resets | Sink-less calls | binds | real analogue |
|---|---|---|---|---|
| **r1** (one reset) | t_1 = b - d | [b - d, b) | b | one move (W2, A) |
| **r3c** (three resets, contiguous) | b - d, b - d + round(d / 3), b - d + round(2d / 3) | [b - d, b) | b | three moves before any bind (VACW rho 1: 30 / 54 / 77, bind 101) |
| **r3e** (three resets, episodic; see D2) | t_1 = b - d - 2g, t_1 + d/3 + g, t_1 + 2d/3 + 2g | three episodes of d / 3 calls | t_1 + d/3, t_1 + 2d/3 + g, b | three moves, each owner binds then generates g calls (VACW rho 0.5) |

g = 25 bound calls between episodes (VACW rho 0.5: 23-24). r3c resets are equally spaced, mirroring equal T_m.
r3c is defined for d >= 25 only; r3e for d in {0, 75} only (d = 0: three resets with the Sink rebound at each reset;
d = 75: three 25-call episodes).

**What each comparison isolates.** r1 vs r3c at the same d and anchor changes only the number of resets inside one
Sink-less window (same d, same final bind call, same withheld Sink): this is the reset-count contrast used by the
hypotheses. **r3e vs r3c does not isolate the reset count**: r3e also rebinds the Sink between episodes, generates g
bound calls twice (with its own refreshes and promotions), rebinds a fresher Sink in later episodes, and spans
d + 2g calls. r3e is therefore a **descriptive episodic comparison** (it reproduces the structure of the VACW rho 0.5
failure) and never enters the D / R / I / E rules.

### 3.3 Bind anchors (absolute call of the final bind)

| anchor | b | realign phase (uninterrupted, Task B: 138/139, 183/184) | loop phase: butterfly (period 8, cuts 6 + 8k) / train (16.25) / audi (32, cuts 30 + 32k) |
|---|---|---|---|
| **b1** | 155 | 16 calls after a realign | 5 after cut 150 / 10 after cut 145 / 3 before cut 158 |
| **b2** | 175 | 8 calls before a realign | 1 after cut 174 / 2 before cut 177 / 17 after cut 158 |

Every d (and both r3 structures) is run at both anchors, so a duration contrast never relies on one absolute position.
Earliest reset: b1 r1/r3c d = 100 at call 55; r3e d = 75 at call 30 (b1) / 50 (b2). All resets are at or after call 30
(the trigger of ExpD / VACW). b1 r3e d = 75 reproduces the VACW rho 0.5 schedule within 3 calls (resets 30 / 80 / 130,
binds 55 / 105 / 155).

### 3.4 Horizon
H = 100 calls after b (to call 254 / 274); the uninterrupted reference covers 330 calls (W1 baseline length).

## 4. Workloads

| workload | role | prior evidence | figures |
|---|---|---|---|
| butterfly-feeding-slow-motion s0 | primary (refresh-heavy, 32-frame LOVEU) | W2 crosses / not sustained; VACW 0 / 18 | LOVEU: no frames in publication figures |
| audi-snow-trail s0 | refresh-heavy (most refresh-active clip, 128-frame LOVEU) | W2 crosses at +40 calls, not sustained | LOVEU: no frames |
| train s0 | refresh-heavy repository clip (D3) | W2 crosses, never sustains | repo clip: figures allowed |
| dog s0 | control (refresh-light) | crosses and sustains in W2, A, VACW | repo clip |

Seed 0 only (seed 1 would double the cost; see D5).

## 5. Outcomes (three separate levels; never merged)

### 5.1 Reference-trajectory recovery (PSNR against the uninterrupted run of the same seed, per call)
- **Primary: terminal PSNR T** = median PSNR over calls b + 90 .. b + 99.
- single crossing: some call in [b, b + 99] >= 35 dB; latency in calls after b;
- sustained recovery: 10 consecutive calls >= 35 dB within [b, b + 99];
- gap PSNR (median over the Sink-less calls), reported.

### 5.2 No-reference temporal consistency (secondary, descriptive; never decides a hypothesis)
Computed on the decoded output frames O, the reference output frames R and the input frames I at the same frame
indices, over three windows (Sink-less window, first 20 calls after b, last 10 calls of H):
- **input-motion-conditioned warp error**: dense flow F_t from I_t to I_{t+1} (OpenCV Farneback, fixed parameters
  pyr_scale 0.5, levels 3, winsize 15, iterations 3, poly_n 5, poly_sigma 1.2, on 1/4-resolution grayscale; D4);
  E_X = mean over pixels whose warped position lies inside the frame of |X_t - X_{t+1} warped back to t along F_t|
  (`cv2.remap`, bilinear), for X in {O, R}; report **E_O / E_R** (the migrated stream against the uninterrupted one
  under the input's own motion);
- **motion magnitude ratio**: mean |O_{t+1} - O_t| / mean |R_{t+1} - R_t| (detects a static or frozen output);
- **event spikes**: frame difference at each reset and bind transition divided by the median of the 8 preceding
  transitions.
Interpretation fixed now: E_O / E_R in [0.8, 1.25] = "comparable to the uninterrupted stream"; > 1.25 = "less
consistent with the input's motion"; < 0.8 = "smoother than the uninterrupted stream", **flagged for visual inspection,
not read as better continuity** (static, over-smoothed or frozen output also lowers warp error); a motion ratio < 0.5
marks the window as possibly static. No perceptual-continuity statement follows from these metrics alone; visual
examples (repo clips only in figures) accompany any statement.

### 5.3 Execution resumption
Not measured in the emulation (no network; the reset call produces output by construction). Checked only as "no
missing call". Measured as TTFO in Phase 2.

## 6. Phases

### Phase 0 - fidelity replay (before any Phase 1 run; gate)
Replay, with the exact reset / bind calls and Sink choice, five frozen real runs (same workload, seed, M):

| target | schedule (resets; binds) | Sink rebound |
|---|---|---|
| W2 butterfly s0 `reuse_dyn` (`expW_W2_butterfly-feeding-slow-motion_s0`) | 34; 58 | withheld |
| VACW butterfly rho 1 `split` rep 1 | 30, 54, 77; 101 | withheld (= trigger) |
| VACW butterfly rho 0.5 `split` rep 1 | 30, 77, 123; 54, 100, 147 | trigger snapshot every time (stale) |
| VACW butterfly rho 0.5 `restart_fresh` rep 1 | 30, 77, 123; 54, 103, 150 | withheld (fresh) |
| VACW dog rho 1 `split` rep 1 | 30, 54, 78; 101 | withheld |

**Pass (each target):** same single-crossing and sustained outcome, |T_emul - T_real| <= 1.0 dB (T over the real run's
last 10 common post-bind calls when shorter than H), and median per-call |dPSNR| <= 1.0 dB over the common post-bind
calls. **Gate: 5 / 5 pass, else stop** (section 8).

### Phase 1 - cause separation (emulation)
Per workload and anchor: r1 at d in {0, 10, 25, 50, 75, 100} (6), r3c at d in {25, 50, 75, 100} (4), r3e at d in
{0, 75} (2) = 12 conditions; 4 workloads x 2 anchors = 96 runs, one run per condition (the runtime is deterministic:
VACW reps agree to 0.1 dB; checked below), plus 4 determinism repeats (r1, d = 75, b1, every workload) = **100 runs**.

### Phase 2 - real-migration validation (after Phase 1 analysis and the user's approval)
Real 4-host harness, warm destinations, frozen M1 + M2 (`split`; no owner binds before it is left, so Sink content =
restart), M chosen so the expected final bind is at b1 = 155:

| config | path / bandwidth | M | expected d / structure |
|---|---|---|---|
| P1 | A -> B, 1 Gbps | 130 | ~25, r1 |
| P2 | A -> B, 320 Mbps (T_s ~ 43.9 s, linear in the 1 Gbps T_s; cap fixed at the freeze) | 80 | ~75-79, r1 |
| P3 | A -> B -> C -> D, rho 1 at 1 Gbps (T_m 14.05 s) | 84 | ~71, r3c |

Workloads butterfly s0, the second refresh-heavy workload with the clearest Phase 1 class (rule fixed now: the one of
audi / train whose class agrees with butterfly; if neither, train), dog s0; 2 reps: **18 runs**, plus 9 emulation
replays of rep 1 with the realized schedules.

## 7. Hypotheses, signatures and decision rules (Phase 1; per refresh-heavy workload; both anchors)

Effects (dB of terminal PSNR T):
- **Duration effect D:** under r1, T(d = 0) - T(d = 100) >= 3.0 dB at both anchors, with no increase > 1.0 dB between
  consecutive d.
- **Reset effect R:** dR(d) = T(r1, d) - T(r3c, d) for d in {25, 50, 75, 100} x 2 anchors (8 values): median >= 2.0 dB
  and >= 6 of 8 positive.
- **Interaction I:** R present and dR(100) - dR(25) >= 2.0 dB at both anchors.
- **Ephemeral-reset effect E:** T(r1, d = 0) < 35 dB at both anchors (a single recent / VAE reset with the Sink present
  already prevents recovery).

Classification of each refresh-heavy workload (first matching row):

| class | rule | reading |
|---|---|---|
| EPHEMERAL | E | the reset of recent KV / VAE itself, not Sink-less time |
| BOTH (+ INTERACTION if I) | D and R | duration and repeated resets each lower recovery |
| DURATION | D and not R | Sink-less generation time; repeated resets add nothing measurable |
| RESET | R and not D | repeated resets; duration alone does not |
| NOT REPRODUCED | not D, not R, and T >= 35 dB in every r1 / r3c condition | the emulated factors do not reproduce the failure (Phase 0 would normally have caught this) |
| UNCLASSIFIED | otherwise | reported as such |

Overall statement rule: if >= 2 of the 3 refresh-heavy workloads share a class, RD states that recovery failure is
"associated with <class> under in-place M1 emulation for 2 (3) of 3 refresh-heavy workloads"; otherwise
"workload-dependent". The wording "caused by" is not used; Phase 2 decides whether the association carries over to
real migration.

Secondary, reported for every condition: crossing and sustained outcome maps (d x structure x anchor); r3e vs r3c at
d = 75 (does a bound gap between episodes help or hurt); dog control (predicted: crosses in every condition; any failure
is reported as a finding that the effect is not specific to refresh-heavy inputs).

Thresholds: 35 dB and 10 calls are the frozen W rules; 3.0 / 2.0 / 1.0 dB are new and chosen against the measured
rep-to-rep spread (<= 0.1 dB within VACW cells) and the ~10 dB between recovering (dog, ~40 dB) and non-recovering
(butterfly, ~29.5 dB) final owners in VACW.

**Phase 2 decision rule (fixed now):** for each workload x config, the Phase 1 condition at b1 with the nearest
(d, structure) is the prediction. Agreement = both reps reproduce its sustained and crossing outcome and the rep median
T is within 2.0 dB of it; plus each rep-1 replay passes the Phase 0 criteria against its real run. **Emulation
validated** if >= 8 of 9 agree and every replay passes; otherwise RD's Phase 1 class is reported as an emulation result
only, with the disagreement.

## 8. Confounders and how each is handled

| confounder | handling |
|---|---|
| absolute position (realign phase, clip-loop / cut phase) | two anchors with different phases; every contrast at both |
| reference Sink change between the reset and b (RVC) | measured from the reference record (W method) and reported per condition; not controlled |
| promotions during the Sink-less window | none by construction (refresh frozen until bind), as in real M1 |
| span: r3e covers d + 2g calls | reported; r3e is compared with r3c only at d = 75 and never enters the D / R rules |
| Sink staleness | withheld Sink in Phase 1 (= trigger snapshot for contiguous windows); stale variant only in Phase 0 |
| nondeterminism | 4 repeats; fallback in section 9 |
| emulation vs real system | Phase 0 replay gate; Phase 2 |
| PSNR as the only recovery measure | section 5.2 metrics reported separately; no perceptual claim |

## 9. Validity, stopping criteria

- Run validity: reference digest of the uninterrupted prefix identical up to t_1 (99 dB); every reset and bind at its
  scheduled call; no missing call; GPU 0 idle before the run; nodes / process on the frozen commit.
- **Stop S1:** any Phase 0 target fails -> no Phase 1 run; the mismatch is reported and its cause investigated (GPU
  execution order, state initialization, schedule, reference); a dated amendment before anything else. A failed target
  by itself (e.g. a > 1 dB terminal difference) is reported as a mismatch of this implementation, not as evidence that
  in-place emulation is unsound in principle.
- **Stop S2:** a determinism repeat differs from its first run by median |dPSNR| > 0.5 dB -> stop; the pre-specified
  fallback is 3 runs per condition with the median T and majority outcomes (cost x 3), started only after the user's
  approval.
- **Stop S3:** dog r1 d = 0 below 35 dB at either anchor -> harness fault suspected; stop.
- Harness failures: <= 2 re-runs per condition (`followup_common.md` section 3); kept and listed.
- Phase 2 starts only after the Phase 1 report and the user's approval. No condition is added after any Phase 1 result
  is seen; an added condition is a dated, exploratory amendment.

## 10. Cost estimate

| phase | runs | per run | GPU time | wall (4 GPUs) |
|---|---|---|---|---|
| 0 replay | 5 | 1.5-3 min (133-250 calls) | ~0.2 h | ~5 min |
| 1 emulation | 96 + 4 | ~2.4 min (calls 0 .. b + 99 at 0.556 s + resets + PSNR / metrics; one baseline per workload) | ~4.2 h | ~1.1-1.3 h (one workload per host) |
| 2 real | 18 | ~4-5 min | - | ~1.5 h |
| 2 replays | 9 | ~2.5 min | ~0.4 h | ~10 min |
| **total** | **132** | | | **~3-3.5 h** |

Implementation (not started): an emulation runner reusing `GpuRuntime` (no new mechanism), the schedule table, the
section 5.2 metric module (OpenCV), a Phase 0 replay checker and an aggregator; one CPU / dry test of the schedule logic
before any GPU run.

## 11. Decisions (closed 2026-10-20, before the freeze)

- **D1** - d = 10 added under r1 (+8 runs; Phase 1 = 100 runs): the sustained-recovery transition for butterfly may lie
  between 0 and 25 Sink-less calls (A ~4: sustained; W2 24: not sustained).
- **D2** - r3e kept as a descriptive episodic comparison (section 3.2); it never enters the hypothesis rules.
- **D3** - workloads butterfly-feeding-slow-motion, audi-snow-trail, train (refresh-heavy) and dog (control), seed 0.
- **D4** - OpenCV Farneback for the section 5.2 flow (no model download). OpenCV is not a declared dependency of the
  repository: availability on the four hosts is checked by the driver's preflight before Phase 0; if it is missing,
  installing `opencv-python-headless` into the hosts' environment needs the user's approval, and Phase 0 / 1 do not
  start without it.
- **D5** - seed 1 excluded from the initial experiment. If Phase 1 leaves butterfly UNCLASSIFIED, a seed-1 run may be
  proposed as a separate exploratory experiment; its results are never merged into the verdicts of this
  preregistration.

## 12. Recorded predictions (before any data)

- butterfly: DURATION (T falls with d; sustained only at d <= 10-25; single crossing lost between d = 25 and 75);
  r3c within 2 dB of r1 at matched d (VACW rho 1 and rho 0.5 both fail). Confidence: moderate for D, low for not-R.
- audi-snow-trail / train: DURATION or BOTH; crossing at d = 25 likely, sustained unlikely at any d > 0.
- dog: crosses in every condition; T >= 38 dB.
- Phase 0: 5 / 5 pass (same code path; cross-host bit-exactness was measured in the earlier single-handoff study).
- If the prediction holds, the paper's statement becomes a measured envelope ("recovery requires the Sink within N
  Sink-less calls for refresh-heavy inputs"), pointing at restoration latency (M2 / M3 scheduling, placement) rather
  than a new M1 cache mechanism.
