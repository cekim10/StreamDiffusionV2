#!/usr/bin/env python3
"""Fig. 8b native StreamDiffusionV2 (osdi/fig8/preregistration.md): upstream `streamv2v/inference.py --profile`,
unmodified, on the Fig. 7 model configuration and inputs. Per-chunk wall time from upstream's own profile log
("Processed N, time: t s, FPS: f"; frames per chunk / per-chunk wall time).

The inputs are short (dog 81 frames, butterfly 32), and upstream processes an input once. The harness repeats the decoded
video in memory (`proto_handoff.build_runtime`). Here the same repetition is done on the file: the H.264 packets are
copied N times without re-encoding (PyAV remux), and the decoded frames are checked equal to the original's repeated
frames before any run (`verify`).

    run     --label A --workload dog --rep 1 [--gpu 0]    one native run on this host -> osdi/fig8/native/{label}_{w}_rep{r}.json
    remote  start|status|fetch [--label B]                the native runs on another host through its experiment agent
            (start runs `run_fig8.sh native_local <label>` there; fetch copies its JSON and logs, never overwriting a
            differing file)
    parse   --log <file>                                  parser self-test on an upstream log
"""

from __future__ import annotations

import argparse
import json
import re
import statistics as st
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/eval"))
sys.path.insert(0, str(ROOT))
OUT_REL = "results/evaluation/osdi/fig8/native"
OUT = ROOT / OUT_REL
INP = ROOT / "results/evaluation/osdi/fig8/_inputs"     # looped inputs and upstream output videos (not committed)
WORKLOADS = {"dog": ("examples/original.mp4", "examples/prompt.txt"),
             "bfly": ("data/loveu_tgve_2023/butterfly-feeding-slow-motion.mp4", "data/loveu_tgve_2023/butterfly-feeding-slow-motion__background.txt")}
CONFIG = "configs/wan_causal_dmd_v2v.yaml"          # the harness default (mobility_node.py --config_path)
CKPT = "ckpts/wan_causal_dmd_v2v"
CHUNKS_NEEDED = 185                                  # > the steady window's last chunk (159) plus warm-up
WINDOW = (40, 159)                                   # steady-state window, upstream "Processed" index
LINE = re.compile(r"Processed (\d+), time: ([\d.]+) s, FPS: ([\d.]+)")
AVG = re.compile(r"Average FPS: ([\d.]+)")


def n_frames(path: Path) -> int:
    import av
    with av.open(str(path)) as c:
        return sum(1 for _ in c.decode(c.streams.video[0]))


def loop_input(src: Path, dst: Path, loops: int):
    """Copy the video packets `loops` times (no re-encode), shifting timestamps by one input length per copy."""
    import av
    with av.open(str(src)) as inp:
        s = inp.streams.video[0]
        pkts = [p for p in inp.demux(s) if p.size > 0]
        span = max(p.pts + (p.duration or 0) for p in pkts) - min(p.pts for p in pkts)
        dst.parent.mkdir(parents=True, exist_ok=True)
        with av.open(str(dst), "w") as out:
            o = out.add_stream_from_template(s) if hasattr(out, "add_stream_from_template") else out.add_stream(template=s)   # PyAV >= 14 / older
            for k in range(loops):
                for p in pkts:
                    q = av.Packet(bytes(p))
                    q.pts, q.dts, q.duration = p.pts + k * span, p.dts + k * span, p.duration
                    q.is_keyframe = p.is_keyframe
                    q.stream = o
                    out.mux(q)


