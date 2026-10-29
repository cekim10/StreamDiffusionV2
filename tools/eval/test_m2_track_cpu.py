#!/usr/bin/env python3
"""CPU test of the GPU runtime's M2 tracker (mobility_node.GpuRuntime.sink_track_start / step / copy, sink_checksums)
on a tiny real CausalWanModel (tools/eval/test_m1_replay.py's harness): over a window with several t_refresh
realignments and adaptive refreshes, the retained Sink + the tracker's output (refreshed entries' current K / V, the
ordered shifts of the others, positions) reproduces the live Sink's digest; summing the shifts does not have to.

    python tools/eval/test_m2_track_cpu.py
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p_ in (ROOT, ROOT / "tools", ROOT / "tools" / "eval"):
    if str(p_) not in sys.path:
        sys.path.insert(0, str(p_))

import torch  # noqa: E402

import mobility_node as mn  # noqa: E402
import test_m1_replay as tr  # noqa: E402
from models.wan.causal_model import _shift_temporal_rope  # noqa: E402


def main():
    fails = []

    def check(name, ok, detail=""):
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} {detail}")
        if not ok:
            fails.append(name)
    gen = tr.build_model()
    pl, step = tr.fresh_stream(gen, 0.0)
    S, fsl = tr.SINK, tr.FSL
    rt = types.SimpleNamespace(torch=torch, pl=pl, sink=tr.SINK, fsl=tr.FSL, device="cpu", _sync=lambda: None)
    for name in ("sink_checksums", "_sink_pos_now", "sink_track_start", "sink_track_step", "sink_track_copy"):
        setattr(rt, name, types.MethodType(getattr(mn.GpuRuntime, name), rt))
    M1, M2 = 26, 82   # t_refresh rewinds at calls 30, 55, 80 in this harness
    for c in range(M1):
        step(c)
    ret = [(l_["k"][:, :S * fsl].clone(), l_["v"][:, :S * fsl].clone()) for l_ in pl.kv_cache1]
    rt.sink_track_start({"v": 1})
    cell = step.__closure__
    st = next(x.cell_contents for x in cell if isinstance(x.cell_contents, dict) and "starts" in x.cell_contents)
    for c in range(M1, M2):
        step(c)
        pl.kv_cache_starts = st["starts"]
        rt.sink_track_step(c)
    trk = rt.sink_track_copy()
    live = rt.sink_checksums(); live.pop("s")
    check("window has refreshes and multi-shifted entries", len(trk["refreshed"]) > 0 and len(trk["shifts"]) > 0,
          f"(refreshed {len(trk['refreshed'])}, shift events {len(trk['shifts'])})")
    cur = {(li, i, s_): (pl.kv_cache1[li]["k"][i, s_ * fsl:(s_ + 1) * fsl].clone(), pl.kv_cache1[li]["v"][i, s_ * fsl:(s_ + 1) * fsl].clone()) for li, i, s_ in trk["refreshed"]}
    pos_now = [l_["pos"][:, :S].clone() for l_ in pl.kv_cache1]
    freqs = gen.model.freqs

    def rebuild(summed: bool):
        for (k0, v0), l_ in zip(ret, pl.kv_cache1):
            l_["k"][:, :S * fsl] = k0; l_["v"][:, :S * fsl] = v0
        if summed:
            tot = {}
            for _, li, i, s_, d in trk["shifts"]:
                tot[(li, i, s_)] = tot.get((li, i, s_), 0) + d
            ev = [(li, i, s_, d) for (li, i, s_), d in tot.items()]
        else:
            ev = [(li, i, s_, d) for _, li, i, s_, d in trk["shifts"]]
        for li, i, s_, d in ev:
            k = pl.kv_cache1[li]["k"]
            k[i, s_ * fsl:(s_ + 1) * fsl] = _shift_temporal_rope(k[i, s_ * fsl:(s_ + 1) * fsl], freqs, d)
        for (li, i, s_), (k_, v_) in cur.items():
            pl.kv_cache1[li]["k"][i, s_ * fsl:(s_ + 1) * fsl] = k_; pl.kv_cache1[li]["v"][i, s_ * fsl:(s_ + 1) * fsl] = v_
        for l_, p_ in zip(pl.kv_cache1, pos_now):
            l_["pos"][:, :S] = p_
        ck = rt.sink_checksums(); ck.pop("s")
        return ck
    check("retained + tracker (current values, ordered shifts) == live Sink digest", rebuild(False) == live)
    multi = sum(1 for k_ in {(e[1], e[2], e[3]) for e in trk["shifts"]} if sum(1 for e in trk["shifts"] if (e[1], e[2], e[3]) == k_) > 1)
    print(f"    info: entries shifted more than once: {multi}; summed shifts {'equal' if rebuild(True) == live else 'differ from'} the live Sink")
    print("ALL PASS" if not fails else f"FAILED: {fails}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
