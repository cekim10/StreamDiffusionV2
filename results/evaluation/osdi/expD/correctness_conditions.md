# Experiment D focused correctness tests - pass conditions (written 2026-10-16, before any testbed run)

Correctness checks of the capabilities added after D0, not Experiment D criteria; no G1-G9 outcome is computed from
these runs. Applied by `tools/eval/check_expD_correctness.py` to `results/evaluation/expD_correctness/` (and, with the
same code, to the D0 shakedown re-run `d0_shakedown_rerun/`). Tests: `tools/eval/run_expD_correctness.sh` (one
configuration per capability, 1 Gbps unless stated, dog seed 0 k = 2).

Every run: version events 0; duplicates 0 (orchestrator and node logs); NIC peaks <= 1.15 x the cap (1 Gbps; unshaped:
the 9.4 Gbps NIC); paced payload egress <= 1.05 x cap in every 10 s window (shaped runs); GPU 0 idle before the run; four distinct
hosts on one commit; stop reason not deadline / window_exhausted; per-move timing non-negative (resume <= first
output); the final owner keeps generating (>= min(8, tail_calls) chunks after the final move); NIC-measured egress of every node within [0.97, 1.12] x the bytes the run
accounts to it (fragments + execution state) when that is >= 100 MiB.
By capability:
  full      state digests of every component match; the Sink component's digest equals the source manifest's; every
            chunk after resume bit-exact (>= 99 dB); the completed transfer carries the whole packed state; a redirected
            (cancelled) transfer's partial state is discarded at its receiver; resume after the completing transfer ends
  cold      no Sink fragment, no execution state and no in-flight rows sent; a PSNR value for every produced chunk;
            first output within 3 chunks of the resume
  revisit   M1 only: the revisited owner held nothing on return and received again every fragment it had verified;
            progress-preserving policies: everything verified before leaving still held on return, nothing received
            again; Sink verified with the source digest and bound at the revisited owner; rejoin >= 35 dB
  hybrid    the GPU session restores (digest, bind, rejoin >= 35 dB); every network session restored at the final
            owner; combined source-A payload (GPU + network sessions) <= 1.05 x cap in every 10 s window; network
            sessions' paced egress valid; GPU session's median chunk time within 5 % of the node's baseline service time
  colddest  the destination process started after the trigger; reference frames available before the first output;
            TTFO from the trigger > runtime-ready time > process start >= 0; Sink verified with the source digest,
            bound, rejoin >= 35 dB
  fast M1-family runs (every non-full, non-cold run): all fragments verified, final Sink digest = source digest, rejoin >= 35 dB

The user's ten required checks map to these conditions as follows: (1) focused tests = one run per capability;
(2) Sink digest consistency = final Sink digest / Full migration's Sink component vs the source manifest; (3) fragment
checksums = all fragments verified (per-fragment SHA-256) and no rejected receipts; (4) Sink version = 0 version events;
(5) generation continuation = the final owner keeps producing chunks and per-move first output after resume;
(6) quality vs the reference = rejoin >= 35 dB, bit-exact after a Full migration, a PSNR value for every cold-restart
chunk; (7) traffic accounting = NIC-measured egress vs accounted bytes per node, completed state transfer = packed state,
combined source payload in scenario E; (8) timing boundaries = per-move resume <= first output, non-negative latencies,
cold-destination ordering; (9) no duplicate application = 0 duplicate receipts in the orchestrator and node logs;
(10) same commit = `nodes_same_commit` (every node's HELLO commit = the orchestrator's).

Amendment before any testbed run (2026-10-16): "keeps generating" was ">= 8 chunks"; set to >= min(8, tail_calls) after the dry
run with tail_calls = 4 (an unshaped Full migration rejoins at once and stops after the tail). Testbed runs use 12.

Amendment after the testbed run (2026-10-17): added "placement delivered": in a run with placement, the fraction of the
Sink verified at the top-1 candidate at the move is >= the allocation minus max(2, 5 % of it) fragments (fragments in
flight at the move are not verified yet; first written as 0.95 x the allocation, changed the same day before any re-run
because at loopback scale one fragment is 6 % of the fake Sink). Reason: the M1 + M2 + top-1
run (`expD_correctness/policy=split_..._pp=top1_..._20261016-224842`) passed every written condition although its
placement flow had been cancelled after 2 of 299 fragments (an implementation bug, fixed in the following commit); the
written conditions did not check that placement happened. That run is kept and judged FAIL under the amended conditions.
