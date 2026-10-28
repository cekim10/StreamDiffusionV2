#!/usr/bin/env python3
"""M1 input-log replay, E2 (osdi/m1_continuity/e2_plan.md): does Recent KV rebuilt by input-log replay keep the
migration boundary continuous? Replay-w (w = 3, 6, 12) on the 12 confirmation cells against S3 (exact Sink, zero
recent) and RS3 (exact Sink, exact recent), both reused from VD-4 / VD-5; VD-3's frozen P1 / P2 metrics and rules.

Replay-w = the S3 condition (same schedule, M1 reset at M, DR-2 decoder, refresh frozen to the exact bind at B) whose
ring is then rebuilt the E1 way: the ring at M - w (Sink, positions, indices, eviction queues exact; recent slots zero)
is restored and calls M - w .. M - 1 are replayed from the source's logged generator inputs with the source's cache
decisions forced (tools/eval/m1_replay.py). A refresh inside the window writes a replayed frame into a Sink slot (Sink
contamination, measured); the bind at B writes the exact Sink as in S3 / RS3.

Nothing frozen is modified: the conditions live in their own overlay (`m1_continuity/e2_schedules.json`), added to
`vc_schedules.unit_sched` inside this process only; vc_emulate / vc_check / vc_metrics run unchanged with that overlay
and a hook after `vd4_reset` (E2 conditions only).

    python tools/eval/m1_e2.py run --frames_dir /home/ckim151/vc_frames --clips_dir /home/ckim151/e2_clips   # on host D
    python tools/eval/m1_e2.py aggregate                                                                     # numeric (+ visual once recorded)
    python tools/eval/m1_e2.py dry --work /tmp/e2dry                                                         # whole pipeline on the fake runtime
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import re
import secrets
import statistics as st
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p_ in (ROOT, ROOT / "tools", ROOT / "tools" / "eval"):
    if str(p_) not in sys.path:
        sys.path.insert(0, str(p_))

OUT = ROOT / "results/evaluation/osdi/m1_continuity"
E2_FILE = OUT / "e2_schedules.json"
SCHED = ROOT / "results/evaluation/osdi/expVC/vc_schedules.json"
THR = ROOT / "results/evaluation/osdi/expVD3/vd3_thresholds.json"
E1_DIR = OUT / "e0e1"
GATE_ROOT = "results/evaluation/expM1E2g"
UNITS = ["train_s0", "train_s1", "audi-snow-trail_s0", "audi-snow-trail_s1", "dog_s1", "butterfly-feeding-slow-motion_s1"]
CONFIRM = [f"{u}|OT-{x}" for u in ("train_s0", "audi-snow-trail_s0", "dog_s1", "train_s1", "butterfly-feeding-slow-motion_s1", "audi-snow-trail_s1") for x in ("1", "L")]
VISUAL = ["dog_s1|OT-1", "dog_s1|OT-L", "train_s0|OT-1", "butterfly-feeding-slow-motion_s1|OT-L", "audi-snow-trail_s0|OT-L", "audi-snow-trail_s1|OT-1"]   # VD-5's six
WS = (3, 6, 12)
PH = ("P1", "P2a", "P2b", "P3")
E2_REQUIRED = ("e2_replay_recorded", "e2_refresh_frozen_before_replay", "e2_conditioning_equal_source", "e2_replay_meta_equal_per_call",
               "e2_meta_equal_snapshot_after_replay", "e2_refresh_frozen_after_replay")
S3_FROZEN_REQUIRED = ("meta_positions_equal_snapshot", "sink_k_equal", "sink_v_equal", "sink_positions_equal")
NAMES_V = ("REF", "V0", "S3", "RS3", "LW")       # blinded session: LW = Replay-w*
PAIRS = (("LW", "RS3"), ("LW", "S3"))
N_REPEAT_CELLS, N_CATCH = 2, 2
VIS = {"P1": [0], "P2a": [2, 3, 4], "P2b": [5, 1], "P3": [6]}
FLAG = {"mild", "strong", "reversed", "change", "changed", "shift", "flicker", "jump"}
ALLOWED_A = ({"none", "mild", "strong"}, {"none", "reversed", "unclear"}, {"none", "change"}, {"kept", "changed", "unsure"}, {"none", "shift"}, {"none", "flicker"}, {"none", "jump"})
ALLOWED_B = {"left", "right", "no difference"}
RATES = {"1 Gbps": 1e9, "10 Gbps": 10e9}


def e2_id(x: str, w: int) -> str:
    return f"E2{x}-L{w}"


def cid_of(name: str, x: str, w: int | None = None) -> str:
    return {"REF": "REF", "V0": f"VD4{x}-V0", "S3": f"VD4{x}-S3", "RS3": f"VD5{x}-RS3"}.get(name) or e2_id(x, int(name[1:]) if name != "LW" else w)


# --------------------------------------------------------------------------- overlay
def build_overlay() -> dict:
    import vc_schedules as vs

    S = json.loads(SCHED.read_text())
    units = {}
    for u in UNITS:
        conds = []
        for c in vs.unit_sched(S, u)["conditions"]:
            if c["id"] in ("VD41-S3", "VD4L-S3"):
                x = c["id"][3]
                for w in WS:
                    conds.append({**{k: v for k, v in c.items() if k != "vd5"}, "id": e2_id(x, w), "e2_replay_w": w, "e2_of": c["id"],
                                  "label": f"M1 E2 Replay-{w}: S3 with the recent KV rebuilt by input-log replay of calls M-{w}..M-1 at the {c['vd4_of']} schedule"})
        assert len(conds) == 2 * len(WS), f"{u}: S3 conditions missing"
        units[u] = conds
    return {"note": "M1 E2 overlay (osdi/m1_continuity/e2_plan.md); appended to vc_schedules.unit_sched by tools/eval/m1_e2.py only", "units": units}


def install_overlay(path: Path = E2_FILE):
    import vc_schedules as vs

    if getattr(vs, "_e2_overlay", None) is not None:
        return
    ov = json.loads(Path(path).read_text())["units"]
    orig = vs.unit_sched

    def unit_sched(sched, unit_name):
        base = orig(sched, unit_name)
        add = ov.get(unit_name) or []
        return {**base, "conditions": base["conditions"] + add} if add else base
    vs.unit_sched, vs._e2_overlay = unit_sched, path


# --------------------------------------------------------------------------- emulation hooks
class _State:
    cur = None      # the E2 condition being emulated
    rec = None      # m1_replay.Recorder (installed on the first E2 step)
    snap = None     # host ring snapshot before call M - w
    cond_src = None  # the source's conditioning (prompt embeddings, cross-attention cache) at M - w


ST = _State()


def conditioning(pl) -> dict:
    return {"pe": pl.conditional_dict["prompt_embeds"].detach().clone(),
            "ca": [(e["k"].detach().clone(), e["v"].detach().clone(), bool(e.get("is_init"))) for e in pl.crossattn_cache]}


def conditioning_equal(torch, pl, src: dict) -> bool:
    if src is None or not torch.equal(pl.conditional_dict["prompt_embeds"], src["pe"]):
        return False
    return all(torch.equal(e["k"], k) and torch.equal(e["v"], v) and bool(e.get("is_init")) == i for e, (k, v, i) in zip(pl.crossattn_cache, src["ca"]))


def ring_of_snapshot(snap: dict) -> dict:
    """The serialized source state at M (vd4_reset's snapshot) in m1_replay's ring format."""
    return {"k": [l_["k"] for l_ in snap["kv"]], "v": [l_["v"] for l_ in snap["kv"]],
            "meta": {"pos": [r["pos"] for r in snap["ring"]], "gi": [r["global_end_index"] for r in snap["ring"]], "li": [r["local_end_index"] for r in snap["ring"]],
                     "cs": [r["current_step"] for r in snap["ring"]], "ev": [None if e is None else [list(x) for x in e] for e in snap["evict"]]}}


def e2_replay(rt, cond: dict, snap: dict, dry: bool, log: dict):
    """After vd4_reset (S3 path; refresh frozen): rebuild the ring by input-log replay; record checks and errors."""
    import m1_replay as mr

    w, M = int(cond["e2_replay_w"]), int(cond["resets"][0])
    chs, e2 = log.setdefault("checks_supp", {}), log.setdefault("e2", {"w": w})
    if dry:
        for k_ in E2_REQUIRED:
            chs[k_] = True
        e2["dry"] = True
        return
    torch, pl = rt.torch, rt.pl
    sync = lambda: torch.cuda.synchronize(rt.device)  # noqa: E731
    calls = list(range(M - w, M))
    rec = ST.rec
    chs["e2_replay_recorded"] = ST.snap is not None and rec is not None and all(c in rec.entries for c in calls)
    if not chs["e2_replay_recorded"]:
        return
    blocks = pl.generator.model.blocks
    chs["e2_refresh_frozen_before_replay"] = {b.self_attn.adapt_sink_thr for b in blocks} == {-1}
    chs["e2_conditioning_equal_source"] = conditioning_equal(torch, pl, ST.cond_src)
    sync(); t0 = time.perf_counter()
    mr.restore(pl, ST.snap, rt.sink, zero_recent=True)
    sync(); e2["restore_s"] = time.perf_counter() - t0
    rows, _ = mr.replay(torch, pl, rec, calls, -1, sync)   # cfg_thr -1: the refresh stays frozen until the bind
    chs["e2_replay_meta_equal_per_call"] = all(not r["meta_diff"] for r in rows)
    ring = mr.compare_ring(torch, pl, ring_of_snapshot(snap), rt.sink, rt.device)
    chs["e2_meta_equal_snapshot_after_replay"] = not ring["meta_diff"]
    chs["e2_refresh_frozen_after_replay"] = {b.self_attn.adapt_sink_thr for b in blocks} == {-1}
    e2.update({"calls": calls, "replay_s": [r["replay_s"] for r in rows], "replay_s_total": sum(r["replay_s"] for r in rows),
               "meta_diff_calls": [r["call"] for r in rows if r["meta_diff"]], "log_bytes": sum(mr.log_bytes(rec.entries[c]) for c in calls),
               "refresh_in_window": {str(c): rec.entries[c]["refresh"] for c in calls if rec.entries[c]["refresh"]},
               "source_gen_s": [rec.entries[c]["gen_s"] for c in calls], "ring_at_M": ring})
    log.setdefault("bytes", {})["e2_log"] = e2["log_bytes"]
    ST.snap = ST.cond_src = None


def install_hooks():
    import m1_replay as mr
    import mobility_node as mn
    import vc_emulate as ve

    if getattr(ve, "_e2_hooks", False):
        return
    orig_rc, orig_vr, orig_step = ve.run_condition, ve.vd4_reset, mn.GpuRuntime.step

    def run_condition(rt, cond, *a, **kw):
        ST.cur = cond if cond.get("e2_replay_w") is not None else None
        ST.snap = ST.cond_src = None
        if ST.rec is not None:
            ST.rec.reset()
        try:
            return orig_rc(rt, cond, *a, **kw)
        finally:
            ST.cur = ST.snap = ST.cond_src = None
            if ST.rec is not None:
                ST.rec.reset()

    def vd4_reset(rt, c, cond, snap, fast_pl, dry, log, *a):
        temp = orig_vr(rt, c, cond, snap, fast_pl, dry, log, *a)
        if cond.get("e2_replay_w") is not None:
            e2_replay(rt, cond, snap, dry, log)
        return temp

    def step(self, c, override=None, skip=False):
        cond = ST.cur
        if cond is None:
            return orig_step(self, c, override, skip)
        M, w = int(cond["resets"][0]), int(cond["e2_replay_w"])
        if ST.rec is None:
            ST.rec = mr.Recorder(self.torch, self.pl, self.sink, self.device, lambda: self.torch.cuda.synchronize(self.device), keep_slots=False)
        if c == M - w:
            ST.snap, ST.cond_src = mr.snapshot(self.pl), conditioning(self.pl)
        if M - w <= c < M:
            ST.rec.call, ST.rec.active = c, True
        try:
            return orig_step(self, c, override, skip)
        finally:
            ST.rec.call, ST.rec.active = None, False

    ve.run_condition, ve.vd4_reset, mn.GpuRuntime.step, ve._e2_hooks = run_condition, vd4_reset, step, True


# --------------------------------------------------------------------------- sub-steps (each its own process)
def sub_emulate(a):
    install_overlay(Path(a.overlay)); install_hooks()
    import vc_emulate as ve

    inp, sd = a.unit.rsplit("_s", 1)
    argv = ["--input", inp, "--seed", sd, "--frames_dir", a.frames_dir, "--out_root", a.out_root, "--only", a.only, "--skip_done"]
    argv += ["--dry_run"] if a.dry else ["--gpu_id", str(a.gpu_id)]
    if a.no_ref_frames:
        argv.append("--no_ref_frames")
    sys.argv = ["vc_emulate.py"] + argv
    ve.main()
    bad = []
    for i in a.only.split(","):
        p = Path(a.out_root) / a.unit / i / "summary.json"
        s = json.loads(p.read_text()) if p.exists() else {}
        if not s.get("valid"):
            bad.append(f"{i}: {((s.get('vd4') or {}).get('invalid')) or 'invalid or missing'}")
    if bad:
        print(f"[E2] {a.unit}: INVALID runs {bad}", flush=True)
        sys.exit(1)


def sub_check(a):
    install_overlay(Path(a.overlay))
    import vc_check as vk

    sys.argv = ["vc_check.py", "--unit", f"{a.out_root}/{a.unit}", "--g3"] + (["--write", "--name", f"e2_checks_{a.unit}"] if not a.dry else [])
    vk.main()


def sub_metrics(a):
    install_overlay(Path(a.overlay))
    import vc_metrics as vm

    sys.argv = ["vc_metrics.py", "--unit", f"{a.out_root}/{a.unit}", "--only", a.only, "--merge"] + (
        ["--embedders", "pixel", "--device", "cpu"] if a.dry else ["--embedders", "dino,dinov2,clip", "--device", "cuda:0"])
    vm.main()


def gate_eval(root: str, groot: str) -> dict:
    import aggregate_vd4 as a4

    at = lambda p: Path(p) if Path(p).is_absolute() else ROOT / p  # noqa: E731
    new, old = a4.digests(at(groot) / "dog_s1", "VD41-S3"), a4.digests(at(root) / "dog_s1", "VD41-S3")
    r = {"calls": len(new), "stored_calls": len(old), "differing": sum(1 for c in set(new) | set(old) if new.get(c) != old.get(c))}
    return {"run": "VD41-S3 (dog_s1) re-emulated with the E2 overlay and hooks installed", **r, "pass": r["calls"] > 0 and r["calls"] == r["stored_calls"] and r["differing"] == 0}


# --------------------------------------------------------------------------- blinded material
def sub_clips(a):
    import numpy as np
    import vc_export_clips as ve
    import vc_frames as vf
    import vc_schedules as vs
    from vd5_export_clips import FIELDS_A, FIELDS_B, pad_grid

    install_overlay(Path(a.overlay))
    w = int(a.w)
    root, clips = Path(a.out_root), Path(a.clips_dir)
    sched = json.loads(SCHED.read_text())
    rng = random.Random(a.order_seed)
    cells = [tuple(c.split("|")) for c in VISUAL]
    rng.shuffle(cells)
    used, key_a, key_b, groups, F, meta = set(), {}, {}, [], {}, {}

    def code():
        while True:
            c_ = secrets.token_hex(3).upper()
            if c_ not in used:
                used.add(c_); return c_
    for unit, ot in cells:
        x = ot.split("-")[1]
        cond = next(c for c in vs.unit_sched(sched, unit)["conditions"] if c["id"] == ot)
        m, b = cond["resets"][0], cond["binds"][-1]
        calls = list(range(m - 16, b + 21))
        for n in NAMES_V:
            sp = root / unit / cid_of(n, x, w) / "summary.json"
            if not sp.exists():
                sys.exit(f"[E2 clips] missing run {unit}/{cid_of(n, x, w)}")
            R = vf.read_calls(Path(json.loads(sp.read_text())["frames"]), calls)
            F[(f"{unit}|{ot}", n)] = [ve.mark(fr, c - m, "M" if c == m else ("B" if c == b else None)) for c in calls for fr in R.get(c, [])]
        meta[f"{unit}|{ot}"] = {"bind_rel": b - m, "repo": unit.rsplit("_s", 1)[0] in ve.REPO_INPUTS}
    for gi, (unit, ot) in enumerate(cells, 1):
        cell = f"{unit}|{ot}"
        n_min = min(len(F[(cell, n)]) for n in NAMES_V)
        codes = []
        for n in NAMES_V:
            c_ = code(); codes.append(c_)
            key_a[c_] = {"cell": cell, "condition": cid_of(n, ot.split("-")[1], w), "name": n, "repeat": False}
            ve.encode(clips / "blockA" / f"group{gi:02d}" / f"{c_}.mp4", F[(cell, n)][:n_min])
        order = list(range(len(NAMES_V))); rng.shuffle(order)
        ve.encode(clips / "blockA" / f"group{gi:02d}" / "grid.mp4", [pad_grid([ve.tile(F[(cell, NAMES_V[j])][i], codes[j]) for j in order]) for i in range(n_min)])
        groups.append({"label": f"group {gi:02d}: one cell" + (" (repository clip)" if meta[cell]["repo"] else " (internal only: LOVEU, never redistributed)"),
                       "head": f"M at 0, B at +{meta[cell]['bind_rel']}; {n_min} frames", "codes": [codes[j] for j in order]})
    rep_cells = rng.sample([f"{u}|{o}" for u, o in cells], N_REPEAT_CELLS)
    reps = [(c_, n) for c_ in rep_cells for n in ("S3", "LW")]
    rng.shuffle(reps)
    gi, rcodes = len(cells) + 1, []
    for c_, n in reps:
        cc = code(); rcodes.append(cc)
        key_a[cc] = {"cell": c_, "condition": cid_of(n, c_.split("|")[1].split("-")[1], w), "name": n, "repeat": True}
        ve.encode(clips / "blockA" / f"group{gi:02d}" / f"{cc}.mp4", F[(c_, n)])
    n_min = min(len(F[r]) for r in reps)
    ve.encode(clips / "blockA" / f"group{gi:02d}" / "grid.mp4", [pad_grid([ve.tile(F[r][i], cc) for r, cc in zip(reps, rcodes)]) for i in range(n_min)])
    groups.append({"label": f"group {gi:02d}: four clips from the cells above, in random order (internal only: may contain LOVEU clips)",
                   "head": "each clip carries its own M / B markers; rate each clip on its own", "codes": rcodes})
    trials = [(f"{u}|{o}", p, "pair") for u, o in cells for p in PAIRS]
    trials += [(c_, ("REF", "V0"), "catch") for c_ in rng.sample([f"{u}|{o}" for u, o in cells], N_CATCH)]
    rng.shuffle(trials)
    for ti, (c_, (n1, n2), kind) in enumerate(trials, 1):
        left, right = (n1, n2) if rng.random() < 0.5 else (n2, n1)
        n_min = min(len(F[(c_, n)]) for n in (left, right, "REF"))
        frames = [np.concatenate([ve.tile(F[(c_, left)][i], "LEFT"), ve.tile(F[(c_, "REF")][i], "REFERENCE"), ve.tile(F[(c_, right)][i], "RIGHT")], 1) for i in range(n_min)]
        tid = f"T{ti:02d}"
        ve.encode(clips / "blockB" / f"{tid}.mp4", frames)
        key_b[tid] = {"cell": c_, "left": left, "right": right, "kind": kind}
    (clips / "sealed").mkdir(parents=True, exist_ok=True)
    kb = json.dumps({"order_seed": a.order_seed, "w_star": w, "block_a": key_a, "block_b": key_b}, indent=1, sort_keys=True).encode()
    (clips / "sealed" / "e2_blind_key.json").write_bytes(kb)
    ksha = hashlib.sha256(kb).hexdigest()
    common = (f"Key: `<clips_dir>/sealed/e2_blind_key.json`, SHA-256 `{ksha}` (do not open before BOTH forms are recorded and committed). "
              f"Order seed {a.order_seed}. Markers: yellow border + 'M' = the move call, cyan border + 'B' = the exact-bind call; the corner number is the call "
              "index relative to M. Use the listed words exactly.")
    LA = ["# M1 E2 blinded inspection, block A: single clips (fill a copy as `e2_inspection_A.md`, commit it BEFORE opening block B)", "", common,
          "Clips in `<clips_dir>/blockA/groupNN/`: one file per code and `grid.mp4`. A jump at M is `mild` or `strong` whenever one is visible; "
          "`unclear` only for motion reversal, `unsure` only for identity.", "", "STATUS: NOT RECORDED   <- replace this whole line by `STATUS: RECORDED` when every row is filled", ""]
    for g in groups:
        LA += [f"## {g['label']} ({g['head']})", "", "| code | " + " | ".join(FIELDS_A) + " |", "|" + "---|" * (len(FIELDS_A) + 1)]
        LA += [f"| {c_} |" + " |" * len(FIELDS_A) for c_ in g["codes"]] + [""]
    LB = ["# M1 E2 blinded inspection, block B: paired comparisons (open only after block A is committed; fill a copy as `e2_inspection_B.md`)", "", common,
          "Videos in `<clips_dir>/blockB/TNN.mp4`: LEFT and RIGHT are two coded outputs of one cell, REFERENCE (middle) is the uninterrupted stream of that cell. "
          "Answer each question with `left`, `right` or `no difference`.", "", "STATUS: NOT RECORDED   <- replace this whole line by `STATUS: RECORDED` when every row is filled", "",
          "| trial | " + " | ".join(FIELDS_B) + " |", "|" + "---|" * (len(FIELDS_B) + 1)]
    LB += [f"| {t} |" + " |" * len(FIELDS_B) for t in key_b] + [""]
    out = Path(a.form_dir)
    for name, L in (("e2_inspection_form_A.md", LA), ("e2_inspection_form_B.md", LB)):
        out.mkdir(parents=True, exist_ok=True)
        (out / name).write_text("\n".join(L) + "\n"); (clips / name).write_text("\n".join(L) + "\n")
    print(f"[E2 clips] w* = {w}: block A {len(key_a)} clips in {len(groups)} groups, block B {len(key_b)} trials -> {clips}; key sha256 {ksha}", flush=True)


# --------------------------------------------------------------------------- aggregation
def _rows(path: Path, n: int) -> list:
    rows = []
    for line in path.read_text().splitlines():
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) >= n + 1 and re.fullmatch(r"([0-9A-F]{6}|T\d\d)", cols[0] or ""):
            rows.append((cols[0], [x.lower() for x in cols[1:n + 1]], cols[n + 1] if len(cols) > n + 1 else ""))
    return rows


def _last_commit(path: Path) -> str:
    return subprocess.run(["git", "log", "-1", "--format=%H", "--", str(path)], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def _first_commit(path: Path) -> str:
    out = subprocess.run(["git", "log", "--format=%H", "--", str(path)], cwd=ROOT, capture_output=True, text=True).stdout.split()
    return out[-1] if out else ""


def session(d: Path, check_git: bool) -> dict | None:
    ia, ib, fa, kp = d / "e2_inspection_A.md", d / "e2_inspection_B.md", d / "e2_inspection_form_A.md", d / "e2_blind_key.json"
    if not all(p.exists() for p in (ia, ib, fa, kp)):
        return None
    if not all(re.search(r"^STATUS: RECORDED\s*$", p.read_text(), re.M) for p in (ia, ib)):
        return None
    kb = kp.read_bytes()
    if hashlib.sha256(kb).hexdigest() != re.search(r"SHA-256 `([0-9a-f]{64})`", fa.read_text()).group(1):
        sys.exit("[E2] key SHA-256 differs from the form's")
    proc = {"checked": check_git}
    if check_git:
        ca, cb, ck = _last_commit(ia), _last_commit(ib), _first_commit(kp)
        anc = lambda x, y: bool(x and y) and subprocess.run(["git", "merge-base", "--is-ancestor", x, y], cwd=ROOT).returncode == 0  # noqa: E731
        proc.update({"block_A_commit": ca, "block_B_commit": cb, "key_commit": ck, "A_before_B": ca != cb and anc(ca, cb), "B_before_key": cb != ck and anc(cb, ck)})
        proc["ok"] = proc["A_before_B"] and proc["B_before_key"]
    else:
        proc["ok"] = True
    K = json.loads(kb)
    A, B, bad = {}, {}, []
    for c_, vals, note in _rows(ia, 7):
        if c_ in K["block_a"]:
            bad += [f"{c_}:{i}:{v}" for i, v in enumerate(vals) if v not in ALLOWED_A[i]]
            A[c_] = {**K["block_a"][c_], "values": vals, "flags": [v in FLAG for v in vals], "note": note}
    for t, vals, note in _rows(ib, 2):
        if t in K["block_b"]:
            bad += [f"{t}:{i}:{v}" for i, v in enumerate(vals) if v not in ALLOWED_B]
            B[t] = {**K["block_b"][t], "values": vals, "note": note}
    return {"A": A, "B": B, "w_star": K.get("w_star"), "vocabulary_errors": bad, "procedure": proc,
            "complete": len(A) == len(K["block_a"]) and len(B) == len(K["block_b"]) and not bad}


def aggregate(root: Path, out: Path, dry: bool, e1_dir: Path = E1_DIR) -> dict:
    import aggregate_vd3 as a3
    import aggregate_vd4 as a4
    import aggregate_vd5 as a5

    tb = THR.read_bytes()
    if not dry and hashlib.sha256(tb).hexdigest()[:16] != a4.THR_SHA_FROZEN:
        sys.exit("[E2] the thresholds differ from VD-3's frozen file")
    T = json.loads(tb)
    names = ("S3", "RS3") + tuple(f"L{w}" for w in WS)
    numeric, validity, e2log, rs3_bytes_seen = {n: {} for n in names}, [], {}, []
    e1 = {}
    if not dry and e1_dir.exists():
        for f in e1_dir.glob("*_s?.json"):
            d = json.loads(f.read_text())
            for cell, r in d["cells"].items():
                for w in WS:
                    e1[(f"{d['unit']}|{cell}", w)] = r["E1"][str(w)]["ring_at_M"]
    for key in CONFIRM:
        unit_name, ot = key.split("|"); x = ot.split("-")[1]
        unit = root / unit_name
        if not (unit / "metrics.json").exists():
            continue
        Mx = json.loads((unit / "metrics.json").read_text())
        a3.EMB = "dino" if "dino" in Mx.get("embedders", []) else Mx.get("embedders", ["dino"])[0]
        ctrl, tol, p99 = a3.cell(unit, Mx, ot), a3.thresholds_for(T, key), Mx.get("ref_spike_P99")
        rb_ = ((a4.vd4_summary(unit, f"VD5{x}-RS3").get("vd4") or {}).get("bytes") or {}).get("oracle_recent")
        if rb_:
            rs3_bytes_seen.append(rb_)
        for w in WS:
            s = a4.vd4_summary(unit, e2_id(x, w))
            if not s:
                validity.append({"cell": key, "w": w, "pass": False, "why": "missing run"}); continue
            v4 = s.get("vd4") or {}
            ck, cs = v4.get("checks") or {}, v4.get("checks_supp") or {}
            miss = [c for c in S3_FROZEN_REQUIRED if c not in ck] + [f"supp:{c}" for c in E2_REQUIRED if c not in cs]
            fail = [c for c, v in ck.items() if v is False] + [f"supp:{c}" for c, v in cs.items() if v is False]
            ok = bool(s.get("valid")) and not miss and not fail and (dry or s.get("prefix_identical_to_reference") is True)
            lg = v4.get("e2") or {}
            ring = lg.get("ring_at_M") or {}
            e1r = e1.get((key, w))
            cons = None if (dry or not e1r or not ring) else all(abs(ring[q][p] - e1r[q][p]) == 0 for q in ("recent_rel", "sink_rel") for p in ("k", "v"))
            validity.append({"cell": key, "w": w, "pass": ok, "missing": miss, "failed": fail, "e1_consistent": cons})
            e2log[(key, w)] = lg
        for n in names:
            cid = {"S3": f"VD4{x}-S3", "RS3": f"VD5{x}-RS3"}.get(n) or e2_id(x, int(n[1:]))
            if not a4.vd4_summary(unit, cid):
                continue
            v = a3.cell(unit, Mx, cid)
            if v is None or tol is None:
                continue
            rr = a3.rules(v, n, tol, p99, ctrl)
            numeric[n][key] = {"rules": {p: bool(rr[p]) for p in PH}, "v1": v["v1_reset"], "late_D_c": v["P"]["sl_late"].get("D_c"),
                               "sinkless": {k_: v["P"]["sinkless"].get(k_) for k_ in ("D_c", "C_c", "dE_cross", "eO", "eR", "dO", "dR")},
                               "badness": a5.badness(v), "tol": a5.tolerances(tol, p99, v["P"]["sinkless"].get("eR") or 0.0), "p99": p99}
    gate_p = out / "e2_gate.json"
    gate = json.loads(gate_p.read_text()) if gate_p.exists() else ({"pass": True, "dry": True} if dry else None)
    valid_all = bool(gate and gate.get("pass")) and all(r["pass"] for r in validity) and len(validity) == 3 * len(CONFIRM)
    # ---- per w: P1 / P2, closeness to RS3, P2 against S3, Sink contamination, cost
    per_w = {}
    for w in WS:
        n = f"L{w}"
        cells = [k for k in CONFIRM if all(k in numeric[q] for q in ("S3", "RS3", n))]
        ni_rs3, ni_s3, gap, rel = [], [], [], []
        for k in cells:
            L, R, S = numeric[n][k], numeric["RS3"][k], numeric["S3"][k]
            ni_rs3.append(L["v1"] <= R["v1"] + R["tol"]["V1"])
            a_, b_ = L["sinkless"], S["sinkless"]
            T_ = a3.thresholds_for(T, k)
            ni_s3.append(a_["D_c"] >= b_["D_c"] - T_["dino"] and a_["C_c"] <= b_["C_c"] + T_["dE_anchor"]
                         and (a_["eO"] - a_["eR"]) <= (b_["eO"] - b_["eR"]) + S["tol"]["warp excess"] and abs(a_["dO"] - b_["dO"]) <= 0.10 * b_["dR"])
            den = S["v1"] - R["v1"]
            gap.append((S["v1"] - L["v1"]) / den if den > 0 else None)
            rel.append((L["v1"] - R["v1"]) / R["p99"])
        lg = [e2log.get((k, w)) or {} for k in CONFIRM]
        per_w[n] = {"cells": len(cells),
                    "P_pass": {p: sum(numeric[n][k]["rules"][p] for k in cells) for p in PH},
                    "V1_non_inferior_to_RS3": sum(ni_rs3), "P2_non_inferior_to_S3": sum(ni_s3), "both": sum(a_ and b_ for a_, b_ in zip(ni_rs3, ni_s3)),
                    "V1_gap_closed": {"median": st.median([g for g in gap if g is not None]) if any(g is not None for g in gap) else None,
                                      "min": min([g for g in gap if g is not None], default=None), "max": max([g for g in gap if g is not None], default=None)},
                    "V1_minus_RS3_over_P99_median": st.median(rel) if rel else None,
                    "sink_rel_k_max": max([((l_.get("ring_at_M") or {}).get("sink_rel") or {}).get("k") or 0.0 for l_ in lg], default=None),
                    "recent_rel_k_range": [min([((l_.get("ring_at_M") or {}).get("recent_rel") or {}).get("k", 1.0) for l_ in lg], default=None),
                                           max([((l_.get("ring_at_M") or {}).get("recent_rel") or {}).get("k", 1.0) for l_ in lg], default=None)],
                    "refresh_writes_in_window": [sum(len(v) for v in (l_.get("refresh_in_window") or {}).values()) for l_ in lg],
                    "replay_s_total_median": st.median([l_["replay_s_total"] for l_ in lg if l_.get("replay_s_total") is not None]) if any(l_.get("replay_s_total") is not None for l_ in lg) else None,
                    "replay_s_per_call_median": st.median([x_ for l_ in lg for x_ in (l_.get("replay_s") or [])]) if any(l_.get("replay_s") for l_ in lg) else None,
                    "log_bytes_median": st.median([l_["log_bytes"] for l_ in lg if l_.get("log_bytes")]) if any(l_.get("log_bytes") for l_ in lg) else None,
                    "per_cell": {k: {"v1": numeric[n][k]["v1"], "V1_NI_RS3": a_, "P2_NI_S3": b_, "gap_closed": g_, "rules": numeric[n][k]["rules"]}
                                 for k, a_, b_, g_ in zip(cells, ni_rs3, ni_s3, gap)}}
    # ---- selection of w* (e2_plan.md section 5; numeric only, before the inspection)
    order = sorted(WS, key=lambda w: (-per_w[f"L{w}"]["both"], -per_w[f"L{w}"]["P_pass"]["P1"],
                                      per_w[f"L{w}"]["V1_minus_RS3_over_P99_median"] if per_w[f"L{w}"]["V1_minus_RS3_over_P99_median"] is not None else 9e9, w))
    w_star = order[0]
    # ---- blinded session
    S = session(out, check_git=not dry)
    vis, calib, pairs = {}, None, None
    if S:
        if S["w_star"] != w_star:
            sys.exit(f"[E2] the session's w* ({S['w_star']}) differs from the rule's ({w_star})")
        for r in S["A"].values():
            if not r["repeat"]:
                vis.setdefault(r["cell"], {})[r["name"]] = r["flags"]
        reps = [r for r in S["A"].values() if r["repeat"]]
        first = {(r["cell"], r["name"]): r["values"] for r in S["A"].values() if not r["repeat"]}
        rep_same = sum(1 for r in reps if first.get((r["cell"], r["name"])) == r["values"])
        f_ = lambda nm, i: sum(1 for c in VISUAL if (vis.get(c) or {}).get(nm, [False] * 7)[i])  # noqa: E731
        v0f, reff = [f_("V0", i) for i in range(7)], [f_("REF", i) for i in range(7)]
        catch = [t for t in S["B"].values() if t["kind"] == "catch"]
        catch_ok = sum(1 for t in catch if t["values"] == ["no difference", "no difference"])
        calib = {"v0_flags_per_field": v0f, "ref_flags_per_field": reff, "v0_ok": all(v <= r + 1 for v, r in zip(v0f, reff)), "catch_ok": catch_ok, "catch": len(catch),
                 "repeats_identical": rep_same, "repeats": len(reps)}
        calib["pass"] = calib["v0_ok"] and catch_ok == len(catch) and rep_same >= 3
        pairs = {}
        for t in S["B"].values():
            if t["kind"] != "pair":
                continue
            other = t["left"] if t["right"] == "LW" else t["right"]
            side = "left" if t["left"] == "LW" else "right"
            pairs.setdefault(other, []).append({"cell": t["cell"], "at M": ["LW better" if v == side else ("no difference" if v == "no difference" else "LW worse") for v in t["values"]][0],
                                                "closer to REF": ["LW better" if v == side else ("no difference" if v == "no difference" else "LW worse") for v in t["values"]][1]})
    flags = {nm: {p: sum(1 for c in VISUAL if any((vis.get(c) or {}).get(nm, [False] * 7)[i] for i in VIS[p])) for p in PH} for nm in NAMES_V} if S else None
    tally = (lambda lst, q: {v: sum(1 for x_ in lst if x_[q] == v) for v in ("LW better", "no difference", "LW worse")})
    blockB = {"LW vs RS3 at M": tally((pairs or {}).get("RS3", []), "at M"), "LW vs RS3 closer": tally((pairs or {}).get("RS3", []), "closer to REF"),
              "LW vs S3 at M": tally((pairs or {}).get("S3", []), "at M"), "LW vs S3 closer": tally((pairs or {}).get("S3", []), "closer to REF")} if S else None
    # ---- recommendation (e2_plan.md section 6)
    q = per_w[f"L{w_star}"]
    num_ok = q["P_pass"]["P1"] == 12 and q["V1_non_inferior_to_RS3"] == 12 and q["P2_non_inferior_to_S3"] == 12 and q["cells"] == 12
    if not valid_all:
        rec_ = "no recommendation: validity failed"
    elif not S:
        rec_ = "pending the blinded inspection (numeric part: " + ("met" if num_ok else "NOT met -> exact-base replay") + ")"
    elif not (S["complete"] and S["procedure"]["ok"]):
        rec_ = ("log-only replay (numeric only; inspection incomplete or procedure violated)" if num_ok else "exact-base replay")
    elif not calib["pass"]:
        rec_ = ("log-only replay (numeric only; rater calibration failed)" if num_ok else "exact-base replay")
    else:
        vis_ok = flags["LW"]["P1"] <= flags["RS3"]["P1"] + 1 and blockB["LW vs RS3 at M"]["LW worse"] <= blockB["LW vs RS3 at M"]["LW better"]
        rec_ = "log-only replay" if (num_ok and vis_ok) else "exact-base replay"
    rs3_bytes = float(st.median(rs3_bytes_seen)) if rs3_bytes_seen else 1725.6e6   # RS3's recorded oracle recent-KV bytes
    res = {"valid": valid_all, "gate": gate, "validity": validity, "numeric": {n: numeric[n] for n in names}, "per_w": per_w, "w_star": w_star, "w_order": order,
           "session": None if not S else {"complete": S["complete"], "procedure": S["procedure"], "vocabulary_errors": S["vocabulary_errors"]},
           "calibration": calib, "flags_six_cells": flags, "block_B": blockB, "pairs": pairs, "recommendation": rec_, "numeric_criteria_met": num_ok,
           "rs3_recent_bytes_reference": {"bytes": rs3_bytes, **{r_: rs3_bytes * 8 / b_ for r_, b_ in RATES.items()}}}
    write_report(res, out)
    return res


def write_report(R: dict, out: Path):
    f3 = lambda v: "-" if v is None else f"{v:.3f}"  # noqa: E731
    L = ["# M1 E2 results: input-log replay vs S3 and RS3", "",
         "Generated by `tools/eval/m1_e2.py aggregate`. Rules: VD-3's frozen thresholds and rules; selection and recommendation rules in `e2_plan.md` (fixed before the run).", "",
         f"Validity: **{'PASS' if R['valid'] else 'FAIL'}**; gate {R['gate']}", ""]
    bad = [v for v in R["validity"] if not v["pass"]]
    L += [f"- invalid: {b}" for b in bad] or ["- all 36 Replay runs valid (stream, prefix, S3-path oracle checks, E2 replay checks)"]
    cons = [v["e1_consistent"] for v in R["validity"] if v.get("e1_consistent") is not None]
    L += [f"- ring errors at M equal E1's (same replay, destination session): {sum(cons)} / {len(cons)}", ""]
    L += ["## Numeric results (12 cells)", "", "| condition | P1 | P2a | P2b | P3 | V1 NI to RS3 | P2 NI to S3 | V1 gap closed (median, min..max) | (V1 - V1 RS3) / P99 median |",
          "|---|---|---|---|---|---|---|---|---|"]
    for n in ("S3", "RS3"):
        num = R["numeric"][n]
        L.append(f"| {n} | " + " | ".join(f"{sum(v['rules'][p] for v in num.values())} / {len(num)}" for p in PH) + " | - | - | - | - |")
    for w in WS:
        q = R["per_w"][f"L{w}"]
        g = q["V1_gap_closed"]
        L.append(f"| Replay-{w} | " + " | ".join(f"{q['P_pass'][p]} / {q['cells']}" for p in PH) + f" | {q['V1_non_inferior_to_RS3']} / {q['cells']} | {q['P2_non_inferior_to_S3']} / {q['cells']} | "
                 f"{f3(g['median'])} ({f3(g['min'])}..{f3(g['max'])}) | {f3(q['V1_minus_RS3_over_P99_median'])} |")
    L += ["", "## Ring, Sink contamination and cost per window", "", "| window | recent K rel at M (min..max) | Sink K rel at M (max) | refresh writes in window (per cell) | replay s/call (median) | replay s total (median) | log bytes (median) |",
          "|---|---|---|---|---|---|---|"]
    for w in WS:
        q = R["per_w"][f"L{w}"]
        L.append(f"| Replay-{w} | {f3(q['recent_rel_k_range'][0])}..{f3(q['recent_rel_k_range'][1])} | {f3(q['sink_rel_k_max'])} | {q['refresh_writes_in_window']} | "
                 f"{f3(q['replay_s_per_call_median'])} | {f3(q['replay_s_total_median'])} | {q['log_bytes_median']} |")
    rb = R["rs3_recent_bytes_reference"]
    L += ["", f"Reference: RS3's recent KV {rb['bytes'] / 1e9:.2f} GB = {rb['1 Gbps']:.1f} s at 1 Gbps, {rb['10 Gbps']:.2f} s at 10 Gbps (idealized lower bounds).", "",
          "## Per cell (V1 with REF P99; rules P1 P2a P2b P3)", "", "| cell | P99 | S3 | RS3 | " + " | ".join(f"Replay-{w}" for w in WS) + " |", "|---|---|---|---|" + "---|" * len(WS)]
    for k in CONFIRM:
        if k not in R["numeric"]["RS3"]:
            continue
        cellv = lambda n: (f"{R['numeric'][n][k]['v1']:.2f} " + "".join("y" if R["numeric"][n][k]["rules"][p] else "n" for p in PH)) if k in R["numeric"][n] else "-"  # noqa: E731
        L.append(f"| {k} | {R['numeric']['RS3'][k]['p99']:.2f} | {cellv('S3')} | {cellv('RS3')} | " + " | ".join(cellv(f"L{w}") for w in WS) + " |")
    L += ["", f"**Most promising window (selection rule): Replay-{R['w_star']}** (order {R['w_order']})", ""]
    if R["session"]:
        L += ["## Blinded inspection (REF, V0, S3, RS3, Replay-w* on the six VD-5 cells)", "", f"Session: {R['session']}", "", f"Rater calibration: {R['calibration']}", "",
              f"Flags on the six cells per phase: {R['flags_six_cells']}", "", f"Block B: {R['block_B']}", ""]
    L += [f"**Recommendation (e2_plan.md section 6): {R['recommendation']}**", ""]
    out.mkdir(parents=True, exist_ok=True)
    (out / "e2_results.md").write_text("\n".join(L) + "\n")
    (out / "e2_results.json").write_text(json.dumps(R, indent=1, default=str))
    print("\n".join(L[:40]))


# --------------------------------------------------------------------------- drivers
def _py(*args) -> list:
    return [sys.executable, str(Path(__file__).resolve())] + list(args)


def _run(cmd: list) -> bool:
    print("[E2] $ " + " ".join(cmd[1:]), flush=True)
    return subprocess.run(cmd, cwd=ROOT).returncode == 0


def ids_for(unit: str) -> str:
    return ",".join(e2_id(x, w) for x in ("1", "L") for w in WS)


def run(a):
    """Host D: preflight, gate, 6 units (emulation, checks, metrics), numeric aggregate, blinded material."""
    want = build_overlay()
    if json.loads(E2_FILE.read_text()) != want:
        sys.exit("[E2] the committed overlay differs from the one built from the frozen schedules")
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "tools", "models", "streamv2v", str(E2_FILE)], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    gpu = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits", "-i", str(a.gpu_id)], capture_output=True, text=True).stdout.strip()
    pre = {"commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(), "dirty": bool(dirty), "gpu_mem_used_mb": gpu,
           "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    (OUT / "e2_preflight.json").write_text(json.dumps(pre, indent=1))
    if dirty or not gpu or int(gpu.split()[0]) > 2000:
        sys.exit(f"[E2] preflight failed: {pre}")
    common = ["--frames_dir", a.frames_dir, "--gpu_id", str(a.gpu_id)]
    if not (OUT / "e2_gate.json").exists() or not json.loads((OUT / "e2_gate.json").read_text()).get("pass"):
        if not _run(_py("emulate", "--unit", "dog_s1", "--only", "VD41-S3", "--out_root", GATE_ROOT, "--no_ref_frames", *common)):
            sys.exit("[E2] gate emulation failed")
        g = gate_eval("results/evaluation/expVC", GATE_ROOT)
        (OUT / "e2_gate.json").write_text(json.dumps(g, indent=1))
        print(f"[E2] gate: {g}", flush=True)
        if not g["pass"]:
            sys.exit("[E2] gate FAILED: the hooks change a non-E2 run; stop")
    for u in UNITS:
        ids = ids_for(u)
        for sub, extra in (("emulate", ["--no_ref_frames", *common]), ("check", []), ("metrics", [])):
            if not _run(_py(sub, "--unit", u, "--only", ids, *extra)):
                sys.exit(f"[E2] {u} {sub} failed; stop")
    R = aggregate(ROOT / "results/evaluation/expVC", OUT, dry=False)
    if not R["valid"]:
        sys.exit("[E2] validity failed: no blinded material")
    if not _run(_py("clips", "--w", str(R["w_star"]), "--clips_dir", a.clips_dir, "--order_seed", time.strftime("%Y%m%d"))):
        sys.exit("[E2] clips failed")
    print(f"[E2] done: w* = {R['w_star']}; next: block A form (e2_inspection_A.md, commit), block B (commit), copy the key (commit)", flush=True)


def dry(a):
    """Whole pipeline on the fake runtime in a scratch work dir: REF / S3 / RS3 / V0 / Replay emulation, checks,
    metrics (pixel embedder), numeric aggregate, blinded material, a synthetic recorded session, the final aggregate."""
    work = Path(a.work); work.mkdir(parents=True, exist_ok=True)
    root, frames, clips, forms = work / "expVC", work / "frames", work / "clips", work / "forms"
    for u in UNITS:
        base = ",".join(f"VD4{x}-S3,VD5{x}-RS3,VD4{x}-V0" for x in ("1", "L"))
        if not _run(_py("emulate", "--unit", u, "--only", base, "--out_root", str(root), "--frames_dir", str(frames), "--dry")):
            sys.exit(f"dry base {u}")
        for sub, extra in (("emulate", ["--frames_dir", str(frames), "--no_ref_frames"]), ("check", []), ("metrics", [])):
            if not _run(_py(sub, "--unit", u, "--only", ids_for(u), "--out_root", str(root), "--dry", *extra)):
                sys.exit(f"dry {sub} {u}")
        if not _run(_py("metrics", "--unit", u, "--only", ",".join(f"VD4{x}-S3,VD5{x}-RS3" for x in ("1", "L")), "--out_root", str(root), "--dry")):
            sys.exit(f"dry metrics base {u}")
    R = aggregate(root, forms, dry=True)
    if not _run(_py("clips", "--w", str(R["w_star"]), "--clips_dir", str(clips), "--order_seed", "1", "--out_root", str(root), "--form_dir", str(forms))):
        sys.exit("dry clips")
    rnd = random.Random(5)
    for blk, n in (("A", 7), ("B", 2)):
        txt = (forms / f"e2_inspection_form_{blk}.md").read_text()
        out = []
        for line in txt.splitlines():
            cols = [c.strip() for c in line.strip().strip("|").split("|")]
            if line.startswith("STATUS:"):
                line = "STATUS: RECORDED"
            elif re.fullmatch(r"([0-9A-F]{6}|T\d\d)", cols[0] or "") and len(cols) >= n + 1:
                vals = [sorted(ALLOWED_A[i])[0] if blk == "A" else rnd.choice(sorted(ALLOWED_B)) for i in range(n)]
                line = "| " + cols[0] + " | " + " | ".join(vals) + " | |"
            out.append(line)
        (forms / f"e2_inspection_{blk}.md").write_text("\n".join(out) + "\n")
    (forms / "e2_blind_key.json").write_bytes((clips / "sealed" / "e2_blind_key.json").read_bytes())
    R2 = aggregate(root, forms, dry=True)
    ok = R2["session"] is not None and R2["session"]["complete"] and R2["calibration"] is not None
    print(f"[E2 dry] {'PASS' if ok else 'FAIL'}: w* {R2['w_star']}, recommendation: {R2['recommendation']}")
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("emulate", "check", "metrics"):
        p = sp.add_parser(name)
        p.add_argument("--unit", required=True); p.add_argument("--only", required=True)
        p.add_argument("--out_root", default="results/evaluation/expVC"); p.add_argument("--frames_dir", default=None)
        p.add_argument("--gpu_id", type=int, default=0); p.add_argument("--dry", action="store_true"); p.add_argument("--no_ref_frames", action="store_true")
        p.add_argument("--overlay", default=str(E2_FILE))
    p = sp.add_parser("clips")
    p.add_argument("--w", required=True); p.add_argument("--clips_dir", required=True); p.add_argument("--order_seed", type=int, required=True)
    p.add_argument("--out_root", default=str(ROOT / "results/evaluation/expVC")); p.add_argument("--form_dir", default=str(OUT)); p.add_argument("--overlay", default=str(E2_FILE))
    sp.add_parser("schedules")
    p = sp.add_parser("aggregate"); p.add_argument("--root", default=str(ROOT / "results/evaluation/expVC"))
    p = sp.add_parser("run"); p.add_argument("--frames_dir", required=True); p.add_argument("--clips_dir", required=True); p.add_argument("--gpu_id", type=int, default=0)
    p = sp.add_parser("dry"); p.add_argument("--work", required=True)
    a = ap.parse_args()
    if a.cmd == "schedules":
        E2_FILE.write_text(json.dumps(build_overlay(), indent=1) + "\n"); print(f"[E2] wrote {E2_FILE}")
    elif a.cmd == "emulate":
        sub_emulate(a)
    elif a.cmd == "check":
        sub_check(a)
    elif a.cmd == "metrics":
        sub_metrics(a)
    elif a.cmd == "clips":
        sub_clips(a)
    elif a.cmd == "aggregate":
        aggregate(Path(a.root), OUT, dry=False)
    elif a.cmd == "run":
        run(a)
    elif a.cmd == "dry":
        dry(a)


if __name__ == "__main__":
    main()
