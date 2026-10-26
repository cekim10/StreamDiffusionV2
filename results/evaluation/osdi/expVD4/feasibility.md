# VD-4 feasibility assessment (2026-10-26; with preregistration draft 1)

## Code paths (emulator, `vc_emulate.py`; nothing in a frozen path changes)

| need | status |
|---|---|
| one snapshot at the reset with every component | exists: `serialize_live()` at the reset (VD, VD-2, VD-3 use it); the withheld Sink and the fast path are packed from it |
| oracle recent KV / decoder cache with the fast path | exists: VD's `keep_state` (restore_state with meta + in-flight + recent / vae in one call; encoder reset for decoder-only); new: run it before writing the temporary-Sink slots, because restore_state zeroes every KV slot |
| oracle Sink slots k / 3 | new, small: write the snapshot's sink K/V for the chosen slots with the source's positions (the snapshot's ring positions = the live meta, no re-rotation) |
| A1 aligned temporary Sink | new, small: `_shift_temporal_rope(k, freqs, delta)` per slot with delta = source pos - prepare pos (the function the bind and the realign already use; its round-trip error was measured in W1 as not bitwise but small) |
| V0 full injection | exists: `restore_full` (Phase 1 full path, refresh unfrozen); new: digest comparison against REF after the move |
| B0 reproduces VD-3 | exists: VD-3's per-call digests in `calls.csv` |
| quantization (exploratory) | new: fp8 e4m3 via torch.float8_e4m3fn (torch 2.6 on the hosts), int4 group-wise in plain torch; dequantized before the write |
| position / completeness / digest logging | new: per stream, in summary.json |
| inspection fields | `vc_export_clips.py`: new field list and per-session condition sets |
| aggregation | new `aggregate_vd4.py` reusing `aggregate_vd3.rules` / phase statistics with the frozen VD-3 thresholds |

GPU memory: the snapshot clones about 6 GB next to the live session (as in VD / VD-3, which ran on the same L40S with
46 GB). Copied-schedule cells (seed-1 OT-L, train OT-L) have no source-run positions; the emulator logs its own.

## Risks

- **A1 rotation error:** RoPE re-rotation is not bitwise (W1 / Task B); the error is reported per stream (max |K
  difference| of a rotate-and-back round trip) so A1's effect is not confused with numerical noise.
- **S3 with frozen refresh** differs from REF wherever REF promotes inside the window; REF's promotions in each window
  are counted and reported next to S3.
- **V0** could fail if any component the generation reads is outside the snapshot (none is known: Phase 1's full path
  reproduces REF); VD-4 stops if it does.
- **Inspection load:** four sessions in the worst case; each includes REF and B0 for its own false-positive baseline.

## Cost

Implementation and dry tests: about one working session. GPU: 40 runs (about 2.4 h) best case, 96 runs (about 5.7 h)
worst case on host D, staged (draft section 5). Inspection: 36-48 clips per session, up to four sessions.
