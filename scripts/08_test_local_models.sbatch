#!/bin/bash
#SBATCH --job-name=motiondisco-llm-test
#SBATCH --account=EU-26-37
#SBATCH --partition=qgpu_exp
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:25:00
#SBATCH --mail-user=zy.xu@tum.de
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --output=logs/md-llm-test-%j.out
#SBATCH --error=logs/md-llm-test-%j.err

set -euo pipefail

BASE=/mnt/proj1/eu-26-37/it4i-dianyu/Zhengying
export OLLAMA_MODELS="$BASE/models/ollama"
export OLLAMA_HOST="127.0.0.1:$((20000 + SLURM_JOB_ID % 30000))"
"$BASE/tools/ollama/bin/ollama" serve > "logs/md-llm-server-$SLURM_JOB_ID.log" 2>&1 &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true' EXIT

for attempt in $(seq 1 60); do
  if curl -fsS "http://$OLLAMA_HOST/api/tags" >/dev/null; then
    break
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "Ollama server exited; see server log" >&2
    exit 1
  fi
  sleep 2
done
curl -fsS "http://$OLLAMA_HOST/api/tags" >/dev/null

apptainer exec --cleanenv --bind "$BASE:$BASE" \
  "$BASE/containers/miniforge3.sif" /bin/bash -c '
    set -euo pipefail
    export PYTHONNOUSERSITE=1
    export MD_ENDPOINT="http://$2/v1"
    cd "$1/motiondisco"
    "$1/envs/motiondisco/bin/python" - <<"PY"
import os
from openai import OpenAI
from shinka.llm.query import query

endpoint = os.environ["MD_ENDPOINT"]
model = f"local/qwen2.5-coder:14b@{endpoint}"
result = query(model, "Reply with exactly: QWEN_OK", "You are a concise assistant.", max_tokens=32, temperature=0)
print("MotionDisco Qwen reply:", result.content)
assert result.content.strip(), "Qwen returned empty text"

client = OpenAI(api_key="local", base_url=endpoint)
embedding = client.embeddings.create(model="embeddinggemma", input="motion discovery")
print("Embedding dimensions:", len(embedding.data[0].embedding))
assert embedding.data[0].embedding
PY
  ' _ "$BASE" "$OLLAMA_HOST"

echo "Local Qwen and embedding checks completed successfully"
