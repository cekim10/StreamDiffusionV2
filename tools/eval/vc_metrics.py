#!/usr/bin/env python3
"""Experiment VC metrics (preregistration draft 3 sections 4-5; implementation_plan.md section 4). Runs on the host
that holds the frames. V6 (DOVER) is excluded (D8, 2026-10-22): no code path here downloads or runs it.

Per condition (paired with REF at the same calls; pairs are matched on the input chunk the output belongs to, never
on wall-clock time), per call:
  V2 / V3  transitions between consecutive output frames (input-motion-conditioned warp error E_O / E_R with
           Farneback flow of the INPUT frames of the same transition, frame difference d_O / d_R); rd_metrics functions
  V1       spike at a reset / bind / cold emit: d_O of the first transition into the event call divided by the median
           d_O of the 8 preceding transitions (the RD definition). A cold restart's event transition spans the skipped
           call (flagged "across_gap"). REF's own spike distribution over its span gives P99 and percentile ranks
           (descriptive context, not a perceptual threshold)
  V4       mean CIELAB of the call's frames; window CIEDE2000 to REF at the same calls, and to the stream's own 16
           pre-move calls
  V5a      DINO ViT-B/16 (primary) / DINOv2 ViT-B/14 (sensitivity) CLS features: cosine to the mean feature of the
           16 pre-move calls; VBench-style mean of first-frame and previous-frame similarity
  V5b      CLIP ViT-L/14 (OpenAI weights) image-text cosine with the prompt
Window statistics are means over calls of per-call means over frames (aggregate_vc.py adds the block bootstrap).

    python tools/eval/vc_metrics.py --unit results/evaluation/expVC/dog_s0 [--only OT-1] [--embedders dino,dinov2,clip]
    python tools/eval/vc_metrics.py --selftest --clip examples/original.mp4     # VC-0 metric sanity on a repository clip
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics as st
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for p_ in (ROOT, ROOT / "tools", ROOT / "tools" / "eval"):
    if str(p_) not in sys.path:
        sys.path.insert(0, str(p_))

import vc_frames as vf  # noqa: E402

PRE = 16
SPIKE_PREV = 8   # RD definition: median of the 8 preceding transitions


# ----------------------------------------------------------------------------- embedders
class Embedder:
    name = "base"

    def image(self, frames: np.ndarray) -> np.ndarray:   # [n, H, W, 3] uint8 -> [n, d] L2-normalized
        raise NotImplementedError

    def text(self, s: str) -> np.ndarray:
        raise NotImplementedError


class PixelEmbedder(Embedder):
    """Tests only: a downsampled-pixel vector (no model)."""
    name = "pixel-test"

    def image(self, frames):
        x = np.stack([f[::16, ::16].astype(np.float32).ravel() for f in frames]); x -= x.mean(1, keepdims=True)
        return x / (np.linalg.norm(x, axis=1, keepdims=True) + 1e-8)

    def text(self, s):
        return None


class _TorchEmbedder(Embedder):
    def __init__(self, device):
        import torch

        self.torch, self.device = torch, device

    def _prep(self, frames, size=224, mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225), resize_ratio=256 / 224):
        """Resize the shorter side to resize_ratio * size (bicubic), center crop size x size, normalize. DINO / DINOv2:
        the ImageNet evaluation transform (256 -> 224); CLIP: OpenAI's transform (shorter side 224, center crop 224)."""
        import torch.nn.functional as F

        t = self.torch.from_numpy(np.ascontiguousarray(frames)).to(self.device).permute(0, 3, 1, 2).float() / 255.0
        h, w = t.shape[-2:]
        s = int(round(size * resize_ratio))
        nh, nw = (s, int(round(w * s / h))) if h <= w else (int(round(h * s / w)), s)
        t = F.interpolate(t, size=(nh, nw), mode="bicubic", align_corners=False, antialias=True).clamp(0, 1)
        top, left = (nh - size) // 2, (nw - size) // 2
        t = t[..., top:top + size, left:left + size]
        m = self.torch.tensor(mean, device=self.device).view(1, 3, 1, 1); sd = self.torch.tensor(std, device=self.device).view(1, 3, 1, 1)
        return (t - m) / sd

    def _norm(self, z):
        z = z.float()
        return (z / z.norm(dim=-1, keepdim=True)).cpu().numpy()


