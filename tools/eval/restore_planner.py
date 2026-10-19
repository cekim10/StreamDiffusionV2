"""Shared Sink-restoration planner (OTTER M2/M3 decision code), used by both harnesses:

    tools/eval/restore_orchestrate.py   network-level restoration harness (no GPU)
    tools/eval/mobility_orchestrate.py  GPU repeated-mobility harness

The functions are pure decisions over plain data: each harness collects its own state (verified holdings, in-flight
fragments, flow backlogs, measured throughput) and applies the returned decision with its own flow machinery. The
code is moved verbatim from restore_orchestrate.py (commit e345ccd, the version that produced every network-level
result); its behaviour is pinned by tools/eval/test_restore_planner.py, which replays the pre-refactor implementation
on randomized states and requires identical decisions.

Decisions provided:
    assign_providers   provider for every missing fragment at a plan (move, start, flow_done):
                       reuse_fixed (M2 wavefront: newest holder forwards), pp_star / fixed_line / fixed_tree /
                       fixed_butterfly (Experiment E baselines), reuse_aware / reuse_aware_in / reuse_dyn (M3
                       bottleneck-aware assignment; _in = with the ingress bound), reuse_adaptive (probe-rate, H3b)
    dyn_decide         event-driven re-plan of the bottleneck provider's remaining fragments (M3; E-pilot v2 rule)
    prepos_alloc       proactive placement allocation before a move (M3)
    dissem_assign      Experiment B dissemination plans
    maxmin             max-min fair rates under per-node caps (the emulated network)
    parse_cap_events   time- or progress-triggered cap changes
"""

from __future__ import annotations

from collections import defaultdict

SOURCE = "A"
DISSEM_PLANS = ["star", "line", "tree", "multipath", "aware"]
FIXED_PLANS = ("pp_star", "fixed_line", "fixed_tree", "fixed_butterfly")
AWARE_PLANS = ("reuse_aware", "reuse_aware_in", "reuse_dyn")


# ----------------------------------------------------------------------------------------------- network emulation
def maxmin(flows, caps):
    """flows: [(id, src, dst)]; caps: {("out"|"in", node): bps}. Max-min fair rates under per-node caps."""
    rate = {f: 0.0 for f, _, _ in flows}
    if not flows:
        return rate
    resid = dict(caps)
    frozen = set()
    while len(frozen) < len(flows):
        act = [(f, s, d) for f, s, d in flows if f not in frozen]
        load = defaultdict(int)
        for _, s, d in act:
            load[("out", s)] += 1; load[("in", d)] += 1
        inc = min(resid[k] / n for k, n in load.items())
        for f, _, _ in act:
            rate[f] += inc
        for k, n in load.items():
            resid[k] -= inc * n
        for f, s, d in act:
            if resid[("out", s)] <= 1e-3 or resid[("in", d)] <= 1e-3:
                frozen.add(f)
    return rate


def parse_cap_events(spec):
    """'t=20:C:out=62.5' (at 20 s) or 'D>=0.5:C:out=62.5' (when D holds 50 % of s0's Sink): set C's egress cap to 62.5 Mbps."""
    out = []
    for item in (spec or "").split(";"):
        item = item.strip()
        if not item:
            continue
        trig, node, capv = item.split(":")
        d, v = capv.split("=")
        e = {"spec": item, "cap_node": node, "dir": d, "mbps": float(v), "fired": False}
        if trig.startswith("t="):
            e["kind"] = "t"; e["at"] = float(trig[2:])
        else:
            n, frac = trig.split(">=")
            e["kind"] = "progress"; e["node"] = n; e["frac"] = float(frac)
        out.append(e)
    return out


# ----------------------------------------------------------------------------------------------- planning at moves
def holder_order(history, own, held, edges):
    """Past owners newest first (never the source), then edges that hold verified fragments without having been owners
    (pre-positioned holders)."""
    holders = [e for e in reversed(history[:-1]) if e != own and e != SOURCE]
    holders = list(dict.fromkeys(holders))
    holders += [e for e in edges if e != own and e not in holders and held[e]]
    return holders


