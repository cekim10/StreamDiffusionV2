# Provenance defect: the W2 audi-snow-trail seed-0 OTTER run generated train seed 1 (found 2026-10-25)

Found while dry-testing VD-3 (checking that the seed-0 OT-1 emulations reproduce their real source runs). No frozen raw
log, result or verdict is modified by this note; the disposition is the user's decision.

## 1. Finding

`results/evaluation/expW_W2_audi-snow-trail_s0/policy=reuse_dyn_bw=1000_rho=none_tm=inf_rep=1_20261019-135751` (the
W2 OTTER run of audi-snow-trail seed 0 that replaced the invalid run `..._20261019-050104`) generated **train, seed 1**:

- its node A baseline frame digests equal those of `expW_W2_train_s1` (both runs) and `expA_train_s1` on 39 / 39
  compared calls, and equal no audi-snow-trail run;
- its Sink-less PSNR (calls 34-57) equals `expW_W2_train_s1` call by call; they differ only after the bind (59 vs 58);
- the genuine audi-snow-trail seed-0 generation is the one of `..._050104`, `expRDX_audi-snow-trail`, `expWX_audi_X1..X6`
  and `expA_audi-snow-trail_s0` (all identical);
- the VC-1 emulation of audi OT-1 (on host D, audi seed 0) reproduces `..._050104` exactly from the move on and
  differs from `..._135751` by up to 8.7 dB.

## 2. Cause (logs, read)

`results/evaluation/wrn_logs/wrn_20261019-132835.log`: at 13:55:02 the W2 train seed-1 invocation launched node A on
elves-01 (pid 1113333, `--video_path examples/train.mp4`, seed 1); the orchestrator's connection was refused while the
node loaded and the invocation ended with a traceback, **leaving the node running**. The audi seed-0 re-run started at
13:57 connected to the same port and ran against that node: the run's recorded node A hello carries pid 1113333. The
orchestrator does not check that a node it connects to was launched with the invocation's input and seed.

## 3. Scope (audit of all 1515 runs with baseline digests, `node_A/baseline_record.json`)

Grouping every non-dry run by its baseline frame digests finds exactly one label conflict: this run. Every other W2
OTTER run of dog, train, butterfly and audi (seeds 0 and 1) shares its generation with runs of the same label in other
experiment families (expA, WX, RDX, ...). Runs without baseline digests are not covered by this check.

## 4. What uses the run

| result | how | status |
|---|---|---|
| W / R / N (frozen): W2 unit audi-snow-trail seed 0, OTTER side | `aggregate_wrn.py` takes the last valid reuse_dyn run: TTFO, service time, bind call, rejoin (crossing 40 calls after the bind, last-10 median 31.9 dB), RVC from the destination's baseline fingerprints, cut-induced classification with audi's cut calls | the unit's OTTER numbers are train seed 1's (a second sample of the train seed-1 unit); the Cold-restart side of the unit (`..._050232`) is genuine audi |
| VC-1 (frozen): audi-snow-trail OT-1 and WFS-1 | the schedule (move 34, bind 59, timeline) is taken from the run; the frames are emulated from audi seed 0 | the content is audi; the schedule was realized by a train seed-1 generation, so it is a copied schedule for audi, not "W2 s1 realized" as labelled |
| VD-3 (draft): audi seed-0 OT-1 cell | same schedule | labelled a counterfactual copied schedule in the VD-3 conditions (`vc_schedules.PROVENANCE`); frozen VC conditions unchanged |

Descriptive, genuine audi seed 0 (the invalid run `..._050104`, invalid by the NIC rule only): bind 58, first
crossing at call 84, last-10 median 34.9 dB (recorded in `wrn_report.md` section 6).

## 5. Options (for decision; nothing done)

1. Re-run the W2 audi-snow-trail seed-0 OTTER configuration once (about 4 min, hosts A and B), after adding a node
   identity check (the node reports its video, prompt and seed in HELLO; the orchestrator refuses a mismatch), store it
   separately, and report a W / R / N reproduction note for the audi seed-0 unit (as for EXEC_START). The frozen verdicts
   stay as recorded until that report is reviewed.
2. Keep the frozen W / R / N and VC results, and state in the paper and the artifact that the audi seed-0 OTTER unit is
   a duplicate train seed-1 sample and that the VC audi OT-1 / WFS-1 schedule is copied.
In either case the orchestrator should get the identity check before any further testbed run.

## 6. Decision (2026-10-25: reproduction approved) and disposition

Decisions: add node identity verification before any new testbed run; reproduce the affected run; keep the frozen run
unchanged; store the reproduction separately; compare the affected W / R / N metrics and verdicts; document; use
verified results in the paper.

**Node identity verification (implemented; before any new testbed run).**
- `mobility_node.py` reports an `identity` in HELLO: label, input video and prompt (repository-relative paths and the
  SHA-256 of their content), seed, size, noise scale, GPU, migration chunk and window, dry-run / cold-start flags, a
  fingerprint of the generation configuration, and the **launch token** (`--launch_id`) of the invocation that started
  it.
