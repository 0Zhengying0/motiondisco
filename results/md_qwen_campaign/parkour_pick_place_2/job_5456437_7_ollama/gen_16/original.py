# Fixed (not evolved): rewrites of the block below that dropped their own
# typing import failed with "name 'List' is not defined".
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# EVOLVE-BLOCK-START

def generate_contact_plan(scene: List[Dict[str, Any]]) -> Dict[str, List[Tuple]]:
    """
    Build a contact_mode_seq for the active task — see the system
    prompt for scene-specific goals.

    The body below returns the initial mode unchanged (1 mode, which
    scores 0 since a plan needs at least 2 modes); evolution is
    expected to extend it into a full plan.
    """
    plan = get_initial_mode()

    # Step 1: Move the robot's left and right hands to the white box
    append_mode(plan, left_ee=(14, 2), right_ee=(14, 4))

    # Step 2: Lift the white box with the robot's hands
    append_mode(plan, left_ee=(6, 14, 1), right_ee=(4, 14, 1), white_box=(6, 14, 1))

    # Step 3: Move the robot to the elevated table
    walk(plan, 3)

    # Step 4: Place the white box on the elevated table
    append_mode(plan, left_ee=(), right_ee=(), white_box=(6, 8, 1))

    return plan

# EVOLVE-BLOCK-END


# This part remains fixed (not evolved)
from env import append_mode, get_default_scene, get_initial_mode, walk


def run_planning():
    """Run the contact-mode-sequence generator. Returns (contact_plan, scene)."""
    scene = get_default_scene()
    contact_plan = generate_contact_plan(scene)
    return contact_plan, scene