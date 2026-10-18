# LOVEU-TGVE-2023: provenance and license verification, and the W subset rule (2026-10-18)

**Nothing was downloaded.** Only public web pages were read on 2026-10-18 (links in section 6). Page content was treated
as data. Outcome: provenance is official and consistent; the license is stated **only at collection level**, and no
official source lists a license per video. Under the approved rule ("download only files whose use is permitted"),
the per-file permission cannot be verified from official sources, so the archive was **not** downloaded; a decision
is needed (section 3).

## 1. Provenance (verified)

| item | finding | source |
|---|---|---|
| organizer page | LOVEU workshop @ CVPR 2023, Track 4 "Text Guided Video Editing": "Our dataset consists of 76 videos. Each video has 4 editing prompts." "Each video consists of either 32 or 128 frames, with a resolution of 480x480." | sites.google.com/view/loveucvpr23/track4 |
| organizer repository | showlab/loveu-tgve-2023 README: same statements; download `loveu-tgve-2023.zip` from the same Google Drive file and `unzip ... -d ./data`; submission layout folders `DAVIS_480p`, `youtube_480p`, `videvo_480p` | github.com/showlab/loveu-tgve-2023 |
| paper | Wu et al., "CVPR 2023 Text Guided Video Editing Competition", arXiv:2310.16003 (authors incl. Mike Zheng Shou, Kurt Keutzer, Forrest Iandola): "We begun by collecting 100 videos from DAVIS, YouTube, and Videvo" ... "filtered it down to 76 videos total"; "we reduce each video to 32 frames (for DAVIS and Videvo) or 128 frames (for YouTube)"; "We crop and downscale the videos to 480x480"; four edit captions per video: style, object, background, multiple changes (ChatGPT-drafted, manually edited) | arxiv.org/abs/2310.16003, HTML v1 |
| download file | Google Drive file id `1D7ZVm66IwlKhS6UINoDgFiFJp_mLIQ0W`, name `loveu-tgve-2023.zip` (the same link on the organizer page and in the README); size not shown on the view page; whether it downloads without signing in is **not verified** (no download attempted) | Drive view page |
| per-source counts | **not stated** by any official source (the paper's Table 1: 76 videos, "DAVIS, YouTube, Videvo", 304 edit prompts). The counts "16 / 37 / 23" in `../expT/trace_candidates.md` are unsupported and withdrawn (erratum appended there) | paper HTML |

## 2. License (what the official sources say)

| scope | statement | status |
|---|---|---|
| whole collection (organizer page and README) | "All videos are creative commons licensed." | documented; no CC variant or version given |
| whole collection (paper) | "All of the videos have Creative Commons or other open licenses that allow us to modify and redistribute the videos." | documented; "other open licenses" unnamed |
| per video | no license, source URL or attribution list on the organizer page, in the README or in the paper | **not available from official sources** (the archive may contain metadata; unknown without downloading) |
| repository | `LICENSE`: Apache-2.0 (the repository's code); the README does not say it covers the videos | documented; not applicable to the videos as far as stated |
| DAVIS (original source) | davischallenge.org, `davis2016/code.html`, `davis2017/code.html`: no license statement, only a citation request; `davisvideochallenge/davis2017-evaluation` LICENSE is BSD-3-Clause for the code only | **unverified** for the videos |
| Videvo (original source) | the former license page `videvo.net/stock-video-footage-licenses/` now redirects (HTTP 301) to freepik.com; today's terms need not be the 2023 terms | not evaluated |
| YouTube (original source) | per-video Creative Commons status not listed anywhere official | unverified |

**Assessment.** The organizers, who assembled and redistribute the collection, state that every video is under a
Creative Commons or other open license permitting modification and redistribution. That is a collection-level
representation; the CC variant per video (e.g. BY vs BY-NC, which differ in attribution and commercial terms) cannot be
checked, and attribution (required by every CC license) cannot be given per video without the sources. Research use
inside this project is consistent with every CC variant; publishing frames of these videos in the paper would need the
per-video attribution.

## 3. Decision needed (no download until then)

1. **Accept the organizers' collection-level statement for internal research use** (no redistribution of the clips or
   derived videos; no LOVEU frames in figures until per-video attribution is established). Then download the one
   archive (official Drive link), record its SHA-256 and listing, and, if the archive contains per-video license
   metadata, exclude any video whose stated license does not permit this use **before** the subset rule runs (exclusions
   recorded); or
2. **ask the organizers** (contact listed on the track page: loveu-tgve@googlegroups.com) for the per-video source and
   license list first. Sending that message is an action on your behalf and needs your explicit approval; or
3. **W on the repository clips only** (4 workloads x 2 seeds = 8 units), every W statement limited to them.

## 4. Deterministic, content-diverse subset rule (fixed now; uses input properties only, never OTTER outcomes)

Applies only after option 1 or 2 permits the download.

1. **Population.** Every video in the archive with (a) a decodable video, (b) >= 32 frames, (c) all four edit
   captions, (d) no license exclusion (section 3). The population list (name, source folder, frame count) is committed
   **before** any motion score is computed.
2. **Source.** The archive folder (`DAVIS_480p`, `youtube_480p`, `videvo_480p`); counts N_s read from the listing.
3. **Motion score** (an input property): decode every frame at the native 480x480, convert to luma (BT.601), take the
   mean absolute luma difference of each consecutive frame pair, average over pairs. Computed by a committed script run
   with `python -I` on the extracted directory (kept outside the repository; the script lives in the repository).
4. **Allocation of 16 videos:** 3 per source minimum, the remaining 7 proportional to N_s by largest remainder (ties by
   source name, alphabetical); a source with fewer videos than its allocation gives all of them and the rest is
   re-allocated by the same rule.
5. **Within a source:** sort by motion score ascending (ties by file name) and take positions floor((j + 0.5) x N_s / n_s),
   j = 0 .. n_s - 1 (evenly spaced across the motion range).
6. **Prompt per video:** order the 16 by (source name, motion rank) and assign the edit caption types in the cycle
   style, object, background, multiple (4 each). The archive's caption column names are mapped to these four types by
   name only.
7. Seeds 0 and 1 for every selected (video, prompt). The selected list, motion scores and the rule's intermediate values
   are committed before any W1 / W2 run.

Known property, not a selection criterion: the 32-frame clips (DAVIS, Videvo) repeat every 8 calls in the harness and the
128-frame clips every 32 calls; W reports them as separate groups (`preregistration_draft.md` sections 3 and 9).

## 5. Not done

No download, no preprocessing, no GPU run, no contact with the organizers.

## 6. Sources (read 2026-10-18)

https://sites.google.com/view/loveucvpr23/track4 ; https://github.com/showlab/loveu-tgve-2023 ;
https://arxiv.org/abs/2310.16003 ; https://arxiv.org/html/2310.16003v1 ;
https://drive.google.com/file/d/1D7ZVm66IwlKhS6UINoDgFiFJp_mLIQ0W/view ; https://davischallenge.org/ ;
https://davischallenge.org/davis2016/code.html ; https://davischallenge.org/davis2017/code.html ;
https://github.com/davisvideochallenge/davis2017-evaluation/blob/master/LICENSE ;
https://www.videvo.net/stock-video-footage-licenses/ (301 to freepik.com)