class DinoEmbedder(_TorchEmbedder):
    def __init__(self, device, v2=False):
        super().__init__(device)
        self.name = "dinov2_vitb14" if v2 else "dino_vitb16"
        repo = "facebookresearch/dinov2" if v2 else "facebookresearch/dino:main"
        self.model = self.torch.hub.load(repo, self.name).to(device).eval()

    def image(self, frames):
        out = []
        with self.torch.no_grad():
            for i in range(0, len(frames), 32):
                out.append(self._norm(self.model(self._prep(frames[i:i + 32]))))
        return np.concatenate(out)


class ClipEmbedder(_TorchEmbedder):
    name = "clip_vitl14_openai"

    def __init__(self, device):
        super().__init__(device)
        import open_clip

        self.model, _, _ = open_clip.create_model_and_transforms("ViT-L-14", pretrained="openai", device=device)
        self.model.eval()
        self.tok = open_clip.get_tokenizer("ViT-L-14")

    def image(self, frames):
        mean, std = (0.48145466, 0.4578275, 0.40821073), (0.26862954, 0.26130258, 0.27577711)   # OpenAI CLIP normalization
        out = []
        with self.torch.no_grad():
            for i in range(0, len(frames), 32):
                out.append(self._norm(self.model.encode_image(self._prep(frames[i:i + 32], 224, mean, std, resize_ratio=1.0))))
        return np.concatenate(out)

    def text(self, s):
        with self.torch.no_grad():
            return self._norm(self.model.encode_text(self.tok([s]).to(self.device)))[0]


def make_embedders(names: str, device: str) -> dict:
    out = {}
    for n in [x for x in names.split(",") if x]:
        out[n] = {"dino": lambda: DinoEmbedder(device), "dinov2": lambda: DinoEmbedder(device, v2=True), "clip": lambda: ClipEmbedder(device),
                  "pixel": lambda: PixelEmbedder()}[n]()
    return out


def provenance() -> dict:
    """SHA-256 of every model weight file in the torch.hub, open_clip / CLIP and Hugging Face caches (D3 record)."""
    import os

    roots = []
    try:
        import torch

        roots.append(Path(torch.hub.get_dir()))
    except ImportError:
        pass
    roots += [Path(os.path.expanduser(p)) for p in ("~/.cache/clip", "~/.cache/open_clip", "~/.cache/huggingface/hub")]
    out = {}
    for r in roots:
        if not r.exists():
            continue
        for f in r.rglob("*"):
            if f.is_file() and f.suffix in (".pth", ".pt", ".bin", ".safetensors"):
                h = hashlib.sha256()
                with open(f, "rb") as fh:
                    for blk in iter(lambda: fh.read(1 << 24), b""):
                        h.update(blk)
                out[str(f)] = {"sha256": h.hexdigest(), "bytes": f.stat().st_size}
    return out


# ----------------------------------------------------------------------------- per-stream series
def lab_mean(frames: np.ndarray) -> np.ndarray:
    from skimage.color import rgb2lab

    return np.mean([rgb2lab(f[::4, ::4].astype(np.float32) / 255.0).reshape(-1, 3).mean(0) for f in frames], axis=0)


def de2000(a, b) -> float:
    from skimage.color import deltaE_ciede2000

    return float(deltaE_ciede2000(np.asarray(a, dtype=np.float64)[None], np.asarray(b, dtype=np.float64)[None])[0])


