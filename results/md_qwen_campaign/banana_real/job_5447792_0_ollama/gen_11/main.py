# Fixed (not evolved): rewrites of the block below that dropped their own
# typing import failed with "name 'List' is not defined".
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# EVOLVE-BLOCK-START

def generate_contact_plan(scene: List[Dict[str, Any]]) -> Dict[str, List[Tuple]]:
    # Start from the initial mode
    plan = {ch: list(seq) for ch, seq in get_initial_mode().items()}

    # Append modes to move the robot towards the banana
    # Move the robot's base closer to the banana
    walk(plan, 5)
    walk(plan, 3)

    # Ensure the soles are properly planted on the floor
    append_mode(plan, left_sole=(1, 1), right_sole=(1, 1))

    # Append modes to make contact with the banana's left and right sides
    append_mode(plan, left_ee=(9, 1), right_ee=())
    append_mode(plan, left_ee=(9, 1), right_ee=(11, 1))

    return plan

# EVOLVE-BLOCK-END


# This part remains fixed (not evolved)
from env import append_mode, get_default_scene, get_initial_mode, walk


def run_planning():
    """Run the contact-mode-sequence generator. Returns (contact_plan, scene)."""
    scene = get_default_scene()
    contact_plan = generate_contact_plan(scene)
    return contact_plan, scene