def assign_providers(policy, *, missing, own, holders, held, soon, skipped, backlog, inbound_bytes, known_caps, flen,
                     history, probe_rate=None):
    """Provider for every missing fragment of one session at the owner `own`.

    missing        fragments neither verified at the owner nor already headed to it
    holders        holder_order(...)
    held           {node: set of verified fragment ids} for this session
    soon           {holder: fragments in flight to that holder (they will be held shortly)}
    skipped        fragments a holder was asked for before it had them
    backlog        {provider: bytes queued at that provider's egress, every session} (aware rules)
    inbound_bytes  bytes already headed to `own` on active flows, every session (ingress bound, aware rules)
    known_caps     caps the planner believes (never the live caps)
    history        ownership sequence of this session including the current owner
    probe_rate     reuse_adaptive only: provider -> max-min rate a new provider->own flow would get now (bps)
    Returns (assign, late): {provider: [fragment ids]} to send now, {holder: [ids]} to forward once they land (queued last).
    """
    assign = defaultdict(list)
    late = defaultdict(list)
    if policy == "reuse_fixed":
        for f in sorted(missing):
            src = next((h for h in holders if f in held[h]), None)
            if src is None:
                src = next((h for h in holders if f in soon[h]), None) if f not in skipped else None
                if src is not None:
                    late[src].append(f); continue
                src = SOURCE
            assign[src].append(f)
    elif policy in FIXED_PLANS:
        # Experiment E fixed plans: keep the owner's own fragments, never drop; differ in which past holders forward.
        #   pp_star nobody; fixed_line the previous owner; fixed_tree the first edge visited (hub);
        #   fixed_butterfly every past holder, a fragment held by several goes to the one with the fewest assigned so far.
        past = [e for e in history[:-1] if e != SOURCE]
        if policy == "pp_star":
            allowed = []
        elif policy == "fixed_line":
            allowed = [past[-1]] if past and past[-1] != own else []
        elif policy == "fixed_tree":
            allowed = [past[0]] if past and past[0] != own else []
        else:
            allowed = [h for h in holders]
        count = {h: 0 for h in allowed}
        for f in sorted(missing):
            have = [h for h in allowed if f in held[h]]
            if have:
                src = min(have, key=lambda h: (count[h], h)); count[src] += 1
                assign[src].append(f); continue
            inbound = next((h for h in allowed if f in soon[h]), None) if f not in skipped else None
            if inbound is not None:
                late[inbound].append(f); continue
            assign[SOURCE].append(f)
    elif policy in AWARE_PLANS:
        # each provider's finish estimate is its whole egress backlog plus what this plan adds, over its egress cap;
        # fragments only the source holds go to it first, so held fragments see the source's true queue
        cand = holders + [SOURCE]
        load = {c: 0.0 for c in cand}
        for c in cand:
            load[c] += backlog.get(c, 0.0)
        rest = []
        for f in sorted(missing):
            inbound = next((h for h in holders if f in soon[h] and f not in held[h]), None) if f not in skipped else None
            if inbound is not None and not any(f in held[h] for h in holders):
                late[inbound].append(f); continue
            if not any(f in held[h] for h in holders):
                assign[SOURCE].append(f); load[SOURCE] += flen
            else:
                rest.append(f)
        # reuse_aware_in / reuse_dyn (H4c correction): a held fragment moves to the source only when its best holder
        # would finish after both the source and the owner's ingress bound
        inbound = inbound_bytes + sum(len(v) for v in assign.values()) * flen
        for f in rest:
            opts = [c for c in cand if c == SOURCE or f in held[c]]
            est = lambda c: (load[c] + flen) / known_caps[("out", c)]  # noqa: E731
            if policy in ("reuse_aware_in", "reuse_dyn"):
                inbound += flen
                hold = min((c for c in opts if c != SOURCE), key=est)
                best = SOURCE if est(hold) > max(est(SOURCE), inbound / known_caps[("in", own)]) else hold
            else:
                best = min(opts, key=lambda c: (est(c), c == SOURCE))  # ties: prefer a holder
            assign[best].append(f); load[best] += flen
    elif policy == "reuse_adaptive":
        # earliest estimated finish per fragment, given per-session queues and the max-min rate of a new flow (H3b rule)
        cand = holders + [SOURCE]
        est = {c: max(1.0, probe_rate(c)) for c in cand}
        load = {c: 0 for c in cand}
        for f in sorted(missing):
            inbound = next((h for h in holders if f in soon[h] and f not in held[h]), None) if f not in skipped else None
            if inbound is not None and not any(f in held[h] for h in holders):
                late[inbound].append(f); continue
            opts = [c for c in cand if c == SOURCE or f in held[c]]
            best = min(opts, key=lambda c: ((load[c] + 1) * flen * 8 / est[c], c == SOURCE))  # ties: prefer a holder
            assign[best].append(f); load[best] += 1
    else:
        raise ValueError(f"no provider rule for policy {policy!r}")
    return assign, late