def transitions(O: dict, R: dict, I: dict) -> list[dict]:
    """O, R, I: {call: [gray 1/4-res frames]} (I = the input frames each output belongs to). Consecutive output frames,
    including across a call with no output (flagged across_gap; flow / warp error not computed there)."""
    import rd_metrics as rm

    frames = [(c, o, R.get(c, [None] * len(O[c]))[j] if c in R else None, I[c][j]) for c in sorted(O) for j, o in enumerate(O[c])]
    out = []
    for k in range(1, len(frames)):
        c0, o0, r0, i0 = frames[k - 1]; c1, o1, r1, i1 = frames[k]
        gap = c1 - c0 > 1
        dO = float(np.abs(o1.astype(np.float32) - o0).mean())
        dR = float(np.abs(r1.astype(np.float32) - r0).mean()) if (r0 is not None and r1 is not None and not gap) else None
        eO = eR = None
        if not gap:
            fl = rm._flow(i0, i1)
            eO = rm.warp_error(o0, o1, fl)
            eR = rm.warp_error(r0, r1, fl) if (r0 is not None and r1 is not None) else None
        out.append({"call": c1, "first": c1 != c0, "across_gap": gap, "dO": dO, "dR": dR, "eO": eO, "eR": eR})
    return out


def spike_at(trans: list[dict], call: int, key="dO") -> dict:
    idx = next((j for j, t in enumerate(trans) if t["call"] == call and t["first"]), None)
    if idx is None or idx < SPIKE_PREV:
        return {"call": call, "spike": None}
    prev = [t[key] for t in trans[idx - SPIKE_PREV:idx] if t[key] is not None]
    m = st.median(prev) if prev else None
    v = trans[idx][key]
    return {"call": call, "spike": (v / m) if (m and v is not None) else None, "across_gap": trans[idx]["across_gap"], "d": v, "local_median": m}


def ref_spike_distribution(trans_ref: list[dict]) -> list[float]:
    """REF's own V1 at every call boundary of its span (d of the first transition into the call / median of the 8 before)."""
    out = []
    for j, t in enumerate(trans_ref):
        if t["first"] and j >= SPIKE_PREV:
            m = st.median(x["dO"] for x in trans_ref[j - SPIKE_PREV:j])
            if m > 0:
                out.append(t["dO"] / m)
    return out


def percentile_rank(dist: list[float], v: float) -> float:
    return 100.0 * sum(1 for x in dist if x <= v) / len(dist) if dist else float("nan")


def windows(cond: dict, k: int) -> dict:
    ops = cond["resets"] + ([cond["cold_call"]] if cond.get("cold_call") is not None else [])
    first = min(ops)
    if cond["kind"] == "cold":
        b = cond["cold_call"] + k - 1
    else:
        b = cond["binds"][-1]
    sinkless = set()
    if cond["kind"] == "ot":
        sinkless = set(range(first, b))
    return {"pre": set(range(first - PRE, first)), "sinkless": sinkless, "post_bind_20": set(range(b, b + 20)), "last_10": set(range(cond["end"] - 9, cond["end"] + 1)),
            "events": ([("reset", c) for c in cond["resets"] if c not in cond["binds"]] + [("bind" if c not in cond["resets"] else "reset+bind", c) for c in cond["binds"]] +
                       ([("cold_emit", cond["cold_call"] + k - 1)] if cond.get("cold_call") is not None else [])), "b": b}


def stream_series(frames: dict, gray_fn, emb: dict, prompt: str | None) -> dict:
    """Per call: Lab mean, embeddings (mean of the frames), CLIP text cosine."""
    out = {"lab": {}, "emb": {n: {} for n in emb}, "clipt": {}}
    tvec = {n: (e.text(prompt) if (prompt and n == "clip") else None) for n, e in emb.items()}
    for c, fr in frames.items():
        out["lab"][c] = lab_mean(fr).tolist()
        for n, e in emb.items():
            z = e.image(fr)
            out["emb"][n][c] = z
            if tvec.get(n) is not None:
                out["clipt"][c] = float((z @ tvec[n]).mean())
    return out


