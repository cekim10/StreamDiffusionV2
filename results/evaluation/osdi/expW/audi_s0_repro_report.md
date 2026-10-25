# W2 audi-snow-trail seed-0 OTTER unit: provenance reproduction (osdi/audi_s0_w2_provenance.md)

Reproduction: `expWP_W2_audi-snow-trail_s0/policy=reuse_dyn_bw=1000_rho=none_tm=inf_rep=1_20261025-134003`; frozen (mislabeled): `expW_W2_audi-snow-trail_s0/policy=reuse_dyn_bw=1000_rho=none_tm=inf_rep=1_20261019-135751`. Nothing frozen is modified.

## 1. Verification: PASS

- valid under the W / R / N rules: True; node A digests equal the genuine audi seed-0 generation: {'expRDX_audi-snow-trail': True, 'expWX_audi_X1': True}; equal train seed 1: False

## 2. Unit metrics (OTTER side; the Cold-restart run is genuine and unchanged)

| metric | frozen (train seed 1, mislabeled) | reproduction (audi seed 0, verified) |
|---|---|---|
| ttfo_s | 0.6815676689147949 | 0.6906211376190186 |
| service_s | 0.5535 | 0.5549 |
| bind_call | 59 | 58 |
| rejoin | True | True |
| rejoin_call | 99 | 84 |
| rejoin_calls | 40 | 26 |
| sustained_calls | None | None |
| psnr_median_last10 | 31.8545 | 34.2087 |
| psnr_final_call | 29.6853 | 34.9024 |
| min_psnr_after_crossing | 29.6853 | 25.5866 |
| RVC events (cut-induced) | 11 (0) | 6 (0) |

Descriptive only: the genuine but invalid run `policy=reuse_dyn_bw=1000_rho=none_tm=inf_rep=1_20261019-050104` (NIC rule) - bind 58, first crossing 84, last-10 median 34.9 dB (wrn_report.md section 6).

## 3. W verdicts: frozen data vs the audi seed-0 OTTER run replaced by the verified reproduction

| criterion | frozen recomputation | corrected | changed |
|---|---|---|---|
| W-H1 | SUPPORTED | SUPPORTED | no |
| W-H2 primary | {"n": 40, "successes": 39, "share": 0.975, "verdict": "SUPPORTED"} | {"n": 40, "successes": 39, "share": 0.975, "verdict": "SUPPORTED"} | no |
| W-H2 S1 | {"n": 4, "successes": 4, "share": null, "verdict": "counts only (n < 10)"} | {"n": 4, "successes": 4, "share": null, "verdict": "counts only (n < 10)"} | no |
| W-H2 S2 | {"n": 26, "successes": 25, "share": 0.9615384615384616, "verdict": "SUPPORTED"} | {"n": 26, "successes": 25, "share": 0.9615384615384616, "verdict": "SUPPORTED"} | no |
| W-H3 | SUPPORTED (Cold reaches 35 dB in 0.0% of 39) | SUPPORTED (Cold reaches 35 dB in 0.0% of 39) | no |
| W-H1 audi TTFO (workload mean) | 0.6774104833602905 | 0.6819372177124023 | - |

The frozen recomputation reproduces the recorded wrn_results.json verdicts: True. Changed verdicts: none.

## 4. Schedule of the reproduction (VD-3 sensitivity analysis, D2b; the VD-3 confirmation cell keeps the copied schedule)

- move call 34, bind call 58, Sink bind at 14.75264835357666 s after the move
