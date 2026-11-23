#!/bin/bash
#SBATCH --job-name=md-qwen-generate
#SBATCH --account=EU-26-37
#SBATCH --partition=qgpu
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=01:45:00
#SBATCH --mail-user=zy.xu@tum.de
#SBATCH --mail-type=BEGIN,END,FAIL,TIME_LIMIT_80
#SBATCH --output=results/md-qwen-generate-%j.out
#SBATCH --error=results/md-qwen-generate-%j.err

set -euo pipefail

ROOT="${SLURM_SUBMIT_DIR:-$PWD}"
BASE=$(dirname "$ROOT")
cd "$ROOT"
export OLLAMA_MODELS="$BASE/models/ollama"
export OLLAMA_HOST=127.0.0.1:11434
export OLLAMA_MAX_LOADED_MODELS=1

job_id=$SLURM_JOB_ID
recorder="$ROOT/scripts/karolina_performance.py"
job_events="$ROOT/results/md-qwen-generate-$job_id.performance.jsonl"
gpu_events="$ROOT/results/md-qwen-generate-$job_id.gpu.jsonl"
server_pid=
sampler_pid=
launcher_pid=
cleanup() {
    local exit_code=$?
    trap - EXIT
    for pid in "$launcher_pid" "$server_pid" "$sampler_pid"; do
        if [[ -n "$pid" ]]; then
            kill "$pid" 2>/dev/null || true
        fi
    done
    if [[ -n "$sampler_pid" ]]; then
        wait "$sampler_pid" 2>/dev/null || true
    fi
    python3 "$recorder" end "$job_events" "$job_id" "$exit_code" || true
    exit "$exit_code"
}
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
motiondisco_commit=$(git rev-parse HEAD) || motiondisco_commit=unknown
faro_commit=$(git -C submodules/faro rev-parse HEAD) || faro_commit=unknown
seed=${MOTIONDISCO_SEED:-}
seed_source=MOTIONDISCO_SEED
if [[ -z "$seed" ]]; then
    seed=$(python3 "$recorder" seed)
    seed_source=system_entropy
fi
if [[ ! "$seed" =~ ^(0|[1-9][0-9]{0,9})$ ]] || (( seed >= 2147483648 )); then
    echo "MOTIONDISCO_SEED must be an integer in [0, 2147483647]" >&2
    exit 2
fi
python3 "$recorder" start-generated "$job_events" "$job_id" "$motiondisco_commit" "$faro_commit" \
    "$seed" "$seed_source" || true
python3 "$recorder" sample "$gpu_events" "$job_id" --interval 5 &
sampler_pid=$!

"$BASE/tools/ollama/bin/ollama" serve > "results/md-qwen-generate-server-$job_id.log" 2>&1 &
server_pid=$!

for attempt in $(seq 1 60); do
    if curl -fsS "http://$OLLAMA_HOST/api/tags" >/dev/null 2>&1; then
        break
    fi
    kill -0 "$server_pid"
    sleep 2
done
kill -0 "$server_pid"
tags=$(curl -fsS --max-time 5 "http://$OLLAMA_HOST/api/tags")
python3 "$recorder" models "$job_events" "$job_id" <<< "$tags" || true

apptainer exec --cleanenv --bind "$BASE:$BASE" \
    "$BASE/containers/miniforge3.sif" /bin/bash -c '
    set -euo pipefail
    root=$1
    prefix=$2
    export MOTIONDISCO_JOB_ID=$3 MOTIONDISCO_PERFORMANCE=1
    export MOTIONDISCO_SEED=$4 MOTIONDISCO_SEED_SOURCE=$5 PYTHONHASHSEED=$4 MOTIONDISCO_OLLAMA_SEED=1
    shift 5
    cd "$root"
    export PATH="$prefix/bin:$PATH" PYTHONPATH="$root" PYTHONNOUSERSITE=1
    export SHINKA_PRICING_MODE=offline SHINKA_IK_MAX_NUM_NODES=50 SHINKA_TO_N_JOB=1
    export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 MAKEFLAGS=-j4
    export ACADOS_SOURCE_DIR="$root/submodules/faro/extern/acados"
    export LD_LIBRARY_PATH="$ACADOS_SOURCE_DIR/lib:$prefix/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    exec "$prefix/bin/python" -m examples.loco_manipulation.scene_generation generate "$@"
' _ "$ROOT" "$BASE/envs/motiondisco" "$job_id" "$seed" "$seed_source" "$@" &
launcher_pid=$!
wait "$launcher_pid"
launcher_pid=
