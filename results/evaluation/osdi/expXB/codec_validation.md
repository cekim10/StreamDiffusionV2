# XB recompute input codecs - CPU-only validation (2026-10-22)

Purpose: choose the input-history codec of the recompute baselines before any GPU calibration
(`preregistration.md` section 3.2). The frames are the runtime's uint8 camera frames at 480 x 832 (1,198,080 B each).
The clip repeats end to end, as in the runtime. Each segment is encoded independently, so an abandoned target shares nothing.
Bit-exact means `np.array_equal(decode(encode(x)), x)`.

Machine: macOS-26.6.2-arm64-arm-64bit. Timings come from one process on this machine and are indicative only;
the GPU hosts measure their own encode and decode times in every run.

Reproduce: `python tools/eval/xb_codec_validate.py` (needs numpy, av, Pillow; CPU only).

## Summary (all four segments per input)

| input | codec | class | ratio vs raw | bit-exact (4 / 4) | encode ms / frame | decode ms / frame | min PSNR (lossy) |
|---|---|---|---|---|---|---|---|
| dog | raw | upper bound | 1.00-1.00 | 4 / 4 | 0.1 | 0.0 | - |
| dog | zlib1 | lossless | 1.42-1.45 | 4 / 4 | 13.6 | 2.2 | - |
| dog | zlib6 | lossless | 1.44-1.47 | 4 / 4 | 20.9 | 2.0 | - |
| dog | png | lossless | 2.04-2.09 | 4 / 4 | 16.9 | 4.6 | - |
| dog | ffv1 | lossless | 2.99-3.05 | 4 / 4 | 4.3 | 4.4 | - |
| dog | x264rgb_qp0 | lossless | 2.64-2.77 | 4 / 4 | 6.8 | 7.5 | - |
| dog | h264_crf23 | lossy | 107.87-139.99 | 0 / 4 | 1.8 | 0.6 | 34.7 dB |
| dog | h264_crf28 | lossy | 202.82-289.61 | 0 / 4 | 1.7 | 0.6 | 31.8 dB |
| butterfly-feeding-slow-motion | raw | upper bound | 1.00-1.00 | 4 / 4 | 0.1 | 0.0 | - |
| butterfly-feeding-slow-motion | zlib1 | lossless | 1.31-1.32 | 4 / 4 | 14.1 | 2.2 | - |
| butterfly-feeding-slow-motion | zlib6 | lossless | 1.31-1.32 | 4 / 4 | 20.1 | 2.1 | - |
| butterfly-feeding-slow-motion | png | lossless | 2.58-2.58 | 4 / 4 | 18.7 | 4.1 | - |
| butterfly-feeding-slow-motion | ffv1 | lossless | 4.12-4.13 | 4 / 4 | 3.2 | 3.6 | - |
| butterfly-feeding-slow-motion | x264rgb_qp0 | lossless | 2.43-2.45 | 4 / 4 | 6.3 | 6.4 | - |
| butterfly-feeding-slow-motion | h264_crf23 | lossy | 122.82-148.94 | 0 / 4 | 1.9 | 0.5 | 36.1 dB |
| butterfly-feeding-slow-motion | h264_crf28 | lossy | 219.75-279.08 | 0 / 4 | 1.8 | 0.5 | 34.0 dB |

## Selection

- **Primary: FFV1** (lossless; `bgr0`, level 3, intra-only, 4 slices with CRC). It was bit-exact on every segment.
  It had the highest lossless ratio on both inputs (3.0x dog, 4.1x butterfly) and the fastest lossless encode.
- x264rgb qp 0 is lossless but larger and slower. PNG and zlib compress less.
- H.264 CRF 23 / 28 (yuv420p) are not bit-exact. They are lossy-input sensitivity cases only and never exact recomputation.
- Raw is the network-byte upper bound. Every recompute run records it, so it needs no separate runs.

## Transmitted bytes per segment and transfer time at 1 Gbps (actual encoded sizes)

