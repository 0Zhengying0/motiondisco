#!/bin/bash
#SBATCH --job-name=motiondisco-env
#SBATCH --account=EU-26-37
#SBATCH --partition=qgpu_exp
#SBATCH --gpus=1
#SBATCH --time=00:45:00
#SBATCH --mail-user=zy.xu@tum.de
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --output=logs/md-env-%j.out
#SBATCH --error=logs/md-env-%j.err

set -euo pipefail

BASE=/mnt/proj1/eu-26-37/it4i-dianyu/Zhengying
ROOT="$BASE/motiondisco"
IMG="$BASE/containers/miniforge3.sif"
ENV_PREFIX="$BASE/envs/motiondisco"
PKGS="$BASE/containers/conda_pkgs"

mkdir -p "$BASE/envs" "$PKGS"
cd "$ROOT"

echo "Node: $(hostname)"
echo "Job: $SLURM_JOB_ID"

apptainer exec --cleanenv \
  --bind "$BASE:$BASE" \
  "$IMG" \
  /bin/bash -c '
    set -e
    export CONDA_PKGS_DIRS="$1"
    /opt/conda/bin/conda create \
      --yes \
      --prefix "$2" \
      --file "$3"
  ' _ \
  "$PKGS" \
  "$ENV_PREFIX" \
  "$ROOT/submodules/faro/conda-linux-64.lock"

apptainer exec --cleanenv \
  --bind "$BASE:$BASE" \
  "$IMG" \
  "$ENV_PREFIX/bin/python" --version

echo "Environment created successfully"
