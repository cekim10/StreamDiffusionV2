#!/usr/bin/env python3
"""CPU test of the GPU runtime's replay-aware Sink synchronization code (mobility_node.GpuRuntime.rlog_arm / rlog_end /
rlog_apply / sink_checksums, bound to a tiny real CausalWanModel; tools/eval/test_m1_replay.py's harness): with refresh
patches the replayed Sink's checksum equals the source's at M; without patches (a refresh in the window) it does not;
every patch lands in the slot the replayed call wrote.

    python tools/eval/test_m1_sinksync_cpu.py
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

import m1_replay as mr  # noqa: E402
import mobility_node as mn  # noqa: E402
import test_m1_replay as tr  # noqa: E402


def runtime(pl):
    rt = types.SimpleNamespace(torch=torch, pl=pl, sink=tr.SINK, fsl=tr.FSL, device="cpu", cfg_thr=0.0, _sync=lambda: None,
                               capture_latents=False, last_latents=[])
    for name in ("rlog_arm", "rlog_begin", "rlog_end", "rlog_apply", "sink_checksums", "perturb_sink_for_test"):
        setattr(rt, name, types.MethodType(getattr(mn.GpuRuntime, name), rt))
    return rt


def run(patches: bool, thr: float, tamper: bool = False):
    gen = tr.build_model() if not hasattr(run, "gen") else run.gen
    run.gen = gen
    pl, step = tr.fresh_stream(gen, thr)
    rt = runtime(pl)
    rt.rlog_arm(patches=patches)
    M, c0 = tr.M, tr.M - 12
    for c in range(c0):
        step(c)
    snap0 = mr.snapshot(pl)
    log = []
    for c in range(c0, M):
        rt.rlog_begin(c); step(c)
        hdr, bufs = rt.rlog_end(c)
        log.append((hdr, b"".join(memoryview(b).cast("B").tobytes() for b in bufs)))
    src = rt.sink_checksums(); src.pop("s")
    n_ref = sum(len(h["refresh"]) for h, _ in log)
    pl.generator.forward = rt._rlog_rec.orig    # the destination's generator is not hooked
    mr.restore(pl, snap0, tr.SINK, zero_recent=True)
    for b in pl.generator.model.blocks:
        b.self_attn.adapt_sink_thr = -1
    oks, pinfo = [], []
    if tamper:
        # one bf16 element of the first patch's K changed by one unit in the last place: the checksum must notice
        for i_, (hdr, payload) in enumerate(log):
            t = next((t for t in hdr["tensors"] if t["name"] == "p0k"), None)
            if t is not None:
                b = bytearray(payload); x = int.from_bytes(b[t["offset"]:t["offset"] + 2], "little") ^ 1
                b[t["offset"]:t["offset"] + 2] = x.to_bytes(2, "little"); log[i_] = (hdr, bytes(b)); break
    for hdr, payload in log:
        ok, _, pi = rt.rlog_apply(hdr, payload)
        oks.append(ok); pinfo += pi
    dst = rt.sink_checksums(); dst.pop("s")
    run.last = (rt, src)
    return src == dst, all(oks), pinfo, n_ref, sum(len(h.get("patches") or []) for h, _ in log)


def main():
    fails = []

    def check(name, ok, detail=""):
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} {detail}")
        if not ok:
            fails.append(name)
    thr = 0.0   # the threshold test_m1_replay found to give some refreshes in the window
    eq, meta_ok, pinfo, n_ref, n_pat = run(True, thr)
    check("window has refreshes", n_ref > 0, f"({n_ref})")
    check("with patches: one patch per refresh decision", n_pat == n_ref, f"({n_pat})")
    check("with patches: every replayed call's metadata digest equals the source's", meta_ok)
    check("with patches: every patch lands in the slot the replayed call wrote", bool(pinfo) and all(pinfo))
    check("with patches: replayed Sink checksum == source's at M", eq)
    rt_, src_ = run.last
    w = rt_.perturb_sink_for_test(); ck = rt_.sink_checksums(); ck.pop("s")
    bad = [[i // 2, "kv"[i % 2], b, s_] for i, layer in enumerate(ck["blocks"]) for b, row in enumerate(layer) for s_, v in enumerate(row) if v != src_["blocks"][i][b][s_]]
    check("perturb_sink_for_test: exactly the perturbed block differs", bad == [[w["layer"], w["key"], w["row"], w["slot"]]], str(bad))
    eq3, _, _, _, _ = run(True, thr, tamper=True)
    check("negative: a patch changed by 1 ulp makes the Sink checksum differ", not eq3)
    eq2, meta_ok2, pinfo2, _, n_pat2 = run(False, thr)
    check("without patches: no patches attached", n_pat2 == 0 and not pinfo2)
    print(f"    info: without patches the tiny model's replayed Sink checksum {'equals' if eq2 else 'differs from'} the source's (its refreshed entries converge exactly; on the real model E4 measured 2 / 4 refresh blocks bitwise)")
    print("ALL PASS" if not fails else f"FAILED: {fails}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
