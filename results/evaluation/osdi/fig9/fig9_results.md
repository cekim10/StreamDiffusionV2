# Fig. 9 results

Rules: `preregistration.md` (FROZEN). **F9-H1: SUPPORTED**; **F9-H2: SUPPORTED**; **F9-H3: NOT SUPPORTED**

## Low-refresh (dog)

| step | valid / runs | gap (s) | TTFO-local (s) | total stall (s) | bytes (GB) | PSNR first 24, median (dB) | min (dB) | terminal (dB) | switch reasons |
|---|---|---|---|---|---|---|---|---|---|
| Wait-for-Sink | 5 / 5 | 15.02 [15.01-15.03] | 15.0 [15.0-15.0] | 14.43 [14.41-14.43] | 1.73 [1.73-1.73] | 42.6 [42.6-42.6] | 19.2 [19.2-19.2] | 47.3 [47.3-47.3] | None |
| P-sink | 5 / 5 | 2.23 [2.22-2.30] | 28.7 [28.7-28.9] | 4.77 [4.74-4.83] | 2.48 [2.48-2.48] | 40.6 [40.6-40.6] | 19.2 [19.2-19.2] | 48.8 [48.8-48.8] | threshold |
| OTTER w/o Sink sync | 5 / 5 | 8.83 [8.72-8.87] | 30.3 [30.2-30.4] | 9.22 [9.11-9.36] | 2.47 [2.47-2.47] | 41.0 [41.0-41.3] | 26.9 [26.4-27.5] | 48.8 [48.8-48.9] | round_limit |
| OTTER | 5 / 5 | 1.63 [1.60-1.66] | 23.3 [23.1-23.5] | 1.99 [1.96-2.02] | 1.76 [1.76-1.76] | 41.0 [41.0-41.0] | 27.5 [26.9-27.5] | 48.8 [48.6-48.8] | round_limit |
| P-full | 5 / 5 | 50.92 [50.75-50.99] | 213.8 [213.6-213.9] | 61.80 [61.48-62.04] | 22.85 [22.85-22.85] | 99.0 [99.0-99.0] | 99.0 [99.0-99.0] | 99.0 [99.0-99.0] | no_shrink |

9a rounds (GB; last = stop-and-copy):

- P-full rep 1: 6.463 -> 5.478 -> 5.461 | stop 5.452 (no_shrink)
- P-full rep 2: 6.463 -> 5.478 -> 5.461 | stop 5.452 (no_shrink)
- P-full rep 3: 6.463 -> 5.478 -> 5.461 | stop 5.452 (no_shrink)
- P-full rep 4: 6.463 -> 5.478 -> 5.461 | stop 5.452 (no_shrink)
- P-full rep 5: 6.463 -> 5.478 -> 5.461 | stop 5.452 (no_shrink)
- P-sink rep 1: 1.725 -> 0.723 -> 0.025 | stop 0.003 (threshold)
- P-sink rep 2: 1.725 -> 0.723 -> 0.025 | stop 0.003 (threshold)
- P-sink rep 3: 1.725 -> 0.723 -> 0.025 | stop 0.003 (threshold)
- P-sink rep 4: 1.725 -> 0.723 -> 0.025 | stop 0.003 (threshold)
- P-sink rep 5: 1.725 -> 0.723 -> 0.025 | stop 0.003 (threshold)

OTTER w/o Sink sync cost (median): replayed_calls 32.000, replay_s_per_call 0.121, replay_s_total 3.886, patches 0.000, patch_mb 0.000, log_mb 12.781, base_mb 1727.637, switch_mb 730.191, ready_wait_s 4.068, stop_to_sent_s 7.350, fallback_mb 0.000, restore_s 0.654, dr2_s 0.521

OTTER cost (median): replayed_calls 32.000, replay_s_per_call 0.120, replay_s_total 3.893, patches 2.000, patch_mb 19.169, log_mb 31.950, base_mb 1727.637, switch_mb 3.199, ready_wait_s 4.079, stop_to_sent_s 1.369, src_sink_digest_s 0.064, dst_sink_check_s 0.064, verdict_wait_s 0.131, fallback_mb 0.000, restore_s 0.683, dr2_s 0.522

F9-H1 {"n_threshold": 5, "holds": true}
F9-H2 {"gaps": {"wait": 15.0237, "psink": 2.234400000000001, "nosync": 8.828999999999997, "otter": 1.6260999999999999}, "holds": true}
F9-H3 {"psnr_first24": {"wait": 42.598600000000005, "psink": 40.55355, "nosync": 41.019949999999994, "otter": 40.9765}, "holds": false}

