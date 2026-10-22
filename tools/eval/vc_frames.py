"""Experiment VC frame storage (implementation_plan.md section 2) and the G3 serialization check.

A stream (one condition of one input, or REF) is stored losslessly as FFV1 segments of up to SEG_CALLS calls on the
executing host's local disk, with an index (`index.json`) holding one entry per call of the saved span:

    {"call", "file", "offset" (first frame in the file), "n" (frames, 0 = no output), "digest" (mobility_node.frame_digest
     of the uint8 frames as generated), "events" (["reset", "bind", "cold_restart", "skip", "emit"]), "phase",
     "out_input_call" (the input chunk these frames belong to; None when there is no output)}

G3 (`check_stream`): every file decodes; frame counts and offsets match the index; every call's decoded frames have the
recorded digest; the calls are contiguous over the span; event markers equal the schedule; no-output calls are exactly
the expected ones; the input-to-output alignment rule holds.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

SEG_CALLS = 25


def frame_digest(fr) -> str | None:
    """Same definition as mobility_node.frame_digest (blake2b-128 of the contiguous uint8 array)."""
    return None if fr is None else hashlib.blake2b(np.ascontiguousarray(fr).tobytes(), digest_size=16).hexdigest()


class FrameStore:
    def __init__(self, root: Path, name: str):
        self.dir = Path(root) / name
        self.dir.mkdir(parents=True, exist_ok=True)
        self.index, self.buf, self.buf_calls = [], [], []

    def add(self, call: int, frames, events=(), phase="", out_input_call=None, digest=None):
        if frames is None:
            self.index.append({"call": call, "file": None, "offset": None, "n": 0, "digest": None, "events": list(events), "phase": phase, "out_input_call": None})
            return
        frames = np.ascontiguousarray(frames, dtype=np.uint8)
        d = frame_digest(frames)
        if digest is not None and digest != d:
            raise AssertionError(f"call {call}: frames differ from their recorded digest before storage")
        self.buf.append(frames); self.buf_calls.append(len(self.index))
        self.index.append({"call": call, "file": None, "offset": None, "n": int(len(frames)), "digest": d, "events": list(events), "phase": phase, "out_input_call": out_input_call})
        if len(self.buf) >= SEG_CALLS:
            self.flush()

    def flush(self):
        if not self.buf:
            return
        import xb_codec as xc

        first = self.index[self.buf_calls[0]]["call"]
        name = f"seg_{first:05d}.mkv"
        arr = np.concatenate(self.buf)
        data = xc.encode(arr, "ffv1")
        (self.dir / name).write_bytes(data)
        off = 0
        for i, f in zip(self.buf_calls, self.buf):
            self.index[i]["file"] = name; self.index[i]["offset"] = off; off += len(f)
        self.buf, self.buf_calls = [], []

    def close(self, meta: dict):
        self.flush()
        (self.dir / "index.json").write_text(json.dumps({"meta": meta, "calls": self.index}, indent=0))
        return self.dir


def load_index(d: Path) -> dict:
    return json.loads((Path(d) / "index.json").read_text())


def read_calls(d: Path, calls=None) -> dict:
    """{call: uint8 frames [n, H, W, 3]} for the requested calls (all with output if None)."""
    import xb_codec as xc

    idx = load_index(d)["calls"]
    want = [e for e in idx if e["n"] and (calls is None or e["call"] in calls)]
    out, cache = {}, {}
    for e in want:
        if e["file"] not in cache:
            cache = {e["file"]: xc.decode((Path(d) / e["file"]).read_bytes(), "ffv1")}   # one segment in memory at a time
        out[e["call"]] = cache[e["file"]][e["offset"]:e["offset"] + e["n"]]
    return out


def check_stream(d: Path, expect: dict) -> tuple[bool, list[str], dict]:
    """G3. expect: {"frames_from", "frames_to", "resets", "binds", "cold_call", "k", "kind"} of the condition (REF: kind "ref")."""
    import xb_codec as xc

    d = Path(d)
    bad = []
    doc = load_index(d)
    idx = doc["calls"]
    calls = [e["call"] for e in idx]
    lo, hi = expect["frames_from"], expect["frames_to"]
    if calls != list(range(lo, hi + 1)):
        bad.append(f"calls not contiguous {lo}..{hi}: got {calls[:3]}..{calls[-3:]} ({len(calls)})")
    files = sorted({e["file"] for e in idx if e["file"]})
    n_dec, n_ok = 0, 0
    for f in files:
        try:
            arr = xc.decode((d / f).read_bytes(), "ffv1")
        except Exception as exc:  # noqa: BLE001
            bad.append(f"{f}: decode failed {exc!r}"); continue
        ents = [e for e in idx if e["file"] == f]
        if sum(e["n"] for e in ents) != len(arr):
            bad.append(f"{f}: {len(arr)} frames decoded, index says {sum(e['n'] for e in ents)}")
        for e in ents:
            n_dec += 1
            if frame_digest(arr[e["offset"]:e["offset"] + e["n"]]) == e["digest"]:
                n_ok += 1
            else:
                bad.append(f"call {e['call']}: decoded frames differ from the recorded digest")
    k = expect.get("k", 2)
    kind = expect["kind"]
    resets, binds, cc = set(expect.get("resets", [])), set(expect.get("binds", [])), expect.get("cold_call")
    for e in idx:
        c, ev = e["call"], set(e["events"])
        want = set()
        if c in resets:
            want.add("reset")
        if c in binds:
            want.add("bind")
        if cc is not None and c == cc:
            want |= {"cold_restart", "skip"}
        if cc is not None and c == cc + k - 1:
            want.add("emit")
        if ev != want:
            bad.append(f"call {c}: markers {sorted(ev)} != schedule {sorted(want)}")
        no_out = cc is not None and c == cc and k > 1
        if no_out != (e["n"] == 0):
            bad.append(f"call {c}: output present {e['n'] > 0}, expected {'none' if no_out else 'output'}")
        if e["n"]:
            exp_in = cc if (cc is not None and c == cc + k - 1) else c - (k - 1)
            if e["out_input_call"] != exp_in:
                bad.append(f"call {c}: output belongs to input chunk {e['out_input_call']}, expected {exp_in}")
    info = {"calls": len(idx), "files": len(files), "decoded_calls": n_dec, "digest_ok_calls": n_ok, "no_output_calls": [e["call"] for e in idx if not e["n"]]}
    return not bad, bad, info
