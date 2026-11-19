#!/bin/bash
#SBATCH --job-name=motiondisco-first-search
#SBATCH --account=EU-26-37
#SBATCH --partition=qgpu
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=8
#SBATCH --time=03:00:00
#SBATCH --mail-user=zy.xu@tum.de
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --output=logs/md-search-%j.out
#SBATCH --error=logs/md-search-%j.err

set -euo pipefail

BASE=/mnt/proj1/eu-26-37/it4i-dianyu/Zhengying
ROOT="$BASE/motiondisco"
export OLLAMA_MODELS="$BASE/models/ollama"
export OLLAMA_HOST=127.0.0.1:11434

cd "$ROOT"
"$BASE/tools/ollama/bin/ollama" serve > "logs/md-search-server-$SLURM_JOB_ID.log" 2>&1 &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true' EXIT

for attempt in $(seq 1 60); do
  if curl -fsS "http://$OLLAMA_HOST/api/tags" >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "Ollama server exited; see server log" >&2
    exit 1
  fi
  sleep 2
done
curl -fsS "http://$OLLAMA_HOST/api/tags" >/dev/null

apptainer exec --cleanenv --bind "$BASE:$BASE" \
  "$BASE/containers/miniforge3.sif" /bin/bash -c '
    set -euo pipefail
    export PATH="$2/bin:$PATH"
    export PYTHONNOUSERSITE=1
    export PYTHONPATH="$1${PYTHONPATH:+:$PYTHONPATH}"
    export SHINKA_PRICING_MODE=offline
    export ACADOS_SOURCE_DIR="$1/submodules/faro/extern/acados"
    export LD_LIBRARY_PATH="$ACADOS_SOURCE_DIR/lib:$2/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    cd "$1"
    "$2/bin/motiondisco_launch" \
      task=loco_manipulation variant=ollama_local cluster=local \
      task.scene=example_scene \
      evo_config.num_generations=10 \
      evo_config.max_api_costs=100 \
      max_evaluation_jobs=1 max_proposal_jobs=1
  ' _ "$ROOT" "$BASE/envs/motiondisco"

echo "First MotionDisco search completed successfully"