| input | segment | frames | raw MB | FFV1 MB | CRF 23 MB | CRF 28 MB | raw s @1 Gbps | FFV1 s @1 Gbps |
|---|---|---|---|---|---|---|---|---|
| dog | R-full t30 (calls 0..30) | 125 | 149.8 | 49.6 | 1.07 | 0.52 | 1.20 | 0.40 |
| dog | R-full later round (30 calls) | 120 | 143.8 | 47.2 | 1.10 | 0.53 | 1.15 | 0.38 |
| dog | R-full t120 (calls 0..120) | 485 | 581.1 | 191.7 | 4.22 | 2.05 | 4.65 | 1.53 |
| dog | R-win W=3 | 13 | 15.6 | 5.2 | 0.14 | 0.08 | 0.12 | 0.04 |
| butterfly-feeding-slow-motion | R-full t30 (calls 0..30) | 125 | 149.8 | 36.3 | 1.01 | 0.54 | 1.20 | 0.29 |
| butterfly-feeding-slow-motion | R-full later round (30 calls) | 120 | 143.8 | 34.8 | 0.98 | 0.52 | 1.15 | 0.28 |
| butterfly-feeding-slow-motion | R-full t120 (calls 0..120) | 485 | 581.1 | 140.8 | 3.95 | 2.11 | 4.65 | 1.13 |
| butterfly-feeding-slow-motion | R-win W=3 | 13 | 15.6 | 3.8 | 0.13 | 0.07 | 0.12 | 0.03 |

R-full replay of 30 chunks takes about 17 s (state study), so input transfer is not the R-full bottleneck at 1 Gbps.
The codec mainly changes network bytes.

## Detail: dog

| segment | codec | bytes | ratio vs raw | encode ms | decode ms | bit-exact | PSNR (dB) |
|---|---|---|---|---|---|---|---|
| R-full t30 (calls 0..30) | raw | 149,760,012 | 1.00 | 16 | 3 | True | - |
| R-full t30 (calls 0..30) | zlib1 | 103,953,639 | 1.44 | 1615 | 248 | True | - |
| R-full t30 (calls 0..30) | zlib6 | 102,303,171 | 1.46 | 2557 | 236 | True | - |
| R-full t30 (calls 0..30) | png | 72,210,268 | 2.07 | 2071 | 554 | True | - |
| R-full t30 (calls 0..30) | ffv1 | 49,600,482 | 3.02 | 528 | 555 | True | - |
| R-full t30 (calls 0..30) | x264rgb_qp0 | 54,066,442 | 2.77 | 837 | 989 | True | - |
| R-full t30 (calls 0..30) | h264_crf23 | 1,069,776 | 139.99 | 209 | 76 | False | 34.8 |
| R-full t30 (calls 0..30) | h264_crf28 | 517,110 | 289.61 | 184 | 62 | False | 31.8 |
| R-full later round (30 calls) | raw | 143,769,612 | 1.00 | 20 | 13 | True | - |
| R-full later round (30 calls) | zlib1 | 99,487,475 | 1.45 | 1610 | 242 | True | - |
| R-full later round (30 calls) | zlib6 | 97,864,019 | 1.47 | 2525 | 230 | True | - |
| R-full later round (30 calls) | png | 68,723,600 | 2.09 | 2017 | 538 | True | - |
| R-full later round (30 calls) | ffv1 | 47,214,624 | 3.05 | 507 | 524 | True | - |
| R-full later round (30 calls) | x264rgb_qp0 | 54,334,974 | 2.65 | 831 | 975 | True | - |
| R-full later round (30 calls) | h264_crf23 | 1,096,803 | 131.08 | 209 | 74 | False | 34.7 |
| R-full later round (30 calls) | h264_crf28 | 532,480 | 270.00 | 183 | 61 | False | 31.8 |
| R-full t120 (calls 0..120) | raw | 581,068,812 | 1.00 | 34 | 10 | True | - |
| R-full t120 (calls 0..120) | zlib1 | 402,892,647 | 1.44 | 6695 | 1116 | True | - |
| R-full t120 (calls 0..120) | zlib6 | 396,414,225 | 1.47 | 10170 | 981 | True | - |
| R-full t120 (calls 0..120) | png | 279,113,153 | 2.08 | 8235 | 2232 | True | - |
| R-full t120 (calls 0..120) | ffv1 | 191,738,282 | 3.03 | 2063 | 2128 | True | - |
| R-full t120 (calls 0..120) | x264rgb_qp0 | 213,672,860 | 2.72 | 3317 | 3366 | True | - |
| R-full t120 (calls 0..120) | h264_crf23 | 4,218,218 | 137.75 | 930 | 299 | False | 34.9 |
| R-full t120 (calls 0..120) | h264_crf28 | 2,048,366 | 283.67 | 840 | 288 | False | 31.9 |
| R-win W=3 | raw | 15,575,052 | 1.00 | 4 | 0 | True | - |
| R-win W=3 | zlib1 | 10,960,092 | 1.42 | 177 | 27 | True | - |
| R-win W=3 | zlib6 | 10,811,072 | 1.44 | 279 | 26 | True | - |
| R-win W=3 | png | 7,619,420 | 2.04 | 226 | 62 | True | - |
| R-win W=3 | ffv1 | 5,215,737 | 2.99 | 65 | 81 | True | - |
| R-win W=3 | x264rgb_qp0 | 5,896,136 | 2.64 | 96 | 262 | True | - |
| R-win W=3 | h264_crf23 | 144,391 | 107.87 | 25 | 12 | False | 34.7 |
| R-win W=3 | h264_crf28 | 76,794 | 202.82 | 21 | 10 | False | 31.8 |