## High-refresh (bfly)

| step | valid / runs | gap (s) | TTFO-local (s) | total stall (s) | bytes (GB) | PSNR first 24, median (dB) | min (dB) | terminal (dB) | switch reasons |
|---|---|---|---|---|---|---|---|---|---|
| Wait-for-Sink | 5 / 5 | 15.02 [15.01-15.03] | 15.0 [15.0-15.0] | 14.42 [14.41-14.43] | 1.73 [1.73-1.73] | 34.5 [34.5-34.5] | 14.1 [14.1-14.1] | 36.2 [36.2-36.2] | None |
| P-sink | 5 / 5 | 2.52 [2.44-2.54] | 35.3 [35.3-35.6] | 6.05 [5.97-6.14] | 3.02 [3.02-3.02] | 41.5 [41.5-41.5] | 14.8 [14.8-14.8] | 39.2 [39.2-39.2] | threshold |
| OTTER w/o Sink sync | 5 / 5 | 10.40 [10.38-10.40] | 32.1 [31.8-32.3] | 10.76 [10.76-10.80] | 2.68 [2.68-2.68] | 43.9 [43.9-43.9] | 22.0 [22.0-22.0] | 44.1 [44.1-44.1] | round_limit |
| OTTER | 5 / 5 | 1.59 [1.57-1.73] | 24.6 [24.4-25.8] | 1.87 [1.87-2.10] | 2.24 [2.24-2.28] | 41.6 [35.9-41.6] | 25.5 [25.5-26.3] | 44.4 [32.4-44.4] | round_limit |
| P-full | 5 / 5 | 52.57 [52.51-52.58] | 219.2 [219.2-219.4] | 63.48 [63.41-63.52] | 23.55 [23.55-23.55] | 99.0 [99.0-99.0] | 99.0 [99.0-99.0] | 99.0 [99.0-99.0] | no_shrink |

9a rounds (GB; last = stop-and-copy):

- P-full rep 1: 6.463 -> 5.729 -> 5.691 | stop 5.671 (no_shrink)
- P-full rep 2: 6.463 -> 5.729 -> 5.691 | stop 5.671 (no_shrink)
- P-full rep 3: 6.463 -> 5.729 -> 5.691 | stop 5.671 (no_shrink)
- P-full rep 4: 6.463 -> 5.729 -> 4.572 -> 4.546 | stop 4.534 (no_shrink)
- P-full rep 5: 6.463 -> 5.729 -> 5.691 | stop 5.671 (no_shrink)
- P-sink rep 1: 1.725 -> 0.895 -> 0.282 -> 0.088 | stop 0.028 (threshold)
- P-sink rep 2: 1.725 -> 0.895 -> 0.282 -> 0.088 | stop 0.028 (threshold)
- P-sink rep 3: 1.725 -> 0.895 -> 0.282 -> 0.088 | stop 0.024 (threshold)
- P-sink rep 4: 1.725 -> 0.895 -> 0.282 -> 0.088 | stop 0.028 (threshold)
- P-sink rep 5: 1.725 -> 0.895 -> 0.282 -> 0.088 | stop 0.028 (threshold)

OTTER w/o Sink sync cost (median): replayed_calls 32.000, replay_s_per_call 0.120, replay_s_total 3.881, patches 0.000, patch_mb 0.000, log_mb 12.781, base_mb 1727.637, switch_mb 935.712, ready_wait_s 4.057, stop_to_sent_s 8.934, fallback_mb 0.000, restore_s 0.656, dr2_s 0.522

OTTER cost (median): replayed_calls 34.000, replay_s_per_call 0.121, replay_s_total 4.334, patches 52.000, patch_mb 498.401, log_mb 511.981, base_mb 1727.637, switch_mb 3.199, ready_wait_s 4.645, stop_to_sent_s 1.239, src_sink_digest_s 0.064, dst_sink_check_s 0.064, verdict_wait_s 0.084, fallback_mb 0.000, restore_s 0.634, dr2_s 0.523

F9-H1 {"n_threshold": 5, "holds": true}
F9-H2 {"gaps": {"wait": 15.0182, "psink": 2.5178999999999974, "nosync": 10.4011, "otter": 1.5865999999999998}, "holds": true}
F9-H3 {"psnr_first24": {"wait": 34.5223, "psink": 41.51235, "nosync": 43.8989, "otter": 41.6245}, "holds": true}
