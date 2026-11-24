# Fixed (not evolved): rewrites of the block below that dropped their own
# typing import failed with "name 'List' is not defined".
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# EVOLVE-BLOCK-START
def generate_contact_plan(scene: List[Dict[str, Any]]) -> Dict[str, List[Tuple]]:
    plan = get_initial_mode()
    
    # Move left hand to the white box
    append_mode(plan, left_ee=(14, 1))
    
    # Grasp the white box with the left hand
    append_mode(plan, left_ee=(14, 1), white_box=(1, 14, 1))
    
    # Lift the white box off the floor
    append_mode(plan, left_ee=(14, 1), white_box=(), right_sole=(2, 1))
    
    # Walk to the elevated table
    walk(plan, 4)
    
    # Move the white box towards the elevated table
    append_mode(plan, left_ee=(14, 1), right_sole=(2, 1), white_box=(1, 8, 1))
    
    # Place the white box on the elevated table
    append_mode(plan, left_ee=(), right_sole=(2, 1), white_box=(6, 8, 1))
    
    return plan

# EVOLVE-BLOCK-END


# This part remains fixed (not evolved)
from env import append_mode, get_default_scene, get_initial_mode, walk


def run_planning():
    """Run the contact-mode-sequence generator. Returns (contact_plan, scene)."""
    scene = get_default_scene()
    contact_plan = generate_contact_plan(scene)
    return contact_plan, scene
