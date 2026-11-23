import asyncio
import importlib
import json
import os
from pathlib import Path
import pickle
import random
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import numpy as np
import openai

from reports import extract_motiondisco_performance, performance_records
from scripts import karolina_performance
from shinka import performance
from shinka.llm.providers.local_openai import query_local_openai, query_local_openai_async


class PerformanceRecordingTests(unittest.TestCase):
    def test_nested_timing_and_interrupted_candidate(self):
        script = """
import sys
from shinka.performance import capture, phase
with capture(sys.argv[1], scene="test", generation=2):
    with phase("candidate_evaluation"):
        with phase("contact_check"):
            pass
        with phase("kso"):
            pass
        with phase("to"):
            with phase("physical_check"):
                pass
            print("ready", flush=True)
            import time
            time.sleep(60)
"""
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            trace = folder / "evaluation_performance.jsonl"
            env = {**os.environ, "MOTIONDISCO_PERFORMANCE": "1"}
            child = subprocess.Popen([sys.executable, "-c", script, str(trace)], env=env,
                                     stdout=subprocess.PIPE, text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(), "ready")
                child.kill()
                self.assertEqual(child.wait(timeout=5), -signal.SIGKILL)
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=5)
                child.stdout.close()
            with trace.open("a") as stream:
                stream.write('{"event":')
            row = performance_records.candidate_record(folder, folder)
        self.assertEqual(row["evaluation_trace_status"], "interrupted")
        self.assertEqual(row["open_timing_spans"], 2)
        self.assertIsNone(row["candidate_evaluation_s"])
        self.assertIsNone(row["to_s"])
        self.assertGreater(row["kso_s"], 0)
        self.assertGreater(row["physical_check_work_s"], 0)

    def test_exclusive_to_subtracts_overlap_once(self):
        def span(a, b):
            return tuple({"monotonic_ns": t * 10**9} for t in (a, b))
        exclusive = performance_records.exclusive_to([span(0, 10)], [span(2, 6), span(4, 8)], [])
        self.assertEqual(exclusive, 4)
        self.assertIsNone(performance_records.exclusive_to([span(0, 10)], [], [span(2, 3)[0]]))

    def test_seed_is_consumed_by_python_numpy(self):
        def draw(seed):
            performance.seed_python_numpy(seed)
            return random.random(), np.random.random()
        candidate_seed = performance.derive_seed(20261123, "evaluation", 2)
        self.assertEqual(draw(candidate_seed), draw(candidate_seed))
        self.assertNotEqual(draw(candidate_seed), draw(performance.derive_seed(20261123, "evaluation", 3)))

    def test_openai_sdk_sends_seeds_and_counts_transport_retries(self):
        # The installed SDK uses httpx2. Older SDKs use httpx.
        http = importlib.import_module(openai.DefaultHttpxClient.__mro__[1].__module__.split(".")[0])
        payloads = []

        def request_handler(request):
            payloads.append(json.loads(request.content))
            if len(payloads) == 1:
                return http.Response(500, headers={"retry-after-ms": "1"}, json={"error": {"message": "retry"}})
            return http.Response(200, json={
                "id": "mock", "object": "chat.completion", "created": 1, "model": "qwen2.5-coder:14b",
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"content": "ok", "role": "assistant"}}],
            })

        def send(path):
            from shinka.llm import client as clients

            transport = http.MockTransport(request_handler)
            default = openai.DefaultHttpxClient
            with patch.object(openai, "DefaultHttpxClient",
                              side_effect=lambda **kw: default(transport=transport, trust_env=False, **kw)), \
                 patch.object(clients, "OPENAI_MAX_RETRIES", 1):
                client, model, _ = clients.get_client_llm("local/qwen2.5-coder:14b@http://localhost:11434/v1")
                with performance.capture(path, generation=2):
                    args = (client, model, "user", "system", [], None)
                    query_local_openai(*args)
                    query_local_openai(*args)
                    query_local_openai(*args, seed=0)
                client.close()

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "proposal_performance.jsonl"
            with patch.dict(os.environ, {"MOTIONDISCO_PERFORMANCE": "1",
                                         "MOTIONDISCO_SEED": "20261123", "MOTIONDISCO_OLLAMA_SEED": "1",
                                         "SHINKA_PRICING_MODE": "offline"}):
                send(path)
            row = performance_records.candidate_record(path.parent, path.parent)
        seeds = [body["seed"] for body in payloads]
        self.assertEqual(seeds[0], seeds[1])
        self.assertNotEqual(seeds[1], seeds[2])
        self.assertEqual(seeds[3], 0)
        self.assertEqual(row["candidate_llm_requests"], 4)
        self.assertEqual(json.loads(row["llm_request_seeds"]), seeds)

    def test_async_provider_passes_the_derived_seed(self):
        reply = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content="ok", reasoning_content=None))], usage=None)
        create = AsyncMock(return_value=reply)
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            "MOTIONDISCO_PERFORMANCE": "1", "MOTIONDISCO_SEED": "20261123", "MOTIONDISCO_OLLAMA_SEED": "1",
            "SHINKA_PRICING_MODE": "offline",
        }):
            with performance.capture(Path(directory) / "p.jsonl", generation=2):
                asyncio.run(query_local_openai_async(client, "qwen", "user", "system", [], None))
        self.assertEqual(create.await_args.kwargs["seed"], performance.derive_seed(20261123, "candidate_chat", 2, 0))

    def _run_sampler(self, folder, nvidia_smi, expected_event):
        smi = folder / "nvidia-smi"
        smi.write_text("#!/bin/sh\n" + nvidia_smi)
        smi.chmod(0o755)
        gpu = folder / "gpu.jsonl"
        env = {**os.environ, "PATH": f"{folder}:{os.environ['PATH']}",
               "SLURM_STEP_GPUS": "7", "CUDA_VISIBLE_DEVICES": "0"}
        child = subprocess.Popen(
            [sys.executable, str(Path(karolina_performance.__file__)), "sample", str(gpu), "42_5"],
            env=env,
        )
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if performance_records.last_event(performance_records.events(gpu), expected_event):
                    break
                time.sleep(0.02)
            else:
                self.fail(f"{expected_event} was not written")
            child.terminate()
            self.assertEqual(child.wait(timeout=5), 0)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
        self.assertEqual(performance_records.events(gpu)[-1]["event"], "sampler_end")
        return gpu

    def test_sampler_uses_visible_uuid_for_remapped_slurm_id(self):
        nvidia_smi = """
case "$3" in
    ''|--id=GPU-test) echo 'GPU-test, NVIDIA A100, 32, 8000, 40000' ;;
    *) echo 'No devices were found'; exit 6 ;;
esac
"""
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            gpu = self._run_sampler(folder, nvidia_smi, "gpu_sample")
            events = performance_records.events(gpu)
            self.assertFalse(performance_records.last_event(events, "sampler_error"))
            self.assertEqual(performance_records.last_event(events, "sampler_selection")["devices"], ["GPU-test"])
            row = performance_records.run_record(folder, None, gpu, {"batch_gpu_util_tres": "77"}, [])
            self.assertEqual(row["gpu_util_source"], "slurm_tres")
            self.assertEqual(row["gpu_vram_source"], "nvidia-smi")
            self.assertEqual(row["gpu_sampled_util_mean_pct"], 32)
            self.assertEqual(row["gpu_sampled_vram_peak_mib"], 8000)

    def test_sampler_keeps_slurm_id_if_extra_gpus_are_visible_and_reports_query_failure(self):
        nvidia_smi = """
if [ -z "$3" ]; then
    echo 'GPU-one, NVIDIA A100, 32, 8000, 40000'
    echo 'GPU-two, NVIDIA A100, 21, 4000, 40000'
else
    echo 'No devices were found'
    echo 'diagnostic stderr' >&2
    exit 6
fi
"""
        with tempfile.TemporaryDirectory() as directory:
            gpu = self._run_sampler(Path(directory), nvidia_smi, "sampler_error")
            events = performance_records.events(gpu)
            error = performance_records.last_event(events, "sampler_error")
        self.assertFalse(performance_records.last_event(events, "gpu_sample"))
        self.assertEqual(error["command"][-1], "--id=7")
        self.assertEqual(error["exit_code"], 6)
        self.assertEqual(error["stdout"], "No devices were found\n")
        self.assertEqual(error["stderr"], "diagnostic stderr\n")

    def test_generated_search_reports_http_budget_and_saved_reach_evidence(self):
        extractor = extract_motiondisco_performance
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outputs = root / "results"
            workflow = outputs / "qwen_generated" / "audit_scene"
            solver = workflow / "motiondisco"
            (solver / ".hydra").mkdir(parents=True)
            scene = "generated.audit_scene"
            (outputs / "md-qwen-generate-42.out").write_text(f"Run artifacts: {workflow}\nBudget exhausted\n")
            (outputs / "md-qwen-generate-server-42.log").write_text(
                '[GIN] now | 200 | 2.0s | localhost | POST "/api/generate"\n'
                '[GIN] now | 200 | 3.0s | localhost | POST "/v1/chat/completions"\n'
                '[GIN] now | 500 | 0.5s | localhost | POST "/v1/embeddings"\n'
            )
            for name, payload in {
                "result.json": {"status": "solved", "scene": scene, "launcher_exit_code": 0},
                "validation.json": {"pass": True, "target_xyz_m": [1, 0, 0.775]},
                "task_catalog.json": {"tasks": {"reach_position": {"completion_check": {"maximum_error_m": 0.10}}}},
            }.items():
                (workflow / name).write_text(json.dumps(payload))
            (solver / ".hydra/config.yaml").write_text(f"task:\n  scene: {scene}\nevo_config:\n  num_generations: 3\n")
            for generation, terminal_x in enumerate((0.95, 0.87)):
                result = solver / f"gen_{generation}/results"
                result.mkdir(parents=True)
                verdict = {"to_valid": True, "to_converged": True, "to_cost": 1.0, "goal_match": True,
                           "ik_feasible": True}
                (result / "metrics.json").write_text(json.dumps({"combined_score": 0.5, "public": verdict}))
                (result / "extra.json").write_text(json.dumps({
                    **verdict, "to_physical": {"pass": True}, "contact_mode_seq": {"left_sole": [[1, 1], []]},
                    "task_completion": {"met": True, "target_xyz_m": [0.87, 0, 0.775], "maximum_error_m": 0.15},
                }))
                states = np.array([[0, 0, 0.775], [terminal_x, 0, 0.775]])
                (result / "to_run.pkl").write_bytes(pickle.dumps(
                    {"results": {"robot_xs": {"robot": states}}}, protocol=pickle.HIGHEST_PROTOCOL
                ))
            jobs = {"42": {"JobName": "md-qwen-generate", "State": "COMPLETED",
                           "ElapsedRaw": "3600", "AllocTRES": "cpu=8,gres/gpu=1"}}
            run, = extractor.discover(root, jobs, [])
            record, candidates = extractor.run_record(root, jobs, [], run, True)
            scene_record, = extractor.summarize([record], {record["results_path"]: candidates})
            self.assertEqual(record["scene_workflow_status"], "solved")
            self.assertEqual(record["scene_search_status"], "budget_underfilled")
            self.assertEqual(record["scene_generate_request_s"], 2)
            self.assertEqual(record["llm_chat_request_s"], 3)
            self.assertEqual(record["embedding_http_errors"], 1)
            self.assertEqual(record["task_completed"], 1)
            self.assertEqual(record["distinct_usable_contact_plans"], 1)
            self.assertEqual(scene_record["alloc_gpu_h_per_usable"], 0.5)
            self.assertEqual(scene_record["alloc_gpu_h_per_completed"], 1)
            self.assertFalse(candidates[1]["task_values"]["agrees_with_evaluator"])
            self.assertAlmostEqual(candidates[1]["task_values"]["error_m"], 0.13)
            (solver / "gen_0/results/to_run.pkl").unlink()
            self.assertEqual(extractor.run_record(root, jobs, [], run, True)[1][0]["semantic_basis"],
                             "trajectory_missing")

    def test_gpu_sampling_status_distinguishes_unrecorded_failed_and_measured_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "gpu.jsonl"

            def summarize():
                return performance_records.run_record(None, None, path, {}, [])

            self.assertEqual(summarize()["gpu_sampling_status"], "unrecorded")
            performance.append_event(path, "sampler_error")
            self.assertEqual(summarize()["gpu_sampling_status"], "failed")
            self.assertEqual(summarize()["gpu_sample_count"], 0)
            performance.append_event(path, "gpu_sample", uuid="GPU-test", gpu_model="A100",
                                     gpu_util_pct=0, vram_used_mib=0, vram_total_mib=40960)
            summary = summarize()
            self.assertEqual(summary["gpu_sampling_status"], "partial")
            self.assertEqual(summary["gpu_sampled_util_mean_pct"], 0)
            self.assertEqual(summary["gpu_sampler_error_records"], 1)


if __name__ == "__main__":
    unittest.main()
