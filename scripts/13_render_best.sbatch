#!/bin/bash
#SBATCH --job-name=motiondisco-render-best
#SBATCH --account=EU-26-37
#SBATCH --partition=qgpu_exp
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:30:00
#SBATCH --mail-user=zy.xu@tum.de
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --output=logs/md-render-%j.out
#SBATCH --error=logs/md-render-%j.err

set -euo pipefail

BASE=/mnt/proj1/eu-26-37/it4i-dianyu/Zhengying
ROOT="$BASE/motiondisco"
PICKLE="$ROOT/results/shinka_loco_manipulation/2026.11.17082902_ollama/best/results/to_run.pkl"

cd "$ROOT"
apptainer exec --nv --cleanenv --bind "$BASE:$BASE" \
  "$BASE/containers/miniforge3.sif" /bin/bash -c '
    set -euo pipefail
    export PATH="$2/bin:$PATH"
    export PYTHONNOUSERSITE=1
    export PYTHONPATH="$1:$1/examples/loco_manipulation${PYTHONPATH:+:$PYTHONPATH}"
    export MUJOCO_GL=egl
    cd "$1"
    "$2/bin/python" - "$3" <<"PY"
import pickle
import sys
from pathlib import Path

from examples.loco_manipulation._task_loader import load_task
from examples.loco_manipulation._replay_common import (
    build_qpos_trajectory, build_replay_model, write_trajectory_mp4,
)
from examples.loco_manipulation.replay_to_run import _task_kwargs_from_hydra

pickle_path = Path(sys.argv[1])
with pickle_path.open("rb") as stream:
    data = pickle.load(stream)
task = load_task(**_task_kwargs_from_hydra(pickle_path))
model = build_replay_model(task)
trajectory = build_qpos_trajectory(data["results"], task, model)
video_path = pickle_path.with_suffix(".mp4")
write_trajectory_mp4(
    model, trajectory, video_path, dt=0.05,
    width=1280, height=720, fps=30,
    step_ts=data["results"].get("step_ts"),
)
print(f"Rendered {len(trajectory)} trajectory frames to {video_path}")
PY
  ' _ "$ROOT" "$BASE/envs/motiondisco" "$PICKLE"
