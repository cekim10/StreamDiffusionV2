#!/usr/bin/env python3
"""M3 (osdi/m3s2/preregistration.md): lineage-aware forwarding of partially restored Sink state and mixed-version Sink
reconstruction. An M3-only path beside the frozen M1 / M2 (47acbe44): nothing here changes the M1 / M2 transfer,
verification or cutover, and a node enters this code only when the orchestrator runs with --m3.

Unit = entry: the K and V blocks of one (layer, row, Sink slot); eid = (layer * rows + row) * S + slot (180 entries).
Every entry travels with the snapshot call it was serialized at (its version) and the SHA-256 of its bytes, issued by
the source that serialized it; holders forward entries unchanged and every receiver verifies the hash on arrival.

Per (node, entry) the path distinguishes:
    verified and held   in the node's EntryStore (hash checked on arrival); the only state that is ever advertised
    in flight           fully written to a socket by a holder, not yet processed by the receiver: M3_HELD waits for it
                        (bounded) before advertising, and never advertises it unverified
    lost                its connection failed during the payload (holder failure): never held, never waited for
    not held            everything else

Source: a per-entry lineage history kept beside the frozen M2 tracker (refresh and shift events per call with the M2
tracker's detection rule, from the first M3 migration on), and the table of (entry, version) -> hash it issued. At a
base boundary c0 an advertised entry (e, v, h) is reused iff the source issued exactly (e, v, h) and e was not refreshed
in calls [v, c0); its K block then gets e's ordered RoPE shifts of calls [v, c0). Every other entry is sent at c0. The
destination assembles the Sink and accepts it only if all 360 block checksums and the Sink positions equal the
source's at c0 and the conditioning digest matches; otherwise it answers DELTANO and the source sends the full base
(the frozen M2 fallback path).
"""

from __future__ import annotations

import hashlib
import json
import struct
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from common import Throttle, tcp_connect
from proto_handoff import bytes_to_tensor, recv_exact, send_msg, tensor_to_bytes

N_ENTRIES_DEFAULT = 180


def eid_of(li: int, i: int, s: int, rows: int, S: int) -> int:
    return (li * rows + i) * S + s


def coords_of(e: int, rows: int, S: int) -> tuple[int, int, int]:
    return e // (S * rows), (e // S) % rows, e % S


def sha_parts(parts) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(memoryview(p).cast("B"))
    return h.hexdigest()


# ---------------------------------------------------------------------------------------------------------- lineage
class LineageHistory:
    """Source-side per-entry lineage (M3 only). Calls are generator calls; version v of an entry = the state at the
    boundary before call v (after call v - 1). Events of call c are recorded after the step of call c."""

    def __init__(self, start: int):
        self.start = int(start)
        self.last = self.start - 1
        self.refresh: dict[int, set] = {}
        self.shifts: dict[int, list] = {}
        self.issued: dict[tuple, str] = {}
        self.lock = threading.Lock()
        self.calls = 0
        self.track_s = 0.0
        self.n_refresh = 0
        self.n_shift = 0

    def record(self, c: int, refreshed, shifts, dt: float = 0.0):
        with self.lock:
            self.refresh[c] = set(int(e) for e in refreshed)
            self.shifts[c] = [(int(e), int(d)) for e, d in shifts]
            self.last = max(self.last, c)
            self.calls += 1; self.track_s += dt; self.n_refresh += len(self.refresh[c]); self.n_shift += len(self.shifts[c])

    def valid(self, e: int, v: int, c0: int) -> bool:
        with self.lock:
            if v < self.start or v > c0 or self.last < c0 - 1:
                return False
            return all(e not in self.refresh.get(c, ()) for c in range(v, c0))

    def shifts_since(self, e: int, v: int, c0: int) -> list:
        with self.lock:
            return [d for c in range(v, c0) for e2, d in self.shifts.get(c, ()) if e2 == e]

    def issue(self, e: int, v: int, h: str):
        with self.lock:
            self.issued[(int(e), int(v))] = h

    def issued_hash(self, e: int, v: int):
        with self.lock:
            return self.issued.get((int(e), int(v)))

    def summary(self) -> dict:
        with self.lock:
            return {"start": self.start, "last": self.last, "calls": self.calls, "track_s": self.track_s, "refresh_events": self.n_refresh,
                    "shift_events": self.n_shift, "issued": len(self.issued)}

    # ---- M3-S3 (osdi/m3s3/preregistration.md): lineage across an ownership change
    def export(self) -> dict:
        """The whole history and issued table (JSON-safe), for the next owner."""
        with self.lock:
            return {"start": self.start, "last": self.last, "refresh": {str(c): sorted(v) for c, v in self.refresh.items()},
                    "shifts": {str(c): [list(x) for x in v] for c, v in self.shifts.items()}, "issued": [[e, v, h] for (e, v), h in sorted(self.issued.items())]}

    def merge_prefix(self, exp: dict) -> dict:
        """New owner: prepend the previous owner's history. Accepted only if it ends exactly at the call before this
        history's first call (contiguous: no call of the lineage is missing); otherwise nothing is merged and versions
        older than this owner's first call stay invalid."""
        with self.lock:
            contiguous = exp is not None and int(exp["last"]) == self.start - 1 and int(exp["start"]) <= self.start
            if not contiguous:
                return {"contiguous": False, "merged_calls": 0, "merged_issued": 0}
            n = 0
            for c, v in exp["refresh"].items():
                if int(c) < self.start:
                    self.refresh[int(c)] = set(int(e) for e in v); n += 1
            for c, v in exp["shifts"].items():
                if int(c) < self.start:
                    self.shifts[int(c)] = [(int(e), int(d)) for e, d in v]
            missing = [c for c in range(int(exp["start"]), self.start) if c not in self.refresh]
            if missing:   # an exported call without a record: refuse (a gap would read as 'no refresh')
                for c in range(int(exp["start"]), self.start):
                    self.refresh.pop(c, None); self.shifts.pop(c, None)
                return {"contiguous": False, "merged_calls": 0, "merged_issued": 0, "missing_calls": missing[:10]}
            first = self.start
            self.start = int(exp["start"])
            k = 0
            for e, v, h in exp["issued"]:
                # only versions older than this owner's first call: those the merged history covers. The switch version
                # itself is issued separately, and only after the version check (cmd_m3_lineage_import).
                if int(v) < first and (int(e), int(v)) not in self.issued:
                    self.issued[(int(e), int(v))] = h; k += 1
            return {"contiguous": True, "merged_calls": n, "merged_issued": k}


