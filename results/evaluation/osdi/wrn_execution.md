# W / R / N execution status and testbed procedure

Frozen plan: `followup_prereg_freeze.md` (freeze commit 4001882, 2026-10-18T23:27Z). Shakedown pass conditions:
`followup_shakedown_conditions.md` (with Amendment 1, written before any GPU run).

## Implemented (commit 4c2bac3 and later; no M1 / M2 / M3 change)

| component | file | what |
|---|---|---|
| Sink value fingerprints, owner-side promotions | `tools/eval/mobility_node.py` (`--sink_fp`) | per call, per layer and sink slot, float64 sum of the slot's value cache (not RoPE-rotated); a change between consecutive owned calls that is not the bind at that call = `sink_promotion` event |
| reference record | same | node baseline (= reference) records per call: output-frame digest (BLAKE2b-128), value fingerprints, slot positions, service time; returned with RUN_END and written to `<run>/node_X/baseline_record.json` |
| fixed horizon | `tools/eval/mobility_orchestrate.py` (`--horizon_calls`) | W2: the final owner generates through call M + H - 1 for every policy (stop reason `horizon`) |
| progress-aligned trigger | same (`--cap_events half:<node>:<dir>=<mbps>`) | S = fragments not verified at the destination at the final move; fires once at ceil(|S| / 2) verified of S; planners not told (`known_caps_unchanged` recorded); trigger record incl. availability and reaction feasibility |
| R exposure | same | background flows from A over the GPU session's final restoration: mean active flows, coverage, bytes, exposure-valid flag |
| termination / censoring | same | `summary["wrn"]["termination"]`: stop reason, timed out, elapsed, last progress, first / last call at the final owner |
| validity | `tools/eval/wrn_validity.py`; `--validity wrn` in `--skip_done` | ExpD checks minus "no rejoin" / "deadline" (censored runs kept); degraded-cap checks after a cap change; at most 3 attempts per configuration + rep |
| W1 runner | `tools/eval/expw_w1.py` | 330 calls through the node baseline code path; promotions by cause, P_w as fed / within-clip |
| W-AR variants | `tools/eval/expw_war_variant.py` | lossless center band (rows 102-377), verified 99 dB against the cropped source |
| driver | `tools/eval/run_wrn.py` | setup, shakedown, w1, w2, r, n, war, all; `--dry` loopback |
| checker / aggregator | `tools/eval/check_wrn_shakedown.py`, `tools/eval/aggregate_wrn.py` | shakedown conditions; frozen verdict rules with censoring |

## CPU-only and loopback validation (2026-10-18, local)

- `expw_w1` call classes equal `loop_audit.json` for all 20 workloads (P1); promotion-by-cause and P_w arithmetic unit-tested.
- `sink_value_fp` unit-tested with CPU torch 2.6.0 on bf16 tensors: 90 values (30 layers x 3 slots); unchanged by key-only
  (RoPE-like) and recent-slot changes; a sink-slot value change moves exactly its index.
- Censoring helpers (median as order statistic, ratio / difference criteria under censoring) unit-tested.
- Degraded-cap egress check: the 10 s estimator charges only bytes completed after the window's first completion
  (a completion-time estimator over-counted by one fragment, ~5 % at 62.5 Mbps; found and fixed in the loopback run).
- Loopback shakedown (fake nodes on 127.0.0.1, 100 Mbps, 64 MiB fake Sink): **all conditions PASS**
  (`_dryrun_wrn_shakedown_check.md`): W2 horizon (c0 34, stop at 134), reference digests / fingerprints equal W1,
  R rho 0.5 c = 3 (move gaps = T_m, restart drops, split reuse 0.94, exposure record), N cell 9 trigger at 8 of 16,
  planner caps unchanged; R c = 0 rho 0.5 (split B_source 1.00 with B_fwd 1.00 from a bound owner; restart 3.00 = 1 + 2
  min(1, 1/rho)); an injected promotion at an intermediate owner counted before the final bind; a forced N timeout kept
  with censoring fields.
- **Full matrix loopback** (`run_wrn.py all --dry`, 2026-10-18 16:58-19:1x, ~2.3 h): all 56 orchestrator invocations
  exit 0; runs produced W1 40 + W-AR W1 4, W2 80, R 90, N 90, W-AR W2 8 (= the frozen 312); every N degraded cell's
  trigger fired; the aggregator reaches a verdict or a stated NOT EVALUABLE reason in every cell
  (`_dryrun_wrn_results.md`). The two dog seed-0 W2 runs are invalid ("nodes on different commits": a commit was pushed
  while they ran), which exercises the commit check. **The dry verdicts are not results**: the fake Sink has 16 fragments
  (one fragment = 0.0625 Sink), so byte criteria are quantized far beyond the thresholds' resolution, and PSNR values are
  synthetic. Operational note: do not commit on the testbed while a sweep runs.

## Testbed procedure (elves-01, repo root, agents running on all four hosts)

```bash
git pull && python tools/eval/d0_remote.py pull && python tools/eval/d0_remote.py status
python tools/eval/run_wrn.py setup
python tools/eval/run_wrn.py shakedown
python tools/eval/check_wrn_shakedown.py
```

Push the shakedown outputs (`results/evaluation/expW_W1/mbike-trick_s0_shk_*`, `results/evaluation/shk_*`,
`results/evaluation/osdi/wrn_shakedown_check.md`). If every condition passes, the full evaluation in the frozen order
(~19 h; run inside tmux):

```bash
python tools/eval/run_wrn.py all
python tools/eval/aggregate_wrn.py
```

A failed shakedown condition is a correctness bug: fix, dated amendment if frozen text is affected, repeat the shakedown.

## Status

- Full evaluation: **not started** (needs the testbed; the GPU shakedown has not run).
- Planned runs: 312 (W1 40, W2 80, R 90, N 90, W-AR 12) + shakedown 8; estimated ~19 h + ~1 h.
