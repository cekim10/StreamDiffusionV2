#!/usr/bin/env python3
"""Pull result directories from another host through its agent (text files only) so that a single host
commits everything. Skips files that already exist locally with the same size unless --overwrite.

    python tools/eval/pull_results.py --from B --path results/evaluation/single_handoff
    python tools/eval/pull_results.py --from B --path results/evaluation/single_handoff --dest results/evaluation/single_handoff
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agents import connect_all, parse_hosts  # noqa: E402
from common import REPO_ROOT  # noqa: E402

TEXT_SUFFIXES = {".csv", ".json", ".txt", ".log", ".md"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="src", type=str, required=True, help="agent label, e.g. B")
    ap.add_argument("--path", type=str, required=True, help="directory relative to the remote repo root")
    ap.add_argument("--dest", type=str, default=None, help="local directory (default: same relative path)")
    ap.add_argument("--host_map", type=str, default=None)
    ap.add_argument("--overwrite", action="store_true")
    a = ap.parse_args()
    agent = connect_all(parse_hosts(a.host_map), [a.src])[a.src]
    dest = REPO_ROOT / (a.dest or a.path)
    paths = agent.glob(f"{a.path}/**/*")
    n_new = n_skip = 0
    for rel in paths:
        if Path(rel).suffix.lower() not in TEXT_SUFFIXES:
            continue
        local = dest / Path(rel).relative_to(a.path)
        if local.exists() and not a.overwrite:
            n_skip += 1; continue
        try:
            text = agent.read(rel)
        except Exception as exc:  # noqa: BLE001
            print(f"[pull] skip {rel}: {exc}"); continue
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(text); n_new += 1
    print(f"[pull] {a.src}:{a.path} -> {dest}: {n_new} files written, {n_skip} already present")


if __name__ == "__main__":
    main()
