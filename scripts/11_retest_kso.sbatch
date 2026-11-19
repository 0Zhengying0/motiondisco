#!/bin/bash
#SBATCH --job-name=motiondisco-kso-retest
#SBATCH --account=EU-26-37
#SBATCH --partition=qgpu
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=8
#SBATCH --time=02:00:00
#SBATCH --mail-user=zy.xu@tum.de
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --output=logs/md-kso-retest-%j.out
#SBATCH --error=logs/md-kso-retest-%j.err

set -euo pipefail

BASE=/mnt/proj1/eu-26-37/it4i-dianyu/Zhengying
ROOT="$BASE/motiondisco"
IMG="$BASE/containers/miniforge3.sif"
ENV_PREFIX="$BASE/envs/motiondisco"
PROGRAM="$ROOT/results/shinka_loco_manipulation/2026.11.16183403_ollama/gen_4/main.py"
RESULTS="$ROOT/results/diagnostics/kso_retest_$SLURM_JOB_ID/gen_4/results"

cd "$ROOT"
apptainer exec --cleanenv --bind "$BASE:$BASE" "$IMG" /bin/bash -c '
  set -euo pipefail
  export PATH="$2/bin:$PATH"
  export PYTHONNOUSERSITE=1
  export PYTHONPATH="$1${PYTHONPATH:+:$PYTHONPATH}"
  export ACADOS_SOURCE_DIR="$1/submodules/faro/extern/acados"
  export LD_LIBRARY_PATH="$ACADOS_SOURCE_DIR/lib:$2/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  if ! command -v make >/dev/null 2>&1; then
    export CONDA_PKGS_DIRS="$3"
    /opt/conda/bin/conda install --yes --freeze-installed \
      --prefix "$2" -c conda-forge make
  fi
  cd "$1"
  "$2/bin/python" - "$4" "$5" <<"PY"
import sys
from examples.loco_manipulation.evaluate import main

main(
    program_path=sys.argv[1],
    results_dir=sys.argv[2],
    scene="example_scene",
    initial_condition="default",
    score_mode="legacy",
    diversity=False,
)
PY
' _ "$ROOT" "$ENV_PREFIX" "$BASE/containers/conda_pkgs" "$PROGRAM" "$RESULTS"

echo "KSO retest completed; results: $RESULTS"
