# Experiment VD-2 - freeze record (2026-10-24)

Frozen document: `expVD2/preregistration.md` (revised draft 2, approved 2026-10-24). The freeze commit is the commit
that adds this file. Implementation: emulator-only conditions in `tools/eval` (commit 5c638cf; `test_vc.py` ALL PASS,
dry run of all 16 conditions per input valid). No mechanism (M1 / M2 / M3-v2) and no frozen result changes.

**Frozen:** the primary research question; conditions DR-1, DR-2, RP-1, TS-in, TS-out, DR-2 + TS-out, RP-1 + TS-out
at OT-1 and OT-L on dog and butterfly-feeding-slow-motion (28 emulations) with frozen M1 (VC-1's OT runs) as the
control; DR-4 as an exploratory diagnostic under the section-4 trigger and outside every verdict; metrics (VC's V1-V5,
the descriptive REF-band restoration criterion, per-layer decoder-cache fidelity, serial reconstruction cost measured
per mechanism and per combination as a whole, bytes added); hypotheses VD2-H1..H6 with the thresholds of section 5 and
the preferred 0.3 s cost target reported; the mapping to the next step; relevance-aware binding excluded.

**Run:** host D after `run_vc.py preflight`; `run_vc.py vd2 --host D --frames_dir <local>` (about 1.5-2 h), then
`aggregate_vd2.py` on elves-01. DR-4 only via `--with_dr4` if the trigger fires.
