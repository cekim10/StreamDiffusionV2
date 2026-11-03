# Fig. 13d frame strips (protocol, 2026-11-03; implements preregistration.md section 10, D8; nothing run)

Strip runs extract frames only. They are not fidelity conditions: `fig13_report.py` never reads them (experiments
`expF13D_*`, outside its name pattern) and the 150-condition statistics are unchanged. Whether 13d appears in the
paper is decided after the frames exist.

## 1. Inputs and conditions (rule fixed before any frame is seen)

- **Inputs: dog and train**, because they are the only non-LOVEU inputs in Fig. 13 (D8: no LOVEU frames in
  publication figures). Not chosen for their results: dog is low refresh (3.6 / 100 calls), train mid-high (34.5).
- **Conditions, per input:** among its 15 OTTER conditions (rep 1), the one with the **median W3 PSNR** (rank 8 of 15,
  sorted by W3, seed, S) and the one with the **lowest W3**, so a typical case and the worst case are both shown.
  `fig13_strip.py select` applies the rule:

| input | role | seed | S | W3 (dB) | schedule diverged |
|---|---|---|---|---|---|
| dog | median | 0 | 79 | 48.0 | no |
| dog | lowest | 0 | 77 | 40.5 | yes |
| train | median | 1 | 76 | 46.0 | no |
| train | lowest | 0 | 72 | 39.8 | yes |

## 2. Runs

The sweep run's command (`run_fig13.sh` OTTER, same input, seed, S, flags) on P1 with the roles swapped (A = elves-02,
B = elves-01, so the destination writes the frames next to the orchestrator), plus `--dump_frames
results/evaluation/osdi/fig13/_dumps --dump_calls 160`: the destination's output after its switch (calls up to 189)
and the same-seed reference frames over that span, lossless (FFV1, `vc_frames`). 4 runs, under 30 min.

## 3. Check and plot

- `fig13_strip.py check`: a strip run is used only if it is valid and its per-call PSNR series and Sink decision equal
  its sweep run's (`fig13_report.same_series`, the test used for the repeats). A strip run that differs is reported
  and not plotted.
- `fig13_strip.py plot`: per condition, reference (top) vs OTTER (bottom), last frame of k = 0 (the source's last
  served call, equal to the reference), 1, 2, 4, 8, 25, 50 calls after the cutover. The figure states the condition's
  rank (median / lowest) and its W3; frames are not selected or cropped by look.
- Frames stay on elves-01 (`_dumps/` is not committed); only the strip figures and `strip_check.json` are.
