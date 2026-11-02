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