# ----------------------------------------------------------------------------------------------- event-driven re-plan
def dyn_decide(*, sid, own, act, rate, rate_est, now, held, known_caps, flen, nodes, window, ctrl, eps, rel):
    """E-pilot v2 re-planning rule for one session (M3, event-driven).

    act       active flows to `own` with remaining fragments: dicts with src, left (set), order (list)
    rate      {provider: measured verified throughput toward `own` over the window, bytes/s} (all of act's providers)
    rate_est  {(sid, node): (bytes/s, t)} persistent store; updated here (kept while a provider is idle)
    nodes     ["A"] + edges, in the order used for estimates and options
    Returns None (no switch) or a dict with q (bottleneck provider), assign {provider: [ids]}, head (in-flight ids left
    to drain at q), eta_cur, eta_new, c_switch, drain, dT, margin, cap_est, stale.
    """
    eta = {}
    rem = defaultdict(int)
    for fl in act:
        rem[fl["src"]] += len(fl["left"]) * flen
    for p_, b in rem.items():
        eta[p_] = b / rate[p_] if rate[p_] > 0 else float("inf")
    q = max(eta, key=eta.get)
    eta_cur = eta[q]
    if eta_cur == float("inf"):
        eta_cur = 1e6
    for n, r in rate.items():
        if r > 0:
            rate_est[(sid, n)] = (r, now)
    cap_est, stale = {}, {}
    for n in nodes:
        if (sid, n) in rate_est:
            cap_est[n], tm = rate_est[(sid, n)]
            stale[n] = now - tm > window
        else:
            cap_est[n], stale[n] = known_caps[("out", n)], None
    qflows = [fl for fl in act if fl["src"] == q]
    head = {next((f for f in fl["order"] if f in fl["left"]), None) for fl in qflows} - {None}   # in flight: let it drain
    movable = set().union(*(fl["left"] for fl in qflows)) - head
    if not movable:
        return None
    load = {n: 0.0 for n in nodes}
    for fl in act:
        if fl["src"] != q:
            load[fl["src"]] += len(fl["left"]) * flen
    load[q] += len(head) * flen
    inbound = sum(len(fl["left"]) for fl in act) * flen
    assign = defaultdict(list)
    for f in sorted(movable):
        opts = [c for c in nodes if c != own and (c == SOURCE or f in held[c])]
        best = min(opts, key=lambda c: ((load[c] + flen) / cap_est[c], c == SOURCE))
        assign[best].append(f); load[best] += flen
    eta_new = max((load[n] / cap_est[n] for n in load if load[n] > 0), default=0.0)
    eta_new = max(eta_new, inbound / known_caps[("in", own)])
    drain = flen / max(rate[q], 1.0) if head else 0.0
    c_switch = ctrl + drain
    dT = eta_cur - eta_new
    margin = max(eps, rel * eta_cur)
    if dT <= c_switch + margin or set(assign) == {q}:
        return None
    return {"q": q, "assign": assign, "head": head, "qflows": qflows, "eta_cur": eta_cur, "eta_new": eta_new, "c_switch": c_switch,
            "drain": drain, "dT": dT, "margin": margin, "cap_est": cap_est, "stale": stale}


