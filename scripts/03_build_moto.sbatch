#!/bin/bash
#SBATCH --job-name=motiondisco-moto
#SBATCH --account=EU-26-37
#SBATCH --partition=qgpu_exp
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --time=01:00:00
#SBATCH --mail-user=zy.xu@tum.de
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --output=logs/md-moto-%j.out
#SBATCH --error=logs/md-moto-%j.err

set -euo pipefail

BASE=/mnt/proj1/eu-26-37/it4i-dianyu/Zhengying
ROOT="$BASE/motiondisco"
IMG="$BASE/containers/miniforge3.sif"
ENV_PREFIX="$BASE/envs/motiondisco"

cd "$ROOT"
apptainer exec --cleanenv --bind "$BASE:$BASE" "$IMG" /bin/bash -c '
  set -euo pipefail
  export PATH="$2/bin:$PATH"
  export LD_LIBRARY_PATH="$1/submodules/faro/extern/acados/lib:$2/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  cd "$1/submodules/faro/extern/moto"
  cmake -S . -B build-karolina -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER="$2/bin/x86_64-conda-linux-gnu-gcc" \
    -DCMAKE_CXX_COMPILER="$2/bin/x86_64-conda-linux-gnu-g++" \
    -DCMAKE_INSTALL_PREFIX="$2" \
    -DCMAKE_PREFIX_PATH="$2" \
    -DPython_EXECUTABLE="$2/bin/python" \
    -DCMAKE_INSTALL_RPATH="$2/lib" \
    -DCMAKE_BUILD_WITH_INSTALL_RPATH=OFF \
    -DWITH_NATIVE_OPT=ON
  cmake --build build-karolina -j4
  cmake --install build-karolina
  "$2/bin/python" -c "import moto; print(\"Moto installed:\", moto.__file__)"
' _ "$ROOT" "$ENV_PREFIX"

echo "Moto build and installation completed successfully"
