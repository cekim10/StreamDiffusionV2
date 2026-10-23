# VC-0 checks (results/evaluation/expVC0/dog_s0)

- **G1: PASS** {"real_run": "results/evaluation/expRDX_dog/policy=split_bw=320_rho=none_tm=inf_rep=1_20261020-165548", "common_calls": 174, "compared_psnr": 174, "max_abs_dpsnr": 0.0, "first_call": 80, "last_call": 253}
- **G2: PASS** {"real_run": "results/evaluation/expW_W2_dog_s0/policy=cold_bw=1000_rho=none_tm=inf_rep=1_20261019-000939", "common_calls": 101, "compared_psnr": 100, "max_abs_dpsnr": 0.0, "first_call": 34, "last_call": 134}
- **G3: PASS** {}
  - COLD-1: ok {"calls": 140, "files": 6, "decoded_calls": 139, "digest_ok_calls": 139, "no_output_calls": [34]}
  - OT-L: ok {"calls": 190, "files": 8, "decoded_calls": 190, "digest_ok_calls": 190, "no_output_calls": []}
  - REF: ok {"calls": 240, "files": 10, "decoded_calls": 240, "digest_ok_calls": 240, "no_output_calls": []}
  - WFS-1: ok {"calls": 140, "files": 6, "decoded_calls": 140, "digest_ok_calls": 140, "no_output_calls": [], "stall_s": 14.42802119255066, "skipped_input_calls_harness": [], "skipped_input_calls_live_realtime": [34, 91, 58], "resume_call": 34, "first_output_input_chunk": 33}

VC-0: ALL PASS
