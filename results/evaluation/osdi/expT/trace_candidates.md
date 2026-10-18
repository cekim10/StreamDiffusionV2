# Experiment T - 2. Public trace candidates (DRAFT, 2026-10-17)

Every provenance and license statement below was read on the primary page on 2026-10-17 (links given); where a fact
could not be confirmed it is marked **unverified**, and nothing is assumed. No file has been downloaded yet (a
download needs the user's approval; some sources need an account the user must use).

## A. Mobility (handover timing -> move schedule)

| id | dataset | provenance | license / access (as read) | granularity, duration, fields | mapping to OTTER | status |
|---|---|---|---|---|---|---|
| M-a | **Lumos5G 1.0** (UMN, IMC'20) | IEEE DataPort https://ieee-dataport.org/node/3598; project site networking.umn.edu/lumos5g | "Lumos5G 1.0 dataset is licensed under the Creative Commons Attribution 4.0 International License." The page says both "requires an IEEE DataPort Subscription" and that "Open Access data files are available to all users upon login" (inconsistent; login required either way) | per-second rows ("the sequence number acts like an index or a per-second timeline"); fields include `tower_id` (anonymized), latitude/longitude, `movingSpeed`, iPerf per-second downlink throughput; 1.53 MB zip; a 1300 m loop in downtown Minneapolis (mmWave 5G) | a change of `tower_id` = handover; inter-handover times -> T_m sequence; cell-to-site clustering k = 1, 2, 4 (`deployment_model.md`). Throughput column is last-mile and is **not** used as inter-edge capacity | candidate (primary); fields to confirm after download |
| M-b | **UCC 5G dataset** (Raca et al., MMSys'20, "Beyond throughput, the next generation") | GitHub https://github.com/uccmisl/5Gdataset; paper record https://cora.ucc.ie/handle/10468/9826 | the GitHub page lists "GPL-3.0 license" for the repository (whether it is meant to cover the data files is **unverified**); the UCC record carries only the ACM author-version notice for the paper | "client-side cellular key performance indicators (KPIs) comprised of channel-related metrics, context-related metrics, cell-related metrics and throughput information", logged with G-NetTrack Pro; mobility patterns "static and car"; per-field list, granularity and trace count **unverified** (inside `5G-production-dataset.zip`) | if a cell-identifier field is present: handover timing for driving mobility (Ireland) | candidate (secondary); field list and data license to confirm |
| M-c | UCC 4G LTE dataset (MMSys'18) | UCC record https://cora.ucc.ie/handle/10468/6400 | **unverified** (data location and license not found) | per a search summary of the abstract: 135 traces, ~15 min average, one sample per second (**unverified** on the primary page) | as M-b | not selected unless verified |

## B. Inter-edge variability (cross-traffic on a site uplink)

| id | dataset | provenance | license / access (as read) | granularity, duration | mapping | status |
|---|---|---|---|---|---|---|
| X-a | **MAWI samplepoint-F** (WIDE) | https://mawi.wide.ad.jp/mawi/ ; FAQ https://mawi.nezu.wide.ad.jp/mawi/faq.html | "You may use WIDE traffic data for only research purposes." "Actions that trespass upon users' privacy are prohibited." (archive page); IP addresses anonymized (Crypto-PAn since August 2015, per the FAQ); no citation rule stated | daily tcpdump packet traces of the 1 Gbps transit link in Tokyo to NTTC GIN (AS2914); since July/August 2023 the 10 Gbps BBIX link is also captured (FAQ / archive page). Daily capture length: 15 min (14:00-14:15 JST) per a MAWI slide deck (secondary; **verify per trace**) | per-second byte counts per direction -> utilization u(t) of the 1 Gbps link -> available = C (1 - u(t)) on an edge site's uplink. Use traces before July 2023 (single 1 Gbps link) | candidate (primary); requires computing per-second series from pcaps (large downloads) |
| X-b | GEANT / TOTEM intradomain traffic matrices (Uhlig et al., CCR 2006) | https://totem.info.ucl.ac.be/dataset.html | "Please refer to the following paper when using the traffic matrices for any publication" (Uhlig, Quoitin, Balon, Lepropre, CCR 36(1), 2006); router IDs and absolute time anonymized | one matrix per 15-min bin, ~4 months, kbps, TOTEM XML | 15-min resolution cannot express variability within a 1-3 min restoration; at most a utilization-level prior for choosing MAWI segments | not selected for dynamics |
| X-c | M-Lab NDT | https://www.measurementlab.net/data | data: "No Rights Reserved Creative Commons Zero Waiver" | per-test client-to-server throughput | end-to-end tests are usually limited by the client's access link (last-mile); applying them to inter-edge links would violate the mapping rule | rejected for inter-edge |
| - | CAIDA passive traces | not investigated (access under an acceptable-use agreement, **unverified**) | - | - | - | not considered |

Rule kept from the request: cellular last-mile throughput (M-a, M-b throughput columns, M-c, X-c) is never applied to
inter-edge links.

## C. Video-to-video workloads (Sink-version stability, `sink_stability_plan.md`)

| id | dataset | provenance | license (as read) | content | fit to the pipeline | status |
|---|---|---|---|---|---|---|
| W-a | repository clips | `examples/` (original/dog, bird, boxing, train + prompt files; dragon_a/b prompts) | as distributed with the repository | the Experiment D workloads | native | used |
| W-b | **LOVEU-TGVE-2023** (CVPR'23 text-guided video editing) | https://sites.google.com/view/loveucvpr23/track4 ; paper arXiv:2310.16003 | "All videos are creative commons licensed." (no version given; the paper: 16 from DAVIS, 37 Videvo, 23 YouTube, all under licenses that allow modification and redistribution) | 76 videos, 480x480, 32 or 128 frames, four editing prompts per video | video + text prompt = v2v input; resized to 480x832; clips are shorter than a run (~1,300 frames) and would loop (loop boundaries must be marked) | candidate; per-video license version **unverified** |
| - | DAVIS videos | davischallenge.org | annotations: CC BY 4.0 (challenge pages); video license **unverified** | - | - | not used directly |
| - | VBench, EvalCrafter | - | not investigated further | text-to-video prompt suites | the harness is video-to-video (`configs/wan_causal_dmd_v2v.yaml`; the Runner feeds input frames every call); a T2V branch exists in `streamv2v/inference.py` but not in the harness path | not usable without source videos |

## Erratum (2026-10-18, appended; nothing above edited)

Re-reading the primary sources for Experiment W (`../expW/loveu_tgve_verification.md`): (1) the per-source counts in row
W-b ("16 from DAVIS, 37 Videvo, 23 YouTube") are **not** stated in the paper (arXiv:2310.16003v1 HTML: "We begun by
collecting 100 videos from DAVIS, YouTube, and Videvo ... filtered it down to 76 videos total"; Table 1 lists the sources
without counts); their origin is unknown and they are withdrawn. The paper states 32 frames for DAVIS and Videvo, 128
for YouTube. (2) The DAVIS row's "annotations: CC BY 4.0 (challenge pages)" is not found on the official pages read on
2026-10-18 (davischallenge.org, davis2016/code.html, davis2017/code.html state no license; the evaluation-code
repository's BSD-3-Clause license covers the code only); it is **unverified**.

## Erratum 2 (2026-10-18, appended)

The official archive (`loveu-tgve-2023.zip`, SHA-256 ed2e7166...0503, downloaded 2026-10-18 for Experiment W) contains
16 DAVIS, 37 Videvo and 23 YouTube videos. The per-source counts withdrawn in the erratum above are therefore correct;
their source is the archive (and its CSV), not the paper. The DAVIS license remains unverified.
