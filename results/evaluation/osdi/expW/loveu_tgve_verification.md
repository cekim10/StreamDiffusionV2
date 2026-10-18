# LOVEU-TGVE-2023: provenance, license, acquisition and the W workload subset (v2, 2026-10-18)

**Status:** the official archive was downloaded on 2026-10-18 under the user's decision, the 16-video subset was fixed
by the pre-written rule, and the selected videos load in the pipeline's own loader. No Experiment W measurement, no GPU
run, no change to OTTER. The original videos are kept outside the repository and are **not redistributed**; no frame of
them may appear in a publication figure until its reuse permission is established (section 2).
History: v1 of this report (c765876) verified provenance and licenses without downloading and asked for a decision.

## 1. Provenance and acquisition

| item | finding | source |
|---|---|---|
| distribution | LOVEU workshop @ CVPR 2023, Track 4 "Text Guided Video Editing": 76 videos, 4 editing prompts each, 32 or 128 frames, 480x480 | https://sites.google.com/view/loveucvpr23/track4 |
| organizer repository | showlab/loveu-tgve-2023 README: same statements; download `loveu-tgve-2023.zip` from the Google Drive link and unzip to `./data`; competition rules (registration, submission format, deadline) only; no other usage terms | https://github.com/showlab/loveu-tgve-2023 |
| paper (cite) | J. Z. Wu, X. Li, D. Gao, Z. Dong, J. Bai, A. Singh, X. Xiang, Y. Li, Z. Huang, Y. Sun, R. He, F. Hu, J. Hu, H. Huang, H. Zhu, X. Cheng, J. Tang, M. Z. Shou, K. Keutzer, F. Iandola, "CVPR 2023 Text Guided Video Editing Competition", arXiv:2310.16003, 2023. Videos collected from DAVIS, YouTube and Videvo, filtered from 100 to 76; 32 frames (DAVIS, Videvo) or 128 (YouTube); cropped and downscaled to 480x480 | https://arxiv.org/abs/2310.16003 |
| archive | `loveu-tgve-2023.zip`, **279,628,311 B, SHA-256 `ed2e7166c566c54d92bab1b5c0bae580ac9a3e768b88024e55181413321a0503`**, downloaded 2026-10-18 22:57 UTC from the official Drive file `1D7ZVm66IwlKhS6UINoDgFiFJp_mLIQ0W` (public, no sign-in; HTTP 200, `attachment; filename="loveu-tgve-2023.zip"`) | Drive |
| archive content | `LOVEU-TGVE-2023_Dataset.csv` (columns: Video name, Our GT caption, Style / Object / Background / Multiple Changes Caption, Source) and, per source folder `DAVIS_480p` / `videvo_480p` / `youtube_480p`, one mp4 per video (`480p_videos/`) and its JPEG frames (`480p_frames/<video>/`); 4,803 entries | archive listing |
| per-source counts | **DAVIS 16, Videvo 37, YouTube 23** (from the archive listing; matches the CSV's three sections). The paper does not state them; v1 of this report withdrew the same numbers from `../expT/trace_candidates.md` as unsupported - the archive now supports them (second erratum appended there) | archive |
| per-video source | the CSV's `Source` column gives a URL for every YouTube video (23, `youtube.com/watch?v=...`) and every Videvo video (37, `videvo.net/video/...`); empty for all 16 DAVIS videos | archive CSV, `loveu_population.csv` |

Copies: the archive and its extraction are in a scratch directory outside the repository; on the testbed,
`tools/eval/expw_loveu.py prepare` verifies the SHA-256 above and writes byte-for-byte copies of the 16 selected mp4s
plus one prompt file each to a directory that must stay outside version control.

## 2. License

| scope | statement | status |
|---|---|---|
| whole collection (organizer page, README) | "All videos are creative commons licensed." | documented; no CC variant or version |
| whole collection (paper) | "All of the videos have Creative Commons or other open licenses that allow us to modify and redistribute the videos." | documented; "other open licenses" unnamed |
| usage restrictions | none stated beyond the competition rules (organizer page, README, paper) | read 2026-10-18 |
| per video | **no license field** in the archive (the CSV has source URLs, not licenses); no per-video list on any official page | not available |
| organizer repository `LICENSE` | Apache-2.0 for the repository's **code**. It does **not** cover the video assets and is not claimed to | - |
| DAVIS videos (16) | official DAVIS pages state no license (citation request only); no source URL in the CSV | unverified |
| Videvo videos (37) | per-video URL in the CSV; Videvo's license page now redirects to freepik.com, so the 2023 terms per clip are not checked; two URL slugs contain "cc-by-natureclip" (an indication only, not verified) | unverified per clip |
| YouTube videos (23) | per-video URL in the CSV; the CC status of each upload is not checked | unverified per clip |

**Basis for the download (decision 2026-10-18).** The organizers who assembled and distribute the collection state
that every video is Creative Commons (or open) licensed for modification and redistribution, and no restriction is
published. Every Creative Commons variant permits non-commercial academic research use, which is the only use here
(local generation runs; no redistribution of the clips or derived videos). The archive was therefore downloaded.

**Limitations that remain (not blockers for W's measurements):**
- the CC variant and attribution text of each video are not verified; DAVIS videos have no source URL at all;
- **no original or generated frame of a LOVEU video goes into a publication figure** until its reuse permission and
  attribution are established per video (for YouTube / Videvo from the CSV URLs; for DAVIS from the DAVIS maintainers or
  the organizers). Quantitative results (TTFO, rejoin calls, promotion counts) may be reported with the dataset citation;
- the original videos and any generated videos are not redistributed (not committed, not uploaded).

## 3. Selection (the rule of section 4, executed 2026-10-18)

Sequence (each step committed before the next): population list `loveu_population.csv` (e5bb17a, no motion score) ->
motion scores `loveu_motion_scores.csv` -> subset `loveu_selection.csv`. No OTTER, Sink-promotion or rejoin result
exists for any LOVEU video; none was consulted.

- **Population:** 76 of 76 included (all decodable, >= 32 frames, four non-empty edit captions, CSV section = folder; no
  CSV name without a video and no video without a CSV row).
- **Allocation:** N = DAVIS 16, Videvo 37, YouTube 23 -> 3 each + 7 by largest remainder (1.474, 3.408, 2.118 -> 1, 3,
  2, + 1 to DAVIS) = **DAVIS 5, Videvo 6, YouTube 5**.
- **Selected (positions floor((j + 0.5) N_s / n_s) in motion order; prompt types cycled in (source, motion rank) order):**

| # | video_id (archive identifier) | source | frames | motion score | rank / N_s | prompt type |
|---|---|---|---|---|---|---|
| 0 | mbike-trick | DAVIS_480p | 32 | 5.576 | 1 / 16 | style |
| 1 | juggling-selfie | DAVIS_480p | 32 | 11.323 | 4 / 16 | object |
| 2 | ice-hockey | DAVIS_480p | 32 | 14.978 | 8 / 16 | background |
| 3 | hurdles-race | DAVIS_480p | 32 | 22.844 | 11 / 16 | multiple |
| 4 | swimmer | DAVIS_480p | 32 | 28.850 | 14 / 16 | style |
| 5 | cows-grazing | videvo_480p | 32 | 1.964 | 3 / 37 | object |
| 6 | seagull-flying | videvo_480p | 32 | 3.433 | 9 / 37 | background |
| 7 | earth-full-view | videvo_480p | 32 | 5.519 | 15 / 37 | multiple |
| 8 | aircraft-landing | videvo_480p | 32 | 8.911 | 21 / 37 | style |
| 9 | street-artist-painting | videvo_480p | 32 | 13.095 | 27 / 37 | object |
| 10 | butterfly-feeding-slow-motion | videvo_480p | 32 | 17.809 | 33 / 37 | background |
| 11 | eiffel-flyover | youtube_480p | 128 | 3.578 | 2 / 23 | multiple |
| 12 | cricket-bat-practice | youtube_480p | 128 | 7.481 | 6 / 23 | style |
| 13 | basketball-shot | youtube_480p | 128 | 9.394 | 11 / 23 | object |
| 14 | circus-ball-act | youtube_480p | 128 | 14.366 | 16 / 23 | background |
| 15 | audi-snow-trail | youtube_480p | 128 | 20.098 | 20 / 23 | multiple |

  Prompts (the archive's caption text, verbatim), GT captions and source URLs are in `loveu_selection.csv`.
- **Decoder sensitivity (reproducibility check, not a re-selection):** the scores above are computed with the project's
  pinned PyAV 13.1.0 and NumPy 1.24.4 (`pyproject.toml`). The first computation used PyAV 19.0.1 / NumPy 2.5.4
  (`loveu_motion_scores_av19_check.csv`): scores differ by at most 0.078 and the **selection is identical** (same 16
  videos, ranks and prompt types). The population list is identical under both versions.

## 4. Subset rule (as fixed in v1, unchanged)

1. **Population.** Every video in the archive with (a) a decodable video, (b) >= 32 frames, (c) all four edit
   captions, (d) no license exclusion. The population list is committed **before** any motion score is computed.
2. **Source.** The archive folder (`DAVIS_480p`, `youtube_480p`, `videvo_480p`); counts N_s read from the listing.
3. **Motion score** (an input property): decode every frame at the native 480x480, convert to luma (BT.601), take the
   mean absolute luma difference of each consecutive frame pair, average over pairs. Computed by a committed script run
   with `python -I` on the extracted directory (kept outside the repository).
4. **Allocation of 16 videos:** 3 per source minimum, the remaining 7 proportional to N_s by largest remainder (ties by
   source name, alphabetical); a source with fewer videos than its allocation gives all of them and the rest is
   re-allocated by the same rule.
5. **Within a source:** sort by motion score ascending (ties by file name) and take positions floor((j + 0.5) x N_s / n_s),
   j = 0 .. n_s - 1.
6. **Prompt per video:** order the 16 by (source name, motion rank) and assign the edit caption types in the cycle
   style, object, background, multiple (4 each); caption columns mapped to types by name.
7. Seeds 0 and 1 for every selected (video, prompt).

(d) excluded nothing: the archive carries no per-video license field to apply it to.

## 5. Video properties and pipeline compatibility

| group | videos | resolution | frames | FPS | duration | codec |
|---|---|---|---|---|---|---|
| DAVIS_480p | 16 (5 selected) | 480x480 | 32 (mp4 = JPEG frame count) | 10 | 3.2 s | H.264, yuv420p |
| videvo_480p | 37 (6 selected) | 480x480 | 32 | 10 | 3.2 s | H.264, yuv420p |
| youtube_480p | 23 (5 selected) | 480x480 | 128 | 14 | 9.14 s | H.264, yuv420p |

Per-video values (frames, FPS, duration, size, SHA-256 of each mp4): `loveu_population.csv`.

**Loader check** (`loveu_pipeline_check.json`; CPU; torch 2.6.0, torchvision 0.21.0, PyAV 13.1.0 = the project pins):
each selected mp4 loaded with the pipeline's own `streamv2v.inference_common.load_mp4_as_tensor(resize_hw=(480, 832))`,
the call `tools/proto_handoff.build_runtime` makes on every node: shape [3, T, 480, 832], values in [-1, 1], all finite,
T = 32 or 128. **All 16 compatible.** Note: torchvision 0.21's `read_video` fails with PyAV >= 14 (`metadata_errors`
argument removed); the testbed must keep the pinned PyAV 13.1.0. The model itself was not run (no GPU work in this step).

**Transformations** (all in memory, by the existing pipeline; nothing on disk is changed; OTTER and the loader are not
modified):
1. decode (torchvision `read_video`, PyAV backend) to RGB uint8;
2. resize each frame from 480x480 to 480x832 (`TF.resize`, antialias): a **horizontal stretch** (aspect 1:1 -> 1.73:1),
   because the pipeline's input size is fixed at 480x832;
3. scale to [-1, 1];
4. the harness repeats the clip until it covers the run (`video.repeat`, hard cut, as for every clip): the first call
   uses 5 frames and each later call 4, so a 32-frame clip wraps every 8 calls and a 128-frame clip every 32 calls
   (W1 330 calls: 1,325 frames = 42 / 11 repeats; W2 160 calls: 645 frames = 21 / 6 repeats);
5. the prompt is the selected caption, written as a one-line text file (`TextDataset` reads one prompt per line).
FPS plays no role: the pipeline consumes frames per call, not per second.

## 6. Remaining blockers before Experiment W (none of them is a dataset blocker)

1. Review and freeze of the W preregistration (and R, N); not done.
2. W implementation items (`../followup_common.md` section 4): value-cache Sink fingerprint, the W1 uninterrupted runner,
   the fixed observation horizon in the orchestrator, loop-boundary marking; then loopback and GPU shakedown.
3. On the testbed: `prepare` from the official archive into a directory outside version control on each of the four
   hosts (the archive download there is the same official link; the SHA-256 is checked).
4. Before any publication figure with LOVEU content: per-video permission and attribution (section 2).

## 7. Sources (read 2026-10-18)

https://sites.google.com/view/loveucvpr23/track4 ; https://github.com/showlab/loveu-tgve-2023 ;
https://raw.githubusercontent.com/showlab/loveu-tgve-2023/main/README.md ; https://arxiv.org/abs/2310.16003 ;
https://arxiv.org/html/2310.16003v1 ; https://drive.google.com/file/d/1D7ZVm66IwlKhS6UINoDgFiFJp_mLIQ0W/view ;
https://davischallenge.org/ ; https://davischallenge.org/davis2016/code.html ; https://davischallenge.org/davis2017/code.html ;
https://github.com/davisvideochallenge/davis2017-evaluation/blob/master/LICENSE ;
https://www.videvo.net/stock-video-footage-licenses/ (301 to freepik.com)

```bibtex
@article{wu2023cvpr,
  title   = {CVPR 2023 Text Guided Video Editing Competition},
  author  = {Wu, Jay Zhangjie and Li, Xiuyu and Gao, Difei and Dong, Zhen and Bai, Jinbin and Singh, Aishani and
             Xiang, Xiaoyu and Li, Youzeng and Huang, Zuwei and Sun, Yuanxi and He, Rui and Hu, Feng and Hu, Junhua and
             Huang, Hai and Zhu, Hanyu and Cheng, Xu and Tang, Jie and Shou, Mike Zheng and Keutzer, Kurt and Iandola, Forrest},
  journal = {arXiv preprint arXiv:2310.16003},
  year    = {2023}
}
```
