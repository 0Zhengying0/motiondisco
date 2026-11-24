# Fixed (not evolved): rewrites of the block below that dropped their own
# typing import failed with "name 'List' is not defined".
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# EVOLVE-BLOCK-START
def initialize_plan() -> Dict[str, List[Tuple]]:
    """
    Initialize the contact plan with the initial mode.
    """
    return get_initial_mode()

def walk_to_position(plan: Dict[str, List[Tuple]], steps: int) -> None:
    """
    Append walking modes to the plan.
    """
    walk(plan, steps)

def finalize_position(plan: Dict[str, List[Tuple]]) -> None:
    """
    Ensure the final mode meets the discrete contact goal.
    """
    final_mode = {
        'left_sole': [(1, 1)],
        'right_sole': [(1, 1)],
        'left_ee': [()],
        'right_ee': [()],
        'white_box': [()],
        'yellow_box': [()],
    }
    for channel, contacts in final_mode.items():
        plan[channel].append(contacts[0])

def generate_contact_plan(scene: List[Dict[str, Any]]) -> Dict[str, List[Tuple]]:
    """
    Build a contact_mode_seq for the active task.
    """
    plan = initialize_plan()
    walk_to_position(plan, 3)  # Adjust the number of steps as needed
    finalize_position(plan)
    return plan


# EVOLVE-BLOCK-END


# This part remains fixed (not evolved)
from env import append_mode, get_default_scene, get_initial_mode, walk


def run_planning():
    """Run the contact-mode-sequence generator. Returns (contact_plan, scene)."""
    scene = get_default_scene()
    contact_plan = generate_contact_plan(scene)
    return contact_plan, scene