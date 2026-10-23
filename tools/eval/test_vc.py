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
            nc = len(out["inputs"][inp]["conditions"])
            check(r_.returncode == 0 and r_.stdout.count("valid True") == nc, f"{inp}: {nc} conditions emulated (7 VC{' + 16 VD' if nc > 7 else ''}), all valid")
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

        print("- 6 metric self-test (pixel stand-in embedder) and dry aggregation")
        r_ = subprocess.run([PY, "tools/eval/vc_metrics.py", "--selftest", "--embedders", "pixel", "--device", "cpu", "--out", str(tmp / "st.json")], cwd=ROOT, capture_output=True, text=True)
        check(r_.returncode == 0, f"self-test passes: cut V1, color-shift V4, content V5a {r_.stdout[-200:] if r_.returncode else ''}")
        r_ = subprocess.run([PY, "tools/eval/vc_metrics.py", "--unit", str(unit), "--embedders", "pixel", "--device", "cpu"], cwd=ROOT, capture_output=True, text=True)
        check(r_.returncode == 0 and (unit / "metrics.json").exists(), "metrics on the dry unit")
        r_ = subprocess.run([PY, "tools/eval/aggregate_vc.py", "--root", str(tmp / "expVCt"), "--dry"], cwd=ROOT, capture_output=True, text=True)
        check(r_.returncode == 0 and "VC-H1" in r_.stdout and "VC-H2" in r_.stdout and "VD" not in r_.stdout.split("## Playback")[0].split("## Descriptive")[-1],
              "VC aggregation (block bootstrap, effect sizes, verdicts; VD conditions excluded)")
        r_ = subprocess.run([PY, "tools/eval/aggregate_vd.py", "--root", str(tmp / "expVCt"), "--dry"], cwd=ROOT, capture_output=True, text=True)
        check(r_.returncode == 0 and "VD-H2" in r_.stdout and "dog | OT-1" in r_.stdout, f"VD aggregation (main effects, verdicts) {r_.stderr[-300:]}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\nALL PASS" if not FAILS else f"\nFAILURES ({len(FAILS)}):\n  " + "\n  ".join(FAILS))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
