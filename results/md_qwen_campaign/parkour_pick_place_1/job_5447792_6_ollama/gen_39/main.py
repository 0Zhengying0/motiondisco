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

def move_hand_to_box(plan, hand):
    append_mode(plan, **{hand: (14, 1)})

def grasp_box(plan, hand):
    append_mode(plan, **{hand: (14, 1), "white_box": (1, 14, 1)})

def lift_box(plan, hand):
    append_mode(plan, **{hand: (14, 1), "white_box": ()})

def move_box_to_table(plan, hand):
    append_mode(plan, **{hand: (14, 1), "white_box": (1, 8, 1)})

def place_box(plan, hand):
    append_mode(plan, **{hand: (), "white_box": (6, 8, 1)})

def generate_contact_plan(scene: List[Dict[str, Any]]) -> Dict[str, List[Tuple]]:
    """
    Build a contact_mode_seq for the active task — see the system
    prompt for scene-specific goals.

    The body below returns the initial mode unchanged (1 mode, which
    scores 0 since a plan needs at least 2 modes); evolution is
    expected to extend it into a full plan.
    """
    plan = get_initial_mode()

    # State machine to manage transitions
    states = {
        "start": "move_to_box",
        "move_to_box": "grasp_box",
        "grasp_box": "lift_box",
        "lift_box": "move_to_table",
        "move_to_table": "place_box",
        "place_box": "end"
    }

    current_state = "start"

    while current_state != "end":
        if current_state == "move_to_box":
            walk(plan, 3)  # Take 3 steps to reach the box
            current_state = states[current_state]
        elif current_state == "grasp_box":
            move_hand_to_box(plan, "left_ee")
            grasp_box(plan, "left_ee")
            current_state = states[current_state]
        elif current_state == "lift_box":
            lift_box(plan, "left_ee")
            current_state = states[current_state]
        elif current_state == "move_to_table":
            walk(plan, 4)  # Take 4 steps to reach the table
            current_state = states[current_state]
        elif current_state == "place_box":
            move_box_to_table(plan, "left_ee")
            place_box(plan, "left_ee")
            current_state = states[current_state]

    return plan

# EVOLVE-BLOCK-END


# This part remains fixed (not evolved)
from env import append_mode, get_default_scene, get_initial_mode, walk


def run_planning():
    """Run the contact-mode-sequence generator. Returns (contact_plan, scene)."""
    scene = get_default_scene()
    contact_plan = generate_contact_plan(scene)
    return contact_plan, scene