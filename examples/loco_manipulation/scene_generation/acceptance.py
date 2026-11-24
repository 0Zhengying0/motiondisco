"""Check MotionDisCo's saved trajectories outside the search and evaluator."""

from importlib import import_module
import pickle

from examples.loco_manipulation import env, trajectory_check
from examples.loco_manipulation.scene_campaign import valid_plans
from reports.extract_motiondisco_performance import TrajectoryReader
from shinka.performance import phase, timed

from .catalogs import read_json, write_json


@timed("scene_trajectory_acceptance")
def accepted_plans(scene, output):
    candidates = valid_plans(str(output)).values()
    if not candidates:
        return []
    task = env.load_task(scene=scene, initial_condition="default")
    completion_check = import_module(f"scenes.{scene}.goals").TASK_COMPLETION
    plans = []
    for candidate in candidates:
        folder = output / candidate["gen"] / "results"
        report = {"pass": False, "solver_to_valid": True, "to_physical": None, "task_completion": None}
        try:
            extra = read_json(folder / "extra.json")
            with (folder / "to_run.pkl").open("rb") as stream:
                saved = TrajectoryReader(stream).load()
            plan = saved["contact_mode_seq"]
            results = saved["results"]
            parts = extra["to_cost_parts"]
            nodes_per_mode, remainder = divmod(parts["num_nodes"], parts["num_modes"])
            if remainder or nodes_per_mode < 1:
                raise ValueError("Inconsistent number of trajectory nodes and contact modes")
            with phase("task_completion_check"):
                completion = completion_check(task.scene, task.resolved_state, results)
            report["task_completion"] = completion
            physics = trajectory_check.check(task, plan, results, nodes_per_mode)
            report["to_physical"] = physics
            report["pass"] = bool(physics["pass"] and completion["met"])
        except (OSError, EOFError, pickle.UnpicklingError, KeyError, TypeError, ValueError, RuntimeError) as exc:
            report["error"] = f"{type(exc).__name__}: {exc}"
        write_json(folder / "acceptance.json", report)
        if report["pass"]:
            plans.append({**candidate, "position_error_m": report["task_completion"]["error_m"]})
    return plans
