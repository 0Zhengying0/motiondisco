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
    # Start with the initial mode
    plan = get_initial_mode()

    # Step 1: Move to the box
    walk(plan, 3)  # Take 3 steps to reach the box
    append_mode(plan, left_ee=(14, 1, 2))  # Grasp the box with the left hand (sliding contact)
    append_mode(plan, left_ee=(14, 1, 1))  # Change to sticking contact

    # Step 2: Move to the table
    walk(plan, 3)  # Take 3 steps to reach the table

    # Step 3: Place the box on the table
    append_mode(plan, left_ee=(6, 8, 1))  # Place the box on the table with the left hand (sticking contact)

    return plan


# EVOLVE-BLOCK-END


# This part remains fixed (not evolved)
from env import append_mode, get_default_scene, get_initial_mode, walk


def run_planning():
    """Run the contact-mode-sequence generator. Returns (contact_plan, scene)."""
    scene = get_default_scene()
    contact_plan = generate_contact_plan(scene)
    return contact_plan, scene