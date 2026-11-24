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

    # Stage 1: Approach the box
    walk(plan, 5)  # Move forward to get closer to the box

    # Stage 2: Grasp the box
    append_mode(plan, left_ee=(14, 1), white_box=(6, 1, 1))  # Grasp the box with the left hand
    append_mode(plan, left_ee=())  # Release the box (optional, to be safe)

    # Stage 3: Walk to the elevated table
    walk(plan, 6)  # Move forward to the elevated table

    # Stage 4: Place the box on the elevated table
    append_mode(plan, left_ee=(14, 1), white_box=(6, 1, 1))  # Grasp the box again
    append_mode(plan, left_ee=(), white_box=(6, 8, 1))  # Release the box on the elevated table

    # Ensure the final state is correct
    append_mode(plan, white_box=(6, 8, 1))  # Ensure the box is correctly placed

    return plan

# EVOLVE-BLOCK-END


# This part remains fixed (not evolved)
from env import append_mode, get_default_scene, get_initial_mode, walk


def run_planning():
    """Run the contact-mode-sequence generator. Returns (contact_plan, scene)."""
    scene = get_default_scene()
    contact_plan = generate_contact_plan(scene)
    return contact_plan, scene