#!/bin/bash
#SBATCH --job-name=motiondisco-faro
#SBATCH --account=EU-26-37
#SBATCH --partition=qgpu_exp
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:30:00
#SBATCH --mail-user=zy.xu@tum.de
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --output=logs/md-faro-%j.out
#SBATCH --error=logs/md-faro-%j.err

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
  export ACADOS_SOURCE_DIR="$1/submodules/faro/extern/acados"
  export LD_LIBRARY_PATH="$ACADOS_SOURCE_DIR/lib:$2/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  cd "$1/submodules/faro"
  "$2/bin/python" -m pip install -e .
  "$2/bin/python" - <<"PY"
import moto
from faro.tasks.ik_task import IkTask
from faro.tasks.to_task import ToTask
from scenes.common.registry import make_scene_with_state

required = ("stage", "casadi_manifold", "codegen_context")
missing = [name for name in required if not hasattr(moto, name)]
assert not missing, f"Moto is missing {missing}"
scene, state = make_scene_with_state("example_scene", "default")
print(f"FARO check passed: {scene.name}, {len(state.robots)} robot(s)")
PY
' _ "$ROOT" "$ENV_PREFIX"

echo "FARO installation and basic check completed successfully"
