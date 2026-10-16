#!/bin/bash
# D0 hardware audit (read-only: no installs, no driver changes). Run on elves-01; it audits itself and, over ssh,
# elves-02..04, writing results/evaluation/osdi/d0/hw_audit/<host>.txt.
#   REMOTE_USER=ckim151 REMOTE_REPO=StreamDiffusionV2 tools/eval/hw_audit.sh
set -uo pipefail
ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"; cd "$ROOT_DIR"
U="${REMOTE_USER:-ckim151}"; R="${REMOTE_REPO:-StreamDiffusionV2}"; OUT=results/evaluation/osdi/d0/hw_audit; mkdir -p "$OUT"
read -r -d '' PROBE <<'PRB'
cd ~/REPO 2>/dev/null || cd .
echo "## host"; hostname; uname -r; date -Is
echo "## gpus"; nvidia-smi --query-gpu=index,name,uuid,memory.total,memory.used,utilization.gpu,driver_version,persistence_mode --format=csv
echo "## gpu processes (any user)"; nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_memory --format=csv
echo "## driver"; cat /proc/driver/nvidia/version 2>/dev/null | head -2
echo "## cuda toolkit"; (command -v nvcc && nvcc --version | tail -2) || echo "nvcc: not on PATH"
echo "## python / torch (repo venv if present)"; PYB=.venv/bin/python; [ -x "$PYB" ] || PYB=python3
"$PYB" -c "import sys,torch;print('python',sys.version.split()[0]);print('torch',torch.__version__,'cuda',torch.version.cuda,'cudnn',torch.backends.cudnn.version());print('devices',[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())])" 2>&1 | tail -4
echo "## network interfaces (MTU, state, speed)"; for i in $(ls /sys/class/net | grep -v lo); do printf "%s mtu=%s state=%s speed=%s Mb/s\n" "$i" "$(cat /sys/class/net/$i/mtu)" "$(cat /sys/class/net/$i/operstate)" "$(cat /sys/class/net/$i/speed 2>/dev/null || echo ?)"; done
echo "## addresses"; ip -4 -o addr show | awk '{print $2, $4}'
echo "## disk"; df -h . /tmp 2>/dev/null
echo "## memory"; free -g | head -2
echo "## criu / cuda-checkpoint"; (command -v criu && criu --version) || echo "criu: not installed"; (command -v cuda-checkpoint && cuda-checkpoint --help 2>&1 | head -3) || echo "cuda-checkpoint: not on PATH"
echo "## privileges (non-interactive check)"; (sudo -n true 2>/dev/null && echo "sudo: passwordless") || echo "sudo: not available without a password"; id
echo "## load"; uptime
PRB
PROBE="${PROBE//REPO/$R}"
bash -c "$PROBE" > "$OUT/$(hostname -s).txt" 2>&1; echo "wrote $OUT/$(hostname -s).txt"
for h in elves-02 elves-03 elves-04; do
  ssh -o BatchMode=yes -o ConnectTimeout=10 "$U@$h.be.ucsc.edu" "bash -s" <<< "$PROBE" > "$OUT/$h.txt" 2>&1 && echo "wrote $OUT/$h.txt" || echo "ssh to $h failed (see $OUT/$h.txt)"
done
