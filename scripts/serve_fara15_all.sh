#!/usr/bin/env bash
# Serve N independent Fara1.5 replicas, one per GPU, for high-throughput /
# concurrent evaluation. Replica i runs on GPU i and listens on port BASE+i.
#
# Run this from the dedicated vLLM serving environment (see serve_fara15.sh /
# harness README). It launches the replicas in the background (nohup), waits
# until every /v1/models endpoint is ready, records PIDs, and prints how to stop
# them. The replicas keep running after this script returns.
#
# Usage:
#   scripts/serve_fara15_all.sh [count] [size] [base_port]
# Examples:
#   scripts/serve_fara15_all.sh                 # 4x Fara1.5-9B on GPUs 0-3, ports 5002-5005
#   scripts/serve_fara15_all.sh 4 9b 5002
#   VLLM_ENFORCE_EAGER=1 scripts/serve_fara15_all.sh 4 9b   # fast startup
#
# Stop them later with:  kill $(cat logs/fara15_servers.pids)
set -euo pipefail

COUNT="${1:-4}"
SIZE="${2:-9b}"
BASE_PORT="${3:-5002}"

case "${SIZE,,}" in
  4b) TAG="4B" ;; 9b) TAG="9B" ;; 27b) TAG="27B" ;;
  *) echo "Unknown size '$SIZE' (expected 4b|9b|27b)" >&2; exit 1 ;;
esac
MODEL="microsoft/Fara1.5-${TAG}"
SERVED_NAME="Fara1.5-${TAG}"

if ! command -v vllm >/dev/null 2>&1; then
  echo "ERROR: 'vllm' not found. Activate the serving env first, e.g.:" >&2
  echo '  source ~/.venvs/fara-serve/bin/activate' >&2
  echo '  pip install "fara[vllm] @ git+https://github.com/microsoft/fara.git"' >&2
  exit 127
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$REPO_ROOT/logs"
mkdir -p "$LOG_DIR"
PID_FILE="$LOG_DIR/fara15_servers.pids"
: > "$PID_FILE"

EAGER_FLAG=()
if [[ "${VLLM_ENFORCE_EAGER:-0}" == "1" ]]; then
  EAGER_FLAG=(--enforce-eager)
fi

echo "Launching ${COUNT}x ${MODEL} (served as '${SERVED_NAME}'), one per GPU..."
declare -a PORTS=()
for ((i = 0; i < COUNT; i++)); do
  PORT=$((BASE_PORT + i))
  PORTS+=("$PORT")
  LOG="$LOG_DIR/fara15_gpu${i}.log"
  echo "  GPU ${i} -> port ${PORT}  (log: ${LOG})"
  CUDA_VISIBLE_DEVICES="$i" nohup vllm serve "$MODEL" \
    --served-model-name "$SERVED_NAME" \
    --port "$PORT" \
    --dtype auto \
    --tensor-parallel-size 1 \
    --max-model-len 20000 \
    "${EAGER_FLAG[@]}" \
    > "$LOG" 2>&1 &
  echo "$!" >> "$PID_FILE"
done

echo ""
echo "Waiting for all ${COUNT} replicas to become ready (this can take several minutes"
echo "on a cold start while vision-tower kernels compile)..."
DEADLINE=$(( $(date +%s) + 1200 ))
for PORT in "${PORTS[@]}"; do
  until curl -s --max-time 3 "http://localhost:${PORT}/v1/models" >/dev/null 2>&1; do
    if (( $(date +%s) > DEADLINE )); then
      echo "TIMEOUT waiting for port ${PORT}. Check logs in ${LOG_DIR}." >&2
      exit 1
    fi
    sleep 5
  done
  echo "  ready: http://localhost:${PORT}/v1/"
done

echo ""
echo "All ${COUNT} replicas ready. Endpoints:"
FARA_URLS=""
for PORT in "${PORTS[@]}"; do
  FARA_URLS+="http://localhost:${PORT}/v1/,"
done
FARA_URLS="${FARA_URLS%,}"
echo "  ${FARA_URLS}"
echo ""
echo "PIDs: $(cat "$PID_FILE" | tr '\n' ' ')"
echo "Stop all:  kill \$(cat ${PID_FILE})"
echo ""
echo "Use with the batch runner (from the harness[fara] env):"
echo "  python -m harness.eval.batch --agent fara15 --env echostay --agent-base-urls ${FARA_URLS} ..."
