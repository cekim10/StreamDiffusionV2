# VD-3 Phase T approval (2026-10-25)

Approved by the user on 2026-10-25 ("APPROVE Phase T only"). This is **not** the VD-3 freeze.

Scope: `run_vc.py vd3 --phase base` on host D after the isolation checks: the seed-1 units (REF baseline and the
frozen-M1 OT-1 / OT-L controls), G1 (OT-1 vs the real W2 seed-1 run) and G3, metrics, the Phase T distributions
(`expVD3/vd3_phaseT.{md,json}`: natural REF variation, measurement noise, cross-seed differences as sensitivity, frozen
M1 as context) and the overlap measurement (`expVD3/vd3_overlap.json`).

Not approved: any VD-3 candidate condition (TSin, DR2, DR2+TSin, TSinKC, DR2stale, DR2noise), the thresholds, the
freeze. The thresholds are chosen after the Phase T distributions and the revised aggregation rules
(`expVD3/preregistration.md` draft 6, sections 3-4) are reviewed; candidate conditions run only after the freeze
(`expVD3_freeze.md`) with `expVD3/vd3_thresholds.json` committed (enforced by `run_vc.py`).
