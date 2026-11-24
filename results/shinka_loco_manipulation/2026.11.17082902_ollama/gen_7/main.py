# Fixed (not evolved): rewrites of the block below that dropped their own
# typing import failed with "name 'List' is not defined".
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# EVOLVE-BLOCK-START
def generate_contact_plan(scene: List[Dict[str, Any]]) -> Dict[str, List[Tuple]]:
    plan = get_initial_mode()
    
    # Define actions
    actions = [
        ("walk", 1),  # Walk 1 step to reach the first box
        ("pick_up", "green_box"),  # Pick up the green box
        ("walk", 1),  # Walk 1 step to reach the table
        ("place", "green_box"),  # Place the green box on the table
        ("walk", 1),  # Walk 1 step to reach the second box
        ("pick_up", "white_box"),  # Pick up the white box
        ("walk", 1),  # Walk 1 step to reach the table
        ("place", "white_box"),  # Place the white box on the table
        ("walk", 1),  # Walk 1 step to reach the third box
        ("pick_up", "yellow_box"),  # Pick up the yellow box
        ("walk", 1),  # Walk 1 step to reach the table
        ("place", "yellow_box"),  # Place the yellow box on the table
    ]

    # Execute actions
    for action in actions:
        if action[0] == "walk":
            walk(plan, action[1])
        elif action[0] == "pick_up":
            pick_up(plan, action[1])
        elif action[0] == "place":
            place(plan, action[1])

    return plan

def pick_up(plan, object_label):
    # Move to the object
    walk(plan, 1)
    # Grasp the object
    append_mode(plan, left_ee=(8, 1), right_ee=(8, 1))
    # Lift the object
    walk(plan, 1)
    # Release the object
    append_mode(plan, left_ee=(), right_ee=())

def place(plan, object_label):
    # Move to the table
    walk(plan, 1)
    # Grasp the object
    append_mode(plan, left_ee=(2, 1), right_ee=(2, 1))
    # Place the object on the table
    append_mode(plan, left_ee=(2, 1), right_ee=(2, 1))
    # Release the object
    append_mode(plan, left_ee=(), right_ee=())

# EVOLVE-BLOCK-END


# This part remains fixed (not evolved)
from env import append_mode, get_default_scene, get_initial_mode, walk


def run_planning():
    """Run the contact-mode-sequence generator. Returns (contact_plan, scene)."""
    scene = get_default_scene()
    contact_plan = generate_contact_plan(scene)
    return contact_plan, scene