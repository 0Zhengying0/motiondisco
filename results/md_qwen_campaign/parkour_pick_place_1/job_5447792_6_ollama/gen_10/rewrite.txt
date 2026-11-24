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

def move_hand_to_box(plan: Dict[str, List[Tuple]], hand: str, box_env_id: int) -> None:
    append_mode(plan, **{hand: (box_env_id, 1)})

def grasp_box(plan: Dict[str, List[Tuple]], hand: str, box_self_id: int, box_env_id: int) -> None:
    append_mode(plan, **{hand: (box_env_id, 1), "white_box": (box_self_id, box_env_id, 1)})

def lift_box(plan: Dict[str, List[Tuple]], hand: str, box_env_id: int, support_env_id: int) -> None:
    append_mode(plan, **{hand: (box_env_id, 1), "white_box": ()})
    append_mode(plan, **{hand: (box_env_id, 1), "right_sole": (support_env_id, 1)})

def move_box_to_table(plan: Dict[str, List[Tuple]], hand: str, box_self_id: int, table_env_id: int) -> None:
    append_mode(plan, **{hand: (box_env_id, 1), "right_sole": (table_env_id, 1), "white_box": (box_self_id, table_env_id, 1)})

def place_box_on_table(plan: Dict[str, List[Tuple]], hand: str, box_self_id: int, table_env_id: int) -> None:
    append_mode(plan, **{hand: (), "right_sole": (table_env_id, 1), "white_box": (box_self_id, table_env_id, 1)})

def generate_contact_plan(scene: List[Dict[str, Any]]) -> Dict[str, List[Tuple]]:
    """
    Build a contact_mode_seq for the active task — see the system
    prompt for scene-specific goals.

    The body below returns the initial mode unchanged (1 mode, which
    scores 0 since a plan needs at least 2 modes); evolution is
    expected to extend it into a full plan.
    """
    plan = get_initial_mode()

    # Move left hand to the white box
    move_hand_to_box(plan, "left_ee", 14)

    # Grasp the white box with the left hand
    grasp_box(plan, "left_ee", 1, 14)

    # Lift the white box off the floor
    lift_box(plan, "left_ee", 14, 2)

    # Walk to the elevated table
    walk(plan, 4)

    # Move the white box towards the elevated table
    move_box_to_table(plan, "left_ee", 1, 8)

    # Place the white box on the elevated table
    place_box_on_table(plan, "left_ee", 1, 8)

    return plan

# EVOLVE-BLOCK-END


# This part remains fixed (not evolved)
from env import append_mode, get_default_scene, get_initial_mode, walk


def run_planning():
    """Run the contact-mode-sequence generator. Returns (contact_plan, scene)."""
    scene = get_default_scene()
    contact_plan = generate_contact_plan(scene)
    return contact_plan, scene