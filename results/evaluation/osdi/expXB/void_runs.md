# XB voided runs (2026-10-22)

Not evidence and not calibration. Kept on the testbed under renamed directories; never aggregated.

| runs | directories (on elves-01) | reason |
|---|---|---|
| exactness gate, 4 runs | `expXB_gate_dog`, `expXB_gate_bfly` -> `*_void1` | harness bugs 1 and 2 below: the source stopped generating at the trigger, so the switchover always happened at the trigger state (P-full final dirty set 0 MiB), and the "source keeps serving" path was never exercised |
| calibration grid, P-full settings 1-8 | `expXB_cal` -> `expXB_cal_void1` | the same bugs: round 1 took 1,630-1,647 s for 6,164 MiB (about 32 Mbps on a 1 Gbps cap) and round 2 found 0 MiB dirty |

**Bug 1 (source generation).** After `SOURCE_PREP`, the XB source started generating with `EXEC_START`. Its run state still
said "Sink verified, not bound", so the generation loop tried to unpack and re-bind its own Sink on its first call. On
the GPU runtime the source has no provisioned receive snapshot, so this fails, and the generation thread ended before
the first chunk. The dry runtime accepted the unpack, so loopback tests passed. Fix: XB passes `source_bound=True` with
`EXEC_START` (the source's live Sink is its own; nothing to unpack). Frozen paths never pass the flag. The dry runtime
now refuses an unpack without provisioned buffers, as the GPU runtime does.

**Bug 2 (pre-copy receiver).** `_xb_recv_frag` used `dict.setdefault(comp, {"buf": bytearray(comp_nbytes)})`, which
builds a zero-filled buffer of the whole component (up to ~2.8 GB for the VAE caches) for every fragment. Fix: allocate
once per component.

**New validity rule (XB, not frozen):** the source must keep generating until the first switchover
(`source_served_until_switch`). The loopback test also checks that round 1 moves data at >= 0.6 x the cap.

Consequences: the gate is re-run before calibration, and the calibration grid starts again from setting 1. The
reported timing of the voided P-full runs (about 27 min to TTFO) is a harness artifact and is never cited.