def series_metrics(S: dict, calls: list[int], pre: set) -> dict:
    """Per call: V4 drift to the stream's own pre-move mean, V5a cosine to the pre-move mean feature and VBench-style."""
    pre_c = [c for c in calls if c in pre]
    lab_pre = np.mean([S["lab"][c] for c in pre_c], axis=0) if pre_c else None
    res = {"v4_pre": {}, "v5a": {n: {} for n in S["emb"]}, "v5a_vbench": {n: {} for n in S["emb"]}, "v5b": dict(S["clipt"])}
    for c in calls:
        if lab_pre is not None:
            res["v4_pre"][c] = de2000(S["lab"][c], lab_pre)
    for n, E in S["emb"].items():
        if not E:
            continue
        mu = np.mean(np.concatenate([E[c] for c in pre_c]), axis=0) if pre_c else None
        mu = mu / np.linalg.norm(mu) if mu is not None else None
        first = E[calls[0]][0]
        prev = None
        for c in calls:
            z = E[c]
            if mu is not None:
                res["v5a"][n][c] = float((z @ mu).mean())
            sims = []
            for f in z:
                if prev is not None:
                    sims.append((max(0.0, float(f @ first)) + max(0.0, float(f @ prev))) / 2)
                prev = f
            res["v5a_vbench"][n][c] = float(np.mean(sims)) if sims else None
    return res


def condition_metrics(cond: dict, k: int, O: dict, R: dict, I: dict, gray_fn, emb: dict, prompt: str, ref_trans: list[dict], ref_spikes: list[float],
                      ref_series: dict) -> dict:
    W = windows(cond, k)
    calls = sorted(O)
    go, gr, gi = ({c: gray_fn(O[c]) for c in calls}, {c: gray_fn(R[c]) for c in calls if c in R}, {c: gray_fn(I[c]) for c in calls})
    tr = transitions(go, gr, gi)
    per_call = {}
    for c in calls:
        ts = [t for t in tr if t["call"] == c and t["eO"] is not None and t["eR"] is not None]
        per_call[c] = {"eO": float(np.mean([t["eO"] for t in ts])) if ts else None, "eR": float(np.mean([t["eR"] for t in ts])) if ts else None,
                       "dO": float(np.mean([t["dO"] for t in tr if t["call"] == c])) if any(t["call"] == c for t in tr) else None,
                       "dR": float(np.mean([t["dR"] for t in tr if t["call"] == c and t["dR"] is not None])) if any(t["call"] == c and t["dR"] is not None for t in tr) else None}
    S = stream_series(O, gray_fn, emb, prompt)
    M = series_metrics(S, calls, W["pre"])
    for c in calls:
        if c in R:
            per_call[c]["v4_ref"] = de2000(S["lab"][c], ref_series["lab"][c])
        per_call[c]["v4_pre"] = M["v4_pre"].get(c)
        per_call[c]["v4_pre_ref"] = ref_series["metrics"]["v4_pre"].get(c)
        for n in emb:
            per_call[c][f"v5a_{n}"] = M["v5a"][n].get(c)
            per_call[c][f"v5a_{n}_ref"] = ref_series["metrics"]["v5a"][n].get(c)
            per_call[c][f"v5a_vbench_{n}"] = M["v5a_vbench"][n].get(c)
            per_call[c][f"v5a_vbench_{n}_ref"] = ref_series["metrics"]["v5a_vbench"][n].get(c)
        if "clip" in emb:
            per_call[c]["v5b"] = M["v5b"].get(c)
            per_call[c]["v5b_ref"] = ref_series["metrics"]["v5b"].get(c)
    win = {}
    for name in ("pre", "sinkless", "post_bind_20", "last_10"):
        cs = [c for c in calls if c in W[name]]
        if not cs:
            win[name] = None; continue
        eO = [per_call[c]["eO"] for c in cs if per_call[c]["eO"] is not None]; eR = [per_call[c]["eR"] for c in cs if per_call[c]["eR"] is not None]
        dO = [per_call[c]["dO"] for c in cs if per_call[c]["dO"] is not None]; dR = [per_call[c]["dR"] for c in cs if per_call[c]["dR"] is not None]
        lab_o = np.mean([S["lab"][c] for c in cs], axis=0); lab_r = np.mean([ref_series["lab"][c] for c in cs], axis=0)
        win[name] = {"calls": [cs[0], cs[-1]], "n": len(cs), "E_ratio": (np.mean(eO) / np.mean(eR)) if (eO and eR and np.mean(eR) > 0) else None,
                     "motion_ratio": (np.mean(dO) / np.mean(dR)) if (dO and dR and np.mean(dR) > 0) else None,
                     "v4_window_to_ref": de2000(lab_o, lab_r)}
    spikes = []
    for kind, c in W["events"]:
        so = spike_at(tr, c)
        rs = spike_at(ref_trans, c)
        spikes.append({"kind": kind, **so, "ref_spike_same_call": rs["spike"], "pct_rank_in_ref": percentile_rank(ref_spikes, so["spike"]) if so["spike"] is not None else None})
    return {"windows": win, "events": spikes, "per_call": {str(c): v for c, v in per_call.items()}, "b": W["b"], "sinkless_calls": sorted(W["sinkless"])}