# ----------------------------------------------------------------------------------------------- proactive placement
def prepos_alloc(pp, caps, sink_bytes, nfr, edges):
    """Placement before a move (M3). pp: {policy, probs (per edge, in `edges` order), L, b, dest, tau}.
    Returns (x {edge: Sink fraction}, frags {edge: [ids]} disjoint in probability order, avail, order)."""
    S = sink_bytes
    order = sorted(edges, key=lambda c: -pp["probs"][edges.index(c)])
    prob = {c: pp["probs"][edges.index(c)] for c in edges}
    deliv = {c: pp["L"] * caps[("in", c)] / 8 / S for c in edges}
    avail = min(pp["b"], pp["L"] * caps[("out", SOURCE)] / 8 / S)
    x = {c: 0.0 for c in edges}
    pol = pp["policy"]
    if pol == "oracle":
        x[pp["dest"]] = min(avail, deliv[pp["dest"]])
    elif pol == "top1":
        x[order[0]] = min(avail, deliv[order[0]])
    elif pol == "greedy":
        rem = avail
        for c in order:
            x[c] = min(rem, deliv[c]); rem -= x[c]
    elif pol == "proportional":
        for c in order:
            x[c] = min(avail * prob[c], deliv[c])
    elif pol == "coverage":
        rem = avail
        for c in order:
            need = max(0.0, 1.0 - (pp["tau"] - 0.3) * caps[("in", c)] / 8 / S)
            x[c] = min(need, deliv[c], rem); rem -= x[c]
        for c in order:
            add = min(rem, deliv[c] - x[c]); x[c] += add; rem -= add
    elif pol != "none":
        raise ValueError(pol)
    pool = list(range(nfr)); pos = 0
    frags = {}
    for c in order:
        n = int(round(x[c] * nfr))
        frags[c] = pool[pos:pos + n]; pos += n
    return x, frags, avail, order


# ----------------------------------------------------------------------------------------------- dissemination
def dissem_assign(plan, nfr, flen, caps, edges=("B", "C", "D")):
    """Experiment B: provider of every (fragment, destination) pair for one Sink held at A and needed at B, C, D."""
    edges = list(edges)
    prov = {}
    if plan == "star":
        for f in range(nfr):
            for d in edges:
                prov[(f, d)] = SOURCE
    elif plan == "line":
        chain = [SOURCE] + edges
        for f in range(nfr):
            for i, d in enumerate(edges, start=1):
                prov[(f, d)] = chain[i - 1]
    elif plan == "tree":
        for f in range(nfr):
            prov[(f, edges[0])] = SOURCE; prov[(f, edges[1])] = edges[0]; prov[(f, edges[2])] = edges[0]
    elif plan == "multipath":
        for f in range(nfr):
            own = edges[f % 3]
            for d in edges:
                prov[(f, d)] = SOURCE if d == own else own
    elif plan == "aware":
        load = {n: 0.0 for n in [SOURCE] + edges}
        inload = {d: 0.0 for d in edges}
        for f in range(nfr):
            will = [SOURCE]
            for d in sorted(edges, key=lambda d: (inload[d], (edges.index(d) - f) % 3)):
                cands = [p for p in will if p != d]
                p = min(cands, key=lambda p: ((load[p] + flen) / caps[("out", p)], p == SOURCE))
                prov[(f, d)] = p; load[p] += flen; inload[d] += flen; will.append(d)
    else:
        raise ValueError(plan)
    return prov


# ----------------------------------------------------------------------------------------------- M3-v2 (2026-10-19)
# Bottleneck-constrained, uncertainty-aware re-planning. Development data: Experiment N cells 7-10 (frozen M3-v1 results,
# results/evaluation/osdi/expN/m3_root_cause.md). M3-v1 (dyn_decide) is unchanged and stays selectable (policy reuse_dyn).
# All rates and capacities inside v2 are bytes/s; the harness's caps (bit/s) are converted once at the boundary.

def bps_to_Bps(x):
    return x / 8.0


