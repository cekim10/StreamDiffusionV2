"""Experiment VC: the last-frame-hold playback model (preregistration draft 3 section 4.2).

A simple player, not a real client: frames are shown in order and never skipped, one every 1 / fps seconds, after a
playout buffer of `buffer_frames`; if a frame has not been delivered by its display time, the previous frame stays on
screen (a stall) until it arrives, and the schedule continues from there.

Delivery: every frame of call c becomes available at the chunk's delivery time t_by_call[c] (seconds, relative to the
first move). Calls with no output (a cold restart's skipped call) deliver nothing.

Two display rates are computed (implementation deviation D-VC-1, reported for decision): the preregistered 16 fps,
and a rate matched to the run's steady-state delivery (4 frames per measured post-bind cadence). The measured
generation rate (one 4-frame chunk per ~0.60 s, about 6.7 fps) is below 16 fps, so at 16 fps every stream, REF
included, stalls continuously.

P1 stall count and total stall time from the first move to the end of the span (a stall counts when the picture freezes
for at least one display-frame interval; shorter lateness from cadence jitter is reported as total_lateness_s); P2
longest single freeze; P3 the (call before, call after) pairs at every counted resume, for the jump measured by vc_metrics.
"""

from __future__ import annotations


def play(t_by_call: dict, calls_with_output: list[int], fps: float, buffer_frames: int = 4, frames_per_call: int = 4,
         t_from: float = 0.0, min_stall_s: float = 1e-6) -> dict:
    frames = []   # (call, availability time)
    for c in sorted(calls_with_output):
        if c in t_by_call:
            frames += [(c, float(t_by_call[c]))] * frames_per_call
    if not frames:
        return {"fps": fps, "stalls": [], "n_stalls": 0, "total_stall_s": 0.0, "longest_stall_s": 0.0, "resumes": []}
    dt = 1.0 / fps
    # playback starts once the first `buffer_frames` are available
    t = frames[min(buffer_frames, len(frames)) - 1][1]
    stalls, resumes = [], []
    shown_prev = None
    for i, (c, avail) in enumerate(frames):
        if i > 0:
            t += dt
        if avail > t + min_stall_s:
            if t >= t_from and shown_prev is not None:
                stalls.append({"start_s": t, "end_s": avail, "dur_s": avail - t, "held_call": shown_prev, "next_call": c})
                resumes.append((shown_prev, c))
            t = avail
        shown_prev = c
    # a stall is counted when the picture freezes for at least one display-frame interval; shorter lateness (cadence
    # jitter) is kept in total_lateness_s only
    counted = [s_ for s_ in stalls if s_["dur_s"] >= dt]
    return {"fps": fps, "buffer_frames": buffer_frames, "stalls": counted, "n_stalls": len(counted), "total_stall_s": sum(s_["dur_s"] for s_ in counted),
            "total_lateness_s": sum(s_["dur_s"] for s_ in stalls), "longest_stall_s": max((s_["dur_s"] for s_ in stalls), default=0.0),
            "resumes": [(s_["held_call"], s_["next_call"]) for s_ in counted], "t_end_s": t}


def playback_for_condition(cond: dict, calls_with_output: list[int], ref_cadence_s: float) -> dict:
    """Both display rates for one condition; the pre-move calls are placed at the run's cadence ending at t = 0."""
    tl = {int(k): v for k, v in cond["timeline"]["t_by_call"].items()}
    first_op = min(cond["resets"] + ([cond["cold_call"]] if cond.get("cold_call") is not None else []))
    cad = cond["timeline"]["cadence_s"]
    for c in range(cond["frames_from"], first_op):
        tl.setdefault(c, -(first_op - 1 - c) * cad)
    out = {"timeline_kind": cond["timeline"]["kind"], "model": "last-frame-hold playback model"}
    out["fps16"] = play(tl, calls_with_output, 16.0)
    out["rate_matched"] = play(tl, calls_with_output, 4.0 / ref_cadence_s)
    return out


def playback_ref(ref: dict, calls_with_output: list[int], first_op: int) -> dict:
    cad = ref["timeline"]["cadence_s"]
    tl = {c: (c - (first_op - 1)) * cad for c in calls_with_output}
    return {"timeline_kind": "derived", "model": "last-frame-hold playback model", "fps16": play(tl, calls_with_output, 16.0),
            "rate_matched": play(tl, calls_with_output, 4.0 / cad)}
