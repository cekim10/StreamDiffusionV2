"""Experiment RD outcome functions (results/evaluation/osdi/expRD/preregistration.md, frozen f850072, section 5).

Reference-trajectory outcomes (PSNR against the uninterrupted run) and the no-reference temporal-consistency metrics
(input-motion-conditioned warp error, motion magnitude ratio, event spikes). The two families are computed and reported
separately; no hypothesis is decided by the no-reference metrics.
"""

from __future__ import annotations

import statistics as st

import numpy as np

REJOIN_DB = 35.0
SUSTAIN = 10
FARNEBACK = dict(pyr_scale=0.5, levels=3, winsize=15, iterations=3, poly_n=5, poly_sigma=1.2, flags=0)   # frozen (section 5.2)


# ----------------------------------------------------------------------------- reference trajectory (section 5.1)
def trajectory(psnr: dict, b: int, calls=None, horizon: int = 100) -> dict:
    """psnr: {call: dB or None}. Window = calls b .. b + horizon - 1 (restricted to `calls` when given, e.g. the calls an
    emulated and a real run have in common). T = median over the last 10 calls of the window (b + 90 .. b + 99 for a full
    horizon); crossing = first call >= 35 dB; sustained = first call starting 10 consecutive calls >= 35 dB."""
    win = [c for c in range(b, b + horizon) if (calls is None or c in calls) and psnr.get(c) is not None]
    if not win:
        return {"n": 0, "T": None, "crossed": False, "cross_call": None, "sustained": False, "sustain_call": None}
    v = [psnr[c] for c in win]
    cross = next((c for c in win if psnr[c] >= REJOIN_DB), None)
    sus = None
    for i in range(len(win) - SUSTAIN + 1):
        seg = win[i:i + SUSTAIN]
        if seg[-1] - seg[0] == SUSTAIN - 1 and all(psnr[c] >= REJOIN_DB for c in seg):
            sus = seg[0]; break
    return {"n": len(win), "T": float(st.median(v[-10:])), "crossed": cross is not None, "cross_call": cross, "cross_after_bind": None if cross is None else cross - b,
            "sustained": sus is not None, "sustain_call": sus, "first_call": win[0], "last_call": win[-1]}


def gap_psnr(psnr: dict, sinkless_calls) -> float | None:
    v = [psnr[c] for c in sinkless_calls if psnr.get(c) is not None]
    return float(st.median(v)) if v else None


# ----------------------------------------------------------------------------- no-reference metrics (section 5.2)
def small_gray(frames):
    """[F, H, W, 3] uint8 -> list of 1/4-resolution grayscale uint8 frames."""
    import cv2

    out = []
    for f in frames:
        g = cv2.cvtColor(np.ascontiguousarray(f), cv2.COLOR_RGB2GRAY)
        out.append(cv2.resize(g, (g.shape[1] // 4, g.shape[0] // 4), interpolation=cv2.INTER_AREA))
    return out


def _flow(a, b):
    import cv2

    return cv2.calcOpticalFlowFarneback(a, b, None, FARNEBACK["pyr_scale"], FARNEBACK["levels"], FARNEBACK["winsize"], FARNEBACK["iterations"],
                                        FARNEBACK["poly_n"], FARNEBACK["poly_sigma"], FARNEBACK["flags"])


def warp_error(xt, xt1, flow) -> float:
    """mean |X_t - X_{t+1} warped back to t along `flow`| over pixels whose warped position is inside the frame."""
    import cv2

    h, w = xt.shape
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    mx, my = gx + flow[..., 0], gy + flow[..., 1]
    valid = (mx >= 0) & (mx <= w - 1) & (my >= 0) & (my <= h - 1)
    back = cv2.remap(xt1.astype(np.float32), mx, my, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    if not valid.any():
        return float("nan")
    return float(np.abs(xt.astype(np.float32) - back)[valid].mean())


def no_reference(seq: list[dict], windows: dict, events: list[tuple[str, int]]) -> dict:
    """seq: per produced call in order, {"call", "O": [gray], "R": [gray], "I": [gray]} (same frame count per call).
    windows: {name: set of calls}; a transition belongs to a window when its second frame's call is in it.
    events: [(kind, call)] reset / bind calls; spike = |frame diff| across the event transition / median of the 8
    preceding transitions (O and R separately)."""
    frames = []   # (call, O, R, I)
    for s in seq:
        for o, r, i in zip(s["O"], s["R"], s["I"]):
            frames.append((s["call"], o, r, i))
    trans = []    # (call of 2nd frame, eO, eR, mO, mR, dO, dR, is_first_of_call)
    for k in range(1, len(frames)):
        c0, o0, r0, i0 = frames[k - 1]; c1, o1, r1, i1 = frames[k]
        if c1 - c0 > 1:
            continue   # a missing call breaks the sequence
        fl = _flow(i0, i1)
        dO = float(np.abs(o1.astype(np.float32) - o0).mean()); dR = float(np.abs(r1.astype(np.float32) - r0).mean())
        trans.append({"call": c1, "eO": warp_error(o0, o1, fl), "eR": warp_error(r0, r1, fl), "dO": dO, "dR": dR, "first": c1 != c0})
    out = {}
    for name, calls in windows.items():
        tw = [t for t in trans if t["call"] in calls]
        if not tw:
            out[name] = None; continue
        eO, eR = float(np.nanmean([t["eO"] for t in tw])), float(np.nanmean([t["eR"] for t in tw]))
        mO, mR = float(np.mean([t["dO"] for t in tw])), float(np.mean([t["dR"] for t in tw]))
        ratio = eO / eR if eR > 0 else None
        mot = mO / mR if mR > 0 else None
        band = None if ratio is None else ("comparable" if 0.8 <= ratio <= 1.25 else ("less consistent with input motion" if ratio > 1.25 else "smoother than reference: inspect visually"))
        out[name] = {"n_transitions": len(tw), "E_O": eO, "E_R": eR, "E_ratio": ratio, "band": band, "motion_ratio": mot, "possibly_static": None if mot is None else mot < 0.5}
    spikes = []
    for kind, c in events:
        idx = next((j for j, t in enumerate(trans) if t["call"] == c and t["first"]), None)
        if idx is None or idx < 8:
            spikes.append({"kind": kind, "call": c, "spike_O": None, "spike_R": None}); continue
        prev = trans[idx - 8:idx]
        mo, mr = st.median([t["dO"] for t in prev]), st.median([t["dR"] for t in prev])
        spikes.append({"kind": kind, "call": c, "spike_O": trans[idx]["dO"] / mo if mo > 0 else None, "spike_R": trans[idx]["dR"] / mr if mr > 0 else None})
    out["event_spikes"] = spikes
    out["flow"] = {"method": "OpenCV Farneback", **FARNEBACK, "resolution": "1/4, grayscale"}
    return out
