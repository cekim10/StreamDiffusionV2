# E8: the two remaining reuse assumptions (offline; plan fixed before the run, 2026-10-28)

Same probe as E7 (`tools/eval/m2_reuse_probe.py`, with per-entry statistics added). Each run is offline, in one
process. There is no M2 protocol.

- **A, multiple realignments:** dog s1, c0 = 31, M1 = 64, interval 100 calls (M2 = 164). Realignments come every
  ~45 calls (48 / 49 in E4, 93 / 94 in E7), so this interval should hold at least two (about 93 / 94 and 138 / 139).
- **B, refresh-heavy:** butterfly s1, same c0, M1 and interval. Fixing the interval lets B also test the
  multi-realignment question.

## Compared, per run, against B's exact Sink at M2 (block-level bitwise, the Sink digest)

- **ordered:** every event in call order.
- **current_values:** each refreshed entry gets B's current K / V. Every unrefreshed entry gets each recorded shift in
  its original order. This is the strategy E8 asks to apply.
- **summed_shift:** as current_values, but one shift by the summed delta. It is not assumed equivalent: it is tested
  on the entries shifted more than once.
- **Diagnostics:** last_written and patches_only, as in E7.

## Reported

- Equality per strategy: blocks and digest.
- Mismatching blocks, related to how many times each entry was shifted.
- Refresh events, distinct refreshed entries, repeated refreshes and the per-entry histogram.
- Shift events and the shifts-per-entry histogram.
- Update bytes: latest K / V per refreshed entry, plus shift metadata, plus positions. Compared with sending every
  refresh event, and with the 1.73 GB fresh base.
- GPU reconstruction time, and host -> GPU time of the retained Sink.

## Reading

- **Multiple realignments need ordered replay** if summed_shift fails on any block while current_values passes.
- **Exact reuse holds for a run** if current_values (or ordered) is digest-equal and 360 / 360 blocks equal.
- **If both runs pass,** a minimal M2 protocol for a first real A -> B -> A migration is proposed. Nothing is
  implemented.
