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

def release_ee(plan, ee: str) -> None:
    """Release the end-effector by setting it to free."""
    append_mode(plan, **{ee: ()})

def move_ee(plan, ee: str, target: Tuple) -> None:
    """Move the end-effector to the target contact."""
    append_mode(plan, **{ee: target})

def move_to(plan, ee: str, target_env_id: int) -> None:
    """Move the end-effector to the target environment ID."""
    move_ee(plan, ee, (target_env_id, 1))

def pick_up(plan, ee: str, object_id: str, object_self_id: int, object_env_id: int) -> None:
    """Pick up the object using the specified end-effector."""
    move_ee(plan, ee, (object_env_id, 1))
    append_mode(plan, **{object_id: (object_self_id, object_env_id, 1)})

def place_on(plan, ee: str, object_id: str, target_env_id: int, target_self_id: int) -> None:
    """Place the object on the target environment ID."""
    move_ee(plan, ee, (target_env_id, 1))
    append_mode(plan, **{object_id: (target_self_id, target_env_id, 1)})

class StateManager:
    def __init__(self, plan):
        self.plan = plan
        self.current_state = "initial"

    def transition(self, new_state):
        if self.current_state == "initial":
            if new_state == "move_to_white_box":
                self.move_to_white_box()
            else:
                raise ValueError(f"Invalid transition from {self.current_state} to {new_state}")
        elif self.current_state == "move_to_white_box":
            if new_state == "pick_up_box":
                self.pick_up_box()
            else:
                raise ValueError(f"Invalid transition from {self.current_state} to {new_state}")
        elif self.current_state == "pick_up_box":
            if new_state == "move_to_floor":
                self.move_to_floor()
            else:
                raise ValueError(f"Invalid transition from {self.current_state} to {new_state}")
        elif self.current_state == "move_to_floor":
            if new_state == "move_to_table":
                self.move_to_table()
            else:
                raise ValueError(f"Invalid transition from {self.current_state} to {new_state}")
        elif self.current_state == "move_to_table":
            if new_state == "place_box":
                self.place_box()
            else:
                raise ValueError(f"Invalid transition from {self.current_state} to {new_state}")
        elif self.current_state == "place_box":
            if new_state == "final":
                self.final()
            else:
                raise ValueError(f"Invalid transition from {self.current_state} to {new_state}")
        else:
            raise ValueError(f"Unknown state: {self.current_state}")

    def move_to_white_box(self):
        move_to(self.plan, "right_ee", 14)
        self.current_state = "move_to_white_box"

    def pick_up_box(self):
        release_ee(self.plan, "left_ee")
        pick_up(self.plan, "right_ee", "white_box", 1, 14)
        release_ee(self.plan, "right_ee")
        self.current_state = "pick_up_box"

    def move_to_floor(self):
        move_to(self.plan, "right_ee", 1)
        release_ee(self.plan, "right_ee")
        self.current_state = "move_to_floor"

    def move_to_table(self):
        move_to(self.plan, "left_ee", 8)
        move_to(self.plan, "right_ee", 8)
        walk(self.plan, 3)
        self.current_state = "move_to_table"

    def place_box(self):
        pick_up(self.plan, "right_ee", "white_box", 1, 8)
        place_on(self.plan, "right_ee", "white_box", 8, 6)
        release_ee(self.plan, "right_ee")
        self.current_state = "place_box"

    def final(self):
        self.current_state = "final"

def generate_contact_plan(scene: List[Dict[str, Any]]) -> Dict[str, List[Tuple]]:
    """
    Build a contact_mode_seq for the active task — see the system
    prompt for scene-specific goals.

    The body below returns the initial mode unchanged (1 mode, which
    scores 0 since a plan needs at least 2 modes); evolution is
    expected to extend it into a full plan.
    """
    plan = get_initial_mode()
    state_manager = StateManager(plan)
    state_manager.transition("move_to_white_box")
    state_manager.transition("pick_up_box")
    state_manager.transition("move_to_floor")
    state_manager.transition("move_to_table")
    state_manager.transition("place_box")
    state_manager.transition("final")
    return plan


# EVOLVE-BLOCK-END


# This part remains fixed (not evolved)
from env import append_mode, get_default_scene, get_initial_mode, walk


def run_planning():
    """Run the contact-mode-sequence generator. Returns (contact_plan, scene)."""
    scene = get_default_scene()
    contact_plan = generate_contact_plan(scene)
    return contact_plan, scene