#!/bin/bash
# D0 external-baseline readiness (read-only): reports, for each host, what NVIDIA cuda-checkpoint + CRIU would need.
# It installs nothing, downloads nothing and changes no driver. Run on elves-01 (it ssh-es to elves-02..04).
# Output: results/evaluation/osdi/d0/cr_readiness/<host>.txt
set -uo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"; cd "$ROOT_DIR"
U="${REMOTE_USER:-ckim151}"; OUT=results/evaluation/osdi/d0/cr_readiness; mkdir -p "$OUT"
read -r -d '' PROBE <<'PRB'
echo "## host"; hostname; uname -r
echo "## driver (cuda-checkpoint: >= 550 for checkpoint/restore; GPU migration API needs >= 580)"; nvidia-smi --query-gpu=index,name,driver_version,persistence_mode --format=csv,noheader
echo "## criu"; (command -v criu && criu --version && criu check 2>&1 | tail -3) || echo "criu: not installed"
echo "## cuda-checkpoint"; (command -v cuda-checkpoint && cuda-checkpoint --help 2>&1 | head -5) || echo "cuda-checkpoint: not on PATH"
echo "## CRIU CUDA plugin"; ls /usr/lib/criu/cuda_plugin.so /usr/local/lib/criu/cuda_plugin.so 2>/dev/null || echo "cuda_plugin.so: not found in default plugin dirs"
echo "## privileges"; (sudo -n true 2>/dev/null && echo "sudo: passwordless") || echo "sudo: not available without a password"
echo "## capabilities of this user"; grep CapEff /proc/self/status
echo "## kernel features CRIU needs"; for f in /proc/sys/kernel/ns_last_pid /proc/sys/kernel/yama/ptrace_scope; do printf "%s = %s\n" "$f" "$(cat $f 2>/dev/null || echo n/a)"; done
PRB
bash -c "$PROBE" > "$OUT/$(hostname -s).txt" 2>&1; echo "wrote $OUT/$(hostname -s).txt"
for h in elves-02 elves-03 elves-04; do
  ssh -o BatchMode=yes -o ConnectTimeout=10 "$U@$h.be.ucsc.edu" "bash -s" <<< "$PROBE" > "$OUT/$h.txt" 2>&1 && echo "wrote $OUT/$h.txt" || echo "ssh to $h failed"
done
