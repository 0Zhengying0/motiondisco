# Fixed (not evolved): rewrites of the block below that dropped their own
# typing import failed with "name 'List' is not defined".
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# EVOLVE-BLOCK-START
def generate_contact_plan(scene: List[Dict[str, Any]]) -> Dict[str, List[Tuple]]:
    # Start from the initial mode
    plan = {ch: list(seq) for ch, seq in get_initial_mode().items()}

    # Walk to the table
    walk(plan, 4)  # 4 walking steps to reach the table

    # Grasp the box
    append_mode(plan, left_ee=(8, 1, 1))  # Grasp the box with left hand

    # Lift the box from the floor
    append_mode(plan, left_ee=(8, 1, 2), white_box=(1, 1, 2))  # Lift the box

    # Release the box from the floor
    append_mode(plan, white_box=())

    # Move the box to the table
    append_mode(plan, left_ee=(2, 1, 2), white_box=(2, 1, 2))  # Move to table

    # Release the hand from the box
    append_mode(plan, left_ee=())

    # Place the box on the table
    append_mode(plan, white_box=(6, 2, 1))  # Place box on table

    # Adjust the robot's position
    walk(plan, 3)  # 3 walking steps to adjust position

    # Ensure the final mode matches the discrete contact goal
    plan['left_sole'][-1] = (1, 1)
    plan['right_sole'][-1] = (1, 1)
    plan['white_box'][-1] = (6, 1, 1)

    return plan
# EVOLVE-BLOCK-END


# This part remains fixed (not evolved)
from env import append_mode, get_default_scene, get_initial_mode, walk


def run_planning():
    """Run the contact-mode-sequence generator. Returns (contact_plan, scene)."""
    scene = get_default_scene()
    contact_plan = generate_contact_plan(scene)
    return contact_plan, scene