- `mobility_orchestrate.py` gives every node it starts a new launch token and, on connecting, compares the HELLO identity
  with the exact command it started the node with: launch token, every identity field, the configuration fingerprint and
  the input content hashes. A mismatch refuses the connection and ends the invocation. A node started outside the
  orchestrator (attach mode, the dry tests) is compared on the fields the orchestrator's node command states.
- `launch` / `connect` now run inside the invocation's `try / finally`, and the cleanup ends every node the invocation
  started: SHUTDOWN to connected nodes (60 s to exit, then killed), an immediate kill for nodes that never connected.
  The 13:55 failure mode (a node left loading after a refused connection) cannot leave an orphan, and an orphan from an
  older invocation is refused by its launch token.
- Tests: `test_xb.py` identity section (launch token, other input / seed, configuration fingerprint, input content,
  path normalization, attach-mode rules, an older node without identity, end-to-end refusal of a node with another
  seed, cleanup of never-connected remote and local nodes).

**Reproduction.** `run_wrn.py w2_repro` (default audi-snow-trail seed 0): the frozen W2 OTTER configuration (reuse_dyn,
1 Gbps, move 34, window 130, hosts A -> B) once, under `results/evaluation/expWP_W2_audi-snow-trail_s0` (the frozen
`expW_W2_audi-snow-trail_s0` is not touched; the Cold-restart run there is genuine and is kept).

**Comparison.** `compare_wrn_audi_repro.py` -> `osdi/expW/audi_s0_repro_report.{md,json}`: (1) verification of the
reproduction (valid under the frozen W / R / N rules; identity with the audi input, seed 0 and a launch token on every
node; node A baseline digests equal to the genuine audi seed-0 generation and not to train seed 1) - no comparison is
made unless it passes; (2) the unit's OTTER metrics frozen vs reproduction; (3) W-H1 / W-H2 (primary, S1, S2) / W-H3
recomputed with the reproduction in place of the mislabeled run, next to the frozen recomputation (which reproduces
the recorded verdicts: checked), changed verdicts listed; (4) the reproduction's schedule for VD-3's sensitivity
analysis. R, N, V and A do not use the run.

**Paper.** The verified results are used: once the comparison report is reviewed, the audi seed-0 unit of W is cited
from the reproduction, with this note; the frozen run is never presented as audi.

## 7. Outcome of the reproduction (2026-10-25)

`expW/audi_s0_repro_report.md` (`results/evaluation/expWP_W2_audi-snow-trail_s0/..._20261025-134003`, commit 31f5ad9):
- **verified**: valid under the frozen W / R / N rules; both nodes report the audi-snow-trail input (same content hash),
  seed 0 and this invocation's launch tokens; node A's baseline digests equal the genuine audi seed-0 generation
  (`expRDX_audi-snow-trail`, `expWX_audi_X1`) and not train seed 1;
- unit metrics, frozen (train seed 1) -> reproduction (audi seed 0): TTFO 0.682 -> 0.691 s; bind call 59 -> 58; rejoin
  at call 99 -> 84 (40 -> 26 calls after the bind); last-10 median 31.9 -> 34.2 dB; RVC events 11 -> 6 (none
  cut-induced). The genuine but invalid run of 2026-10-19 (bind 58, crossing 84) agrees with the reproduction;
- **W verdicts unchanged**: W-H1 SUPPORTED, W-H2 primary 39 / 40 SUPPORTED, S1 counts only (4 / 4), S2 25 / 26
  SUPPORTED, W-H3 SUPPORTED (Cold reaches 35 dB in 0 of 39); the audi workload's mean TTFO 0.677 -> 0.682 s. The
  frozen recomputation reproduces the recorded verdicts.

Disposition: the paper cites the audi seed-0 unit of W from the verified reproduction, with this note; the frozen
`..._135751` run stays in the artifact, labelled as a train seed-1 generation, never as audi.

## 8. Corrected aggregates (approved 2026-10-25: recompute everything affected)

`aggregate_wrn.py --corrected` writes the provenance-corrected set (`corrected_wrn_results.{json,md}`,
`corrected_w2_table.csv`) with the audi seed-0 OTTER run replaced by the verified reproduction; the frozen outputs are
unchanged. `diff_wrn_corrected.py` -> `expW/audi_s0_corrected_aggregate.md`:
- 82 verdicts compared (W, R, N, V, A): **none changed**;
- one aggregate field differs: W-H1's audi-snow-trail workload mean TTFO 0.677 -> 0.682 s;
- one W2 table row differs (audi seed 0: TTFO, bind call, rejoin calls 40 -> 26, last-10 median 31.9 -> 34.2 dB, final
  call 29.7 -> 34.9 dB, RVC events 11 -> 6, cuts between [62, 94] -> [62]);
- the counts the paper cites are identical: 39 / 40 crossing, 31 sustained, 8 crossing but never sustained, 9 crossing
  units ending with a last-10 median below 35 dB (10 including the non-crossing unit);
- no figure script reads the W / R / N outputs (checked), so no figure changes.
Text that quotes the audi seed-0 unit's own numbers (`wrn_report.md` section 2: "audi-snow-trail s0 31.9, whose single
crossing came 40 calls after the bind") is cited in the paper from the corrected set (34.2 dB, 26 calls); the frozen
report stays as recorded.
