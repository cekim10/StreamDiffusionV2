# Second-model survey for OTTER (2026-10-20; roadmap step 4, survey only)

Desk survey of public repositories and papers (sources linked; "unverified" = not confirmed from a source). KV sizes are
derived arithmetic (Wan-1.3B: 30 blocks, 12 x 128 heads, 1,560 tokens per latent frame at 480 x 832, 16-bit: ~0.268 GiB
per latent frame). Nothing was downloaded or run. **All candidates except MAGI-1 are Wan2.1-based and descend from the
CausVid / Self-Forcing code: a second model from this set shows the decomposition under a different cache policy, not a
different architecture.**

| candidate | code / weights licence | mode | state relevant to OTTER | L40S fit | porting |
|---|---|---|---|---|---|
| **LongLive-1.3B** (NVIDIA, ICLR 2026, arXiv 2509.22622; github.com/NVlabs/LongLive) | code Apache-2.0 (since 2025-11-01); HF weights tagged CC-BY-NC-SA-4.0 | T2V, interactive prompt switching; blocks of 3 latent frames, 4 steps | 12-frame KV (~3.2 GiB): 3-frame **frame sink** (~0.8 GiB, protected) + 9 rolling frames; cross-attention cache ~94 MB; **KV-recache path exists** (`_recache_after_switch`); no streaming VAE decoder cache in the repo | docs: >= 40 GB, tested A100 / H100; L40S unverified | low-medium |
| **Rolling Forcing** (Tencent ARC / NTU, ICLR 2026, arXiv 2509.25161) | LICENSE "academic use only" vs HF tag MIT (conflict) | T2V, long streaming | 24-frame KV (~6.4 GiB), sink = first block (3 frames, ~0.8 GiB); rolling window of 4 blocks at staggered noise levels (in-flight, like SDV2's stream batch); no recache path | unverified | medium |
| Self-Forcing (NeurIPS 2025) | Apache-2.0 / Apache-2.0 | T2V, fixed 21 frames | full non-rolling KV (~5.6 GiB), no effective sink; streaming VAE decoder in the demo | >= 24 GB | weak fit |
| CausVid (CVPR 2025) | CC-BY-NC-SA / CC-BY-NC | T2V | full KV, re-prefill; direct ancestor of SDV2 (not independent evidence) | - | - |
| Krea Realtime 14B | weights Apache-2.0, code CC-BY-NC-SA | V2V supported | 3-frame KV recomputed on eviction: almost no durable KV (degenerate case) | >= 40 GB recommended, unverified | high |
| MAGI-1 4.5B-distill | - | chunk-wise AR, bounded KV range | the only architecturally distinct option; code-level state not verified | >= 24 GB | high |

StreamDiffusionV2's own configurations (local repo): `wan_causal_dmd_v2v_fast.yaml` (5 KV frames, 2 sink, no adaptive
refresh), `wan_causal_dmd_t2v.yaml` (21 KV frames, no sink), `--step` 1-4, free resolution; 14B on one L40S likely does
not fit (paper reports 4 x H100). These are a cheap sensitivity axis, not a second model.

**Recommendation of the survey:** (1) LongLive-1.3B (frame sink + short window map onto durable / ephemeral; existing
recache = destination-side reconstruction; prompt switching is a scenario SDV2 cannot do; closest code); (2) Rolling
Forcing (staggered in-flight window exercises the immediate class; larger ephemeral share; licence conflict, no recache).
Risks for both: T2V only (no VAE encoder cache), no streaming VAE decode in the repo, L40S fit to be measured.
