#!/usr/bin/env bash
# Serve a released Fara1.5 model (4B / 9B / 27B) with vLLM for the Echoverse
# Fara1.5 reference agent (`python -m harness.run_agent --agent fara15`).
#
# The reference agent talks to this endpoint over an OpenAI-compatible API. The
# served model name must match the agent's `--agent-model` (or the FARA_MODEL env
# var; default Fara1.5-9B) and the port must match `--agent-base-url` (or the
# FARA_BASE_URL env var; default http://localhost:5002/v1/).
#
# Requires vLLM in THIS environment (kept separate from the harness):
#   pip install "fara[vllm] @ git+https://github.com/microsoft/fara.git"
# (installs vllm==0.19.1, transformers>=5.2.0, nvidia-cutlass-dsl==4.5.2).
#
# Model weights (public, ungated on Hugging Face) are fetched automatically on
# first launch into the HF cache (~/.cache/huggingface, override with HF_HOME).
# Sizes: 4B ~8 GB, 9B ~18 GB, 27B ~54 GB (bf16). To use pre-downloaded weights,
# pass a local directory as the 5th argument (see MODEL_PATH below).
#
# Usage:
#   scripts/serve_fara15.sh <4b|9b|27b> [port] [gpus] [tp] [model_path]
# Examples:
#   CUDA_VISIBLE_DEVICES=0 scripts/serve_fara15.sh 9b            # 1 GPU, port 5002
#   scripts/serve_fara15.sh 27b 5002 0,1 2                       # tensor-parallel 2 on NVLink pair 0,1
#   scripts/serve_fara15.sh 9b 5002 0 1 ./models/Fara1.5-9B      # serve pre-downloaded weights
#
# Tip: set VLLM_ENFORCE_EAGER=1 to skip torch.compile/CUDA-graph capture for a
# much faster (~1 min) startup — ideal for smoke tests, small runtime cost.
set -euo pipefail

SIZE="${1:?usage: serve_fara15.sh <4b|9b|27b> [port] [gpus] [tp] [model_path]}"
PORT="${2:-5002}"
GPUS="${3:-}"
TP="${4:-}"
MODEL_PATH="${5:-}"

case "${SIZE,,}" in
  4b)  TAG="4B"  ; DEFAULT_TP=1 ;;
  9b)  TAG="9B"  ; DEFAULT_TP=1 ;;
  27b) TAG="27B" ; DEFAULT_TP=2 ;;   # 27B: default to NVLink-pair tensor parallelism
  *) echo "Unknown size '$SIZE' (expected 4b|9b|27b)" >&2; exit 1 ;;
esac
TP="${TP:-$DEFAULT_TP}"

# Serve a pre-downloaded local directory if given, else the HF repo id (vLLM
# downloads it on first launch). The served name is always Fara1.5-<SIZE>.
MODEL="${MODEL_PATH:-microsoft/Fara1.5-${TAG}}"
SERVED_NAME="Fara1.5-${TAG}"

if [[ -n "$GPUS" ]]; then
  export CUDA_VISIBLE_DEVICES="$GPUS"
fi

EAGER_FLAG=()
if [[ "${VLLM_ENFORCE_EAGER:-0}" == "1" ]]; then
  EAGER_FLAG=(--enforce-eager)
fi

# Preflight: vLLM must be installed in the ACTIVE environment. It is kept
# separate from the harness (the harness[fara] extra does not include vLLM).
if ! command -v vllm >/dev/null 2>&1; then
  cat >&2 <<'MSG'
ERROR: 'vllm' was not found in the active environment.

vLLM is NOT part of the harness install; serve the model from a dedicated env.
Create it once (Python >= 3.11) and activate it before running this script:

  python3.12 -m venv ~/.venvs/fara-serve      # or: uv venv --python 3.12 ~/.venvs/fara-serve
  source ~/.venvs/fara-serve/bin/activate
  pip install "fara[vllm] @ git+https://github.com/microsoft/fara.git"

Then re-run this script from that activated environment. See harness/README.md
("Run with Fara1.5" -> "Serve the model") for details.
MSG
  exit 127
fi

echo "Serving ${MODEL} as '${SERVED_NAME}' on port ${PORT}" \
     "(tp=${TP}, CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-all}${EAGER_FLAG:+, eager})"
exec vllm serve "${MODEL}" \
  --served-model-name "${SERVED_NAME}" \
  --port "${PORT}" \
  --dtype auto \
  --tensor-parallel-size "${TP}" \
  --max-model-len 20000 \
  "${EAGER_FLAG[@]}"
