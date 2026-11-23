"""Regression coverage for geometric feedback sent to the scene generator."""

from importlib.util import find_spec
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def proposal(scene_id, white_xy, table_yaw=0):
    return {
        "schema_version": 1,
        "scene_id": scene_id,
        "floor": {"half_extents": [3, 2]},
        "robot": {"initial_xy_yaw": [0.5, -1, 0]},
        "objects": [
            {"asset_id": "table_short", "instance_id": "table",
             "support_object": "floor", "support_surface": "surface",
             "relative_xy_yaw": [-1, 0, table_yaw]},
            {"asset_id": "green_box", "instance_id": "green",
             "support_object": "table", "support_surface": "top", "relative_xy_yaw": [0, 0, 0]},
            {"asset_id": "white_box", "instance_id": "white",
             "support_object": "table", "support_surface": "top", "relative_xy_yaw": [*white_xy, 0]},
        ],
        "task": {"type": "reach_position", "parameters": {"target_xy": [1, 1.5]}},
    }


@unittest.skipUnless(find_spec("faro") and find_spec("mujoco"), "Requires FARO and MuJoCo")
class SceneGenerationFeedbackTests(unittest.TestCase):
    def test_reach_target_uses_tighter_to_bounds_and_keeps_3d_acceptance(self):
        import numpy as np

        from examples.loco_manipulation.scene_generation import convert
        from examples.loco_manipulation.scene_generation.spec import parse_spec

        spec, errors = parse_spec(json.dumps(proposal("reach_goal_check", (0, 0.3))))
        self.assertFalse(errors)
        scene = convert.make_scene(spec)
        state = scene.resolve(convert.initial_state(spec))
        target = convert.reach_terminal(spec, scene, state).robots["robot"]
        np.testing.assert_allclose(target.tolerance("kso"), [0.1] * 3)
        np.testing.assert_allclose(target.tolerance("to"), [0.005] * 3)

        poses = np.array([state.robots["robot"].q, state.robots["robot"].q])
        poses[-1, :3] = target.xyz + [-0.1, -0.1, 0]
        results = {"robot_xs": {"robot": poses}}
        completion = convert.reach_completion(spec, scene, state, results)
        self.assertFalse(completion["met"])
        self.assertAlmostEqual(completion["error_m"], 2 ** 0.5 / 10)
        poses[-1, :3] = target.xyz + [0.055] * 3
        self.assertTrue(convert.reach_completion(spec, scene, state, results)["met"])

    def test_retry_uses_feasible_support_axis_and_then_registers(self):
        from examples.loco_manipulation.scene_generation import __main__ as cli

        with TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "feedback_scene"
            work.mkdir()
            args = SimpleNamespace(host="http://127.0.0.1:11434", model="qwen2.5-coder:14b",
                                   request_timeout=10, attempts=3, seed=21, brief=None)
            generated = [proposal(work.name, position, table_yaw=0.4)
                         for position in ((0.5, 0), (0.2, 0), (0, 0.3))]
            requests = []

            def respond(host, path, timeout, payload=None):
                if path == "/api/version":
                    return {"version": "test"}
                if path == "/api/tags":
                    return {"models": [{"name": args.model, "digest": "test"}]}
                self.assertEqual(path, "/api/generate")
                requests.append(payload)
                return {"response": json.dumps(generated[len(requests) - 1])}

            with patch.object(cli, "SCENES_DIR", root / "registry"), patch.object(cli, "request", respond):
                self.assertEqual(cli.generate(args, work), f"generated.{work.name}")

            first = json.loads((work / "attempt_01/validation.json").read_text())
            self.assertEqual(first["errors"][0]["code"], "OUT_OF_BOUNDS")
            self.assertEqual(first["errors"][0]["details"]["center_abs_limits_xy_m"], [0.2175, 0.5725])
            self.assertIn('"center_abs_limits_xy_m": [0.2175, 0.5725]', requests[1]["prompt"])

            second = json.loads((work / "attempt_02/validation.json").read_text())
            self.assertEqual(second["errors"][0]["code"], "PENETRATION")
            hint = second["errors"][0]["details"]["separation_hint"]
            self.assertEqual(hint["move_instance"], "white")
            self.assertEqual(hint["center_ranges_m"], {"x": [], "y": [[-0.5725, -0.2425], [0.2425, 0.5725]]})
            self.assertIn(json.dumps(hint), requests[2]["prompt"])
            self.assertIn("This is the final attempt", requests[2]["prompt"])
            self.assertTrue(json.loads((work / "attempt_03/validation.json").read_text())["pass"])
            self.assertTrue((root / "registry" / work.name / "scene_spec.json").is_file())


if __name__ == "__main__":
    unittest.main()