# ------------------------------------------------------------------------------------------------------ entry store
class EntryStore:
    """Verified entries held by a node (host memory). Version-aware: a newer version replaces an older one; the same
    version again is a duplicate; an older version than the one held is ignored."""

    def __init__(self):
        self.lock = threading.Lock()
        self.held: dict[int, dict] = {}
        self.lost: set = set()
        self.counts = defaultdict(int)

    def put(self, e: int, rec: dict) -> str:
        with self.lock:
            cur = self.held.get(e)
            if cur is not None and cur["v"] == rec["v"]:
                self.counts["dup"] += 1; return "dup"
            if cur is not None and cur["v"] > rec["v"]:
                self.counts["older_ignored"] += 1; return "older"
            self.held[e] = rec
            self.counts["replace" if cur is not None else "new"] += 1
            return "replace" if cur is not None else "new"

    def get(self, e: int):
        with self.lock:
            return self.held.get(e)

    def has(self, e: int, v: int) -> bool:
        with self.lock:
            d = self.held.get(e)
            return d is not None and d["v"] >= v

    def mark_lost(self, e: int, v: int):
        with self.lock:
            self.lost.add((int(e), int(v))); self.counts["lost"] += 1

    def advert(self) -> list:
        with self.lock:
            return sorted([e, d["v"], d["h"]] for e, d in self.held.items())

    def snapshot(self) -> dict:
        with self.lock:
            return {e: dict(d) for e, d in self.held.items()}


# --------------------------------------------------------------------------- dry-run Sink (protocol tests only)
class FakeSinkModel:
    """Dry runs only (no torch): a deterministic 180-entry Sink whose content at boundary b is a function of b, with
    refreshes and additive 'shifts' (protocol test of versions, validity and ordered shifts; never used for results)."""

    N = N_ENTRIES_DEFAULT
    EB = 4096

    @staticmethod
    def refresh(c: int) -> set:
        return {(c * 37) % 180, (c * 53 + 7) % 180} if c % 2 == 0 else set()

    @classmethod
    def shifts(cls, c: int) -> list:
        R = cls.refresh(c)
        out = []
        for j in range(4):
            e = (c * 11 + j * 61) % 180
            if e not in R:
                out.append((e, 1 + (c + j) % 3))
        return out

    @classmethod
    def entry(cls, e: int, b: int) -> tuple[bytes, bytes]:
        r = next((c for c in range(b - 1, -1, -1) if e in cls.refresh(c)), -1)
        g = np.random.default_rng([e, r + 1, 7])
        k0 = g.integers(0, 256, size=cls.EB, dtype=np.uint8); v = g.integers(0, 256, size=cls.EB, dtype=np.uint8)
        sh = sum(d for c in range(r + 1, b) for e2, d in cls.shifts(c) if e2 == e)
        return ((k0.astype(np.int64) + sh) % 256).astype(np.uint8).tobytes(), v.tobytes()

    @staticmethod
    def shift(k: bytes, d: int) -> bytes:
        return ((np.frombuffer(k, dtype=np.uint8).astype(np.int64) + d) % 256).astype(np.uint8).tobytes()

    @classmethod
    def checksums(cls, kv: dict) -> dict:
        # the GPU layout blocks[2 * layer + (K 0 | V 1)][row][slot], with one "layer" per entry, row 0, slot 0
        return {"blocks": [[[hashlib.sha256(kv[e][j]).hexdigest()[:16]]] for e in range(cls.N) for j in (0, 1)], "pos": []}


# ------------------------------------------------------------------------------------------- runtime helpers (GPU)
def gpu_geometry(rt, snap=None) -> tuple[int, int, int]:
    layers = (snap or {}).get("kv") or rt.pl.kv_cache1
    return len(layers), int(layers[0]["k"].shape[0]), int(rt.sink)


def gpu_track_events(rt, last):
    """The frozen M2 tracker's detection rule (GpuRuntime.sink_track_step), per entry: a Sink slot whose position became
    the current frame's position was refreshed; any other position change is a shift by the difference."""
    pos = rt._sink_pos_now()
    if last is None:
        return pos, set(), []
    starts = rt.pl.kv_cache_starts.cpu().tolist()
    rows, S = len(pos[0]), int(rt.sink)
    ref, sh = set(), []
    for li, rr in enumerate(pos):
        for i, row in enumerate(rr):
            newp = int(starts[i]) // rt.fsl
            for s, p in enumerate(row):
                pre = last[li][i][s]
                if p == pre:
                    continue
                e = eid_of(li, i, s, rows, S)
                if p == newp:
                    ref.add(e)
                else:
                    sh.append((e, int(p - pre)))
    return pos, ref, sh


