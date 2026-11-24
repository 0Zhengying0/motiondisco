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

class StateManager:
    def __init__(self, plan: Dict[str, List[Tuple]]):
        self.plan = plan
        self.current_state = "initial"

    def transition_to(self, new_state: str, **channel_updates) -> None:
        if new_state == "move_to_target":
            self.move_to_target(**channel_updates)
        elif new_state == "pick_up_object":
            self.pick_up_object(**channel_updates)
        elif new_state == "place_object":
            self.place_object(**channel_updates)
        self.current_state = new_state

    def move_to_target(self, target_env_id: int, steps: int) -> None:
        walk(self.plan, steps)
        append_mode(self.plan, left_ee=(target_env_id, 1))

    def pick_up_object(self, object_env_id: int) -> None:
        walk(self.plan, 2)
        append_mode(self.plan, left_ee=(), white_box=(1, object_env_id, 1))

    def place_object(self, object_env_id: int, target_env_id: int) -> None:
        walk(self.plan, 2)
        append_mode(self.plan, left_ee=(), white_box=(6, target_env_id, 1))

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

    # Step 1: Move to the white box
    state_manager.transition_to("move_to_target", target_env_id=14, steps=5)

    # Step 2: Pick up the white box
    state_manager.transition_to("pick_up_object", object_env_id=14)

    # Step 3: Move to the elevated table
    state_manager.transition_to("move_to_target", target_env_id=8, steps=5)

    # Step 4: Place the white box on the elevated table
    state_manager.transition_to("place_object", object_env_id=14, target_env_id=8)

    return plan


# EVOLVE-BLOCK-END


# This part remains fixed (not evolved)
from env import append_mode, get_default_scene, get_initial_mode, walk


def run_planning():
    """Run the contact-mode-sequence generator. Returns (contact_plan, scene)."""
    scene = get_default_scene()
    contact_plan = generate_contact_plan(scene)
    return contact_plan, scene