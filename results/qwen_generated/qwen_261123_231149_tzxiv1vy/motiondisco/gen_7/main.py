"""MotionDisco's initial contact plan for generated reach_position tasks."""

from math import ceil, dist
from typing import Any, Dict, List, Tuple

# EVOLVE-BLOCK-START
def generate_contact_plan(scene: List[Dict[str, Any]]) -> Dict[str, List[Tuple]]:
    plan = get_initial_mode()
    task = load_task()
    start = task.resolved_state.robots[task.robot_id].q[:2]
    target = task.terminal_goal.robots[task.robot_id].xyz[:2]

    # Calculate the distance to the target
    distance = dist(start, target)

    # Determine the number of walking steps
    # Base step length is approximately 0.4 m
    # Add an extra step to ensure the robot reaches the target
    # Adjust the number of steps to account for the robot's step length and target distance
    n_steps = ceil(distance / 0.4) + 2

    # Walk to the target with a more appropriate duration
    walk(plan, n_steps)
    # Add a small pause to ensure the robot reaches the target accurately
    append_mode(plan, left_sole=(1, 1), right_sole=(1, 1))

    return plan
# EVOLVE-BLOCK-END

from _task_loader import load_task
from env import append_mode, get_default_scene, get_initial_mode, walk


def run_planning():
    scene = get_default_scene()
    return generate_contact_plan(scene), scene