def gpu_entry_payload(rt, snap, e: int):
    L, rows, S = gpu_geometry(rt, snap)
    li, i, s = coords_of(e, rows, S)
    fsl = rt.fsl
    mk, bk = tensor_to_bytes(snap["kv"][li]["k"][i, s * fsl:(s + 1) * fsl])
    mv, bv = tensor_to_bytes(snap["kv"][li]["v"][i, s * fsl:(s + 1) * fsl])
    return mk, mv, [bk, bv], int(bk.nbytes)


def gpu_assemble(rt, entries: dict, shifts: dict) -> tuple[dict, dict]:
    """Destination: write every entry's K / V into the receive snapshot (meta already unpacked), restore the shadow ring
    (frozen shadow_base: meta + Sink, recent zero, refresh frozen), apply each reused entry's ordered K shifts on the live
    ring, and return the Sink checksums."""
    from models.wan.causal_model import _shift_temporal_rope

    torch, fsl = rt.torch, rt.fsl
    snap = rt.snap
    L, rows, S = gpu_geometry(rt, snap)
    rt._sync(); t0 = time.perf_counter()
    for e, rec in entries.items():
        li, i, s = coords_of(e, rows, S)
        view = memoryview(rec["payload"])
        nk = int(rec["nk"])
        snap["kv"][li]["k"][i, s * fsl:(s + 1) * fsl] = bytes_to_tensor(rec["mk"], view[:nk], rt.device)
        snap["kv"][li]["v"][i, s * fsl:(s + 1) * fsl] = bytes_to_tensor(rec["mv"], view[nk:], rt.device)
    snap.setdefault("have", set()).add("sink")
    rt._sync(); t1 = time.perf_counter()
    base_s = rt.shadow_base()
    freqs = rt.pl.generator.model.freqs.to(rt.device)
    n_sh = 0
    for e, ds in shifts.items():
        li, i, s = coords_of(e, rows, S)
        k = rt.pl.kv_cache1[li]["k"]
        for d in ds:
            k[i, s * fsl:(s + 1) * fsl] = _shift_temporal_rope(k[i, s * fsl:(s + 1) * fsl], freqs, int(d)); n_sh += 1
    rt._sync(); t2 = time.perf_counter()
    ck = rt.sink_checksums(); ck_s = ck.pop("s")
    return ck, {"h2d_s": t1 - t0, "shadow_base_s": base_s, "shift_s": t2 - t1 - (base_s or 0.0), "n_shift_ops": n_sh, "digest_s": ck_s}


def retained_entries(hdr: dict, buf, rows: int, S: int, fsl: int):
    """M3-S3: the Sink entries of an M2 retained host copy (proto_handoff.pack_component 'sink': per layer kv/{l}/k and
    kv/{l}/v of shape [rows, S * fsl, ...], C-contiguous). Yields (e, mk, mv, k_bytes, v_bytes) with the same metadata and
    bytes gpu_entry_payload produces for k[i, s * fsl:(s + 1) * fsl] (checked offline by m3s3_p0.py)."""
    mvb = memoryview(buf)
    by = {t_["name"]: t_ for t_ in hdr["tensors"]}
    L = sum(1 for n in by if n.startswith("kv/") and n.endswith("/k"))
    for li in range(L):
        tk, tv = by[f"kv/{li}/k"], by[f"kv/{li}/v"]
        T = int(tk["shape"][1])
        assert int(tk["shape"][0]) == rows and T == S * fsl, (tk["shape"], rows, S, fsl)
        tok_k, tok_v = tk["nbytes"] // (rows * T), tv["nbytes"] // (rows * T)
        mk = {"shape": [fsl] + list(tk["shape"][2:]), "dtype": tk["dtype"]}
        mv = {"shape": [fsl] + list(tv["shape"][2:]), "dtype": tv["dtype"]}
        for i in range(rows):
            for s in range(S):
                ok_ = tk["offset"] + (i * T + s * fsl) * tok_k
                ov_ = tv["offset"] + (i * T + s * fsl) * tok_v
                yield eid_of(li, i, s, rows, S), mk, mv, mvb[ok_:ok_ + fsl * tok_k], mvb[ov_:ov_ + fsl * tok_v]


