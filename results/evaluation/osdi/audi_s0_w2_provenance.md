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
