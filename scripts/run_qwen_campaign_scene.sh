#!/bin/bash
set -euo pipefail

scene=$1
nodes=$2
description=$3
array_job=$4
array_index=$5
if [[ -n "${6:-}" ]]; then
  export MOTIONDISCO_PERFORMANCE=1
  export MOTIONDISCO_SEED=$6
  export MOTIONDISCO_SEED_SOURCE=${7:-MOTIONDISCO_SEED}
  export MOTIONDISCO_OLLAMA_SEED=1
  export MOTIONDISCO_JOB_ID="${array_job}_${array_index}"
  export PYTHONHASHSEED="$MOTIONDISCO_SEED"
fi

BASE=/mnt/proj1/eu-26-37/it4i-dianyu/Zhengying
ROOT="$BASE/motiondisco"
ENV_PREFIX="$BASE/envs/motiondisco"
export PATH="$ENV_PREFIX/bin:$PATH"
export PYTHONNOUSERSITE=1
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export SHINKA_PRICING_MODE=offline
export SHINKA_IK_MAX_NUM_NODES=50
export SHINKA_TO_N_JOB=1
export ACADOS_SOURCE_DIR="$ROOT/submodules/faro/extern/acados"
export LD_LIBRARY_PATH="$ACADOS_SOURCE_DIR/lib:$ENV_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

scene_tag=${scene##*.}
exp_name="md_qwen_campaign/$scene_tag"
run_name="job_${array_job}_${array_index}"
cd "$ROOT"
"$ENV_PREFIX/bin/motiondisco_launch" \
  task=loco_manipulation variant=ollama_local \
  database=island_small evolution=small_budget cluster=local \
  "task.scene=$scene" \
  "task.description=\"$description\"" \
  task.score_mode=legacy \
  "evo_config.num_generations=$nodes" \
  evo_config.max_api_costs=100 \
  ++evo_config.max_novelty_attempts=6 \
  ++evo_config.evolve_prompts=false \
  ++evo_config.meta_rec_interval=null \
  max_evaluation_jobs=1 max_proposal_jobs=1 \
  "exp_name=$exp_name" "run_name=$run_name"