def fluid_eta(load, c_est, ingress, own):
    """Completion time of an assignment {provider: bytes} under per-provider capacities c_est {provider: bytes/s} and the
    destination's ingress capacity `ingress` (bytes/s), with max-min fair sharing (the emulated network's allocation).
    Fluid: the rates are re-solved whenever a provider finishes."""
    left = {p: float(b) for p, b in load.items() if b > 0}
    t = 0.0
    while left:
        flows = [(p, p, own) for p in left]
        caps = {("in", own): ingress}
        for p in left:
            caps[("out", p)] = max(c_est.get(p, 0.0), 1.0)
        r = maxmin(flows, caps)
        dt = min(left[p] / max(r[p], 1e-9) for p in left)
        if dt == float("inf") or dt > 1e7:
            return 1e6
        t += dt
        for p in list(left):
            left[p] -= r[p] * dt
            if left[p] <= 1e-6 * dt * max(r[p], 1.0) + 1e-3:
                del left[p]
    return t


def update_bottlenecks(state, rate, nom_out, nom_in, res, now=0.0, window=2.0, flen=None, min_frags=8):
    """See below. `rate` are the harness's window rates (bytes/s over `window`); for the attribution they are averaged
    over an estimation span long enough to hold >= `min_frags` fragments in aggregate at the current ingress estimate
    (= `window` at 1 Gbps, ~6 s at 62.5 Mbps), and differences count as evidence only above two fragments per span."""
    """Per measurement window: separate the destination's ingress capacity from per-provider capacities, using only
    the measured verified rates {provider: bytes/s} of the active providers, the nominal caps (bytes/s) and the
    measurement resolution `res` (bytes/s = one fragment per window). Rules (differences below `res` are not evidence):
      - initial estimates = nominal caps;
      - a provider whose rate is below the fair share by more than res while another provider is above the fair
        share by more than res is provider-limited: c_est[p] = rate[p];
      - if no provider is provider-limited and the aggregate is below the ingress estimate by more than res, the
        ingress is the bottleneck: I_est = aggregate (all providers dropped together);
      - upward revisions are immediate (a provider or the aggregate seen faster than its estimate);
      - a single active provider below the ingress estimate is attributed to its own egress (ambiguous; bounded cost:
        at most one re-plan that adds the source, after which the shared drop is seen and I_est is lowered)."""
    if "I_est" not in state:
        state["I_est"] = nom_in
        state["c_est"] = dict(nom_out)
    c = state["c_est"]
    flen = flen if flen is not None else res * window
    span = max(window, min_frags * flen / max(state["I_est"], 1.0))
    hist = state.setdefault("hist", [])
    hist.append((now, dict(rate)))
    while hist and hist[0][0] < now - span:
        hist.pop(0)
    sm = {p: sum(h[1].get(p, 0.0) for h in hist) / len(hist) for p in rate}   # window rates averaged over the span
    res_eff = flen / span
    margin = 2 * res_eff
    # downward revisions need a span without a transition: every window rate in the span within two raw-window
    # fragments of each other (a span that straddles a provider finishing or a flow starting is not steady); upward
    # revisions are immediate
    steady = {p: (len(hist) >= 2 and max(h[1].get(p, 0.0) for h in hist) - min(h[1].get(p, 0.0) for h in hist) <= 2 * res) for p in rate}
    # a provider that delivered nothing says nothing about the ingress: it is left out of the aggregate and the fair
    # share; if it stays at zero for two checks while others deliver, it is stalled (its fragments can move)
    pos = {p: r for p, r in sm.items() if r > 0}
    n = len(pos)
    R = sum(pos.values())
    I = state["I_est"]
    limited = []
    single = state.setdefault("single_attr", set())   # providers attributed from single-provider evidence (unconfirmed)
    withdrawn = state.setdefault("withdrawn", {})       # provider -> I_est when its single-provider attribution was withdrawn
    pr = state.pop("probe_result", None)
    if pr is not None:
        # the probe flow's own rate decides: a source that delivered much faster than the "limited" provider shows the
        # provider's own egress is the bottleneck (confirmed); a probe that only shared the provider's rate shows the
        # destination's ingress is (withdrawn: I_est = the shared aggregate, the provider is not re-probed until I_est rises)
        p = pr["provider"]
        if pr["rate"] > c.get(p, nom_out[p]) + margin:
            state.setdefault("confirmed", set()).add(p); single.discard(p)
            state["I_est"] = min(nom_in, max(I, c[p] + pr["rate"]))
        else:
            single.discard(p); c[p] = nom_out[p]
            state["I_est"] = max(min(I, sm.get(p, 0.0) + pr["rate"]), res_eff)   # the shared aggregate = the ingress
            withdrawn[p] = state["I_est"]
        I = state["I_est"]
    if n >= 2:
        share = I / n
        limited = [p for p in pos if steady[p] and pos[p] < share - margin and any(pos[o] > share + margin for o in pos if o != p)]
        for p in limited:
            single.discard(p)   # confirmed by a second provider's higher rate
        if not limited and all(steady[p] for p in pos) and R < I - margin:
            single.clear()      # all dropped together: the ingress explains it; single-provider attributions are withdrawn
    elif n == 1:
        p = next(iter(pos))
        blocked = p in withdrawn and I <= withdrawn[p] + margin   # ingress explained it; nothing has changed since
        if steady[p] and pos[p] < I - margin and not blocked:
            limited = [p]
            if p not in state.get("confirmed", set()):
                single.add(p)
    for p in list(withdrawn):
        if I > withdrawn[p] + margin:
            del withdrawn[p]   # the ingress estimate rose: the provider may be attributed (and probed) again
    stalled = [p for p in rate if sm[p] <= 0 and steady[p] and n >= 1]
    for p in rate:
        if p in limited:
            c[p] = min(nom_out[p], sm[p])
        elif p in stalled:
            c[p] = res_eff / 2
        elif sm[p] > c[p] + margin:
            c[p] = min(nom_out[p], sm[p])
    if n >= 1 and not limited and all(steady[p] for p in pos) and R < I - margin:
        state["I_est"] = max(R, res_eff)
    elif R > I + margin:
        state["I_est"] = min(nom_in, R)
    if n >= 2:
        for p in list(limited):
            state.setdefault("confirmed", set()).add(p)
    state["last_rate"] = dict(sm)
    state["res_eff"] = res_eff
    state["n_pos"] = n


