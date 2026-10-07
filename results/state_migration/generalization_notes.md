# Generalization reading (results/state_migration/gen, 10 runs, all bit-exact floors)

Grid: original/bird/boxing x k in {1,2,4} x seed 0, plus original seed 1 k=2. Key configs only. PSNR vs each run's own baseline.

## Claim tally under the pre-set thresholds
IMMEDIATE 4/7 (k>=2 runs), DURABLE 8/10, EPHEMERAL 9/10.

## What holds in every run
- The sink is required for continuity: with meta + in-flight but no sink, long-term PSNR is 15-25 dB in all 10 runs (a different valid stream).
- The in-flight row helps in every k>=2 run: M+0 goes from 10-15 dB (lost) to 15-21 dB (transferred), long-term gains +1 to +10 dB. The 6 dB threshold was arbitrary; the effect size is content- and k-dependent.
- Recent KV and VAE caches heal without transfer in 9/10 runs (>= 35 dB long-term); the 10th (bird k=4) is still climbing at M+39 (32 / 30 dB), i.e. slow healing, not permanent divergence.
- A sink swapped in 8 chunks late rejoins in every run; rejoin takes 0-6 calls in 7 runs and 8-14 calls in bird k=2/k=4 and boxing k=4. The local placeholder keeps the gap 1-3 dB closer and never slows rejoin.
- k=1 is the cleanest case: sink + metadata alone restores 43-49 dB (there is no in-flight row).

## The variable that explains the weak runs: adaptive sink refresh frequency
| run | true mid-session refreshes before M (detector events at 4 and 48 are the first fill and the t_refresh realign) | sink slots at M | policy M+16.. | rejoin (zero / local) |
|---|---|---|---|---|
| original k1/k2/s1k2, bird k1, boxing k1/k2 | none | [0,1,6] | 35-49 | 0-6 |
| original k4 | none before M (32, 33 after) | [0,1,6] | 45 | 10 / 6 |
| boxing k4 | 14, 20 | [22,16,6] | 42 | 9 / 5 |
| bird k2 | 20 | [22,1,6] | 30 | 9 / 8 |
| bird k4 | 5, 21 | [6,23,7] | 24 (rising) | 14 / 13 |

When the adaptive refresh (`adapt_sink_threshold: 0.2`) promotes recent frames into the sink, the "durable" anchor is itself derived from ephemeral content and later refresh decisions become sensitive to any perturbation at the migration boundary. More refreshes (higher motion, larger k with more batch rows evaluating the similarity test) mean slower healing and slower rejoin. The semantics hold; their timescales stretch with the refresh rate.

## Consequences for the design
1. The policy (fast path: in-flight + metadata ~2 MB; background: sink 1.6 GB; nothing else) is confirmed on 10/10 runs for the qualitative claims. Healing time, not the semantic class, varies with content.
2. The sink's refresh history is part of the durable state. Promotions that happen before migration travel with the sink; promotions during the gap must be suppressed at the destination (refresh off while waiting, as in the ph_* configs) or they cannot be undone by the late swap.
3. For the paper: report continuity as a time series (gap, rejoin, long-term) with the refresh events marked, and include a high-motion stress case rather than hiding it.

## Caveats
- bird and boxing are 1080x1920 portrait sources squeezed to 480x832; fine for claim checks, not for visual quality judgments.
- 40 post-migration calls is too short for the slowest run; extend to 80 when replicating the stress case.
- The refresh detector flags the t_refresh realign at call 48 as an event; ignore it when counting refreshes.
