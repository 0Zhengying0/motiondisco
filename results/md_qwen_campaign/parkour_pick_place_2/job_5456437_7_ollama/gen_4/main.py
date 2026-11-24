# Fixed (not evolved): rewrites of the block below that dropped their own
# typing import failed with "name 'List' is not defined".
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# EVOLVE-BLOCK-START
def generate_contact_plan(scene: List[Dict[str, Any]]) -> Dict[str, List[Tuple]]:
    # Start from the initial mode
    plan = get_initial_mode()
    
    # Step 1: Move left_ee to the white_box
    append_mode(plan, left_ee=(14, 1))
    
    # Step 2: Grasp the white_box with left_ee
    append_mode(plan, left_ee=(14, 1, 1))
    
    # Step 3: Lift the white_box to the height of the table
    append_mode(plan, left_ee=(14, 1, 1), right_ee=(14, 1, 1))
    walk(plan, 2)  # Take two steps to lift the box
    
    # Step 4: Move right_ee to the table
    append_mode(plan, right_ee=(8, 1))
    
    # Step 5: Place the white_box on the table with right_ee
    append_mode(plan, right_ee=(6, 8, 1))
    
    # Ensure the final mode matches the discrete contact goal
    final_mode = {
        'left_sole': plan['left_sole'][-1],
        'right_sole': plan['right_sole'][-1],
        'left_ee': plan['left_ee'][-1],
        'right_ee': plan['right_ee'][-1],
        'white_box': [(6, 8, 1)],
    }
    
    # Append the final mode to the plan
    for channel, contacts in final_mode.items():
        plan[channel].append(contacts[0])
    
    return plan
# EVOLVE-BLOCK-END


# This part remains fixed (not evolved)
from env import append_mode, get_default_scene, get_initial_mode, walk


def run_planning():
    """Run the contact-mode-sequence generator. Returns (contact_plan, scene)."""
    scene = get_default_scene()
    contact_plan = generate_contact_plan(scene)
    return contact_plan, scene