def dyn_decide_v2(*, own, act, rate, state, now, held, nom_out, nom_in, flen, nodes, window, ctrl, eps, rel, probe_n=4):
    """M3-v2 re-planning decision for one session (bytes/s everywhere).

    act     active flows to `own`: dicts with src, left (set), order (list)
    rate    {provider: measured verified throughput toward `own` over the window, bytes/s}
    state   persistent per-ownership estimator state (dict; reset by the harness when the owner changes)
    nom_out {node: nominal egress capacity, bytes/s}; nom_in: own's nominal ingress capacity, bytes/s
    Returns None or {assign: {provider: [ids]} (only fragments whose provider changes), cancel: [flows whose fragments
    move], eta_cur, eta_new, eta_cur_opt, eta_new_pess, c_switch, margin, I_est, c_est, moved_from}.
    """
    update_bottlenecks(state, rate, nom_out, nom_in, flen / window, now=now, window=window, flen=flen)
    res = state["res_eff"]
    I, c = state["I_est"], state["c_est"]
    cur_prov = {}
    head = {}
    for fl in act:
        cur_prov.setdefault(fl["src"], set()).update(fl["left"])
        h = next((f for f in fl["order"] if f in fl["left"]), None)
        if h is not None:
            head.setdefault(fl["src"], set()).add(h)
    load_cur = {p: len(ids) * flen for p, ids in cur_prov.items()}
    eta_cur = fluid_eta(load_cur, c, I, own)
    # joint candidate: fragments move only away from the provider that finishes last, to the provider that would finish
    # earliest with them (by its capacity estimate), while that shortens the longest finish; in-flight heads stay. The
    # current assignment is the starting point, so nothing moves when no provider is behind (no churn).
    movable = {p: sorted(f for f in ids if f not in head.get(p, ())) for p, ids in cur_prov.items()}
    load = {p: len(ids) * flen for p, ids in cur_prov.items()}
    for p in nodes:
        load.setdefault(p, 0.0)
    cap = lambda p: max(c.get(p, nom_out[p]), 1.0)  # noqa: E731
    cand = {}
    while True:
        behind = [p for p in movable if movable[p]]
        if not behind:
            break
        q = max(behind, key=lambda p: load[p] / cap(p))
        f = movable[q][-1]
        opts = [p for p in nodes if p != own and p != q and (p == SOURCE or f in held[p])]
        if not opts:
            movable[q].pop(); continue
        best = min(opts, key=lambda p: ((load[p] + flen) / cap(p), p == SOURCE))
        if (load[best] + flen) / cap(best) < load[q] / cap(q):
            movable[q].pop(); load[q] -= flen; load[best] += flen; cand[f] = best
        else:
            break
    load_new = {p: b for p, b in load.items() if b > 0}
    eta_new = fluid_eta(load_new, c, I, own)
    moved = dict(cand)
    if not moved:
        state["last_decision"] = None
        return None
    # uncertainty: a provider attributed as the bottleneck from single-provider evidence only (the alternative, that
    # the destination's ingress itself dropped, is indistinguishable without a second provider) is probed first: at most
    # `probe_n` of its fragments move; the next checks see two providers and either confirm the attribution (the
    # aggregate rises: the rest moves) or withdraw it (both share the same aggregate: I_est drops, nothing more moves)
    if state.get("probe_pending"):
        return None   # the probe's outcome decides the next step
    single = state.get("single_attr", set())
    losing = {next(q for q, ids in cur_prov.items() if f in ids) for f in moved}
    if losing and losing <= single and len(moved) > probe_n:
        keep = sorted(moved, key=lambda f: -f)[:probe_n]
        moved = {f: moved[f] for f in keep}
        load_new = {p: b for p, b in load.items() if b > 0}
        probe = True
    else:
        probe = False
    # pessimistic gain: the current providers may be faster than measured (+res), the new ones slower (-res)
    c_opt = {p: min(nom_out.get(p, v), v + res) for p, v in c.items()}
    c_pess = {p: max(v - res, res) for p, v in c.items()}
    eta_cur_opt = fluid_eta(load_cur, c_opt, I, own)
    eta_new_pess = fluid_eta(load_new, c_pess, I, own)
    # switching cost: control delay + the in-flight fragment of every provider that loses fragments drains first
    # drain of a losing provider's in-flight fragment: at its measured rate, or at its capacity estimate when it has not
    # delivered in this window (a just re-started flow measures 0; v1 never reaches this case because it skips the check)
    drain = max((flen / max(rate.get(q, 0.0), c.get(q, 0.0), res) for q in losing), default=0.0)
    resend = len(moved) * 0  # fragments move before they are sent (heads excluded): no duplicate payload by design
    c_switch = ctrl + drain + resend
    margin = max(eps, rel * eta_cur)
    dT = eta_cur_opt - eta_new_pess
    # anti-oscillation: do not undo the previous re-plan unless a bottleneck estimate changed by more than res since
    last = state.get("last_replan")
    pairs = {(next(q for q, ids in cur_prov.items() if f in ids), p) for f, p in moved.items()}
    if last is not None and any((b, a_) in pairs for a_, b in last["pairs"]):
        changed = abs(state["I_est"] - last["I_est"]) > res or any(abs(c.get(p, 0) - last["c_est"].get(p, 0)) > res for p in set(c) | set(last["c_est"]))
        if not changed:
            return None
    if dT <= c_switch + margin:
        return None
    assign = defaultdict(list)
    for f, p in moved.items():
        assign[p].append(f)
    state["last_replan"] = {"t": now, "pairs": pairs, "I_est": state["I_est"], "c_est": dict(c)}
    return {"assign": assign, "moved_from": sorted(losing), "eta_cur": eta_cur, "eta_new": eta_new, "eta_cur_opt": eta_cur_opt, "eta_new_pess": eta_new_pess,
            "c_switch": c_switch, "margin": margin, "dT": dT, "I_est": I, "c_est": dict(c), "res": res, "probe": probe,
            "probe_provider": next(iter(losing)) if probe else None}
