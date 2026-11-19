#!/bin/bash
#SBATCH --job-name=motiondisco-install
#SBATCH --account=EU-26-37
#SBATCH --partition=qgpu_exp
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:30:00
#SBATCH --mail-user=zy.xu@tum.de
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --output=logs/md-install-%j.out
#SBATCH --error=logs/md-install-%j.err

set -euo pipefail

BASE=/mnt/proj1/eu-26-37/it4i-dianyu/Zhengying
ROOT="$BASE/motiondisco"
IMG="$BASE/containers/miniforge3.sif"
ENV_PREFIX="$BASE/envs/motiondisco"

cd "$ROOT"
apptainer exec --cleanenv --bind "$BASE:$BASE" "$IMG" /bin/bash -c '
  set -euo pipefail
  export PATH="$2/bin:$PATH"
  export PYTHONNOUSERSITE=1
  cd "$1"
  "$2/bin/python" -m pip install -e .
  "$2/bin/python" -c "import shinka; print(\"MotionDisco installed:\", shinka.__file__)"
  test -x "$2/bin/motiondisco_launch"
' _ "$ROOT" "$ENV_PREFIX"

echo "MotionDisco installation completed successfully"
