# Fixed (not evolved): rewrites of the block below that dropped their own
# typing import failed with "name 'List' is not defined".
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# EVOLVE-BLOCK-START
def generate_contact_plan(scene: List[Dict[str, Any]]) -> Dict[str, List[Tuple]]:
    # Start from the initial mode
    plan = {ch: list(seq) for ch, seq in get_initial_mode().items()}

    # Move the box to the desired location
    # 1. Grasp the box with the left hand
    append_mode(plan, left_ee=(8, 1, 1))
    # 2. Lift the box
    append_mode(plan, left_ee=(8, 1, 2), white_box=(1, 1, 2))
    # 3. Move the box to the other side of the table
    append_mode(plan, left_ee=(2, 1, 2), white_box=(2, 1, 2))
    # 4. Place the box on the table
    append_mode(plan, left_ee=(), white_box=(6, 2, 1))

    # Adjust the robot's position to match the discrete contact goal
    # 1. Move the robot to the table
    walk(plan, 4)
    # 2. Ensure the robot's feet are on the table
    append_mode(plan, left_sole=(2, 1, 1), right_sole=(2, 1, 1))

    return plan
# EVOLVE-BLOCK-END


# This part remains fixed (not evolved)
from env import append_mode, get_default_scene, get_initial_mode, walk


def run_planning():
    """Run the contact-mode-sequence generator. Returns (contact_plan, scene)."""
    scene = get_default_scene()
    contact_plan = generate_contact_plan(scene)
    return contact_plan, scene