# ----------------------------------------------------------------------------- unit driver
def gray_quarter(frames):
    import rd_metrics as rm

    return rm.small_gray(frames)


def input_provider(meta: dict, dry: bool, hw=None):
    """Input frames of output call c's chunk, exactly as RD (Runner.input_frames_for_output_call: bf16 input -> uint8)."""
    if dry:
        import vc_emulate as ve

        return lambda in_call: ve.dry_frames(in_call, 0, *hw)
    import torch

    from streamv2v.inference_common import load_mp4_as_tensor

    v = load_mp4_as_tensor(meta["video"], resize_hw=(480, 832)).to(torch.bfloat16)   # [C, T, H, W] normalized, as the runtime
    T = v.shape[1]
    first, chunk = 5, 4

    def get(in_call):
        lo = first + in_call * chunk
        idx = [(lo + j) % T for j in range(chunk)]
        x = v[:, idx].float().permute(1, 2, 3, 0)
        return np.clip((x * 0.5 + 0.5).numpy() * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return get


def playback_metrics(cond_sched: dict, O: dict, ref_cadence_s: float, ref=False) -> dict:
    """P1-P3 under the last-frame-hold playback model, at 16 fps and rate-matched; P3 = mean |difference| between the
    held frame and the next shown frame, divided by the stream's median consecutive-frame difference over the 8
    transitions before the stall (same normalization as V1)."""
    import vc_playback as vp

    calls = sorted(O)
    pb = vp.playback_ref(cond_sched, calls, cond_sched["first_op"]) if ref else vp.playback_for_condition(cond_sched, calls, ref_cadence_s)
    seq = [(c, j) for c in calls for j in range(len(O[c]))]
    diffs = {}
    for (c0, j0), (c1, j1) in zip(seq, seq[1:]):
        diffs[(c0, j0, c1, j1)] = float(np.abs(O[c1][j1].astype(np.float32) - O[c0][j0]).mean())
    keys = list(diffs)
    for mode in ("fps16", "rate_matched"):
        jumps = []
        for held, nxt in pb[mode]["resumes"]:
            k_ = next((i for i, kk in enumerate(keys) if kk[0] == held and kk[2] == nxt), None)
            if k_ is None or k_ < SPIKE_PREV:
                jumps.append(None); continue
            m = st.median(diffs[kk] for kk in keys[k_ - SPIKE_PREV:k_])
            jumps.append(diffs[keys[k_]] / m if m > 0 else None)
        pb[mode]["resume_jumps"] = jumps
        pb[mode].pop("resumes", None)
        pb[mode]["stalls"] = pb[mode]["stalls"][:50]
    return pb


def run_unit(unit: Path, only: list[str], emb_names: str, device: str) -> dict:
    sched_ref = json.loads((unit / "REF" / "summary.json").read_text())
    dry = bool(sched_ref.get("dry_run"))
    ref_dir = Path(sched_ref["frames"])
    R = vf.read_calls(ref_dir)
    hw = R[min(R)].shape[1:3]
    k = int(sched_ref.get("k", 2))
    getI = input_provider(sched_ref, dry, hw)
    emb = make_embedders(emb_names, device)
    prompt = None if dry else Path(sched_ref["prompt_file"]).read_text().strip().splitlines()[0]
    ref_calls = sorted(R)
    Rg = {c: gray_quarter(R[c]) for c in ref_calls}
    Ig = {c: gray_quarter(getI(c - (k - 1))) for c in ref_calls}
    ref_trans = transitions(Rg, Rg, Ig)
    ref_spikes = ref_spike_distribution(ref_trans)
    out = {"embedders": list(emb), "playback_model": "last-frame-hold playback model (vc_playback.py)", "ref_spike_P99": float(np.percentile(ref_spikes, 99)) if ref_spikes else None, "ref_spike_n": len(ref_spikes), "conditions": {}}
    conds = sorted(d.name for d in unit.iterdir() if (d / "calls.csv").exists() and (not only or d.name in only))
    sched = json.loads((ROOT / "results/evaluation/osdi/expVC/vc_schedules.json").read_text())["inputs"][unit.name.rsplit("_s", 1)[0]]
    sconds = {c["id"]: c for c in sched["conditions"]}
    ref_cad = sched["ref"]["timeline"]["cadence_s"]
    ref_raw = stream_series(R, gray_quarter, emb, prompt)   # REF embeddings once; its per-window references per pre-move span below
    ref_by_pre = {}
    for cid in conds:
        s = json.loads((unit / cid / "summary.json").read_text())
        cond = s["condition"]
        O = vf.read_calls(Path(s["frames"]))
        idx = {e["call"]: e for e in vf.load_index(Path(s["frames"]))["calls"]}
        I = {c: getI(idx[c]["out_input_call"]) for c in O}
        Rc = {c: R[c] for c in O if c in R and idx[c]["out_input_call"] == c - (k - 1)}   # paired on the input chunk
        W = windows(cond, k)
        key = min(W["pre"])
        if key not in ref_by_pre:
            ref_by_pre[key] = {"lab": ref_raw["lab"], "metrics": series_metrics(ref_raw, ref_calls, W["pre"])}
        ref_S = ref_by_pre[key]
        out["conditions"][cid] = condition_metrics(cond, k, O, Rc, I, gray_quarter, emb, prompt, ref_trans, ref_spikes, ref_S)
        out["conditions"][cid]["unpaired_calls"] = sorted(c for c in O if c not in Rc)
        out["conditions"][cid]["playback"] = playback_metrics(sconds[cid], O, ref_cad)
        if "REF" not in out:
            fo = min(min(c["resets"] + ([c["cold_call"]] if c.get("cold_call") is not None else [])) for c in sconds.values())
            out["REF_playback"] = playback_metrics({**sched["ref"], "first_op": fo}, R, ref_cad, ref=True)
            out["REF"] = True
        print(f"[VCm] {unit.name} {cid}: {len(O)} calls, windows {list(out['conditions'][cid]['windows'])}", flush=True)
    return out


# ----------------------------------------------------------------------------- self-test (VC-0)
def _load_clip(path: str) -> np.ndarray:
    import av

    from PIL import Image

    with av.open(path) as c:
        return np.stack([np.asarray(Image.fromarray(f.to_ndarray(format="rgb24")).resize((832, 480))) for f in c.decode(video=0)])


def selftest(clip: str, emb_names: str, device: str, clip2: str = str(ROOT / "examples/train.mp4")) -> dict:
    """Identity, an injected cut and an injected global color shift on a repository clip; the expected direction of
    every metric is checked (V1 large at the cut, V4 equal to the injected shift, V5a lower after the cut)."""
    fr = _load_clip(clip)
    calls = list(range(len(fr) // 4))
    R = {c: fr[4 * c:4 * c + 4] for c in calls}
    I = R
    emb = make_embedders(emb_names, device)
    res, bad = {}, []
    g = {c: gray_quarter(R[c]) for c in calls}
    t_id = transitions(g, g, g)
    s_id = spike_at(t_id, calls[len(calls) // 2])
    cut = len(calls) // 2
    other = _load_clip(clip2)   # a different repository clip spliced in at the cut
    other = np.concatenate([other] * (len(fr) // len(other) + 1))[:len(fr)]
    O = {c: (R[c] if c < cut else other[4 * c:4 * c + 4]) for c in calls}
    go = {c: gray_quarter(O[c]) for c in calls}
    s_cut = spike_at(transitions(go, g, g), cut)
    res["v1_identity"], res["v1_cut"] = s_id["spike"], s_cut["spike"]
    if not (s_cut["spike"] and s_id["spike"] and s_cut["spike"] > 3 * s_id["spike"]):
        bad.append(f"V1: cut spike {s_cut['spike']} not > 3 x identity {s_id['spike']}")
    shift = np.array([0, 0, 25], dtype=np.int16)
    Oc = {c: np.clip(R[c].astype(np.int16) + shift, 0, 255).astype(np.uint8) for c in calls}
    lab_r = np.mean([lab_mean(R[c]) for c in calls], 0); lab_o = np.mean([lab_mean(Oc[c]) for c in calls], 0)
    res["v4_identity"] = de2000(lab_r, lab_r); res["v4_shift"] = de2000(lab_o, lab_r)
    if not (res["v4_identity"] == 0.0 and res["v4_shift"] > 1.0):
        bad.append(f"V4: identity {res['v4_identity']}, blue shift {res['v4_shift']}")
    for n, e in emb.items():
        zr = {c: e.image(R[c]) for c in calls}; zo = {c: e.image(O[c]) for c in calls}
        mu = np.mean(np.concatenate([zr[c] for c in calls[:4]]), 0); mu /= np.linalg.norm(mu)
        before = float(np.mean([(zr[c] @ mu).mean() for c in calls[cut:]])); after = float(np.mean([(zo[c] @ mu).mean() for c in calls[cut:]]))
        res[f"v5a_{n}_identity"], res[f"v5a_{n}_cut"] = before, after
        if n != "clip" and not after < before:
            bad.append(f"V5a {n}: similarity after the cut {after:.3f} not below identity {before:.3f}")
        if n == "clip":
            t = e.text("a photo of a cat"); t2 = e.text("a photo of a spaceship")
            res["v5b_cat"], res["v5b_spaceship"] = float(np.mean([(zr[c] @ t).mean() for c in calls])), float(np.mean([(zr[c] @ t2).mean() for c in calls]))
            if not res["v5b_cat"] > res["v5b_spaceship"]:
                bad.append("V5b: the cat clip is not closer to 'a photo of a cat' than to 'a photo of a spaceship'")
    res["pass"] = not bad; res["failures"] = bad
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--unit", default=None)
    ap.add_argument("--only", default="")
    ap.add_argument("--embedders", default="dino,dinov2,clip")
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--clip", default=str(ROOT / "examples/original.mp4"))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.selftest:
        res = selftest(a.clip, a.embedders, a.device)
        res["provenance"] = provenance() if "pixel" not in a.embedders else {}
        p = Path(a.out or ROOT / "results/evaluation/osdi/expVC/vc0_metric_selftest.json")
        p.write_text(json.dumps(res, indent=1, default=float))
        print(json.dumps({k: v for k, v in res.items() if k != "provenance"}, indent=1, default=float))
        sys.exit(0 if res["pass"] else 1)
    unit = Path(a.unit)
    res = run_unit(unit, [x for x in a.only.split(",") if x], a.embedders, a.device)
    res["provenance"] = provenance() if "pixel" not in a.embedders else {}
    (unit / "metrics.json").write_text(json.dumps(res, default=float))
    print(f"[VCm] wrote {unit / 'metrics.json'}")


if __name__ == "__main__":
    main()