def verify(src: Path, dst: Path, need: int) -> dict:
    """The looped file's first `need` decoded frames equal the original's frames repeated (exact uint8 RGB)."""
    import av
    import numpy as np

    def frames(p, n=None):
        out = []
        with av.open(str(p)) as c:
            for f in c.decode(c.streams.video[0]):
                out.append(f.to_rgb().to_ndarray())
                if n is not None and len(out) >= n:
                    break
        return np.stack(out)

    a = frames(src)
    b = frames(dst, need)
    ref = np.concatenate([a] * (need // len(a) + 1))[:need]
    ok = b.shape == ref.shape and bool((b == ref).all())
    return {"frames_checked": int(len(b)), "equal": ok, "src_frames": int(len(a))}


def prepare(w: str) -> tuple[Path, dict]:
    src = ROOT / WORKLOADS[w][0]
    need = 1 + 4 * CHUNKS_NEEDED
    n = n_frames(src)
    loops = -(-need // n)
    dst = INP / f"{w}_x{loops}.mp4"
    if not dst.exists():
        loop_input(src, dst, loops)
    chk = verify(src, dst, need)
    try:   # also through the loader upstream uses (torchvision read_video when present, else PyAV)
        import torch
        from streamv2v.inference_common import load_mp4_as_tensor
        a_ = load_mp4_as_tensor(str(src), normalize=False)
        b_ = load_mp4_as_tensor(str(dst), normalize=False)[:, :need]
        rep = torch.cat([a_] * (need // a_.shape[1] + 1), dim=1)[:, :need]
        chk["loader_equal"] = b_.shape == rep.shape and bool(torch.equal(b_, rep))
        chk["equal"] = chk["equal"] and chk["loader_equal"]
    except ImportError:
        chk["loader_equal"] = None   # no torch here (local test); the run host always checks
    if not chk["equal"]:
        raise SystemExit(f"[F8] looped input {dst} does not decode to the repeated original frames: {chk}")
    return dst, {**chk, "loops": loops, "path": str(dst.relative_to(ROOT) if dst.is_relative_to(ROOT) else dst)}


def parse(text: str) -> dict:
    rows = [(int(m.group(1)), float(m.group(2)), float(m.group(3))) for m in LINE.finditer(text)]
    win = [t for n, t, _ in rows if WINDOW[0] <= n <= WINDOW[1]]
    avg = AVG.findall(text)
    return {"chunks": [{"processed": n, "time_s": t, "fps": f} for n, t, f in rows], "n_window": len(win),
            "median_chunk_s": st.median(win) if win else None, "fps_window": 4 / st.median(win) if win else None,
            "upstream_average_fps": float(avg[-1]) if avg else None}


def gpu_name(gpu: int) -> str:
    try:
        return subprocess.run(["nvidia-smi", "-i", str(gpu), "--query-gpu=name,driver_version", "--format=csv,noheader"],
                              capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception as exc:  # noqa: BLE001
        return f"unknown ({exc})"


def run(a):
    video, info = prepare(a.workload)
    OUT.mkdir(parents=True, exist_ok=True)
    tag = f"{a.label}_{a.workload}_rep{a.rep}"
    log = OUT / f"{tag}.log"
    cmd = [sys.executable, "streamv2v/inference.py", "--config_path", CONFIG, "--checkpoint_folder", CKPT,
           "--output_folder", str(INP / f"out_{tag}"), "--prompt_file_path", WORKLOADS[a.workload][1], "--video_path", str(video),
           "--noise_scale", "0.8", "--height", "480", "--width", "832", "--fps", "16", "--step", "2", "--seed", "0",
           "--model_type", "T2V-1.3B", "--gpu_id", str(a.gpu), "--profile"]
    print(f"[F8] native {tag}: {' '.join(cmd)}", flush=True)
    with open(log, "w") as fh:
        rc = subprocess.run(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT).returncode
    res = parse(log.read_text())
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    rec = {"label": a.label, "workload": a.workload, "rep": a.rep, "rc": rc, "gpu": gpu_name(a.gpu), "commit": commit, "input": info,
           "cmd": cmd, "window": WINDOW, **res}
    (OUT / f"{tag}.json").write_text(json.dumps(rec, indent=1))
    print(f"[F8] native {tag}: rc {rc}, {res['n_window']} chunks in the window, median {res['median_chunk_s']} s, "
          f"{res['fps_window'] and round(res['fps_window'], 3)} fps (upstream average {res['upstream_average_fps']})", flush=True)
    if rc != 0 or res["n_window"] < WINDOW[1] - WINDOW[0] + 1:
        sys.exit(1)


def remote(a):
    from d0_remote import agents
    pids_f = OUT / "_remote_pids.json"
    pids = json.loads(pids_f.read_text()) if pids_f.exists() else {}
    for lb, ag in agents((a.label,), a.agent_hosts).items():
        logf = f"{OUT_REL}/_remote_{lb}.log"
        if a.cmd == "start":
            pid = ag.run(["bash", "tools/eval/run_fig8.sh", "native_local", lb], log=logf, env={"PY": ag.ping()["python"]})
            pids[lb] = pid; OUT.mkdir(parents=True, exist_ok=True); pids_f.write_text(json.dumps(pids))
            print(f"{lb}: native runs started, pid {pid}, log {logf}")
        elif a.cmd == "status":
            stt = ag.poll(pids[lb]) if lb in pids else {"running": None, "rc": None}
            try:
                tail = [ln for ln in ag.read(logf).splitlines() if ln.startswith("[F8]")]
            except Exception as exc:  # noqa: BLE001
                tail = [f"(no log: {exc})"]
            n = len(ag.glob(f"{OUT_REL}/{lb}_*.json"))
            print(f"{lb}: {'running' if stt['running'] else 'finished rc=' + str(stt['rc'])} | {n} / 10 result files | " + " / ".join(tail[-2:]))
        else:
            new = same = diff = 0
            for rel in ag.glob(f"{OUT_REL}/{lb}_*.json") + ag.glob(f"{OUT_REL}/{lb}_*.log"):
                txt, dst = ag.read(rel), ROOT / rel
                if dst.exists():
                    if dst.read_text() == txt:
                        same += 1
                    else:
                        diff += 1; print(f"  {lb}: {rel} differs from the local copy; left untouched")
                    continue
                dst.write_text(txt); new += 1
            print(f"{lb}: copied {new}, identical {same}, differing {diff}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    r = sub.add_parser("run"); r.add_argument("--label", required=True); r.add_argument("--workload", choices=list(WORKLOADS), required=True)
    r.add_argument("--rep", type=int, required=True); r.add_argument("--gpu", type=int, default=0)
    m = sub.add_parser("remote"); m.add_argument("cmd", choices=["start", "status", "fetch"]); m.add_argument("--label", default="B")
    m.add_argument("--agent_hosts", default=None)
    p = sub.add_parser("parse"); p.add_argument("--log", required=True)
    a = ap.parse_args()
    if a.mode == "run":
        run(a)
    elif a.mode == "remote":
        remote(a)
    else:
        print(json.dumps({k: v for k, v in parse(Path(a.log).read_text()).items() if k != "chunks"}, indent=1))


if __name__ == "__main__":
    main()
