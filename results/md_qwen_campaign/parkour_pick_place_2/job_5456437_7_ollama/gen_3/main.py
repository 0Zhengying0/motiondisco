# Fixed (not evolved): rewrites of the block below that dropped their own
# typing import failed with "name 'List' is not defined".
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# EVOLVE-BLOCK-START
"""
Contact-mode-sequence generator for humanoid loco-manipulation.

Only this one function is evolved by ShinkaEvolve. The notation, the
task, the scene IDs and how plans are judged are described in the
system prompt.

A `contact_mode_seq` is a dict of channels -> list of contact tuples
(one entry per mode). Channels are:

    "left_ee", "right_ee"     : (env_id, contact_type)            or () for free
    "left_sole", "right_sole" : (env_id, contact_type)            or () for free
    "<object_label>"          : (self_id, env_id, contact_type)   or () for free

contact_type: 1 = sticking, 2 = sliding (see the system prompt).
All channels in the dict must have the same length (= number of modes).

Helpers available in this module's namespace (do NOT redefine):

    get_initial_mode() -> Dict[str, List[Tuple]]
        Returns the scene's initial contact mode as a single-mode
        contact_mode_seq (length-1 channel lists). Use this as mode 0
        of your plan and append further modes from there.

    append_mode(plan, **channel_updates) -> None
        Appends one new mode to ``plan``. Channels not mentioned
        keep their previous value.

    walk(plan, n_steps) -> None
        Optional shorthand: appends n_steps alternating steps (right
        foot lifts first), finishing in double support on the same
        surfaces.
"""

def plan_movement_to_table(plan: Dict[str, List[Tuple]], table_env_id: int) -> None:
    """
    Plans the robot's movement to the specified table.
    """
    walk(plan, 10)  # Move forward to the table
    append_mode(plan, left_ee=(table_env_id, 1), right_ee=(table_env_id, 1))

def plan_grasping_of_white_box(plan: Dict[str, List[Tuple]], white_box_env_id: int) -> None:
    """
    Plans the robot's grasping of the white box.
    """
    walk(plan, 5)  # Move forward to the white box
    append_mode(plan, left_ee=(white_box_env_id, 1), right_ee=(white_box_env_id, 1))

def plan_placement_of_white_box_on_table(plan: Dict[str, List[Tuple]], white_box_self_id: int, table_env_id: int) -> None:
    """
    Plans the robot's placement of the white box on the specified table.
    """
    walk(plan, 10)  # Move forward to the table
    append_mode(plan, left_ee=(), right_ee=(), white_box=(white_box_self_id, table_env_id, 1))

def generate_contact_plan(scene: List[Dict[str, Any]]) -> Dict[str, List[Tuple]]:
    """
    Build a contact_mode_seq for the active task — see the system
    prompt for scene-specific goals.

    The body below returns the initial mode unchanged (1 mode, which
    scores 0 since a plan needs at least 2 modes); evolution is
    expected to extend it into a full plan.
    """
    plan = get_initial_mode()

    table_env_id = 8  # env_id of the elevated table
    white_box_env_id = 14  # env_id of the white box
    white_box_self_id = 6  # self_id of the top face of the white box

    plan_movement_to_table(plan, table_env_id)
    plan_grasping_of_white_box(plan, white_box_env_id)
    plan_placement_of_white_box_on_table(plan, white_box_self_id, table_env_id)

    return plan


# EVOLVE-BLOCK-END


# This part remains fixed (not evolved)
from env import append_mode, get_default_scene, get_initial_mode, walk


def run_planning():
    """Run the contact-mode-sequence generator. Returns (contact_plan, scene)."""
    scene = get_default_scene()
    contact_plan = generate_contact_plan(scene)
    return contact_plan, scene