def block_mismatches(ck: dict, src: dict) -> list:
    return [[i // 2, "kv"[i % 2], b, s_] for i, layer in enumerate(ck["blocks"]) for b, row in enumerate(layer) for s_, v in enumerate(row) if v != src["blocks"][i][b][s_]]


# ------------------------------------------------------------------------------------------------------ node mixin
class M3NodeMixin:
    """Methods of mobility_node.Node for the M3 path. Entered only through the M3_* commands, the MENTRY / MPLAN data
    messages, PROUND mode 'm3' and replay_m3 in PRECOPY_START (all sent only by an orchestrator run with --m3)."""

    # ---- state
    def _m3(self) -> dict:
        r = self.run
        st = r.get("m3s")
        if st is None:
            st = r["m3s"] = {"store": EntryStore(), "fwd": {}, "adv": None, "plan": None, "hist": None, "track_req": False, "track_ready": threading.Event(),
                             "last_pos": None, "failed": False, "test_fault": None, "rx": defaultdict(int)}
        return st

    @property
    def _m3_dry(self) -> bool:
        return bool(self.a.dry_run)

    def _m3_n(self) -> int:
        if self._m3_dry:
            return FakeSinkModel.N
        L, rows, S = gpu_geometry(self.rt)
        return L * rows * S

    # ---- source: lineage tracking (hooks in Node._generate; no effect unless M3_TRACK was received)
    def cmd_m3_track(self, h):
        st = self._m3()
        if st["hist"] is None:
            st["track_req"] = True
            r = self.run
            if r.get("gen_thread") is None or not r["gen_thread"].is_alive():
                self._m3_before_step(int(r["call"]))
            if not st["track_ready"].wait(float(h.get("timeout_s", 60))):
                return {"tracking": False}
        return {"tracking": True, "start": st["hist"].start}

    def _m3_before_step(self, c: int):
        st = self.run.get("m3s")
        if st is None or not st["track_req"] or st["hist"] is not None:
            return
        st["last_pos"] = None if self._m3_dry else gpu_track_events(self.rt, None)[0]
        st["hist"] = LineageHistory(c)
        st["track_ready"].set()

    def _m3_after_step(self, c: int):
        st = self.run.get("m3s")
        hist = st and st["hist"]
        if hist is None or c < hist.start:
            return
        t0 = time.perf_counter()
        if self._m3_dry:
            ref, sh = FakeSinkModel.refresh(c), FakeSinkModel.shifts(c)
        else:
            st["last_pos"], ref, sh = gpu_track_events(self.rt, st["last_pos"])
        hist.record(c, ref, sh, time.perf_counter() - t0)

    def cmd_m3_valid(self, h):
        st = self._m3(); hist = st["hist"]
        if hist is None:
            return {"valid": [], "call": None}
        c = hist.last + 1
        return {"call": c, "valid": [[int(e), int(v)] for e, v, hh in h.get("pairs") or [] if hist.issued_hash(e, v) == hh and hist.valid(int(e), int(v), c)]}

    # ---- source: the mixed-version base (round 1 of a replay pre-copy with replay_m3)
    def _m3_payload(self, snap, e: int, c0: int):
        if self._m3_dry:
            k, v = FakeSinkModel.entry(e, c0)
            m = {"dtype": "u8", "shape": [len(k)]}
            return m, m, [k, v], len(k)
        return gpu_entry_payload(self.rt, snap, e)

    def _m3_source_ck(self, snap, c0: int) -> dict:
        if self._m3_dry:
            return FakeSinkModel.checksums({e: FakeSinkModel.entry(e, c0) for e in range(FakeSinkModel.N)})
        ck = self.rt.sink_checksums(snap); ck.pop("s")
        return ck

    def _m3_send_base(self, task: dict, conn, snap: dict, c: int) -> int:
        rp = task["replay"]
        st = self._m3(); hist = st["hist"]
        n = self._m3_n()
        t0 = time.time()
        why = {"not_issued": 0, "refreshed": 0, "no_history": 0}
        avail = {}
        for e, v, hh in rp.get("m3_held") or []:
            e, v = int(e), int(v)
            if hist is None:
                why["no_history"] += 1
            elif hist.issued_hash(e, v) != hh:
                why["not_issued"] += 1
            elif not hist.valid(e, v, c):
                why["refreshed"] += 1
            else:
                avail[e] = (v, hh)
        reuse = [[e, avail[e][0], avail[e][1], hist.shifts_since(e, avail[e][0], c)] for e in range(n) if e in avail]
        send = [e for e in range(n) if e not in avail]
        ck0 = self._m3_source_ck(snap, c)
        t_plan = time.time()
        sent_m, headers, digests = self._xb_send_dirty(task, conn, snap, ("meta",), whole=("meta",))
        base = rp["base"] = {"mode": "m3", "bytes": sent_m, "meta_bytes": sent_m, "advertised": len(rp.get("m3_held") or []), "reused": len(reuse), "planned_send": len(send),
                             "sent_entries": 0, "entry_bytes": 0, "header_bytes": 0, "shift_ops": sum(len(x[3]) for x in reuse), "rejected": why,
                             "reuse_versions": dict(sorted(defaultdict(int, {v: sum(1 for x in reuse if x[1] == v) for v in {x[1] for x in reuse}}).items())), "plan_s": t_plan - t0}
        with task["send_lock"]:
            send_msg(conn, "MPLAN", {"task": task["id"], "call": c, "reuse": reuse, "send": send, "sink_ck": ck0, "n_entries": n}, b"", None)
        t_e = time.time(); hash_s = d2h_s = 0.0

        def prep(e_):
            # serialization of the next entries overlaps the current entry's transfer (D2H and SHA-256 release the GIL)
            if not self._m3_dry:
                self._thread_init()
            t_a = time.perf_counter()
            mk_, mv_, parts_, nk_ = self._m3_payload(snap, e_, c)
            t_b = time.perf_counter()
            return mk_, mv_, parts_, nk_, sha_parts(parts_), t_b - t_a, time.perf_counter() - t_b

        ex = ThreadPoolExecutor(max_workers=2)
        futs = deque(ex.submit(prep, e_) for e_ in send[:2])
        for j, e in enumerate(send):
            if task["cancel"]:
                break
            mk, mv, parts, nk, hsh, dt_d2h, dt_hash = futs.popleft().result()
            if j + 2 < len(send):
                futs.append(ex.submit(prep, send[j + 2]))
            d2h_s += dt_d2h; hash_s += dt_hash
            if hist is not None:
                hist.issue(e, c, hsh)
            mh = {"task": task["id"], "e": e, "ver": c, "sha256": hsh, "mk": mk, "mv": mv, "nk": nk, "origin": self.label, "from": self.label, "flow": task["id"], "role": "base"}
            with task["send_lock"]:
                send_msg(conn, "MENTRY", mh, parts, task["throttle"])
            nb = sum(memoryview(p).nbytes for p in parts)
            base["sent_entries"] += 1; base["entry_bytes"] += nb; base["bytes"] += nb
            base["header_bytes"] += 16 + len(json.dumps({"kind": "MENTRY", "t_send": time.time(), **mh}).encode())
        ex.shutdown(wait=False, cancel_futures=True)
        base.update({"entries_send_s": time.time() - t_e, "d2h_s": d2h_s, "hash_s": hash_s})
        if task["cancel"]:
            self.event("m3_base_cancelled", task=task["id"], call=c, **base)
            return base["bytes"]
        with task["send_lock"]:
            send_msg(conn, "PROUND", {"task": task["id"], "round": 1, "call": c, "headers": headers, "digests": digests, "cond_digest": self.rt.cond_digest(), "W": rp["W"],
                                      "mode": "m3", "sink_ck": ck0}, b"", None)
        t_d = time.time()
        got = rp["delta_ev"].wait(300)
        base.update({"verdict": rp["delta_verdict"] if got else "timeout", "verdict_wait_s": time.time() - t_d, "verdict_detail": rp["delta_detail"]})
        if not (got and rp["delta_verdict"] == "DELTAOK"):
            # the destination rejected the assembled Sink: the frozen full-base path (as M2's DELTANO fallback)
            sent, headers, digests = self._xb_send_dirty(task, conn, snap, ("sink", "meta"), whole=("meta",))
            with task["send_lock"]:
                send_msg(conn, "PROUND", {"task": task["id"], "round": 1, "call": c, "headers": headers, "digests": digests, "cond_digest": self.rt.cond_digest(), "W": rp["W"]}, b"", None)
            base.update({"mode": "full", "fallback_reason": "the destination rejected the M3 base", "fallback_bytes": sent}); base["bytes"] += sent
        self.event("m3_base_sent", task=task["id"], call=c, **base)
        self.event("replay_base_sent", task=task["id"], call=c, **base)
        return base["bytes"]

    # ---- every node: entries on the data port
    def _m3_recv_entry(self, conn, hdr: dict, pl: int):
        st = self._m3()
        e, v = int(hdr["e"]), int(hdr["ver"])
        t0 = time.time()
        try:
            data = bytes(recv_exact(conn, pl))
        except (ConnectionError, OSError):
            st["store"].mark_lost(e, v)
            self.event("m3_entry_lost", e=e, ver=v, src=hdr.get("from"), flow=hdr.get("flow"), role=hdr.get("role"))
            raise
        ok = hashlib.sha256(data).hexdigest() == hdr["sha256"]
        if not ok:
            st["rx"]["bad"] += 1
            self.event("m3_entry_bad", e=e, ver=v, src=hdr.get("from"), flow=hdr.get("flow"), role=hdr.get("role"))
            return
        res = st["store"].put(e, {"v": v, "h": hdr["sha256"], "mk": hdr["mk"], "mv": hdr["mv"], "nk": int(hdr["nk"]), "payload": data, "origin": hdr.get("origin"),
                                  "src": hdr.get("from"), "flow": hdr.get("flow"), "role": hdr.get("role"), "t": time.time()})
        st["rx"][f"{hdr.get('role')}:{res}"] += 1; st["rx"][f"{hdr.get('role')}_bytes"] += pl
        self.event("m3_entry", e=e, ver=v, src=hdr.get("from"), flow=hdr.get("flow"), role=hdr.get("role"), result=res, bytes=pl, recv_s=time.time() - t0)

    def _m3_recv_plan(self, hdr: dict):
        self._m3()["plan"] = hdr

    # ---- holder / candidate commands
    def cmd_m3_held(self, h):
        """Verified entries held here. With `expect` ([entry, version] fully written toward this node by holders whose
        flows were just stopped): wait until each is verified here or lost, at most wait_s. With advertise: freeze the
        advertised set (the destination assembles exactly these bytes)."""
        st = self._m3(); store = st["store"]
        expect = [(int(e), int(v)) for e, v in h.get("expect") or []]
        t0 = time.time(); wait_s = float(h.get("wait_s", 0.0))
        while True:
            missing = [(e, v) for e, v in expect if not store.has(e, v) and (e, v) not in store.lost]
            if not missing or time.time() - t0 >= wait_s:
                break
            time.sleep(0.01)
        adv = [] if st["failed"] else store.advert()
        if h.get("advertise"):
            snap_ = store.snapshot()
            st["adv"] = {e: snap_[e] for e, v, hh in adv if e in snap_}
            st["test_fault"] = h.get("test_fault")
            self.event("m3_advertise", n=len(adv), waited_s=time.time() - t0, expected=len(expect), missing_expected=len(missing), lost=len(store.lost),
                       versions=dict(sorted(defaultdict(int, {vv: sum(1 for x in adv if x[1] == vv) for vv in {x[1] for x in adv}}).items())))
        return {"held": adv, "waited_s": time.time() - t0, "missing": missing, "lost": sorted(store.lost), "counts": dict(store.counts), "failed": st["failed"]}

    def cmd_m3_forward(self, h):
        st = self._m3()
        fl = {"id": h["flow"], "to": h["to"], "host": h["to_host"], "port": int(h["to_port"]), "entries": [(int(e), int(v)) for e, v in h["entries"]],
              "rate": float(h.get("rate_bps") or 0.0), "fail_after": h.get("fail_after"), "cancel": False, "sent": [], "skipped": [], "bytes": 0, "done": threading.Event(),
              "t_start": time.time()}
        st["fwd"][fl["id"]] = fl
        if st["failed"]:
            fl["done"].set(); self.event("m3_forward_done", flow=fl["id"], to=fl["to"], n_sent=0, bytes=0, cancelled=False, refused="holder failed"); return {"refused": True}
        threading.Thread(target=self._m3_forward, args=(fl,), daemon=True).start()
        return {}

    def _m3_forward(self, fl: dict):
        self._thread_init()
        st = self._m3(); store = st["store"]
        try:
            conn = tcp_connect(fl["host"], fl["port"], self.a.mss, timeout=60)
        except Exception as exc:  # noqa: BLE001
            self.event("m3_forward_failed", flow=fl["id"], to=fl["to"], error=repr(exc)); fl["done"].set(); return
        thr = Throttle(fl["rate"]) if fl["rate"] > 0 else None
        fl["thr"] = thr
        injected = None
        try:
            for e, v in fl["entries"]:
                if fl["cancel"]:
                    break
                rec = store.get(e)
                if rec is None or rec["v"] != v:
                    fl["skipped"].append([e, v]); continue
                mh = {"e": e, "ver": v, "sha256": rec["h"], "mk": rec["mk"], "mv": rec["mv"], "nk": rec["nk"], "origin": rec["origin"], "from": self.label, "flow": fl["id"],
                      "role": "forward"}
                if fl["fail_after"] is not None and len(fl["sent"]) >= int(fl["fail_after"]):
                    # holder failure (test only): the connection drops in the middle of this entry's payload; the holder is gone
                    hb = json.dumps({"kind": "MENTRY", "t_send": time.time(), **mh}).encode()
                    conn.sendall(struct.pack("!QQ", len(hb), len(rec["payload"]))); conn.sendall(hb); conn.sendall(rec["payload"][:len(rec["payload"]) // 2])
                    injected = [e, v]; st["failed"] = True
                    break
                send_msg(conn, "MENTRY", mh, rec["payload"], thr)
                fl["sent"].append([e, v]); fl["bytes"] += len(rec["payload"])
        except (ConnectionError, OSError) as exc:
            fl["error"] = repr(exc)
        finally:
            try:
                if injected is None:
                    send_msg(conn, "FLOW_END", {"flow_id": fl["id"]}, b"", None)
                conn.close()
            except OSError:
                pass
        fl["t_end"] = time.time()
        self.event("m3_forward_done", flow=fl["id"], to=fl["to"], n_sent=len(fl["sent"]), bytes=fl["bytes"], cancelled=fl["cancel"], skipped=len(fl["skipped"]),
                   failed_injected=injected, error=fl.get("error"), s=fl["t_end"] - fl["t_start"])
        fl["done"].set()

    def cmd_m3_forward_stop(self, h):
        """Stop every forward flow toward `to` (the in-flight entry completes or the flow ends) and return every entry
        fully written toward it by any of this node's flows (the receiver's M3_HELD waits for those)."""
        st = self._m3()
        flows = [fl for fl in st["fwd"].values() if fl["to"] == h["to"]]
        for fl in flows:
            fl["cancel"] = True
        for fl in flows:
            fl["done"].wait(120)
        return {"sent": [x for fl in flows for x in fl["sent"]], "n_flows": len(flows), "bytes": sum(fl["bytes"] for fl in flows)}

    def cmd_m3_state(self, h):
        st = self._m3()
        return {"held": len(st["store"].held), "counts": dict(st["store"].counts), "rx": dict(st["rx"]), "hist": st["hist"].summary() if st["hist"] else None,
                "failed": st["failed"], "flows": {k: {"to": f["to"], "sent": len(f["sent"]), "bytes": f["bytes"], "done": f["done"].is_set()} for k, f in st["fwd"].items()}}

    # ---- destination: assemble and verify (PROUND mode 'm3')
    def _m3_replay_base(self, conn, hdr: dict):
        from proto_handoff import component_digest, payload_slices

        self._thread_init()
        r = self.run
        rs, xst = self._replay_state(), r["xb_store"]
        st = self._m3()
        t0 = time.time()
        plan = st["plan"]
        c0 = int(hdr["call"])
        c = (xst or {}).get("comps", {}).get("meta")
        meta_ok = c is not None and component_digest(payload_slices(hdr["headers"]["meta"], c["buf"])) == hdr["digests"]["meta"]
        plan_ok = plan is not None and plan.get("task") == hdr["task"] and int(plan["call"]) == c0
        adv = st["adv"] or {}
        entries, shifts, problems = {}, {}, []
        if plan_ok:
            for e, v, hh, ds in plan["reuse"]:
                rec = adv.get(int(e))
                if rec is None or rec["v"] != int(v) or rec["h"] != hh:
                    problems.append([int(e), "reused entry not in the advertised set"]); continue
                entries[int(e)] = rec
                if ds:
                    shifts[int(e)] = [int(d) for d in ds]
            for e in plan["send"]:
                rec = st["store"].get(int(e))
                if rec is None or rec["v"] != c0:
                    problems.append([int(e), "sent entry not held at the boundary version"]); continue
                entries[int(e)] = rec
        injected = None
        if st["test_fault"] == "corrupt_held" and plan_ok and plan["reuse"]:
            # Phase B (test only): the bytes assembled for one reused entry differ from the advertised version (one bit)
            e = int(plan["reuse"][0][0])
            if e in entries:
                pay = bytearray(entries[e]["payload"]); pay[0] ^= 1
                entries[e] = {**entries[e], "payload": bytes(pay)}; injected = {"fault": "corrupt_held", "entry": e}
        n = int((plan or {}).get("n_entries") or self._m3_n())
        complete = plan_ok and not problems and len(entries) == n
        detail = {"meta_ok": meta_ok, "plan_ok": plan_ok, "complete": complete, "n_problems": len(problems), "problems": problems[:20],
                  "reused": len(plan["reuse"]) if plan_ok else None, "sent": len(plan["send"]) if plan_ok else None, "shift_ops": sum(len(x) for x in shifts.values()),
                  "versions": dict(sorted(defaultdict(int, {rec["v"]: sum(1 for x in entries.values() if x["v"] == rec["v"]) for rec in entries.values()}).items())),
                  # M3-S3 record: per (issuer, sender, version) how many entries of the assembled Sink came that way
                  "provenance": dict(sorted(defaultdict(int, {k_: sum(1 for x in entries.values() if f"{x.get('origin')}|{x.get('src')}|{x['v']}" == k_)
                                                              for k_ in {f"{x.get('origin')}|{x.get('src')}|{x['v']}" for x in entries.values()}}).items()))}
        match, tm, bad, pos_ok = False, {}, [], None
        if meta_ok and complete:
            self.rt.unpack(dict(hdr["headers"]["meta"]), c["buf"])
            if self._m3_dry:
                kv = {}
                for e, rec in entries.items():
                    k, v = rec["payload"][:rec["nk"]], rec["payload"][rec["nk"]:]
                    for d in shifts.get(e, ()):
                        k = FakeSinkModel.shift(k, d)
                    kv[e] = (k, v)
                ck = FakeSinkModel.checksums(kv); self.rt.shadow_base()
            else:
                ck, tm = gpu_assemble(self.rt, entries, shifts)
            src = hdr["sink_ck"]
            bad = block_mismatches(ck, src)
            pos_ok = ck["pos"] == src["pos"]
            match = not bad and pos_ok
        cond_ok = self.rt.cond_digest() == hdr["cond_digest"] if match else None
        ok = match and bool(cond_ok)
        detail.update({"n_block_mismatch": len(bad), "positions_equal": pos_ok, "digest_equal": match, "cond_equal": cond_ok})
        try:
            with rs["send_lock"]:
                send_msg(conn, "DELTAOK" if ok else "DELTANO", {"detail": {k: v for k, v in detail.items() if k != "problems"}}, b"", None)
        except OSError:
            pass
        self.event("m3_base", task=hdr["task"], call=c0, accepted=ok, mismatched_blocks=bad[:40], total_s=time.time() - t0, test_injected=injected, **detail, **tm)
        st["plan"] = None
        if ok:
            # the same record the frozen M1 base writes (the orchestrator's replay validity reads it)
            self.event("replay_base", task=hdr["task"], call=c0, verified=True, components_ok={"meta": meta_ok, "sink": True}, cond_equal=cond_ok, mode="m3",
                       verify_s=time.time() - t0, base_s=tm.get("shadow_base_s"))
            rs["c0"], rs["conn"] = c0, conn
            rs["base"] = {"verified": True, "mode": "m3", "cond_equal": cond_ok, "t": time.time(), **tm}
            rs["base_ready"].set()
            if rs["worker"] is None:
                rs["worker"] = threading.Thread(target=self._replay_worker, args=(rs,), daemon=True); rs["worker"].start()

    # ---------------------------------------------------------------- M3-S3: lineage across an ownership change
    # (osdi/m3s3/preregistration.md). Entered only when the orchestrator runs with --m3 --m3_owner.
    def cmd_m3_owner_arm(self, h):
        """Every node: if it becomes the owner through a switchover, start its own lineage history at the switch call."""
        st = self._m3(); st["owner_arm"] = True
        return {"armed": True}

    def _m3_become_owner(self, call: int):
        """Hook in Node._xb_become_owner (before the generation thread starts): the new owner's history begins at the switch
        call. The M2 tracking version this node verified at the switch (Sink digest equal to the source's) is kept: it
        decides whether the previous owner's retained entries may be issued under this owner's lineage."""
        st = self.run.get("m3s")
        if st is None or not st.get("owner_arm"):
            return
        tr = getattr(self.rt, "_track", None)
        st["owner_prev_hist"] = st["hist"]
        st["hist"] = None; st["track_req"] = True; st["track_ready"].clear()
        st["owner_since"] = int(call); st["owner_version"] = (tr or {}).get("version")
        self.event("m3_owner_begin", call=int(call), tracking_version=st["owner_version"])

    def cmd_m3_handover_begin(self, h):
        """Old owner, right after its switchover: in the background, turn the M2 retained host copy (the Sink verified at
        the switch) into verified-held entries at version = switch call, hashed here (it serialized them). No GPU work."""
        st = self._m3()
        if st.get("handover") is not None:
            return {"started": False}
        ho = st["handover"] = {"done": threading.Event(), "t0": time.time(), "test_fault": h.get("test_fault")}
        threading.Thread(target=self._m3_handover_build, args=(ho,), daemon=True).start()
        return {"started": True}

    def _m3_handover_build(self, ho: dict):
        st = self._m3(); r = self.run
        # Note 1 (m3s3 preregistration): the old owner's switch thread retains the Sink (host copy, ~1 s on GPU) after the
        # new owner already resumed; wait until that thread has finished (retained copy present, or switch done without
        # one, e.g. SINKNO) before reading it. Bounded wait.
        t_w = time.time()
        while r.get("retained") is None and not (r.get("xb") or {}).get("done") and time.time() - t_w < 120:
            time.sleep(0.02)
        ret = r.get("retained")
        out = {"retained_version": None if ret is None else ret["version"], "n_entries": 0, "bytes": 0, "retain_wait_s": time.time() - t_w}
        try:
            if ret is not None:
                v = int(ret["version"]["call"])
                if self._m3_dry:
                    it = ((e, {"dtype": "u8", "shape": [FakeSinkModel.EB]}, {"dtype": "u8", "shape": [FakeSinkModel.EB]}) + FakeSinkModel.entry(e, v)
                          for e in range(FakeSinkModel.N))
                else:
                    L, rows, S = gpu_geometry(self.rt)
                    it = retained_entries(ret["hdr"], ret["buf"], rows, S, self.rt.fsl)
                hist = st["hist"]
                for e, mk, mv, bk, bv in it:
                    payload = bytes(bk) + bytes(bv)
                    hsh = hashlib.sha256(payload).hexdigest()
                    if ho["test_fault"] == "corrupt_retained" and out["n_entries"] == 0:
                        # Phase B (test only): the held bytes of the first entry differ from the hash advertised for it
                        pb = bytearray(payload); pb[0] ^= 1; payload = bytes(pb); out["corrupted_entry"] = e
                    st["store"].put(e, {"v": v, "h": hsh, "mk": mk, "mv": mv, "nk": len(bk), "payload": payload, "origin": self.label, "src": self.label,
                                        "flow": None, "role": "retained", "t": time.time()})
                    if hist is not None:
                        hist.issue(e, v, hsh)
                    out.setdefault("retained_hashes", []).append([e, v, hsh])
                    out["n_entries"] += 1; out["bytes"] += len(payload)
            out["history"] = st["hist"].export() if st["hist"] is not None else None
        except Exception as exc:  # noqa: BLE001
            out["error"] = repr(exc)
        out["build_s"] = time.time() - ho["t0"]
        ho["out"] = out; ho["done"].set()
        self.event("m3_handover_built", **{k: v for k, v in out.items() if k not in ("history", "retained_hashes")},
                   history_calls=None if not out.get("history") else len(out["history"]["refresh"]))

    def cmd_m3_handover(self, h):
        """Old owner: wait for the build, return the history, the issued table and the retained version."""
        ho = self._m3().get("handover")
        if ho is None:
            return {"missing": True}
        ho["done"].wait(float(h.get("wait_s", 300)))
        return ho.get("out") or {"timeout": True}

    def cmd_m3_lineage_import(self, h):
        """New owner: prepend the previous owner's history (only if contiguous with this owner's first call) and issue the
        previous owner's hashes of its retained entries only if their version is the one this node verified at the switch
        (M2 tracking version: same session, call and Sink digest). Anything refused stays not issued, so the entries are
        re-sent rather than reused."""
        st = self._m3()
        if not st["track_ready"].wait(float(h.get("wait_s", 60))) or st["hist"] is None:
            self.event("m3_lineage_import", accepted=False, reason="no history at this owner"); return {"accepted": False}
        hist = st["hist"]
        exp = h.get("export") or {}
        hx = exp.get("history")
        mr = hist.merge_prefix(hx) if hx else {"contiguous": False, "merged_calls": 0, "merged_issued": 0}
        rv, mine = exp.get("retained_version"), st.get("owner_version")
        version_equal = rv is not None and mine is not None and rv == mine and int(rv["call"]) == hist_start_of(st)
        issued_retained = 0
        if version_equal:
            v = int(rv["call"])
            for e, vv, hh in exp.get("retained_hashes") or []:
                if int(vv) == v:
                    hist.issue(int(e), v, hh); issued_retained += 1
        res = {"accepted": True, **mr, "version_equal": version_equal, "issued_retained": issued_retained, "owner_since": st.get("owner_since"),
               "history_start": hist.start, "history_last": hist.last}
        self.event("m3_lineage_import", **res)
        return res

    def cmd_m3_forward_rate(self, h):
        """Re-rate active forward flows (cap-conserving shares computed by the orchestrator at each re-plan)."""
        st = self._m3(); n = 0
        for fid, bps in (h.get("rates") or {}).items():
            fl = st["fwd"].get(fid)
            if fl is not None and fl.get("thr") is not None and not fl["done"].is_set():
                fl["thr"].rate = float(bps) / 8.0; fl["rate"] = float(bps); n += 1
        return {"updated": n}


def hist_start_of(st: dict) -> int | None:
    """The call this owner's own history began at (the switch call)."""
    return st.get("owner_since")
