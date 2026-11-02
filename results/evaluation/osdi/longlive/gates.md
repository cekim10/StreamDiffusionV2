# LongLive second model: gates before any migration experiment (DRAFT, nothing run)

Survey: `osdi/second_model_survey.md`. Port: `third_party/longlive` (LongLive 1.0 at 2426358, unmodified) and
`tools/longlive/ll_runtime.py` (one call = one 3-latent-frame block; per-call seeding; streaming VAE decode; explicit
state by OTTER role). CPU test on a tiny random model: `tools/longlive/test_ll_runtime.py`, ALL PASS. Labels: [V] verified
in code / the CPU test, [H] expectation, [D] decision for the user.

## State roles (480 x 832, bf16; sizes computed from shapes [H], measured by gate0)

| role | component | size [H] |
|---|---|---|
| durable | sink K / V: 3 latent frames x 30 layers, written by call 0 only (global_sink) [V] | 0.86 GB |
| ephemeral | window K / V (9 frames), cross-attention K / V (prompt-derived), VAE decoder cache | 2.59 + 0.09 + 1.89 GB |
| immediate | last 12 output latents, counters, cache end indices, prompt segment | 2.4 MB |

Per-call seeding (seed, call, step) makes the RNG stateless, so no RNG state migrates. Replay log = one output-latent
block per call (about 0.6 MB) [H]; T2V has no input frames.

## Gate 0, feasibility (one host)

`run_gates.sh gate0`: 60 calls, 10 warm-up; steady FPS, generate / decode time per call, peak GPU memory, inventory,
one KV recache. [D1] pass rule. Proposal: pass unless the session does not fit one L40S or a call takes > 2 s; FPS is
reported, not gated (SDV2 in the harness is 0.45x real time as well).

## Gate 1, determinism and reconstruction (two hosts)

`run_gates.sh gate1` on elves-01 and elves-02: reference R (60 calls, full export before call 30), a repeat, a full
import at 30, and four reconstructions of the state at 30 without the window / VAE cache:

| variant | what it ships / runs | expectation |
|---|---|---|
| recache | sink + 12 latents; LongLive KV recache; VAE warmed on the last block | inexact beyond layer 0 [V tiny] |
| replay_all | replay log of calls 0-29 (context pass + decode per block) | exact [V tiny] |
| replay_w3 / w6 / w12 | sink + replay of the last W calls from an empty window | approximate; converges with W [H] |

Required to continue [D2]: in-process repeat equal (latents, frames, state); full import equal; R chain equal on both
hosts. A failure is a runtime defect to fix before any experiment (e.g. a nondeterministic kernel), not a result.
Descriptive (no rule): each variant's time, layers exact, VAE cache exact, PSNR per call after 30.

## After the gates (to design with their numbers)

E10 single migration, like Fig. 7 (TTFO, delivery gap, bytes, quality): Full (whole state), Llumnix-style P-full,
ServerlessLLM-style R-full (= replay_all: exact, cost grows with the call index), P-sink + recache (LongLive-native,
the strongest simple baseline), OTTER (sink pre-copy + replay of the last W calls; [D3] whether the VAE decoder cache
is pre-copied or warmed). Needs a LongLive backend in `mobility_node.py` (harness change + regression), written after
Gate 1 fixes W and the VAE choice. [D4] prompts: LongLive `example/interactive_example.jsonl` (first prompt of each
set), seeds 0-1, with and without one prompt switch.

## Commands

```
each host (once, after Fig. 13 ends):  bash tools/longlive/run_gates.sh setup
elves-01:                               bash tools/longlive/run_gates.sh gate0
elves-01:                               bash tools/longlive/run_gates.sh gate1
elves-02:                               bash tools/longlive/run_gates.sh gate1
```

## Results (2026-11-02; run commit f48919f6 + checkpoint path fix 4dec2ed1 / symlinks; measured)

Environment: elves-01 and elves-02 identical except `hf-xet` (1.6.0 vs 1.7.0; download transport only). Setup added
only easydict 1.13 and peft 0.21.2 (uv dry-run, freeze diff on elves-01); torch 2.6.0+cu124 unchanged.

**Gate 0 (elves-01): NOT PASSED under the D1 proposal (call > 2 s).** 50 calls after 10 warm-up: median call 2,112 ms
(generate 1,365 + decode 748), 5.69 FPS (12 frames per call); peak GPU memory 24.2 GB (fits one L40S, 48 GB); one KV
recache 1,227 ms. Inventory (measured): sink K / V 0.86 GB (durable), window K / V 2.59 GB, cross-attention K / V
0.09 GB, VAE decoder cache 1.89 GB (ephemeral, 4.57 GB), latent buffer 2.4 MB (immediate). The 2 s limit was a
proposal written before the run; whether to continue is the user's decision, recorded here.

**Gate 1 (elves-01, elves-02): PASSED (D2).** In-process repeat == R and full import at call 30 == R (latents, frames,
state) on both hosts; R chain 1be3fa55268df638 on both (cross-host determinism). Reconstructions of the state at call
30 (no window, no VAE cache), scored on the next 30 calls (identical on the two hosts except time, < 1 %):

| variant | time (s) | window layers exact | VAE cache exact | PSNR first / median / min (dB) |
|---|---|---|---|---|
| recache (P-sink + LongLive recache) | 2.0 | 1 / 30 | no | 30.8 / 26.6 / 19.5 |
| replay_all (calls 0-29) | 30.5 | 30 / 30 | yes | 99 / 99 / 99 (bit-exact, latents 30 / 30) |
| replay_w3 | 3.1 | 1 / 30 | no | 26.6 / 26.7 / 20.3 |
| replay_w6 | 6.1 | 2 / 30 | no | 39.9 / 28.7 / 22.2 |
| replay_w12 (OTTER analogue) | 12.3 | 5 / 30 | no | 51.2 / 29.4 / 24.1 |

Reading: replay from call 0 is exact at about 1.0 s per replayed call (about 2x faster than a live call). Sink +
last-W replay does not become exact: exact layers grow slowly with W (1 / 2 / 5) and the output drifts to a 29.4 dB
median after a 51 dB first call, about 3 dB above recache at 6x its time. [H] one layer becomes exact per window
turnover or so, so a bounded W would need on the order of 3 x 30 = 90 calls; not tested. The SDV2 OTTER replay rule
therefore does not carry over to LongLive as is; E10's OTTER design is reopened (D3).
