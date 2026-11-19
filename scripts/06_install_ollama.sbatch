#!/bin/bash
#SBATCH --job-name=motiondisco-ollama-install
#SBATCH --account=EU-26-37
#SBATCH --partition=qgpu_exp
#SBATCH --gpus=1
#SBATCH --time=00:30:00
#SBATCH --mail-user=zy.xu@tum.de
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --output=logs/md-ollama-install-%j.out
#SBATCH --error=logs/md-ollama-install-%j.err

set -euo pipefail

BASE=/mnt/proj1/eu-26-37/it4i-dianyu/Zhengying
ARCHIVE="$BASE/containers/cache/ollama-linux-amd64.tar.zst"
INSTALL_DIR="$BASE/tools/ollama"

mkdir -p "$INSTALL_DIR"
if [ ! -s "$ARCHIVE" ]; then
  curl -fL --retry 3 -o "$ARCHIVE" \
    https://ollama.com/download/ollama-linux-amd64.tar.zst
fi
zstd -dc "$ARCHIVE" | tar -xf - -C "$INSTALL_DIR"
test -x "$INSTALL_DIR/bin/ollama"
"$INSTALL_DIR/bin/ollama" --version
echo "Ollama installed successfully at $INSTALL_DIR/bin/ollama"
