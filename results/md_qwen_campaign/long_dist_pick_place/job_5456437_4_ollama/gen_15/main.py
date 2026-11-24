# Fixed (not evolved): rewrites of the block below that dropped their own
# typing import failed with "name 'List' is not defined".
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# EVOLVE-BLOCK-START
def generate_contact_plan(scene: List[Dict[str, Any]]) -> Dict[str, List[Tuple]]:
    plan = {ch: list(seq) for ch, seq in get_initial_mode().items()}
    
    # Calculate the number of walking steps needed to reach the table
    initial_x = scene[0]['xyz'][0]
    table_x = scene[2]['xyz'][0]
    distance_to_table = abs(table_x - initial_x)
    steps_to_table = int(distance_to_table / 0.4) + 1  # 0.4 m per step

    # Walk towards the table
    walk(plan, steps_to_table)
    
    # Pick up the yellow box with the left hand
    append_mode(
        plan,
        left_ee=(8, 1),  # Left hand sticks to the top of the yellow box
        right_ee=(1, 1),  # Right hand is free
        left_sole=(1, 1),  # Left foot is on the floor
        right_sole=(1, 1)  # Right foot is on the floor
    )
    
    # Calculate the number of walking steps needed to reach the distant table
    distance_to_distant_table = abs(table_x - 2.5)  # Assuming the distant table is at x=2.5
    steps_to_distant_table = int(distance_to_distant_table / 0.4) + 1  # 0.4 m per step

    # Walk towards the distant table
    walk(plan, steps_to_distant_table)
    
    # Place the yellow box on the distant table with the correct contact type
    append_mode(
        plan,
        left_ee=(1, 1),  # Left hand is free
        right_ee=(2, 2),  # Right hand slides to the top of the distant table
        left_sole=(1, 1),  # Left foot is on the floor
        right_sole=(1, 1)  # Right foot is on the floor
    )
    
    return plan

# EVOLVE-BLOCK-END


# This part remains fixed (not evolved)
from env import append_mode, get_default_scene, get_initial_mode, walk


def run_planning():
    """Run the contact-mode-sequence generator. Returns (contact_plan, scene)."""
    scene = get_default_scene()
    contact_plan = generate_contact_plan(scene)
    return contact_plan, scene