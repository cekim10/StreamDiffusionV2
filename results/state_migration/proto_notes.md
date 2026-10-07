# Prototype run 1 reading (results/state_migration/proto, harness 7e71a38) and what changed for run 2

## What run 1 established
- The two-process handoff works end to end over a bandwidth-limited TCP link: `full` restores bit-exactly (99 dB) at every bandwidth; `cold` stays at ~20 dB; `replay` lands at 28-33 dB; `ours` binds the sink and rejoins to 43-46 dB when the sink arrives before call 48, and never binds at 500 Mbps within the 60-call window.
- Full state at k=2 is **6.2 GB**, not 9.5 GB: the earlier figure double-counted the KV cache (kv_all plus its sink/recent halves). Corrected in the harness (state_ablation byte sums) and to be corrected wherever 9.5 GB was quoted.

## Harness artifacts found in run 1 (fixed in e4368ec)
1. **Timing offset.** The destination recorded t_mig when it sent READY, but the source only then ran its session to M (~16 s) and serialized. Every "first output" carried a ~17.4 s offset, so `ours`/`cold` stall looked like 17.5 s. Protocol is now PREP -> source runs to M and serializes -> PREPARED -> destination provisions -> READY (t_mig) -> transfer.
2. **Sink bind after the t_refresh realign.** At call 48 the stream rewinds RoPE positions and re-rotates cached keys. A sink that arrived after call 48 (1-2 Gbps) was written with its M-time rotation into a realigned window, which is why those points rejoined to only 30 dB while binds before call 48 rejoined to 44 dB. The bind now re-rotates each transferred sink slot by the per-slot position delta (`_shift_temporal_rope`).
3. **Serialization overhead.** 6.2 GB through Python cost ~18 s on top of link time at 10 Gbps (two host copies per side). Sender now streams numpy buffers directly and the receiver uses `torch.frombuffer`; the remaining cost is one device-to-host and one host-to-device copy, which is real.
4. Added `ours_refresh` (adaptive refresh left on during the gap, true sink overwrites at bind) because the frozen-refresh gap (16.5 dB) was worse than a cold restart (19.2 dB); run 2 shows whether letting the model promote its own sinks during the gap costs rejoin.

## Run 2 configuration
5 policies (ours, ours_refresh, cold, replay, full) x {500, 1000, 2000, 5000, 10000} Mbps, 80 post-migration calls so that a 500 Mbps sink (1.6 GB, ~27 s link time) binds inside the window.
