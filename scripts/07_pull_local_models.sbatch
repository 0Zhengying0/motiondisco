#!/bin/bash
#SBATCH --job-name=motiondisco-models
#SBATCH --account=EU-26-37
#SBATCH --partition=qgpu_exp
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:45:00
#SBATCH --mail-user=zy.xu@tum.de
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --output=logs/md-models-%j.out
#SBATCH --error=logs/md-models-%j.err

set -euo pipefail

BASE=/mnt/proj1/eu-26-37/it4i-dianyu/Zhengying
OLLAMA="$BASE/tools/ollama/bin/ollama"
export OLLAMA_MODELS="$BASE/models/ollama"
export OLLAMA_HOST="127.0.0.1:$((20000 + SLURM_JOB_ID % 30000))"
mkdir -p "$OLLAMA_MODELS"

"$OLLAMA" serve > "logs/md-models-server-$SLURM_JOB_ID.log" 2>&1 &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true' EXIT

for attempt in $(seq 1 60); do
  if curl -fsS "http://$OLLAMA_HOST/api/tags" >/dev/null; then
    break
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "Ollama server exited; see server log" >&2
    exit 1
  fi
  sleep 2
done
curl -fsS "http://$OLLAMA_HOST/api/tags" >/dev/null

"$OLLAMA" pull qwen2.5-coder:14b
"$OLLAMA" pull qwen2.5-coder:7b
"$OLLAMA" pull embeddinggemma
"$OLLAMA" list

echo "Local models downloaded successfully to $OLLAMA_MODELS"
