#!/usr/bin/env python3
"""Experiment W: LOVEU-TGVE-2023 workload preparation (no OTTER run, no GPU).

The rule is fixed in results/evaluation/osdi/expW/loveu_tgve_verification.md section 4. Steps, in order:

    population  list every video of the extracted archive (identifiers, source, captions, decode properties); no
                motion score. Its output is committed before `select` runs.
    select      motion score of every included video (an input property) and the deterministic 16-video subset with
                its prompt types.
    check       load the selected videos with the pipeline's own loader (streamv2v.inference_common.load_mp4_as_tensor,
                resize to 480x832) and report what the harness would feed it (loop period, repeats); CPU only.
    prepare     on a host that runs W: verify the official archive's SHA-256, copy the selected mp4s byte-for-byte and
                write one prompt file per (video, prompt type). Output goes to a directory outside version control.

The archive and the videos are untrusted input data: run this script with `python -I` and pass paths as arguments;
nothing in the data is executed. The original videos are never modified or committed.

    # versions = the project pins (pyproject.toml); torchvision 0.21's read_video fails with PyAV >= 14
    uv run --no-project --python 3.11 --with av==13.1.0 --with numpy==1.24.4 python -I tools/eval/expw_loveu.py population --root <dir>/loveu-tgve-2023
    uv run --no-project --python 3.11 --with av==13.1.0 --with numpy==1.24.4 python -I tools/eval/expw_loveu.py select --root <dir>/loveu-tgve-2023
    uv run --no-project --python 3.12 --with torch==2.6.0 --with torchvision==0.21.0 --with av==13.1.0 --with numpy --with einops \
        --with omegaconf python -I tools/eval/expw_loveu.py check --root <dir>/loveu-tgve-2023
    python -I tools/eval/expw_loveu.py prepare --zip <path>/loveu-tgve-2023.zip --out data/loveu_tgve_2023   # git-ignored
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "results/evaluation/osdi/expW"
POP_CSV = OUT_DIR / "loveu_population.csv"
SEL_CSV = OUT_DIR / "loveu_selection.csv"
MOTION_CSV = OUT_DIR / "loveu_motion_scores.csv"
CHECK_JSON = OUT_DIR / "loveu_pipeline_check.json"

ARCHIVE_SHA256 = "ed2e7166c566c54d92bab1b5c0bae580ac9a3e768b88024e55181413321a0503"   # loveu-tgve-2023.zip, 279,628,311 B, downloaded 2026-10-18
ARCHIVE_URL = "https://drive.google.com/file/d/1D7ZVm66IwlKhS6UINoDgFiFJp_mLIQ0W/view"  # official link (track page and README)
SOURCES = ["DAVIS_480p", "videvo_480p", "youtube_480p"]   # archive folders, in the rule's tie-break order (alphabetical)
CSV_SECTIONS = {"DAVIS Videos:": "DAVIS_480p", "Youtube Videos:": "youtube_480p", "Videvo Videos:": "videvo_480p"}
CAPTIONS = [("style", "Style Change Caption"), ("object", "Object Change Caption"),
            ("background", "Background Change Caption"), ("multiple", "Multiple Changes Caption")]
N_SELECT, MIN_PER_SOURCE = 16, 3


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read_dataset_csv(root: Path) -> dict:
    """Video name -> {section, gt caption, four edit captions, source url} from LOVEU-TGVE-2023_Dataset.csv."""
    out, section = {}, None
    with open(root / "LOVEU-TGVE-2023_Dataset.csv", newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    head = rows[0]
    for r in rows[1:]:
        r = r + [""] * (len(head) - len(r))
        name = r[0].strip()
        if name in CSV_SECTIONS:
            section = CSV_SECTIONS[name]
            continue
        if not name:
            continue
        d = dict(zip(head, r))
        out[name] = {"csv_section": section, "gt_caption": d["Our GT caption"].strip(), "source_url": d["Source"].strip(),
                     **{t: d[col].strip() for t, col in CAPTIONS}}
    return out


def probe(mp4: Path) -> dict:
    import av

    with av.open(str(mp4)) as c:
        s = c.streams.video[0]
        n, w, h = 0, None, None
        for fr in c.decode(s):
            n += 1
            w, h = fr.width, fr.height
        return {"frames": n, "width": w, "height": h, "fps": float(s.average_rate) if s.average_rate else None,
                "codec": s.codec_context.name, "pix_fmt": s.codec_context.pix_fmt,
                "container_duration_s": (c.duration / 1e6) if c.duration else None}


def cmd_population(a):
    root = Path(a.root)
    meta = read_dataset_csv(root)
    rows, seen = [], set()
    for src in SOURCES:
        for mp4 in sorted((root / src / "480p_videos").glob("*.mp4")):
            name = mp4.stem
            seen.add(name)
            m = meta.get(name)
            frames_dir = root / src / "480p_frames" / name
            row = {"video_id": name, "source": src, "csv_section": m["csv_section"] if m else "", "source_url": m["source_url"] if m else "",
                   "mp4_bytes": mp4.stat().st_size, "mp4_sha256": sha256_file(mp4),
                   "jpg_frames": len(list(frames_dir.glob("*.jpg"))) if frames_dir.is_dir() else 0}
            reasons = []
            try:
                row.update(probe(mp4))
            except Exception as e:   # noqa: BLE001 - a decode failure is an exclusion reason, recorded
                row.update({"frames": 0}); reasons.append(f"decode_error:{type(e).__name__}")
            row["duration_s"] = round(row["frames"] / row["fps"], 4) if row.get("fps") else None
            if row["frames"] < 32:
                reasons.append("fewer_than_32_frames")
            if not m:
                reasons.append("not_in_dataset_csv")
            elif any(not m[t] for t, _ in CAPTIONS):
                reasons.append("missing_edit_caption")
            if m and m["csv_section"] != src:
                reasons.append("csv_section_mismatch")
            row["included"] = not reasons
            row["exclusion"] = ";".join(reasons)
            rows.append(row)
    orphans = sorted(set(meta) - seen)
    POP_CSV.parent.mkdir(parents=True, exist_ok=True)
    cols = ["video_id", "source", "csv_section", "source_url", "frames", "jpg_frames", "width", "height", "fps", "duration_s",
            "container_duration_s", "codec", "pix_fmt", "mp4_bytes", "mp4_sha256", "included", "exclusion"]
    with open(POP_CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
    print(f"[population] {len(rows)} videos, {sum(r['included'] for r in rows)} included; CSV names without a video: {orphans or 'none'}")
    for src in SOURCES:
        print(f"  {src}: {sum(1 for r in rows if r['source'] == src and r['included'])} included")
    print(f"  -> {POP_CSV.relative_to(REPO_ROOT)}")


def motion_score(mp4: Path) -> float:
    """Mean absolute BT.601 luma difference between consecutive frames at the native resolution (0-255 scale)."""
    import av
    import numpy as np

    prev, tot, n = None, 0.0, 0
    with av.open(str(mp4)) as c:
        for fr in c.decode(c.streams.video[0]):
            rgb = fr.to_ndarray(format="rgb24").astype(np.float64)
            y = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
            if prev is not None:
                tot += float(np.abs(y - prev).mean()); n += 1
            prev = y
    return tot / n


def allocate(counts: dict) -> dict:
    """>= MIN_PER_SOURCE per source, the rest proportional to the source sizes by largest remainder (ties: source name).
    A source smaller than its allocation gives all its videos; the shortfall is re-allocated by the same rule."""
    alloc, active, budget = {}, dict(counts), N_SELECT
    while True:
        base = {s: min(MIN_PER_SOURCE, n) for s, n in active.items()}
        rest = budget - sum(base.values())
        tot = sum(active.values())
        quota = {s: rest * n / tot for s, n in active.items()}
        add = {s: math.floor(q) for s, q in quota.items()}
        left = rest - sum(add.values())
        for s in sorted(active, key=lambda s: (-(quota[s] - add[s]), s))[:left]:
            add[s] += 1
        want = {s: base[s] + add[s] for s in active}
        short = [s for s in active if want[s] > active[s]]
        if not short:
            alloc.update(want); return alloc
        for s in short:   # take all, remove from the pool, re-allocate the remaining budget
            alloc[s] = active.pop(s); budget -= alloc[s]


def cmd_select(a):
    root = Path(a.root)
    with open(POP_CSV, newline="") as fh:
        pop = [r for r in csv.DictReader(fh) if r["included"] == "True"]
    meta = read_dataset_csv(root)
    import av
    import numpy as np

    scores = []
    for r in pop:
        s = motion_score(root / r["source"] / "480p_videos" / f"{r['video_id']}.mp4")
        scores.append({"video_id": r["video_id"], "source": r["source"], "frames": r["frames"], "motion_score": round(s, 6)})
    with open(MOTION_CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(scores[0])); w.writeheader(); w.writerows(scores)
    counts = {s: sum(1 for r in scores if r["source"] == s) for s in SOURCES}
    alloc = allocate(counts)
    chosen = []
    for src in SOURCES:
        lst = sorted((r for r in scores if r["source"] == src), key=lambda r: (r["motion_score"], r["video_id"]))
        n, k = len(lst), alloc[src]
        for j in range(k):
            pos = math.floor((j + 0.5) * n / k)
            chosen.append({**lst[pos], "motion_rank_in_source": pos, "n_source": n, "alloc_source": k})
    chosen.sort(key=lambda r: (r["source"], r["motion_rank_in_source"]))
    out = []
    for i, r in enumerate(chosen):
        ptype = CAPTIONS[i % 4][0]
        m = meta[r["video_id"]]
        out.append({"order": i, **r, "prompt_type": ptype, "prompt_column": dict(CAPTIONS)[ptype], "prompt": m[ptype],
                    "source_url": m["source_url"], "gt_caption": m["gt_caption"]})
    with open(SEL_CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    print(f"[select] counts {counts} -> allocation {alloc}; av {av.__version__}, numpy {np.__version__}")
    for r in out:
        print(f"  {r['order']:2d} {r['source']:13s} {r['video_id']:32s} frames {r['frames']:>4} motion {r['motion_score']:8.3f} "
              f"(rank {r['motion_rank_in_source']}/{r['n_source']}) {r['prompt_type']}")
    print(f"  -> {SEL_CSV.relative_to(REPO_ROOT)}, {MOTION_CSV.relative_to(REPO_ROOT)}")


def cmd_check(a):
    """The pipeline's loader on each selected video (CPU) and the harness's repeat arithmetic (proto_handoff.build_runtime)."""
    sys.path.insert(0, str(REPO_ROOT))
    import torch
    import torchvision

    from streamv2v.inference_common import load_mp4_as_tensor

    root = Path(a.root)
    with open(SEL_CSV, newline="") as fh:
        sel = list(csv.DictReader(fh))
    chunk, first = 4, 5   # base_chunk_size 4 x num_frame_per_block 1; the first call consumes 1 + chunk frames
    plans = {"W1 (330 calls)": 330, "W2 (M 30 + post 130)": 160}
    res = []
    for r in sel:
        v = load_mp4_as_tensor(str(root / r["source"] / "480p_videos" / f"{r['video_id']}.mp4"), resize_hw=(480, 832))
        T = int(v.shape[1])
        row = {"video_id": r["video_id"], "source": r["source"], "loaded_shape_CTHW": list(v.shape), "dtype": str(v.dtype),
               "min": round(float(v.min()), 4), "max": round(float(v.max()), 4), "finite": bool(torch.isfinite(v).all()),
               "loop_period_calls": T / chunk}
        for lab, calls in plans.items():
            need = 1 + chunk + calls * chunk
            row[f"{lab}: frames needed / repeats"] = [need, (need + T - 1) // T]
        res.append(row)
        print(f"  {r['video_id']:32s} {row['loaded_shape_CTHW']} [{row['min']}, {row['max']}] finite {row['finite']} loop every {T / chunk:g} calls")
    out = {"torch": torch.__version__, "torchvision": torchvision.__version__,
           "loader": "streamv2v.inference_common.load_mp4_as_tensor(resize_hw=(480, 832)) as called by tools/proto_handoff.build_runtime",
           "videos": res, "all_ok": all(x["finite"] and x["loaded_shape_CTHW"][0] == 3 and x["loaded_shape_CTHW"][2:] == [480, 832] for x in res)}
    CHECK_JSON.write_text(json.dumps(out, indent=1))
    print(f"[check] all_ok {out['all_ok']} -> {CHECK_JSON.relative_to(REPO_ROOT)}")


def cmd_prepare(a):
    """Byte-for-byte copies of the selected mp4s + one prompt file each (the prompt is the archive's caption, one line)."""
    z = Path(a.zip)
    got = sha256_file(z)
    if got != ARCHIVE_SHA256:
        sys.exit(f"[prepare] archive SHA-256 {got} != {ARCHIVE_SHA256} (official archive of {ARCHIVE_URL}); stopping")
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    with open(SEL_CSV, newline="") as fh:
        sel = list(csv.DictReader(fh))
    with zipfile.ZipFile(z) as zf:
        for r in sel:
            member = f"loveu-tgve-2023/{r['source']}/480p_videos/{r['video_id']}.mp4"
            data = zf.read(member)
            dst = out / f"{r['video_id']}.mp4"
            dst.write_bytes(data)
            (out / f"{r['video_id']}__{r['prompt_type']}.txt").write_text(r["prompt"] + "\n", encoding="utf-8")
            print(f"  {dst.name} ({len(data)} B, sha256 {hashlib.sha256(data).hexdigest()[:16]}) + {r['video_id']}__{r['prompt_type']}.txt")
    (out / "README.txt").write_text("LOVEU-TGVE-2023 videos (CVPR 2023 Text Guided Video Editing Competition, arXiv:2310.16003), "
                                    "selected for Experiment W. Not for redistribution. Source and license notes: "
                                    "results/evaluation/osdi/expW/loveu_tgve_verification.md\n")
    print(f"[prepare] {len(sel)} videos -> {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("population", "select", "check"):
        p = sp.add_parser(name); p.add_argument("--root", required=True, help="extracted archive directory (.../loveu-tgve-2023)")
    p = sp.add_parser("prepare"); p.add_argument("--zip", required=True); p.add_argument("--out", required=True)
    a = ap.parse_args()
    {"population": cmd_population, "select": cmd_select, "check": cmd_check, "prepare": cmd_prepare}[a.cmd](a)


if __name__ == "__main__":
    main()
