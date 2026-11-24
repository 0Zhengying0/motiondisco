# Fixed (not evolved): rewrites of the block below that dropped their own
# typing import failed with "name 'List' is not defined".
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# EVOLVE-BLOCK-START
def generate_contact_plan(scene: List[Dict[str, Any]]) -> Dict[str, List[Tuple]]:
    plan = get_initial_mode()

    # Walk to the white box
    walk_to_target(plan, target_env_id=14)

    # Reach for the white box with the right hand
    reach_object(plan, object_env_id=14, ee_channel="right_ee")

    # Pick up the white box
    pick_up_object(plan, object_env_id=14, ee_channel="right_ee", object_self_id=1)

    # Walk to the elevated table
    walk_to_target(plan, target_env_id=8)

    # Place the white box on the elevated table
    place_object(plan, object_env_id=8, object_self_id=6, ee_channel="right_ee")

    return plan


def walk_to_target(plan: Dict[str, List[Tuple]], target_env_id: int) -> None:
    """Walk to a target environment ID."""
    walk(plan, 5)
    # Ensure the target is within reach
    append_mode(plan, right_ee=(target_env_id, 1))


def reach_object(plan: Dict[str, List[Tuple]], object_env_id: int, ee_channel: str) -> None:
    """Reach for an object with a specific end-effector."""
    append_mode(plan, **{ee_channel: (object_env_id, 1)})


def pick_up_object(plan: Dict[str, List[Tuple]], object_env_id: int, ee_channel: str, object_self_id: int) -> None:
    """Pick up an object using a specific end-effector."""
    append_mode(plan, **{ee_channel: (object_env_id, 1), "white_box": (object_self_id, object_env_id, 1)})


def place_object(plan: Dict[str, List[Tuple]], object_env_id: int, object_self_id: int, ee_channel: str) -> None:
    """Place an object on a target surface."""
    append_mode(plan, **{ee_channel: (), "white_box": (object_self_id, object_env_id, 1)})


# EVOLVE-BLOCK-END


# This part remains fixed (not evolved)
from env import append_mode, get_default_scene, get_initial_mode, walk


def run_planning():
    """Run the contact-mode-sequence generator. Returns (contact_plan, scene)."""
    scene = get_default_scene()
    contact_plan = generate_contact_plan(scene)
    return contact_plan, scene