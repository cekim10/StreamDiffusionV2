# OTTER OSDI evaluation roadmap (fixed 2026-10-20)

Order agreed with the user after the OSDI-readiness review (claims list `paper_claims.md`, sections B and D):

1. **M3E results** - final OTTER (M3-v2) end-to-end (`expM3E/preregistration.md`, frozen abf74d6): GPU shakedown and
   48-run sweep on the testbed, then the report and the claims-list update (M3-2, gap D4).
2. **Workload expansion of the core mobility experiments** - repeat the key repeated-mobility / network-adaptation
   scenarios (R / M3E) on 2-3 refresh-heavy clips besides dog (currently dog only). New preregistration.
3. **External baselines (re-implemented in OTTER's harness)** - Llumnix-style pre-copy and ServerlessLLM-style recompute
   (both OSDI '24, LLM serving), plus a wait-for-Sink internal ablation. Older or distant-domain methods (VM post-copy,
   edge proactive sync) are related work only; proactive placement is OTTER's own M3 (ExpD C / D). The fairness rule
   (whether the source may keep serving after the trigger, and how remote-serving time is charged) is fixed in the
   preregistration before any implementation.
4. **Second model** - port M1 / M2 to another streaming video diffusion model (or, at minimum, another configuration of
   StreamDiffusionV2) to show that the state decomposition generalizes. Candidate survey and porting-cost estimate run
   in parallel from now; implementation after step 3.
5. Afterwards, if time allows: realism / scale (trace-driven evaluation, ExpT, or a measurement-calibrated simulator),
   continuous camera input, multi-session interference.

Standing rules unchanged: preregister before runs, never change criteria after seeing results, report negative results,
no commits or pulls on the testbed while a sweep runs, frozen results are never modified.

Input-clip note: the workload called "dog" is `examples/original.mp4`, a tabby **cat** walking on grass, with the prompt
"A dog walks on the grass, realistic"; papers and reports must describe it that way.
