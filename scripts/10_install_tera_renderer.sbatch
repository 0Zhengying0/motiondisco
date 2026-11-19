#!/bin/bash
#SBATCH --job-name=motiondisco-tera
#SBATCH --account=EU-26-37
#SBATCH --partition=qgpu_exp
#SBATCH --gpus=1
#SBATCH --time=00:15:00
#SBATCH --mail-user=zy.xu@tum.de
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --output=logs/md-tera-%j.out
#SBATCH --error=logs/md-tera-%j.err

set -euo pipefail

ACADOS=/mnt/proj1/eu-26-37/it4i-dianyu/Zhengying/motiondisco/submodules/faro/extern/acados
TARGET="$ACADOS/bin/t_renderer"
URL=https://github.com/acados/tera_renderer/releases/download/v0.2.0/t_renderer-v0.2.0-linux-amd64

mkdir -p "$ACADOS/bin"
if [ ! -s "$TARGET" ]; then
  curl -fL --retry 3 -o "$TARGET.tmp" "$URL"
  chmod 755 "$TARGET.tmp"
  mv "$TARGET.tmp" "$TARGET"
fi
test -x "$TARGET"
BASE=/mnt/proj1/eu-26-37/it4i-dianyu/Zhengying
apptainer exec --cleanenv --bind "$BASE:$BASE" \
  "$BASE/containers/miniforge3.sif" "$TARGET" --version
echo "Acados Tera renderer installed successfully: $TARGET"
