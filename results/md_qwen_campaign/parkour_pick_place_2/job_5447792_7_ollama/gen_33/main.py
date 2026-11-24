# Fixed (not evolved): rewrites of the block below that dropped their own
# typing import failed with "name 'List' is not defined".
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# EVOLVE-BLOCK-START
class Task:
    def __init__(self):
        self.plan = get_initial_mode()

    def pick_box(self):
        # Approach the box
        self.append_mode(left_ee=(14, 1), right_ee=(14, 1))
        # Lift the box
        self.append_mode(left_ee=(), right_ee=(), left_sole=(1, 1), right_sole=(1, 1))
        # Move the box to the front of the robot
        self.append_mode(left_ee=(14, 1), right_ee=(), left_sole=(1, 1), right_sole=(1, 1))

    def walk_to_table(self):
        # Walk to the table
        walk(self.plan, 4)

    def place_box(self):
        # Move the box towards the table
        self.append_mode(left_ee=(14, 1), right_ee=(), left_sole=(1, 1), right_sole=(1, 1))
        # Place the box on the table
        self.append_mode(left_ee=(), right_ee=(), left_sole=(8, 1), right_sole=(8, 1), white_box=(6, 8, 1))

    def append_mode(self, **channel_updates) -> None:
        append_mode(self.plan, **channel_updates)

    def generate_plan(self) -> Dict[str, List[Tuple]]:
        self.pick_box()
        self.walk_to_table()
        self.place_box()
        return self.plan

def generate_contact_plan(scene: List[Dict[str, Any]]) -> Dict[str, List[Tuple]]:
    task = Task()
    return task.generate_plan()

# EVOLVE-BLOCK-END


# This part remains fixed (not evolved)
from env import append_mode, get_default_scene, get_initial_mode, walk


def run_planning():
    """Run the contact-mode-sequence generator. Returns (contact_plan, scene)."""
    scene = get_default_scene()
    contact_plan = generate_contact_plan(scene)
    return contact_plan, scene