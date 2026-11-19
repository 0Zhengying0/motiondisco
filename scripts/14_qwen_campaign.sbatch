#!/bin/bash
#SBATCH --job-name=md-qwen-campaign
#SBATCH --account=EU-26-37
#SBATCH --partition=qgpu
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=8
#SBATCH --time=12:00:00
#SBATCH --array=0-8%1
#SBATCH --mail-user=zy.xu@tum.de
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --output=logs/md-campaign-%A_%a.out
#SBATCH --error=logs/md-campaign-%A_%a.err

set -euo pipefail

BASE=/mnt/proj1/eu-26-37/it4i-dianyu/Zhengying
ROOT="$BASE/motiondisco"
TABLE="$ROOT/scripts/qwen_campaign.tsv"
line=$(sed -n "$((SLURM_ARRAY_TASK_ID + 2))p" "$TABLE")
if [ -z "$line" ]; then
  echo "No scene for array index $SLURM_ARRAY_TASK_ID" >&2
  exit 2
fi
IFS=$'\t' read -r scene nodes description <<< "$line"
test -n "$scene" && test -n "$nodes" && test -n "$description"

export OLLAMA_MODELS="$BASE/models/ollama"
export OLLAMA_HOST=127.0.0.1:11434
export OLLAMA_MAX_LOADED_MODELS=1
cd "$ROOT"
"$BASE/tools/ollama/bin/ollama" serve > "logs/md-campaign-server-${SLURM_JOB_ID}.log" 2>&1 &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true' EXIT

for attempt in $(seq 1 60); do
  if curl -fsS "http://$OLLAMA_HOST/api/tags" >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "Ollama server exited; see its log" >&2
    exit 1
  fi
  sleep 2
done
kill -0 "$server_pid"
curl -fsS "http://$OLLAMA_HOST/api/tags" >/dev/null
model_list=$("$BASE/tools/ollama/bin/ollama" list)
for expected in \
  'qwen2.5-coder:14b 9ec8897f747e' \
  'qwen2.5-coder:7b dae161e27b0e' \
  'embeddinggemma:latest 85462619ee72'; do
  read -r model model_id <<< "$expected"
  if ! awk -v model="$model" -v model_id="$model_id" \
      '$1 == model && $2 == model_id {found = 1} END {exit !found}' \
      <<< "$model_list"; then
    echo "Missing expected model: $expected" >&2
    exit 1
  fi
done

echo "Scene: $scene | nodes: $nodes | array: ${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}"
echo "MotionDisco commit: $(git rev-parse HEAD)"
echo "FARO commit: $(git -C submodules/faro rev-parse HEAD)"
echo "$model_list"

apptainer exec --cleanenv --bind "$BASE:$BASE" \
  "$BASE/containers/miniforge3.sif" /bin/bash \
  "$ROOT/scripts/run_qwen_campaign_scene.sh" \
  "$scene" "$nodes" "$description" \
  "$SLURM_ARRAY_JOB_ID" "$SLURM_ARRAY_TASK_ID"

echo "Campaign scene completed: $scene"