## Detail: butterfly-feeding-slow-motion

| segment | codec | bytes | ratio vs raw | encode ms | decode ms | bit-exact | PSNR (dB) |
|---|---|---|---|---|---|---|---|
| R-full t30 (calls 0..30) | raw | 149,760,012 | 1.00 | 15 | 3 | True | - |
| R-full t30 (calls 0..30) | zlib1 | 113,682,072 | 1.32 | 1799 | 274 | True | - |
| R-full t30 (calls 0..30) | zlib6 | 113,649,707 | 1.32 | 2448 | 261 | True | - |
| R-full t30 (calls 0..30) | png | 58,002,513 | 2.58 | 2313 | 513 | True | - |
| R-full t30 (calls 0..30) | ffv1 | 36,292,304 | 4.13 | 404 | 445 | True | - |
| R-full t30 (calls 0..30) | x264rgb_qp0 | 61,100,835 | 2.45 | 779 | 850 | True | - |
| R-full t30 (calls 0..30) | h264_crf23 | 1,005,474 | 148.94 | 240 | 69 | False | 36.3 |
| R-full t30 (calls 0..30) | h264_crf28 | 536,616 | 279.08 | 214 | 59 | False | 34.2 |
| R-full later round (30 calls) | raw | 143,769,612 | 1.00 | 11 | 5 | True | - |
| R-full later round (30 calls) | zlib1 | 109,018,922 | 1.32 | 1679 | 281 | True | - |
| R-full later round (30 calls) | zlib6 | 108,974,652 | 1.32 | 2351 | 247 | True | - |
| R-full later round (30 calls) | png | 55,634,685 | 2.58 | 2208 | 484 | True | - |
| R-full later round (30 calls) | ffv1 | 34,811,387 | 4.13 | 387 | 431 | True | - |
| R-full later round (30 calls) | x264rgb_qp0 | 58,637,692 | 2.45 | 750 | 819 | True | - |
| R-full later round (30 calls) | h264_crf23 | 975,741 | 147.34 | 232 | 66 | False | 36.3 |
| R-full later round (30 calls) | h264_crf28 | 521,769 | 275.54 | 209 | 57 | False | 34.2 |
| R-full t120 (calls 0..120) | raw | 581,068,812 | 1.00 | 43 | 18 | True | - |
| R-full t120 (calls 0..120) | zlib1 | 441,268,129 | 1.32 | 6788 | 1059 | True | - |
| R-full t120 (calls 0..120) | zlib6 | 441,158,560 | 1.32 | 9900 | 1056 | True | - |
| R-full t120 (calls 0..120) | png | 225,032,223 | 2.58 | 9135 | 1988 | True | - |
| R-full t120 (calls 0..120) | ffv1 | 140,821,481 | 4.13 | 1564 | 1742 | True | - |
| R-full t120 (calls 0..120) | x264rgb_qp0 | 237,095,058 | 2.45 | 3058 | 2834 | True | - |
| R-full t120 (calls 0..120) | h264_crf23 | 3,952,610 | 147.01 | 948 | 258 | False | 36.4 |
| R-full t120 (calls 0..120) | h264_crf28 | 2,113,290 | 274.96 | 906 | 264 | False | 34.2 |
| R-win W=3 | raw | 15,575,052 | 1.00 | 3 | 0 | True | - |
| R-win W=3 | zlib1 | 11,892,598 | 1.31 | 185 | 29 | True | - |
| R-win W=3 | zlib6 | 11,895,194 | 1.31 | 258 | 28 | True | - |
| R-win W=3 | png | 6,031,410 | 2.58 | 244 | 54 | True | - |
| R-win W=3 | ffv1 | 3,780,983 | 4.12 | 46 | 59 | True | - |
| R-win W=3 | x264rgb_qp0 | 6,400,889 | 2.43 | 83 | 243 | True | - |
| R-win W=3 | h264_crf23 | 126,810 | 122.82 | 27 | 10 | False | 36.1 |
| R-win W=3 | h264_crf28 | 70,877 | 219.75 | 22 | 8 | False | 34.0 |

