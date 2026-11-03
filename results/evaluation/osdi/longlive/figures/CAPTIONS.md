# LongLive figures (measured; `tools/eval/plot_fig_longlive.py`; data `migrate_m1/`, rules `m1_prereg.md`)

**figll_a_gap.** Maximum output gap of one LongLive migration at 1 Gbps (median bar; dots are the 8 runs, 4 streams x
2 reps). Full = stop-and-copy of the 5.06 GiB state; Recache = LongLive's own KV recache at the cutover; OTTER = Continuity
Replay with a 96-call horizon (0.87 GiB sent). One served call takes 2.11 s, so 3.24 s is about 1.5 call intervals.

**figll_b_fidelity.** PSNR of each post-cutover call against the source's uninterrupted continuation (median line,
min-max band over the 8 runs). OTTER's output is bit-exact in every call of every run (drawn at "Exact"); Full is
bit-exact too (not drawn). The 12-call replay (the horizon used on SDV2) and Recache diverge (W3 28.7 / 26.9 dB).

Text, not figure: OTTER's destination is ready 11.2 s later than Full's (58.7 vs 47.5 s, +24 %), the cost of replaying
96 calls; LongLive is a port of the M1 mechanism, not the frozen SDV2 harness; M2 / M3 are not exercised.
