# Fixed (not evolved): rewrites of the block below that dropped their own
# typing import failed with "name 'List' is not defined".
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# EVOLVE-BLOCK-START
def generate_contact_plan(scene: List[Dict[str, Any]]) -> Dict[str, List[Tuple]]:
    """
    Build a contact_mode_seq for the active task — see the system
    prompt for scene-specific goals.
    """
    plan = get_initial_mode()

    # Step 1: Lift the right foot and move forward to the table
    append_mode(plan, right_ee=(2, 1))
    walk(plan, 1)
    append_mode(plan, right_ee=(), left_ee=(2, 1))

    # Step 2: Move the left foot forward to the table
    walk(plan, 1)
    append_mode(plan, left_sole=(2, 1), right_sole=(2, 1))

    # Step 3: Hold the box with the left hand
    append_mode(plan, left_ee=(9, 1))

    # Step 4: Hold the box with the right hand
    append_mode(plan, right_ee=(11, 1))

    # Step 5: Lift the white box
    append_mode(plan, left_ee=(), right_ee=(), white_box=(1, 2, 1))

    # Step 6: Move the white box to the table
    walk(plan, 1)
    append_mode(plan, left_ee=(9, 1), right_ee=(11, 1), white_box=(1, 2, 1))

    return plan


# EVOLVE-BLOCK-END


# This part remains fixed (not evolved)
from env import append_mode, get_default_scene, get_initial_mode, walk


def run_planning():
    """Run the contact-mode-sequence generator. Returns (contact_plan, scene)."""
    scene = get_default_scene()
    contact_plan = generate_contact_plan(scene)
    return contact_plan, scene