#!/bin/bash
#SBATCH --job-name=md-object-catalog
#SBATCH --account=EU-26-37
#SBATCH --partition=qcpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --output=logs/md-object-catalog-%j.out
#SBATCH --error=logs/md-object-catalog-%j.err

set -euo pipefail

ROOT="${SLURM_SUBMIT_DIR:-$PWD}"
PYTHON="$ROOT/../envs/motiondisco/bin/python"
cd "$ROOT"
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
exec "$PYTHON" "$ROOT/scripts/export_object_catalog.py" "$@"
