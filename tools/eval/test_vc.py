#!/usr/bin/env python3
"""VC-0 local tests (implementation_plan.md section 5): fake runtime and CPU only; not evidence.

    python tools/eval/test_vc.py      # needs numpy, av, opencv, scikit-image, Pillow
"""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
PY = sys.executable
FAILS = []


def check(cond, msg):
    print(("  [ok] " if cond else "  [FAIL] ") + msg)
    if not cond:
        FAILS.append(msg)


def main():
    import vc_check as vc
    import vc_frames as vf
    import vc_playback as vp
    import vc_schedules as vs

    print("- 1 schedules vs the frozen source runs")
    out = vs.build()
    check(not vs.check(out), f"every condition matches its source run ({sum(len(u['conditions']) for u in out['inputs'].values())} conditions)")
    tr = next(c for c in out["inputs"]["train"]["conditions"] if c["id"] == "OT-L")
    check(tr["counterfactual"] and "counterfactual" in tr["label"], "train OT-L labelled a counterfactual replay under a copied schedule")
    w = next(c for c in out["inputs"]["dog"]["conditions"] if c["id"] == "WFS-1")
    check(w["resets"] == w["binds"] and w["skipped_input_calls_harness"] == [] and w["skipped_input_calls_live_realtime"][0] == w["resets"][0] and w["stall_s"] > 10,
          f"WFS-1: Sink bound at the reset call, stall {w['stall_s']:.2f} s, live real-time skip {len(w['skipped_input_calls_live_realtime'])} input chunks from call {w['resets'][0]}")
    r = next(c for c in out["inputs"]["dog"]["conditions"] if c["id"] == "OT-R")
    check(len(r["resets"]) == 3 and "not M3-v2" in r["label"], "OT-R: three moves, M1 + M2 (split), labelled not M3-v2")

    tmp = Path(tempfile.mkdtemp(prefix="vc_test_"))
    try:
        print("- 2 dry emulation (dog, audi-snow-trail; all seven conditions) and G3")
        for inp in ("dog", "audi-snow-trail"):
            r_ = subprocess.run([PY, "tools/eval/vc_emulate.py", "--input", inp, "--dry_run", "--frames_dir", str(tmp / "frames"), "--out_root", str(tmp / "expVCt")],
                                cwd=ROOT, capture_output=True, text=True)
            nc = sum(1 for c in out["inputs"][inp]["conditions"] if c["kind"] not in ("vd2", "vd3"))   # VD-2 / VD-3 conditions run only on request
            check(r_.returncode == 0 and r_.stdout.count("valid True") == nc, f"{inp}: {nc} conditions emulated (7 VC{' + 16 VD' if nc > 7 else ''}; VD-2 / VD-3 skipped by default), all valid")
            ok, why, info = vc.g3(tmp / "expVCt" / f"{inp}_s0", out)
            check(ok, f"{inp}: G3 passes on REF + {nc} streams {why[:2]}")
            if nc > 7:
                vd = [json.loads((tmp / "expVCt" / f"{inp}_s0" / c["id"] / "summary.json").read_text()) for c in out["inputs"][inp]["conditions"] if c["kind"] == "vd"]
                check(len(vd) == 16 and all(s_["vd"] and s_["vd"]["mask_violations"] == 0 for s_ in vd), f"{inp}: 16 VD conditions recorded with mask / keep settings, no mask violations")
            if inp == "dog":
                wf = info["WFS-1"]
                check(wf["first_output_input_chunk"] == wf["resume_call"] - 1, f"WFS-1: first output after the resume belongs to input chunk {wf['first_output_input_chunk']} (call - (k - 1))")
                c1 = info["COLD-1"]
                check(c1["no_output_calls"] == [34], "COLD-1: no output exactly at the cold-restart call 34")
        print("- 3 G3 negative cases (must fail)")
        unit = tmp / "expVCt" / "dog_s0"
        s = json.loads((unit / "OT-1" / "summary.json").read_text())
        fdir = Path(s["frames"])
        exp = {**{k: s["condition"][k] for k in ("frames_from", "frames_to", "resets", "binds", "cold_call")}, "k": 2, "kind": "ot"}
        bad_dir = tmp / "bad"
        shutil.copytree(fdir, bad_dir)
        seg = sorted(bad_dir.glob("seg_*.mkv"))[1]
        b = bytearray(seg.read_bytes()); b[len(b) // 2] ^= 0xFF; seg.write_bytes(bytes(b))
        check(not vf.check_stream(bad_dir, exp)[0], "a flipped byte in a segment is detected")
        shutil.rmtree(bad_dir); shutil.copytree(fdir, bad_dir)
        doc = json.loads((bad_dir / "index.json").read_text()); doc["calls"][20]["events"] = ["bind"]; (bad_dir / "index.json").write_text(json.dumps(doc))
        check(not vf.check_stream(bad_dir, exp)[0], "a wrong reset / bind marker is detected")
        shutil.rmtree(bad_dir); shutil.copytree(fdir, bad_dir)
        doc = json.loads((bad_dir / "index.json").read_text()); doc["calls"][30]["out_input_call"] += 1; (bad_dir / "index.json").write_text(json.dumps(doc))
        check(not vf.check_stream(bad_dir, exp)[0], "a mismatched input chunk is detected")
        shutil.rmtree(bad_dir); shutil.copytree(fdir, bad_dir)
        doc = json.loads((bad_dir / "index.json").read_text()); doc["calls"] = doc["calls"][:-1]; (bad_dir / "index.json").write_text(json.dumps(doc))
        check(not vf.check_stream(bad_dir, exp)[0], "a missing call index is detected")

        print("- 4 G1 / G2 comparison logic against the real runs' own logs")
        for cid, cond in (("OT-L", next(c for c in out["inputs"]["dog"]["conditions"] if c["id"] == "OT-L")), ("COLD-1", next(c for c in out["inputs"]["dog"]["conditions"] if c["id"] == "COLD-1"))):
            u = tmp / "g" / "dog_s0" / cid; u.mkdir(parents=True, exist_ok=True)
            real = list(csv.DictReader(open(ROOT / cond["sources"][0] / "metrics.csv", newline="")))
            rows = [{"call": r["call"], "produced": r["missing"] not in ("True", "true"), "psnr": r["psnr"]} for r in real]
            for perturb in (0.0, 0.01):
                with open(u / "calls.csv", "w", newline="") as fh:
                    wr = csv.DictWriter(fh, fieldnames=["call", "produced", "psnr"]); wr.writeheader()
                    for i, r in enumerate(rows):
                        p = r["psnr"]
                        if perturb and i == 40 and p:
                            p = f"{float(p) + perturb:.4f}"
                        wr.writerow({**r, "psnr": p})
                (u / "summary.json").write_text(json.dumps({"valid": True, "prefix_identical_to_reference": True, "realized": {}}))
                ok, why, info = vc.replay_equivalence(tmp / "g" / "dog_s0", cid, out)
                check(ok == (perturb == 0.0), f"{cid}: identical log {'passes' if perturb == 0 else 'with one call +0.01 dB fails'} ({info['common_calls']} calls)")

        print("- 5 last-frame-hold playback model")
        tl = {c: 0.6 * c for c in range(10)}; tl.update({c: 0.6 * c + 5.0 for c in range(10, 20)})
        p = vp.play(tl, list(range(20)), fps=4 / 0.6)
        check(p["n_stalls"] == 1 and abs(p["longest_stall_s"] - 5.0) < 0.1 and p["resumes"] == [(9, 10)], f"one 5 s stall between calls 9 and 10 ({p['n_stalls']}, {p['longest_stall_s']:.2f} s)")
        p16 = vp.play({c: 0.6 * c for c in range(20)}, list(range(20)), fps=16)
        check(p16["n_stalls"] > 10, f"at 16 fps a 0.6 s / chunk stream stalls continuously ({p16['n_stalls']} stalls): deviation D-VC-1")

        print("- 5b VD-2 conditions (dry): emulation on the existing unit, merged metrics, aggregation")
        ids = [c["id"] for c in out["inputs"]["dog"]["conditions"] if c["kind"] == "vd2"]
        r_ = subprocess.run([PY, "tools/eval/vc_emulate.py", "--input", "dog", "--dry_run", "--frames_dir", str(tmp / "frames"), "--out_root", str(tmp / "expVCt"), "--only", ",".join(ids), "--no_ref_frames"],
                            cwd=ROOT, capture_output=True, text=True)
        check(r_.returncode == 0 and r_.stdout.count("valid True") == 16, "dog: 16 VD-2 conditions emulated, all valid (DR1, DR2, RP1, TSin, TSout, combos, DR4) x 2 schedules")
        s2 = json.loads((tmp / "expVCt" / "dog_s0" / "VD21-RP1+TSout" / "summary.json").read_text())["vd2"]
        check(s2["rp"] and s2["ts"] == "out" and {"ts_prepare_s", "rp_replay_s", "total_serial_s"} <= set(s2["cost_s"]), f"RP1+TSout records its reconstruction steps and costs {s2['cost_s']}")
        ok, why, info = vc.g3(tmp / "expVCt" / "dog_s0", out)
        check(ok, f"G3 passes with the VD-2 streams added ({len(info)} streams) {why[:2]}")
        r_ = subprocess.run([PY, "tools/eval/vc_metrics.py", "--selftest", "--embedders", "pixel", "--device", "cpu", "--out", str(tmp / "st.json")], cwd=ROOT, capture_output=True, text=True)
        check(r_.returncode == 0, f"self-test passes: cut V1, color-shift V4, content V5a {r_.stdout[-200:] if r_.returncode else ''}")
        r_ = subprocess.run([PY, "tools/eval/vc_metrics.py", "--unit", str(unit), "--embedders", "pixel", "--device", "cpu"], cwd=ROOT, capture_output=True, text=True)
        check(r_.returncode == 0 and (unit / "metrics.json").exists(), "metrics on the dry unit")
        r_ = subprocess.run([PY, "tools/eval/vc_metrics.py", "--unit", str(unit), "--embedders", "pixel", "--device", "cpu", "--only", ",".join(ids), "--merge"], cwd=ROOT, capture_output=True, text=True)
        mj = json.loads((unit / "metrics.json").read_text())["conditions"] if r_.returncode == 0 else {}
        check(r_.returncode == 0 and "OT-1" in mj and "VD21-TSout" in mj, "VD-2 metrics merged into the unit's metrics.json (VC conditions kept)")
        r_ = subprocess.run([PY, "tools/eval/aggregate_vd2.py", "--root", str(tmp / "expVCt"), "--dry"], cwd=ROOT, capture_output=True, text=True)
        check(r_.returncode == 0 and "VD2-H3" in r_.stdout and ("PENDING" in r_.stdout or "NOT SUPPORTED" in r_.stdout), f"VD-2 aggregation runs on one input (verdicts pending or failed on synthetic data) {r_.stderr[-300:]}")
        r_ = subprocess.run([PY, "tools/eval/aggregate_vc.py", "--root", str(tmp / "expVCt"), "--dry"], cwd=ROOT, capture_output=True, text=True)
        check(r_.returncode == 0 and "VC-H1" in r_.stdout and "VC-H2" in r_.stdout and "VD" not in r_.stdout.split("## Playback")[0].split("## Descriptive")[-1],
              "VC aggregation (block bootstrap, effect sizes, verdicts; VD conditions excluded)")
        r_ = subprocess.run([PY, "tools/eval/aggregate_vd.py", "--root", str(tmp / "expVCt"), "--dry"], cwd=ROOT, capture_output=True, text=True)
        check(r_.returncode == 0 and "VD-H2" in r_.stdout and "dog | OT-1" in r_.stdout, f"VD aggregation (main effects, verdicts) {r_.stderr[-300:]}")
        vd3_tests(tmp, out, vc)
        vd4_tests()
        vd4_supp_tests()
        vd4_rows_tests()
        vd4_a1_tests()
        vd4_a1_torch_tests()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\nALL PASS" if not FAILS else f"\nFAILURES ({len(FAILS)}):\n  " + "\n  ".join(FAILS))
    sys.exit(1 if FAILS else 0)


def vd3_tests(tmp: Path, out: dict, vc):
    """Experiment VD-3 (dry): schedules, seed-1 unit, the six conditions, tolerances, blinded clips, inspection gate,
    aggregation, overlap, and the remote pull's identical-copy resolution."""
    import hashlib
    import re

    print("- 6 VD-3 (dry)")
    for inp in ("dog", "train", "butterfly-feeding-slow-motion", "audi-snow-trail"):
        u = out["units"][f"{inp}_s1"]
        o1, oL = (next(c for c in u["conditions"] if c["id"] == x) for x in ("OT-1", "OT-L"))
        check(o1["resets"] == [34] and o1["binds"][0] in (58, 59) and "expW_W2_" in o1["sources"][0] and "_s1/" in o1["sources"][0] and not o1.get("counterfactual")
              and oL["counterfactual"] and "copied" in oL["label"] and sum(1 for c in u["conditions"] if c["kind"] == "vd3") == 12,
              f"{inp} seed 1: OT-1 realized from the W2 seed-1 run (bind {o1['binds']}), OT-L copied and labelled counterfactual, 12 VD-3 conditions")
    check(sum(1 for c in out["inputs"]["dog"]["conditions"] if c["kind"] == "vd2") == 16, "the frozen VD-2 conditions are unchanged (16 on dog)")
    root, frames = tmp / "expVCt", tmp / "frames"
    r_ = subprocess.run([PY, "tools/eval/vc_emulate.py", "--input", "dog", "--seed", "1", "--dry_run", "--frames_dir", str(frames), "--out_root", str(root)], cwd=ROOT, capture_output=True, text=True)
    check(r_.returncode == 0 and r_.stdout.count("valid True") == 2, "dog seed 1: REF + frozen-M1 OT-1 / OT-L controls emulated by default (VD-3 conditions only on request)")
    for sd in (0, 1):
        ids = [c["id"] for c in out["units"]["dog_s1"]["conditions"] if c["kind"] == "vd3"] if sd else [c["id"] for c in out["inputs"]["dog"]["conditions"] if c["kind"] == "vd3"]
        r_ = subprocess.run([PY, "tools/eval/vc_emulate.py", "--input", "dog", "--seed", str(sd), "--dry_run", "--frames_dir", str(frames), "--out_root", str(root), "--only", ",".join(ids), "--no_ref_frames"],
                            cwd=ROOT, capture_output=True, text=True)
        check(r_.returncode == 0 and r_.stdout.count("valid True") == 12, f"dog seed {sd}: 12 VD-3 conditions emulated, all valid")
    u1 = root / "dog_s1"
    ok, why, info = vc.g3(u1, out)
    check(ok and len(info) == 15, f"G3 on the seed-1 unit (REF + 2 controls + 12 VD-3 streams) {why[:2]}")
    lg = {c: json.loads((u1 / c / "summary.json").read_text())["vd3"] for c in ("VD31-TSinKC", "VD31-DR2stale", "VD31-DR2noise", "VD3L-DR2+TSin")}
    check(lg["VD31-DR2stale"]["stale_calls"] == [16, 17] and lg["VD31-DR2noise"]["noise"]["seed"] == 1 * 1000003 + 34, "DR2stale reads calls m-18, m-17; DR2noise records its seed")
    check(lg["VD31-TSinKC"]["kc_digest_equal"] and lg["VD31-TSinKC"]["ts_slots_written"] == 2 and "kc_copy_s_not_counted" in lg["VD31-TSinKC"]
          and lg["VD31-TSinKC"]["cost_s"]["total_serial_s"] == lg["VD31-TSinKC"]["cost_s"]["ts_prepare_s"], "TSinKC: kept cache verified by digest; the emulation copy is not counted in its cost")
    check(set(lg["VD3L-DR2+TSin"]["cost_s"]) == {"ts_prepare_s", "dr_decode_s", "total_serial_s"} and lg["VD3L-DR2+TSin"]["temp_slots_left_after_bind"] == 0,
          "DR2+TSin: both reconstruction costs recorded; no temporary-Sink slot left after the bind")
    for sd in (0, 1):
        r_ = subprocess.run([PY, "tools/eval/vc_metrics.py", "--unit", str(root / f"dog_s{sd}"), "--embedders", "pixel", "--device", "cpu"], cwd=ROOT, capture_output=True, text=True)
        check(r_.returncode == 0, f"metrics on dog seed {sd} (early / late Sink-less windows)")
    mj = json.loads((u1 / "metrics.json").read_text())["conditions"]["VD3L-DR2+TSin"]["windows"]
    check(mj["sl_early"]["calls"] == [80, 87] and mj["sl_late"]["calls"] == [146, 153], f"early / late windows are the first / last 8 Sink-less calls {mj['sl_early']['calls']} {mj['sl_late']['calls']}")
    pt = tmp / "phaseT"
    r_ = subprocess.run([PY, "tools/eval/vd3_phaseT.py", "--root", str(root), "--inputs", "dog", "--embedder", "pixel", "--device", "cpu", "--dry", "--out", str(pt)], cwd=ROOT, capture_output=True, text=True)
    P = json.loads(pt.with_suffix(".json").read_text()) if r_.returncode == 0 else {"cells": {}}
    c1 = P["cells"].get("dog_s1|OT-1", {})
    check(r_.returncode == 0 and len(P["cells"]) == 4 and c1.get("confirmation") and c1["natural_ref_variation"]["dino"].get("P95-P5") is not None
          and c1["measurement_noise"]["embedder_recompute"] is not None and c1["sensitivity_cross_seed"] is not None and c1["context_frozen_m1"]["available"]
          and "threshold" not in json.dumps(c1).lower() and P["cells"]["dog_s1|OT-L"]["counterfactual"],
          f"Phase T: per-cell distributions (natural REF variation, measurement noise, cross-seed sensitivity, frozen-M1 context), no threshold chosen {r_.stderr[-200:]}")
    tol = tmp / "thr"
    tol.with_suffix(".json").write_text(json.dumps({"global": {"dino": 0.05, "dE_anchor": 1.5, "dE_cross": 2.9, "E": 0.4, "motion": 0.26}}))   # synthetic, test only
    clips, form = tmp / "clips", tmp / "form.md"
    r_ = subprocess.run([PY, "tools/eval/vc_export_clips.py", "--root", str(root), "--clips_dir", str(clips), "--order_seed", "3", "--inputs", "dog", "--form", str(form)], cwd=ROOT, capture_output=True, text=True)
    ftxt = form.read_text() if form.exists() else ""
    codes = re.findall(r"^\| ([0-9A-F]{6}) \|", ftxt, flags=re.M)
    kb = (clips / "sealed" / "vd3_blind_key.json").read_bytes() if r_.returncode == 0 else b""
    names = [str(p.relative_to(clips)) for p in clips.rglob("*.mp4")]
    check(r_.returncode == 0 and len(codes) == 24 and len(names) == 28 and hashlib.sha256(kb).hexdigest() in ftxt
          and not any(w in ftxt + " ".join(names) for w in ("TSin", "DR2", "REF", "OT-1", "OT-L", "frozen")),
          f"blinded clips: 4 cells x 6 codes + 4 grids, key SHA-256 in the form, no condition names in the form or the file names {r_.stderr[-200:]}")
    res = tmp / "res"
    agg = lambda insp: subprocess.run([PY, "tools/eval/aggregate_vd3.py", "--root", str(root), "--thresholds", str(tol.with_suffix(".json")), "--inspection", str(insp),  # noqa: E731
                                       "--key", str(clips / "sealed" / "vd3_blind_key.json"), "--form", str(form), "--out", str(res)], cwd=ROOT, capture_output=True, text=True)
    r_ = agg(tmp / "none.md")
    check(r_.returncode == 0 and "Verdicts withheld" in r_.stdout and "GO" not in res.with_suffix(".md").read_text().split("Verdicts withheld")[1], "no recorded inspection: verdicts withheld, validity only")
    filled = re.sub(r"^\| ([0-9A-F]{6}) \|( \|)+$", lambda m: f"| {m.group(1)} | kept | kept | no shift | no visible jump | stable | no visible jump | dry |", ftxt.replace("STATUS: NOT RECORDED", "STATUS: RECORDED"), flags=re.M)
    (tmp / "insp.md").write_text(filled)
    r_ = agg(tmp / "insp.md")
    check(r_.returncode == 0 and "inspection vetoes none" in r_.stdout and "C3" in r_.stdout, "recorded inspection: keyed; 'no shift' / 'no visible jump' are not vetoes")
    key = json.loads(kb)["key"]
    cand = next(c for c, k in key.items() if k["name"] == "DR2+TSin" and k["cell"] == "dog_s1|OT-1")
    (tmp / "insp2.md").write_text(re.sub(rf"^\| {cand} \| kept \| kept \| no shift \| no visible jump", f"| {cand} | kept | kept | no shift | jump", filled, flags=re.M))
    r_ = agg(tmp / "insp2.md")
    check(r_.returncode == 0 and "inspection vetoes ['dog_s1|OT-1']" in r_.stdout, "a 'jump' answer on a confirmation clip of DR2+TSin vetoes its GO")
    (clips / "sealed" / "vd3_blind_key.json").write_bytes(kb.replace(b'"order_seed": 3', b'"order_seed": 4'))
    r_ = agg(tmp / "insp.md")
    check(r_.returncode == 0 and "differs from the form" in r_.stdout, "a replaced key (SHA-256 differs from the form) is refused")
    import aggregate_vd3 as a3

    # synthetic phase statistics: each rule clause, then the phase classes and the overall rule (PASS / FAIL / INCONCLUSIVE)
    t = {"dino": 0.04, "dE_anchor": 0.9, "dE_cross": 1.5}
    good = {"D_c": -0.01, "C_c": 0.2, "dE_cross": 0.5, "eO": 2.6, "eR": 2.5, "dO": 3.0, "dR": 3.1, "dino": 0.95, "dino_ref": 0.96}
    def syn(**over):
        P = {k: dict(good) for k in ("sinkless", "sl_early", "sl_late", "post_bind_20", "last_10")}
        for k, v in over.items():
            if "__" in k:
                ph, key = k.split("__")
                P[ph][key] = v
        return {"valid": True, "v1_reset": over.get("v1", 2.0), "v1_bind": 1.0, "P": P, "X_late": over.get("X", 0.0), "cost_s": 1.0}
    R0 = a3.rules(syn(), "DR2+TSin", t, 3.4)
    check(R0["all"] and all(R0[p] for p in a3.PHASES), "synthetic: a stream inside every limit passes P1, P2a, P2b, P3 and cost")
    cases = {"P1": syn(v1=5.0), "P2a": syn(sinkless__D_c=-0.08), "P2a ": syn(X=0.06), "P2b": syn(sinkless__eO=2.8), "P2b  ": syn(sinkless__dO=2.7), "P3": syn(post_bind_20__C_c=1.2)}
    check(all(not a3.rules(v, "DR2+TSin", t, 3.4)[p.strip()] for p, v in cases.items()),
          "synthetic: boundary V1, content drift, late excess drift, warp error +12 %, motion -13 %, post-bind color each fail their phase")
    near0 = syn(sinkless__eO=0.55, sinkless__eR=0.5)   # +10 % of 0.5 = 0.05 < 0.10 absolute allowance
    check(a3.rules(near0, "DR2+TSin", t, 3.4)["P2b"] and not a3.rules(syn(sinkless__eO=0.65, sinkless__eR=0.5), "DR2+TSin", t, 3.4)["P2b"]
          and a3.rules(syn(sinkless__eO=2.0), "DR2+TSin", t, 3.4)["P2b"],
          "warp: absolute safeguard near zero REF (0.05 above 0.5 passes, 0.15 fails); less warp error than REF passes (one-sided)")
    ctrl_ = syn(v1=8.0, sinkless__D_c=-0.4, post_bind_20__eO=2.9, post_bind_20__D_c=-0.03)   # frozen M1: post-bind still recovering
    check(a3.rules(ctrl_, "OT", t, 3.4, ctrl_)["P3"] and not a3.rules(ctrl_, "OT", t, 3.4)["P3"],
          "P3 no-harm is relative to frozen M1: its own post-bind recovery passes (the absolute REF form would fail it)")
    check(a3.rules(syn(post_bind_20__eO=2.9, post_bind_20__D_c=-0.03), "DR2+TSin", t, 3.4, ctrl_)["P3"]
          and not a3.rules(syn(post_bind_20__eO=3.3, post_bind_20__D_c=-0.03), "DR2+TSin", t, 3.4, ctrl_)["P3"]
          and not a3.rules(syn(post_bind_20__eO=2.9, last_10__D_c=-0.08), "DR2+TSin", t, 3.4, ctrl_)["P3"],
          "P3: a candidate equal to frozen M1 after the bind passes; 14 % more post-bind warp error than M1, or a last-10 content gap, fails")
    big_bind = syn(post_bind_20__eO=2.9, post_bind_20__D_c=-0.03); big_bind["v1_bind"] = 3.6
    ctrl_b = dict(ctrl_); ctrl_b["v1_bind"] = 3.8
    check(not a3.rules(big_bind, "DR2+TSin", t, 3.4, ctrl_b)["P3"],
          "P3 bind boundary is absolute: V1(bind) 3.6 > REF P99 3.4 fails even when frozen M1's bind V1 (3.8) is larger")
    m1 = a3.rules(syn(v1=8.0, sinkless__D_c=-0.4), "OT", t, 3.4)
    cl = a3.classify_phases(R0, m1)
    check(cl == {"P1": "DISCRIMINATIVE PASS", "P2a": "DISCRIMINATIVE PASS", "P2b": "NON-DISCRIMINATIVE PASS", "P3": "PASS", "cost": "PASS"}
          and set(a3.classify_phases(dict(R0, valid=False), m1).values()) == {"FAIL"},
          f"phase classes vs frozen M1 (P1, P2a discriminative; P2b not; P3 / cost no-harm); an invalid stream fails every phase {cl}")
    D, N_, F = "DISCRIMINATIVE PASS", "NON-DISCRIMINATIVE PASS", "FAIL"
    ph = lambda p1, p2a, p2b, p3="PASS": {"P1": p1, "P2a": p2a, "P2b": p2b, "P3": p3, "cost": "PASS"}  # noqa: E731
    ins = {"dog", "train"}
    go = {"dog_s1|OT-1": ph(D, D, N_), "train_s0|OT-1": ph(D, N_, N_), "train_s1|OT-1": ph(N_, D, D)}
    check(a3.overall(go, [], ins) == {"continuity": "GO", "identity": "ESTABLISHED"}, "overall GO: every input has discriminative P1 and P2; identity established (P2a)")
    check(a3.overall({"dog_s1|OT-1": ph(D, D, N_), "train_s0|OT-1": ph(D, N_, D)}, [], ins) == {"continuity": "GO", "identity": "INCONCLUSIVE"},
          "GO on continuity but train has only motion (P2b) discrimination: identity INCONCLUSIVE")
    check(a3.overall({"dog_s1|OT-1": ph(D, D, N_), "train_s0|OT-1": ph(N_, D, N_)}, [], ins)["continuity"] == "INCONCLUSIVE",
          "no discriminative boundary (P1) evidence on train: INCONCLUSIVE")
    check(a3.overall(dict(go, **{"train_s1|OT-L": ph(D, D, D, p3="FAIL")}), [], ins)["continuity"] == "NO-GO"
          and a3.overall(dict(go, **{"train_s1|OT-L": ph(F, D, D)}), [], ins)["continuity"] == "NO-GO"
          and a3.overall(go, ["dog_s1|OT-1"], ins)["continuity"] == "NO-GO",
          "NO-GO: a P3 (no-harm) failure, a phase FAIL, or an inspection veto")
    r_ = subprocess.run([PY, "tools/eval/aggregate_vd3.py", "--root", str(root), "--thresholds", str(tmp / "missing.json")], cwd=ROOT, capture_output=True, text=True)
    check(r_.returncode != 0 and "thresholds" in (r_.stdout + r_.stderr), "aggregation refuses without frozen thresholds")
    r_ = subprocess.run([PY, "tools/eval/vd3_overlap.py", "--dry_run", "--reps", "2", "--out", str(tmp / "ov.json")], cwd=ROOT, capture_output=True, text=True)
    ov = json.loads((tmp / "ov.json").read_text()) if r_.returncode == 0 else {}
    check(set(ov.get("checks", {})) == {"a_digests_equal", "b_contention_within_10pct", "c_first_output_earlier"} and len(ov["trials"]) == 4, "overlap measurement: alternating serial / overlap trials and the three checks (dry)")
    if not (ROOT / "results/evaluation/osdi/expVD3_freeze.md").exists():   # VD-3 was frozen on 2026-10-25: this check applies only before that
        r_ = subprocess.run([PY, "tools/eval/run_vc.py", "vd3", "--phase", "cand", "--frames_dir", "/x", "--clips_dir", "/y"], cwd=ROOT, capture_output=True, text=True)
        check(r_.returncode != 0 and "not frozen" in (r_.stdout + r_.stderr), "run_vc vd3 refuses candidate conditions before the freeze")
    if not (ROOT / "results/evaluation/osdi/expVD3_phaseT_approval.md").exists():
        r_ = subprocess.run([PY, "tools/eval/run_vc.py", "vd3", "--phase", "base", "--frames_dir", "/x"], cwd=ROOT, capture_output=True, text=True)
        check(r_.returncode != 0 and "Phase T is not approved" in (r_.stdout + r_.stderr), "run_vc vd3 refuses Phase T without its approval record")
    # remote pull: a blocked pull clears only byte-identical result copies
    import d0_remote as dr

    g = tmp / "git"
    run = lambda cwd, *c: subprocess.run(list(c), cwd=cwd, capture_output=True, text=True)  # noqa: E731
    run(tmp, "git", "init", "-q", "--bare", str(g / "o.git")); run(tmp, "git", "clone", "-q", str(g / "o.git"), str(g / "a"))
    (g / "a" / "README").write_text("r\n"); run(g / "a", "git", "add", "."); run(g / "a", "git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "c0"); run(g / "a", "git", "push", "-q", "origin", "HEAD")
    run(tmp, "git", "clone", "-q", str(g / "o.git"), str(g / "b"))
    (g / "b" / "results").mkdir(); (g / "b" / "results" / "x.txt").write_text("same\n")
    (g / "a" / "results").mkdir(); (g / "a" / "results" / "x.txt").write_text("same\n"); run(g / "a", "git", "add", "."); run(g / "a", "git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "c1"); run(g / "a", "git", "push", "-q", "origin", "HEAD")

    class FakeAg:
        def __init__(self, cwd):
            self.cwd = cwd

        def exec(self, cmd, timeout=30):
            r = subprocess.run(cmd, cwd=self.cwd, capture_output=True, text=True)
            return {"rc": r.returncode, "stdout": r.stdout, "stderr": r.stderr}
    ag = FakeAg(g / "b")
    r1 = ag.exec(["git", "pull", "--ff-only"])
    done, kept = dr._resolve_identical(ag, r1["stderr"] + r1["stdout"])
    r2 = ag.exec(["git", "pull", "--ff-only"])
    check(r1["rc"] != 0 and done == ["results/x.txt"] and not kept and r2["rc"] == 0, f"a pull blocked by an identical untracked result copy is resolved ({done}, {kept})")
    (g / "b" / "results" / "z.txt").write_text("mine\n")
    (g / "a" / "results" / "z.txt").write_text("theirs\n"); run(g / "a", "git", "add", "."); run(g / "a", "git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "c2"); run(g / "a", "git", "push", "-q", "origin", "HEAD")
    r1 = ag.exec(["git", "pull", "--ff-only"])
    done, kept = dr._resolve_identical(ag, r1["stderr"] + r1["stdout"])
    check(r1["rc"] != 0 and not done and kept == ["results/z.txt"] and (g / "b" / "results" / "z.txt").read_text() == "mine\n", "a differing local result file is left untouched and reported")


def vd4_tests():
    """Experiment VD-4 (dry): schedules overlay (frozen file untouched), conditions, oracle verification incl. negative
    cases, resolution classes, kappa, clips, aggregation and the stage gates."""
    import hashlib
    import re

    import aggregate_vd4 as a4
    import mobility_node as mn
    import vc_emulate as ve
    import vc_schedules as vs

    print("- 7 VD-4 (dry)")
    frozen = re.search(r"vc_schedules.json` \| `([0-9a-f]{64})`", (ROOT / "results/evaluation/osdi/expVD3_freeze.md").read_text()).group(1)
    check(hashlib.sha256((ROOT / "results/evaluation/osdi/expVC/vc_schedules.json").read_bytes()).hexdigest() == frozen,
          "the frozen vc_schedules.json is byte-identical to the VD-3 freeze record (VD-4 lives in an overlay)")
    S = json.loads((ROOT / "results/evaluation/osdi/expVC/vc_schedules.json").read_text())
    v4 = [c for c in vs.unit_sched(S, "train_s0")["conditions"] if c["kind"] == "vd4"]
    v0 = next(c for c in v4 if c["id"] == "VD41-V0")
    check(len(v4) == 26 and v0["binds"] == [] and next(c for c in v4 if c["id"] == "VD41-S2")["oracle_sink_slots"] == [2, 1]
          and next(c for c in v4 if c["id"] == "VD41-A1S1")["exploratory"], "overlay: 13 VD-4 conditions per schedule; V0 without a bind; S2 = slots 2, 1; A1S1 exploratory")
    tmp = Path(tempfile.mkdtemp(prefix="vd4_test_"))
    try:
        root, frames = tmp / "expVC", tmp / "frames"
        for inp, sd in (("dog", 1), ("train", 0)):
            ids = [c["id"] for c in vs.unit_sched(S, f"{inp}_s{sd}")["conditions"] if c["kind"] == "vd4"]
            r_ = subprocess.run([PY, "tools/eval/vc_emulate.py", "--input", inp, "--seed", str(sd), "--dry_run", "--frames_dir", str(frames), "--out_root", str(root), "--only", "OT-1,OT-L"], cwd=ROOT, capture_output=True, text=True)
            r2 = subprocess.run([PY, "tools/eval/vc_emulate.py", "--input", inp, "--seed", str(sd), "--dry_run", "--frames_dir", str(frames), "--out_root", str(root), "--only", ",".join(ids), "--no_ref_frames"], cwd=ROOT, capture_output=True, text=True)
            check(r2.returncode == 0 and r2.stdout.count("valid True") == 26, f"{inp} seed {sd}: 26 VD-4 streams emulated, all valid")
        import vc_check

        ok, why, info = vc_check.g3(root / "train_s0", S)
        check(ok and "VD41-V0" in info, f"G3 on the VD-4 streams including V0 (no bind) {why[:2]}")
        lg = json.loads((root / "train_s0" / "VD41-A1S2" / "summary.json").read_text())["vd4"]
        check(lg["checks"].get("sink_k_equal") and lg["checks"].get("ts_v_unrotated") and lg["checks"].get("meta_positions_equal_snapshot") and lg["checks"]["layers"] == 30
              and lg["source_positions_layer0"] and lg["prepare_positions_layer0"],
              "A1S2: oracle slots verified (K, V, positions), the remaining TS slot's V unrotated, source / prepare positions logged")
        # negative cases on the fake runtime: a digest mismatch, and a later reset step overwriting an injected slot
        margs = mn.parse_args(["--label", "T", "--dry_run", "--dry_sink_mb", "4", "--dry_service_s", "0.0005", "--migration_chunk", "0", "--post_chunks", "10"])

        class Bad(mn.FakeRuntime):
            def kv_digest(self, slots, part, snap=None, kv_override=None):
                return "snapshot" if (kv_override is not None or snap is not None) else "live"

        class Overwrite(mn.FakeRuntime):
            hit = False

            def decode_latents(self, lats):
                self.hit = True; return 0.001

            def kv_digest(self, slots, part, snap=None, kv_override=None):
                return "changed" if (self.hit and snap is None and kv_override is None) else "same"
        for cls, cond, key_, what in ((Bad, {"dec": "dr2", "ts": "in", "oracle_sink_slots": [2]}, "sink_k_equal", "an oracle Sink slot whose live K differs from the snapshot"),
                                      (Overwrite, {"dec": "dr2", "oracle_recent": True, "ts": "in"}, "recent_k_equal", "a later reset step (DR-2 decode) overwriting the injected recent KV")):
            rt = cls(margs); rt.provision()
            log = {"cost_s": {}, "checks": {}, "bytes": {}}
            ve.vd4_reset(rt, 5, cond, {}, [], True, log, None, [])
            check(log["checks"].get(key_) is False, f"oracle verification catches {what} ({[k for k, v in log['checks'].items() if v is False]})")
        check(a4.resolution(12, 12, 1, 1, 12) == "STRICT" and a4.resolution(12, 12, 2, 1, 12) == "NEAR" and a4.resolution(12, 12, 3, 1, 12) == "not resolved"
              and a4.resolution(11, 12, 0, 1, 12) == "not resolved" and a4.resolution(12, 12, 0, 0, 0) == "not inspected" and a4.resolution(12, 12, 0, 0, 12) == "STRICT",
              "resolution: STRICT (flags <= REF), NEAR (REF + 1), not resolved (more flags, or any numeric failure), not inspected; 0 flags is still only a count")
        check(abs(a4.kappa({"mm": 10, "mp": 0, "pm": 0, "pp": 10}) - 1.0) < 1e-9 and abs(a4.kappa({"mm": 5, "mp": 5, "pm": 5, "pp": 5})) < 1e-9, "Cohen's kappa: 1 for perfect agreement, 0 for chance")
        # clips, a synthetic recorded session, aggregation
        insp = tmp / "insp"; insp.mkdir()
        for inp, sd in (("dog", 1), ("train", 0)):
            subprocess.run([PY, "tools/eval/vc_emulate.py", "--input", inp, "--seed", str(sd), "--dry_run", "--frames_dir", str(frames), "--out_root", str(root), "--only", "VD31-DR2+TSin,VD3L-DR2+TSin", "--no_ref_frames"], cwd=ROOT, capture_output=True, text=True)
            subprocess.run([PY, "tools/eval/vc_metrics.py", "--unit", str(root / f"{inp}_s{sd}"), "--embedders", "pixel", "--device", "cpu"], cwd=ROOT, capture_output=True, text=True)
        r_ = subprocess.run([PY, "tools/eval/vd4_export_clips.py", "--root", str(root), "--session", "stage1", "--names", "DR,D,R,A1", "--cells", "dog_s1|OT-1,train_s0|OT-1",
                             "--clips_dir", str(tmp / "clips"), "--order_seed", "3", "--form", str(insp / "_dryrun_vd4_inspection_form_stage1.md")], cwd=ROOT, capture_output=True, text=True)
        ftxt = (insp / "_dryrun_vd4_inspection_form_stage1.md").read_text() if r_.returncode == 0 else ""
        kb = (tmp / "clips" / "sealed" / "vd4_stage1_blind_key.json").read_bytes() if r_.returncode == 0 else b""
        check(r_.returncode == 0 and len(re.findall(r"^\| [0-9A-F]{6} \|", ftxt, flags=re.M)) == 12 and hashlib.sha256(kb).hexdigest() in ftxt
              and "flicker / jitter" in ftxt and not any(w in re.sub(r"[0-9A-F]{6}|[0-9a-f]{64}", "", ftxt) for w in ("B0", "DR", "A1", "REF")),
              "VD-4 session clips: 2 cells x 6 codes, key SHA-256 in the form, flicker / motion fields, no condition names")
        (insp / "_dryrun_vd4_stage1_blind_key.json").write_bytes(kb)
        key = json.loads(kb)["key"]
        def fill(m):
            n = key[m.group(1)]["name"]
            return f"| {m.group(1)} | kept | none | no shift | {'jump' if n == 'B0' else 'no visible jump'} | none | natural | no visible jump | dry |"
        (insp / "_dryrun_vd4_inspection_stage1.md").write_text(re.sub(r"^\| ([0-9A-F]{6}) \|( \|)+$", fill, ftxt.replace("STATUS: NOT RECORDED", "STATUS: RECORDED"), flags=re.M))
        r_ = subprocess.run([PY, "tools/eval/aggregate_vd4.py", "--root", str(root), "--dry", "--insp_dir", str(insp), "--sessions", "stage1", "--out", str(tmp / "res")], cwd=ROOT, capture_output=True, text=True)
        R = json.loads((tmp / "res.json").read_text()) if r_.returncode == 0 else {}
        b0 = (R.get("conditions", {}).get("B0", {}).get("phases", {}).get("P1") or {})
        check(r_.returncode == 0 and b0.get("visual_flags") == 2 and b0.get("ref_flags_same_session") == 0
              and all(v["pass"] for v in R["validity"]) and set(R["attribution"]) == {"P1", "P2a", "P2b"} and not R["gates"]["duplicate_controls"],
              f"aggregation: per-cell visual flags against REF of the same cell and session, validity rows, attribution per phase {r_.stderr[-200:]}")
        check(R["gates"]["stage0_valid"] is False, "stage-0 gate stays closed while any of the four stage-0 cells lacks its V0 / B0 / A1 / S3 validity")
        for f_ in ("vd4_inspection_form_stage1", "vd4_inspection_stage1", "vd4_stage1_blind_key"):   # the same controls in a second session
            src = insp / f"_dryrun_{f_}.{'json' if 'key' in f_ else 'md'}"
            (insp / src.name.replace("stage1", "stage1b")).write_bytes(src.read_bytes())
        r_ = subprocess.run([PY, "tools/eval/aggregate_vd4.py", "--root", str(root), "--dry", "--insp_dir", str(insp), "--sessions", "stage1,stage1b", "--out", str(tmp / "res2")], cwd=ROOT, capture_output=True, text=True)
        R2 = json.loads((tmp / "res2.json").read_text()) if r_.returncode == 0 else {"gates": {}}
        check(bool(R2["gates"].get("duplicate_controls")), "a control inspected in two sessions is reported (never counted twice)")
        cells_a, cells_b = a4.STAGE1_SESSIONS["stage1a"], a4.STAGE1_SESSIONS["stage1b"]
        check(sorted(cells_a + cells_b) == sorted(a4.CONFIRM) and not set(cells_a) & set(cells_b)
              and all({c.split("_s")[0] for c in cs} == {"train", "audi-snow-trail", "dog", "butterfly-feeding-slow-motion"} for cs in (cells_a, cells_b)),
              "stage-1 inspection split: two sessions of 6 cells partition the 12, every input in both")
        s0pos = {"dog_s1|OT-1": "aligned [0, 1]", "train_s0|OT-1": "positive [22, 24]", "butterfly-feeding-slow-motion_s0|OT-L": "negative [-29, -10]", "audi-snow-trail_s1|OT-1": "mixed [22, 1]"}
        check(a4.STAGE0 == list(s0pos) and {c.split("_s")[0] for c in a4.STAGE0} == {"dog", "train", "butterfly-feeding-slow-motion", "audi-snow-trail"},
              "stage 0: one cell per input covering aligned, positive, negative and mixed sink positions")
        r_ = subprocess.run([PY, "tools/eval/run_vc.py", "vd4", "--stage", "1", "--frames_dir", "/x", "--clips_dir", "/y"], cwd=ROOT, capture_output=True, text=True)
        gates_ = json.loads((ROOT / "results/evaluation/osdi/expVD4/vd4_gates.json").read_text()) if (ROOT / "results/evaluation/osdi/expVD4/vd4_gates.json").exists() else {}
        if not (ROOT / "results/evaluation/osdi/expVD4_freeze.md").exists():
            check(r_.returncode != 0 and "not frozen" in (r_.stdout + r_.stderr), "run_vc vd4 refuses before the VD-4 freeze")
        elif not gates_.get("stage0_supp_valid"):   # frozen, stage 0 passed: stage 1 still waits for addendum 1's supplemental validation
            check(r_.returncode != 0 and "supplemental stage-0 validation" in (r_.stdout + r_.stderr), "run_vc vd4 refuses stage 1 until the supplemental stage-0 validation (addendum 1) passed")
        elif not gates_.get("stage0_rows_valid"):   # addendum 1b: batch-row positions not yet validated
            check(r_.returncode != 0 and "batch-row position validation" in (r_.stdout + r_.stderr), "run_vc vd4 refuses stage 1 until the batch-row validation (addendum 1b) passed")
        elif not gates_.get("stage0_a1_rows_valid"):   # addendum 2: the corrected A1 not yet validated
            check(r_.returncode != 0 and "corrected A1 validation" in (r_.stdout + r_.stderr), "run_vc vd4 refuses stage 1 until the corrected-A1 validation (addendum 2) passed")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def vd4_supp_tests():
    """VD-4 addendum 1 (dry): the stage-0s plan, per-layer / per-slot records and checks, negative cases (overwrite after
    the write, decoder layout, per-slot mismatch, positions), the supplemental gate incl. A1 digest equality."""
    import csv as csv_

    import aggregate_vd4 as a4
    import mobility_node as mn
    import run_vc as rv
    import vc_emulate as ve

    print("- 8 VD-4 addendum 1 (dry)")
    units, sess = rv.vd4_plan("0s", {})
    check(units == {"dog_s1": ["VD41-A1"], "train_s0": ["VD41-A1", "VD41-D", "VD41-R"], "butterfly-feeding-slow-motion_s0": ["VD4L-A1"], "audi-snow-trail_s1": ["VD41-A1"]} and sess == [],
          f"stage 0s: A1 on the four stage-0 cells, D and R on {a4.SUPP_DR_CELL}, no inspection ({units})")
    margs = mn.parse_args(["--label", "T", "--dry_run", "--dry_sink_mb", "4", "--dry_service_s", "0.0005", "--migration_chunk", "0", "--post_chunks", "10"])

    def reset(cls, cond):
        rt = cls(margs); rt.provision()
        log = {"cost_s": {}, "checks": {}, "bytes": {}}
        ve.vd4_reset(rt, 5, cond, {}, [], True, log, None, [])
        return log
    ok_d = reset(mn.FakeRuntime, {"dec": "oracle", "ts": "in"}); ok_r = reset(mn.FakeRuntime, {"dec": "dr2", "oracle_recent": True, "ts": "in"})
    ok_a = reset(mn.FakeRuntime, {"dec": "dr2", "ts": "in_aligned"})
    check(all(ok_d["checks_supp"].get(c) for c in a4.SUPP_REQUIRED["D"][1]) and all(ok_r["checks_supp"].get(c) for c in a4.SUPP_REQUIRED["R"][1])
          and all(ok_a["checks_supp"].get(c) for c in a4.SUPP_REQUIRED["A1"][1]) and len(ok_a["supp"]["source_positions"]) == 30 and len(ok_a["supp"]["final_positions"]) == 30
          and len(ok_a["supp"]["a1_per_layer_row_slot"]) == 120,
          "D / R / A1: every supplemental check present and true; positions logged for every layer; 30 x 2 x 2 A1 (layer, row, slot) records (addendum 2)")

    class DecOverwrite(mn.FakeRuntime):   # the decoder equals the snapshot at the write (the fake write's digest), a later step changes it
        def dec_digest(self, tensors=None):
            return "changed"

    class DecLayout(mn.FakeRuntime):
        def dec_layout(self, snap):
            return {**super().dec_layout(snap), "layout_mismatch": [3], "layout_ok": False, "tensors_equal": False}

    class SlotBad(mn.FakeRuntime):
        def slot_equal(self, slots, part, snap=None, saved=None, override=None):
            rows = super().slot_equal(slots, part, snap, saved, override)
            rows[17][0] = False   # one layer, one slot
            return rows

    class PosMoved(mn.FakeRuntime):
        n = 0

        def positions(self, slots, snap=None):
            if snap is None:
                self.n += 1
            out = super().positions(slots, snap)
            if snap is None and self.n > 1 and len(slots) == 6:
                out[29] = [out[29][0] + 1] + out[29][1:]   # the last layer's slot 0 moved after the restore
            return out
    for cls, cond, key_, what in ((DecOverwrite, {"dec": "oracle", "ts": "in"}, "decoder_equal", "the decoder cache changed after its write (equal at the write)"),
                                  (DecLayout, {"dec": "oracle", "ts": "in"}, "supp:decoder_layout_equal", "a decoder-cache layout mismatch (entry 3)"),
                                  (SlotBad, {"dec": "dr2", "oracle_recent": True, "ts": "in"}, "supp:recent_k_equal_per_layer_slot", "one (layer, slot) of the recent KV differing"),
                                  (SlotBad, {"dec": "dr2", "ts": "in_aligned"}, "supp:ts_k_as_written_per_layer_slot", "one (layer, slot) of A1's rotated K differing"),
                                  (PosMoved, {"dec": "dr2", "ts": "in_aligned"}, "supp:positions_final_equal_snapshot", "a position changed after the restore")):
        lg = reset(cls, cond)
        bad = [k for k, v in lg["checks"].items() if v is False] + [f"supp:{k}" for k, v in lg["checks_supp"].items() if v is False]
        extra = (lg["checks_supp"].get("decoder_equal_at_write") is True) if cls is DecOverwrite else True
        check(key_ in bad and extra, f"addendum 1 catches {what} ({bad})")
    tmp = Path(tempfile.mkdtemp(prefix="vd4s_test_"))
    try:
        S = json.loads((ROOT / "results/evaluation/osdi/expVC/vc_schedules.json").read_text())
        root, sroot, frames = tmp / "expVC", tmp / "expVD4s", tmp / "frames"
        s0, _ = rv.vd4_plan("0", {})
        for unit, ids in s0.items():   # the original stage 0 (dry), then stage 0s in its own root
            inp, sd = unit.rsplit("_s", 1)
            subprocess.run([PY, "tools/eval/vc_emulate.py", "--input", inp, "--seed", sd, "--dry_run", "--frames_dir", str(frames), "--out_root", str(root), "--only", "OT-1,OT-L,VD31-DR2+TSin,VD3L-DR2+TSin"], cwd=ROOT, capture_output=True, text=True)
            subprocess.run([PY, "tools/eval/vc_emulate.py", "--input", inp, "--seed", sd, "--dry_run", "--frames_dir", str(frames), "--out_root", str(root), "--only", ",".join(ids), "--no_ref_frames"], cwd=ROOT, capture_output=True, text=True)
            subprocess.run([PY, "tools/eval/vc_metrics.py", "--unit", str(root / unit), "--embedders", "pixel", "--device", "cpu"], cwd=ROOT, capture_output=True, text=True)
        nvalid = 0
        for unit, ids in units.items():
            inp, sd = unit.rsplit("_s", 1)
            r_ = subprocess.run([PY, "tools/eval/vc_emulate.py", "--input", inp, "--seed", sd, "--dry_run", "--frames_dir", str(frames), "--out_root", str(sroot), "--only", ",".join(ids), "--no_ref_frames"], cwd=ROOT, capture_output=True, text=True)
            nvalid += r_.stdout.count("valid True")
        check(nvalid == 6 and not (sroot / "train_s0" / "VD41-B0").exists() and (root / "train_s0" / "VD41-A1" / "summary.json").exists(),
              "stage 0s: six valid streams in their own root; the stage-0 results stay where they are")

        def agg(tag):
            r_ = subprocess.run([PY, "tools/eval/aggregate_vd4.py", "--root", str(root), "--supp_root", str(sroot), "--dry", "--sessions", "", "--out", str(tmp / tag)], cwd=ROOT, capture_output=True, text=True)
            return (json.loads((tmp / f"{tag}.json").read_text()) if r_.returncode == 0 else {"gates": {}, "supplemental_stage0": {"runs": []}}), r_
        R, r_ = agg("s_ok")
        a1 = [r for r in R["supplemental_stage0"]["runs"] if r["condition"] == "A1"]
        check(R["gates"].get("stage0_valid") is True and R["gates"].get("stage0_supp_valid") is True and len(a1) == 4 and all(r["digests_equal_stage0"] for r in a1)
              and "Stage-0 supplemental validity (addendum 1" in (tmp / "s_ok.md").read_text(), f"supplemental gate opens on a complete dry stage 0s; A1 digests equal stage 0 {r_.stderr[-300:]}")
        p_ = sroot / "train_s0" / "VD41-A1" / "calls.csv"
        rows = list(csv_.DictReader(open(p_, newline="")))
        rows[-1]["frame_digest"] = "0" * 16
        with open(p_, "w", newline="") as fh:
            w = csv_.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
        R, _ = agg("s_dig")
        check(R["gates"].get("stage0_supp_valid") is False and R["gates"].get("stage0_valid") is True, "one A1 output digest differing from stage 0 closes the supplemental gate (the stage-0 gate is untouched)")
        shutil.rmtree(sroot / "train_s0" / "VD41-D")
        R, _ = agg("s_noD")
        check(R["gates"].get("stage0_supp_valid") is False, "a missing D run closes the supplemental gate")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def vd4_rows_tests():
    """VD-4 addendum 1b (dry): the stage-0r plan, per-(layer, row, slot) records and checks, a differing row recorded as a
    finding (not a validity failure), a prepare whose rows filled different slots caught, the gates."""
    import csv as csv_

    import aggregate_vd4 as a4
    import mobility_node as mn
    import run_vc as rv
    import vc_emulate as ve

    print("- 9 VD-4 addendum 1b (dry)")
    units, sess = rv.vd4_plan("0r", {})
    check(units == {"dog_s1": ["VD41-A1"], "train_s0": ["VD41-A1"], "butterfly-feeding-slow-motion_s0": ["VD4L-A1"], "audi-snow-trail_s1": ["VD41-A1"]} and sess == [],
          f"stage 0r: A1 on the four stage-0 cells, no inspection ({units})")
    margs = mn.parse_args(["--label", "T", "--dry_run", "--dry_sink_mb", "4", "--dry_service_s", "0.0005", "--migration_chunk", "0", "--post_chunks", "10"])

    def reset(cls, cond):
        rt = cls(margs); rt.provision()
        log = {"cost_s": {}, "checks": {}, "bytes": {}}
        ve.vd4_reset(rt, 5, cond, {}, [], True, log, None, [])
        return log
    lg = reset(mn.FakeRuntime, {"dec": "dr2", "ts": "in_aligned"})
    sp, cs = lg["supp"], lg["checks_supp"]
    check(all(cs.get(c) for c in a4.ROWS_REQUIRED) and sp["batch_rows"] == 2 and len(sp["source_positions_rows"]) == 30 and len(sp["source_positions_rows"][0]) == 2
          and sp["rows_differ"] == [] and sp["batch_rows_identical"] == {"sink": True, "recent": True, "all": True} and sp["a1_row_deltas_equal_row0"] is True
          and len(sp["a1_row_deltas"]) == 30 and len(sp["a1_row_deltas"][0]) == 2,
          "A1: per-(layer, row, slot) positions logged (30 x 2 x 6), every row check true, no differing row, row deltas equal row 0's")

    class Row1(mn.FakeRuntime):   # the second row's slot 1 (a sink slot) and slot 4 (recent) differ in layer 3, consistently live and snapshot
        def positions_all(self, slots, snap=None):
            out = super().positions_all(slots, snap)
            out[3][1] = [v + (5 if s_ in (1, 4) else 0) for s_, v in zip(slots, out[3][1])]
            return out
    lg = reset(Row1, {"dec": "dr2", "oracle_recent": True, "ts": "in_aligned", "oracle_sink_slots": [2]})
    sp, cs = lg["supp"], lg["checks_supp"]
    bad = [k for k, v in lg["checks"].items() if v is False] + [f"supp:{k}" for k, v in cs.items() if v is False]
    check(not bad and sp["rows_differ"] == [{"layer": 3, "row": 1, "slot": 1, "row0": 1, "value": 6}, {"layer": 3, "row": 1, "slot": 4, "row0": 32, "value": 37}]
          and sp["batch_rows_identical"] == {"sink": False, "recent": False, "all": False} and sp["a1_row_deltas_equal_row0"] is False,
          f"a differing batch row is recorded exactly (layer, row, slot, both values) and flagged, without failing validity ({bad})")

    class PrepRows(mn.FakeRuntime):   # the prepare filled different slots in the two rows
        def temp_sink_prepare(self, images, c):
            saved, dt = super().temp_sink_prepare(images, c)
            import numpy as np_

            class P:
                def __init__(self, a): self.a = a
                def __getitem__(self, i): return P(self.a[i])
                def tolist(self): return self.a.tolist()
            return [("k", "v", P(np_.array([[0, 1, -(1 << 30)], [0, -(1 << 30), -(1 << 30)]])))], dt
    check(reset(PrepRows, {"dec": "dr2", "ts": "in"})["checks_supp"].get("prepare_rows_filled_identical") is False, "a prepare whose rows filled different slots fails prepare_rows_filled_identical")
    tmp = Path(tempfile.mkdtemp(prefix="vd4r_test_"))
    try:
        root, sroot, rroot, frames = tmp / "expVC", tmp / "expVD4s", tmp / "expVD4r", tmp / "frames"
        s0, _ = rv.vd4_plan("0", {})
        for unit, ids in s0.items():
            inp, sd = unit.rsplit("_s", 1)
            subprocess.run([PY, "tools/eval/vc_emulate.py", "--input", inp, "--seed", sd, "--dry_run", "--frames_dir", str(frames), "--out_root", str(root), "--only", "OT-1,OT-L,VD31-DR2+TSin,VD3L-DR2+TSin"], cwd=ROOT, capture_output=True, text=True)
            subprocess.run([PY, "tools/eval/vc_emulate.py", "--input", inp, "--seed", sd, "--dry_run", "--frames_dir", str(frames), "--out_root", str(root), "--only", ",".join(ids), "--no_ref_frames"], cwd=ROOT, capture_output=True, text=True)
            subprocess.run([PY, "tools/eval/vc_metrics.py", "--unit", str(root / unit), "--embedders", "pixel", "--device", "cpu"], cwd=ROOT, capture_output=True, text=True)
        us, _ = rv.vd4_plan("0s", {})
        for stage_units, out in ((us, sroot), (units, rroot)):
            for unit, ids in stage_units.items():
                inp, sd = unit.rsplit("_s", 1)
                subprocess.run([PY, "tools/eval/vc_emulate.py", "--input", inp, "--seed", sd, "--dry_run", "--frames_dir", str(frames), "--out_root", str(out), "--only", ",".join(ids), "--no_ref_frames"], cwd=ROOT, capture_output=True, text=True)

        def agg(tag):
            r_ = subprocess.run([PY, "tools/eval/aggregate_vd4.py", "--root", str(root), "--supp_root", str(sroot), "--rows_root", str(rroot), "--dry", "--sessions", "", "--out", str(tmp / tag)], cwd=ROOT, capture_output=True, text=True)
            return (json.loads((tmp / f"{tag}.json").read_text()) if r_.returncode == 0 else {"gates": {}}), r_
        R, r_ = agg("r_ok")
        check(R["gates"].get("stage0_supp_valid") is True and R["gates"].get("stage0_rows_valid") is True and R["gates"].get("batch_rows_identical") is True
              and "Batch-row positions (addendum 1b" in (tmp / "r_ok.md").read_text(), f"rows gate opens on a complete dry stage 0r with identical rows and digests equal stage 0s {r_.stderr[-300:]}")
        p_ = rroot / "dog_s1" / "VD41-A1" / "summary.json"
        sj = json.loads(p_.read_text()); sj["vd4"]["supp"]["rows_differ"] = [{"layer": 0, "row": 1, "slot": 0, "row0": 0, "value": 3}]; sj["vd4"]["supp"]["batch_rows_identical"] = {"sink": False, "recent": True, "all": False}
        p_.write_text(json.dumps(sj))
        R, _ = agg("r_diff")
        check(R["gates"].get("stage0_rows_valid") is True and R["gates"].get("batch_rows_identical") is False and "layer 0 row 1 slot 0: row 0 0, row 1 3" in (tmp / "r_diff.md").read_text(),
              "a differing row keeps the validation gate open but closes batch_rows_identical, and is listed")
        p_ = rroot / "train_s0" / "VD41-A1" / "calls.csv"
        rows = list(csv_.DictReader(open(p_, newline="")))
        rows[-1]["frame_digest"] = "0" * 16
        with open(p_, "w", newline="") as fh:
            w = csv_.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
        R, _ = agg("r_dig")
        check(R["gates"].get("stage0_rows_valid") is False and R["gates"].get("stage0_supp_valid") is True, "one A1 output digest differing from stage 0s closes the rows gate (the earlier gates are untouched)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def vd4_a1_tests():
    """VD-4 addendum 2 (dry, fake runtime): row-wise deltas passed to rotate_temp, the regression guard, the zero-delta rule,
    the stage-0a plan, gate and digest reporting."""
    import csv as csv_

    import aggregate_vd4 as a4
    import mobility_node as mn
    import run_vc as rv
    import vc_emulate as ve

    print("- 10 VD-4 addendum 2 (dry)")
    units, sess = rv.vd4_plan("0a", {})
    check(units == {"dog_s1": ["VD41-A1"], "train_s0": ["VD41-A1"], "butterfly-feeding-slow-motion_s0": ["VD4L-A1"], "audi-snow-trail_s1": ["VD41-A1"]} and sess == [], "stage 0a: the corrected A1 on the four stage-0 cells")
    margs = mn.parse_args(["--label", "T", "--dry_run", "--dry_sink_mb", "4", "--dry_service_s", "0.0005", "--migration_chunk", "0", "--post_chunks", "10"])

    def reset(cls, cond):
        rt = cls(margs); rt.provision()
        log = {"cost_s": {}, "checks": {}, "bytes": {}}
        ve.vd4_reset(rt, 5, cond, {}, [], True, log, None, [])
        return rt, log

    class Rows(mn.FakeRuntime):   # row 1's slot 0 sits 5 frames later in layer 3; rotate_temp records what it received
        got = None

        def positions_all(self, slots, snap=None):
            out = super().positions_all(slots, snap)
            out[3][1] = [v + (5 if s_ == 0 else 0) for s_, v in zip(slots, out[3][1])]
            return out

        def rotate_temp(self, saved, deltas):
            self.got = deltas
            return super().rotate_temp(saved, deltas)
    rt, lg = reset(Rows, {"dec": "dr2", "ts": "in_aligned"})
    sp, cs = lg["supp"], lg["checks_supp"]
    check(rt.got is not None and len(rt.got) == 30 and len(rt.got[3]) == 2 and rt.got[3][0] == [0, 0, None] and rt.got[3][1] == [5, 0, None] and rt.got[0] == [[0, 0, None], [0, 0, None]]
          and cs.get("a1_deltas_applied_per_row") is True and cs.get("a1_zero_delta_rows_unchanged") is True and cs.get("ts_k_as_written_rows") is True and cs.get("ts_v_unrotated_rows") is True
          and len(sp["a1_per_layer_row_slot"]) == 120 and lg["a1_deltas_layer0"] == [0, 0, None] and [k for k, v in cs.items() if v is False] == [],
          f"rotate_temp receives per-(layer, row, slot) deltas (row 1 of layer 3 = [5, 0, None], row 0 = [0, 0, None]); 30 x 2 x 2 records; frozen layer-0 field = row 0 ({rt.got and rt.got[3]})")

    class WrongDelta(Rows):   # rotate_temp reports a delta other than the one it should have applied
        def rotate_temp(self, saved, deltas):
            out, info = super().rotate_temp(saved, deltas)
            info["per_layer_row_slot"][7]["delta"] = 99
            return out, info
    _, lg = reset(WrongDelta, {"dec": "dr2", "ts": "in_aligned"})
    check(lg["checks_supp"].get("a1_deltas_applied_per_row") is False, "a delta applied that differs from the computed per-row delta fails a1_deltas_applied_per_row")

    class ZeroChanged(Rows):   # a zero-delta (layer, row, slot) whose live K no longer equals the prepare's
        def slot_equal_rows(self, slots, part, saved=None, tensors=None):
            out = super().slot_equal_rows(slots, part, saved, tensors)
            if part == "k" and saved is not None and saved is not getattr(self, "_expect", None):
                out[2][1][0] = False
            return out
    tmp = Path(tempfile.mkdtemp(prefix="vd4a_test_"))
    try:
        S = json.loads((ROOT / "results/evaluation/osdi/expVC/vc_schedules.json").read_text())
        root, sroot, rroot, aroot, frames = tmp / "expVC", tmp / "expVD4s", tmp / "expVD4r", tmp / "expVD4a", tmp / "frames"
        s0, _ = rv.vd4_plan("0", {})
        for unit, ids in s0.items():
            inp, sd = unit.rsplit("_s", 1)
            subprocess.run([PY, "tools/eval/vc_emulate.py", "--input", inp, "--seed", sd, "--dry_run", "--frames_dir", str(frames), "--out_root", str(root), "--only", "OT-1,OT-L,VD31-DR2+TSin,VD3L-DR2+TSin"], cwd=ROOT, capture_output=True, text=True)
            subprocess.run([PY, "tools/eval/vc_emulate.py", "--input", inp, "--seed", sd, "--dry_run", "--frames_dir", str(frames), "--out_root", str(root), "--only", ",".join(ids), "--no_ref_frames"], cwd=ROOT, capture_output=True, text=True)
            subprocess.run([PY, "tools/eval/vc_metrics.py", "--unit", str(root / unit), "--embedders", "pixel", "--device", "cpu"], cwd=ROOT, capture_output=True, text=True)
        us, _ = rv.vd4_plan("0s", {})
        for stage_units, out in ((us, sroot), (units, rroot), (units, aroot)):
            for unit, ids in stage_units.items():
                inp, sd = unit.rsplit("_s", 1)
                subprocess.run([PY, "tools/eval/vc_emulate.py", "--input", inp, "--seed", sd, "--dry_run", "--frames_dir", str(frames), "--out_root", str(out), "--only", ",".join(ids), "--no_ref_frames"], cwd=ROOT, capture_output=True, text=True)

        def agg(tag):
            r_ = subprocess.run([PY, "tools/eval/aggregate_vd4.py", "--root", str(root), "--supp_root", str(sroot), "--rows_root", str(rroot), "--a1_root", str(aroot), "--dry", "--sessions", "", "--out", str(tmp / tag)], cwd=ROOT, capture_output=True, text=True)
            return (json.loads((tmp / f"{tag}.json").read_text()) if r_.returncode == 0 else {"gates": {}}), r_
        R, r_ = agg("a_ok")
        a1 = R.get("a1_rows", {}).get("runs", [])
        check(R["gates"].get("stage0_a1_rows_valid") is True and len(a1) == 4 and all(r["digests_vs_stage0r"]["pre_move_differing"] == 0 for r in a1)
              and "Corrected A1 (addendum 2" in (tmp / "a_ok.md").read_text(), f"corrected-A1 gate opens on a complete dry stage 0a; digest differences vs stage 0r reported {r_.stderr[-300:]}")
        p_ = aroot / "dog_s1" / "VD41-A1" / "summary.json"
        sj = json.loads(p_.read_text()); sj["vd4"]["checks_supp"]["a1_k_within_1ulp_of_independent_reference"] = False; p_.write_text(json.dumps(sj))
        R, _ = agg("a_ref")
        check(R["gates"].get("stage0_a1_rows_valid") is False and R["gates"].get("stage0_rows_valid") is True, "a rotated K outside 1 ulp of the independent reference closes the corrected-A1 gate (earlier gates untouched)")
        sj["vd4"]["checks_supp"]["a1_k_within_1ulp_of_independent_reference"] = True; sj["prefix_identical_to_reference"] = False; p_.write_text(json.dumps(sj))
        R, _ = agg("a_pre")
        check(R["gates"].get("stage0_a1_rows_valid") is False, "pre-move outputs differing from REF close the corrected-A1 gate")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def vd4_a1_torch_tests():
    """VD-4 addendum 2 (CPU torch, when torch is importable): the real rotate_temp and the independent reference on
    synthetic bf16 keys - batch indexing, row isolation, per-row deltas, V unchanged, zero-delta rows unchanged, and
    the rotated K against the independently built expectation."""
    try:
        import torch
    except ImportError:
        print("- 11 VD-4 addendum 2 (torch): SKIPPED - torch not importable in this environment"); return
    import re
    import types

    print("- 11 VD-4 addendum 2 (torch)")
    src = (ROOT / "models/wan/causal_model.py").read_text()
    fn = re.search(r"def _shift_temporal_rope\(.*?\n(?=\n\n)", src, re.S).group(0)
    mod = types.ModuleType("models.wan.causal_model"); mod.torch = torch; exec(fn, mod.__dict__); mod.KV_POS_EMPTY = -(1 << 30)
    saved_mods = {n: sys.modules.get(n) for n in ("models", "models.wan", "models.wan.causal_model")}
    for name in ("models", "models.wan"):
        sys.modules[name] = types.ModuleType(name)
    sys.modules["models.wan.causal_model"] = mod
    try:
        import mobility_node as mn
        G = mn.GpuRuntime
        H, D, fsl, L, NS, B = 2, 16, 3, 4, 6, 2
        c = D // 2
        inv = 1.0 / (10000 ** (torch.arange(0, c, dtype=torch.float64) / c))
        freqs = torch.polar(torch.ones(1024, c, dtype=torch.float64), torch.outer(torch.arange(1024, dtype=torch.float64), inv))
        torch.manual_seed(0)
        # per-layer source positions = the prepare's (0, 1) plus the deltas below; slot 2 is empty in the prepare
        POS = [[[22, 24, 6, 33, 34, 35], [34, 24, 6, 32, 33, 31]], [[0, 1, 6, 33, 34, 35], [7, 1, 6, 32, 33, 31]],
               [[-29, 1, 6, 33, 34, 35], [0, 21, 6, 32, 33, 31]], [[1, 1, 6, 33, 34, 35], [1, 1, 6, 32, 33, 31]]]
        layers = [{"k": (torch.randn(B, NS * fsl, H, D) * 8).to(torch.bfloat16), "v": torch.randn(B, NS * fsl, H, D).to(torch.bfloat16),
                   "pos": torch.tensor(POS[l_])} for l_ in range(L)]

        class SA:
            @staticmethod
            def kv_layers(pl): return layers
        rt = types.SimpleNamespace(torch=torch, device="cpu", fsl=fsl, sink=3, sa=SA, pl=types.SimpleNamespace(generator=types.SimpleNamespace(model=types.SimpleNamespace(freqs=freqs))))
        for m in ("_slot", "rotate_temp", "a1_reference", "slot_equal_rows", "within_ulp"):
            setattr(rt, m, types.MethodType(getattr(G, m), rt))
        temp = [(l["k"][:, :3 * fsl].clone(), l["v"][:, :3 * fsl].clone(), torch.tensor([[0, 1, -(1 << 30)], [0, 1, -(1 << 30)]])) for l in layers]
        snap = {"ring": [{"pos": l["pos"].clone()} for l in layers]}
        deltas = [[[22, 23, None], [34, 23, None]], [[0, 0, None], [7, 0, None]], [[-29, 0, None], [0, 20, None]], [[1, 0, None], [1, 0, None]]]
        out, info = rt.rotate_temp(temp, deltas)
        per = {(q["layer"], q["row"], q["slot"]): q for q in info["per_layer_row_slot"]}
        check(len(per) == L * B * 3 and info["rotated_slot_layers"] == 9 and per[(1, 0, 0)]["k_elements_changed"] == 0 and per[(1, 1, 0)]["k_elements_changed"] > 0
              and per[(2, 0, 0)]["k_elements_changed"] > 0 and per[(2, 1, 0)]["k_elements_changed"] == 0 and per[(2, 1, 1)]["k_elements_changed"] > 0 and per[(2, 0, 1)]["k_elements_changed"] == 0,
              "rotate_temp: 4 x 2 x 3 records, 9 rotations, each (layer, row, slot) rotated by its own delta (layer 1: row 1 only; layer 2: row 0 slot 0 and row 1 slot 1)")
        eq = lambda a, b: bool(torch.equal(a.view(torch.int16), b.view(torch.int16)))  # noqa: E731
        check(eq(out[1][0][0], temp[1][0][0]) and not eq(out[1][0][1], temp[1][0][1]) and eq(out[1][0][1, 3 * fsl - fsl:], temp[1][0][1, 2 * fsl:])
              and not eq(out[2][0][0, :fsl], temp[2][0][0, :fsl]) and eq(out[2][0][1, :fsl], temp[2][0][1, :fsl]) and eq(out[2][0][0, fsl:2 * fsl], temp[2][0][0, fsl:2 * fsl]) and not eq(out[2][0][1, fsl:2 * fsl], temp[2][0][1, fsl:2 * fsl]),
              "row isolation: rotating row 1 of layer 1 leaves row 0 bitwise unchanged; in layer 2 row 0 slot 0 and row 1 slot 1 change, the other row / slot of each does not; the empty slot 2 is untouched")
        check(all(eq(o[1], t[1]) for o, t in zip(out, temp)) and all(torch.equal(o[2], t[2]) for o, t in zip(out, temp)), "V and the prepare's positions are unchanged for every row")
        # different row deltas give different rotations: row 0 of layer 0 by 22 equals a direct rotation by 22, row 1 by 34 equals a direct rotation by 34
        sh = mod._shift_temporal_rope
        check(eq(out[0][0][0, :fsl], sh(temp[0][0][0, :fsl], freqs, 22)) and eq(out[0][0][1, :fsl], sh(temp[0][0][1, :fsl], freqs, 34)) and not eq(out[0][0][1, :fsl], sh(temp[0][0][1, :fsl], freqs, 22)),
              "different row deltas (22 vs 34) produce the rotation of each row's own delta, not row 0's")
        # independent reference from the raw tensors (the snapshot's pos minus the prepare's pos)
        ref_k, ref_d = rt.a1_reference(temp, snap)
        check(ref_d == deltas, f"the independent reference derives the same per-(layer, row, slot) deltas from the position tensors ({ref_d[0]})")
        for l_, o in zip(layers, out):
            l_["k"][:, :3 * fsl] = o[0]
        w = rt.within_ulp([0, 1], ref_k, 1)
        eqr = rt.slot_equal_rows([0, 1], "k", tensors=ref_k)
        check(w["within_ulp"] and w["max_abs"] <= 0.25 and all(all(r) for rows in eqr for r in rows) and w["bitwise_equal_fraction"] == 1.0,
              f"the rotated K equals the independently built expectation (bitwise on CPU; max abs {w['max_abs']})")
        ku = rt.slot_equal_rows([0, 1], "k", saved=temp)
        check(ku[1][0] == [True, True] and ku[1][1] == [False, True] and ku[3][0] == [False, True] and ku[3][1] == [False, True], "zero-delta (layer, row, slot) entries keep the prepare's K bitwise; rotated ones differ")
        layers[0]["k"][1, 0, 0, 0] += 1.0   # one element off in row 1
        w2 = rt.within_ulp([0, 1], ref_k, 1)
        check(not w2["within_ulp"] and w2["bitwise_equal_fraction"] < 1.0, "a one-element deviation beyond 1 ulp is caught by the reference comparison")
    finally:
        for n, m in saved_mods.items():
            if m is None:
                sys.modules.pop(n, None)
            else:
                sys.modules[n] = m


if __name__ == "__main__":
    main()

