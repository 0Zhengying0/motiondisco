#!/bin/bash
#SBATCH --job-name=motiondisco-acados
#SBATCH --account=EU-26-37
#SBATCH --partition=qgpu_exp
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --time=01:00:00
#SBATCH --mail-user=zy.xu@tum.de
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --output=logs/md-acados-%j.out
#SBATCH --error=logs/md-acados-%j.err

set -euo pipefail

BASE=/mnt/proj1/eu-26-37/it4i-dianyu/Zhengying
ROOT="$BASE/motiondisco"
IMG="$BASE/containers/miniforge3.sif"
ENV_PREFIX="$BASE/envs/motiondisco"

cd "$ROOT"
apptainer exec --cleanenv --bind "$BASE:$BASE" "$IMG" /bin/bash -c '
  set -euo pipefail
  export PATH="$2/bin:$PATH"
  export ACADOS_SOURCE_DIR="$1/submodules/faro/extern/acados"
  export LD_LIBRARY_PATH="$ACADOS_SOURCE_DIR/lib:$2/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  cd "$ACADOS_SOURCE_DIR"
  cmake -S . -B build-karolina -G Ninja \
    -DCMAKE_C_COMPILER="$2/bin/x86_64-conda-linux-gnu-gcc" \
    -DCMAKE_CXX_COMPILER="$2/bin/x86_64-conda-linux-gnu-g++" \
    -DBLASFEO_TARGET=X64_AUTOMATIC \
    -DHPIPM_TARGET=AVX \
    -DACADOS_WITH_OPENMP=ON \
    -DACADOS_NUM_THREADS=10
  cmake --build build-karolina --target install -j4
  "$2/bin/python" -m pip install "$ACADOS_SOURCE_DIR/interfaces/acados_template"
  "$2/bin/python" -c "import acados_template; print(\"Acados Python package installed\")"
' _ "$ROOT" "$ENV_PREFIX"

echo "Acados build and Python installation completed successfully"
