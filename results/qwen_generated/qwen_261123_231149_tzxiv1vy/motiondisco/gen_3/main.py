"""MotionDisco's initial contact plan for generated reach_position tasks."""

from math import ceil, dist
from typing import Any, Dict, List, Tuple

# EVOLVE-BLOCK-START
def generate_contact_plan(scene: List[Dict[str, Any]]) -> Dict[str, List[Tuple]]:
    plan = get_initial_mode()
    task = load_task()
    start = task.resolved_state.robots[task.robot_id].q[:2]
    target = task.terminal_goal.robots[task.robot_id].xyz[:2]
    # Reduce step length to 0.3 meters and add intermediate support
walk(plan, ceil(dist(start, target) / 0.3))
# Add an intermediate support step if the distance is more than 1 meter
if dist(start, target) > 1.0:
    walk(plan, 1)
    return plan
# EVOLVE-BLOCK-END

from _task_loader import load_task
from env import append_mode, get_default_scene, get_initial_mode, walk


def run_planning():
    scene = get_default_scene()
    return generate_contact_plan(scene), scene