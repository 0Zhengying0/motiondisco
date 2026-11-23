"""Generate, validate, register and solve declarative Qwen scenes."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import mkdtemp
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from examples.loco_manipulation.register_generated import SCENES_DIR
from examples.loco_manipulation.scene_campaign import valid_plans
from shinka.performance import SEED_LIMIT, capture, configured_seed, event, phase, source_revision, timed, tracing

from .catalogs import DIRECTORY, ROOT, read_json, write_json
from .novelty import reference_layouts
from .register import register_spec
from .validate import validate


def request(host, path, timeout, payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = Request(f"{host.rstrip('/')}{path}", data=body, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=timeout) as response:
        return json.load(response)


@timed("scene_generation")
def generate(args, work):
    artifacts = {
        name: read_json(DIRECTORY / name)
        for name in ("asset_catalog.json", "task_catalog.json", "scene_spec.schema.json")
    }
    for name, content in artifacts.items():
        write_json(work / name, content)
    novelty = [{"support_forest": sig, "existing_scenes": names} for sig, names in reference_layouts().items()]
    prompt = (DIRECTORY / "prompt.txt").read_text(encoding="utf-8")
    for name, content in artifacts.items():
        prompt += f"\n{name}\n" + json.dumps(content, ensure_ascii=False)
    prompt += ("\nExisting support forests to avoid (each entry is [asset_id, children], with floor implicit):\n"
               + json.dumps(novelty))
    prompt += f'\nUse scene_id "{work.name}" for this run.'
    if args.brief:
        prompt += f"\nDesign brief: {args.brief}"

    versions = {"host": args.host, "requested_model": args.model}
    write_json(work / "model.json", versions)
    versions["server"] = request(args.host, "/api/version", args.request_timeout)
    versions["model"] = next((entry for entry in request(args.host, "/api/tags", args.request_timeout)["models"]
                              if args.model in (entry["name"], entry.get("model"))), None)
    write_json(work / "model.json", versions)
    if versions["model"] is None:
        raise ValueError(f"Cached model {args.model!r} was not found in Ollama")
    feedback = None
    for attempt in range(1, args.attempts + 1):
        folder = work / f"attempt_{attempt:02d}"
        folder.mkdir()
        attempt_prompt = prompt
        if feedback:
            raw, report = feedback
            attempt_prompt += ("\nRevise the previous proposal using the validator feedback. "
                               "For a box on a support, center_abs_limits_xy_m bounds the absolute local center "
                               "offset on each axis for the current yaw. A negative limit means it does not fit "
                               "on that axis. For a separation_hint, move the named instance along an axis "
                               "with a nonempty center_ranges_m list; each pair is a [min, max] range for that "
                               "local center coordinate, with the other box and yaw held fixed. Keep the other "
                               "coordinate inside its center limit. Resolve all "
                               "errors together. If local changes would recreate an earlier failure, change "
                               "the layout or place a movable box on clear floor space. Return the entire "
                               "corrected JSON object.\nPrevious response:\n" + raw +
                               "\nValidator feedback:\n" + json.dumps(report["errors"], ensure_ascii=False))
            if attempt == args.attempts:
                attempt_prompt += ("\nThis is the final attempt. If the placement is still difficult, use a simpler "
                                   "layout, for example one catalog object on the floor beside a clear walking route. "
                                   "Keep the task and follow all SceneSpec constraints.")
        (folder / "prompt.txt").write_text(attempt_prompt, encoding="utf-8")
        payload = {"model": args.model, "prompt": attempt_prompt, "stream": False, "format": "json",
                   "options": {"temperature": 0.7, "num_ctx": 8192, "num_predict": 1600}}
        attempt_seed = (args.seed + attempt - 1) % SEED_LIMIT if args.seed is not None else None
        if attempt_seed is not None:
            payload["options"]["seed"] = attempt_seed
        write_json(folder / "request.json", payload)
        event("scene_llm_request", attempt=attempt, model=args.model, seed=attempt_seed)
        try:
            with phase("scene_ollama_generate"):
                answer = request(args.host, "/api/generate", args.request_timeout, payload)
        except (OSError, ValueError) as exc:
            error = {"type": type(exc).__name__, "message": str(exc),
                     "http_status": exc.code if isinstance(exc, HTTPError) else None}
            write_json(folder / "request_error.json", error)
            event("scene_llm_error", attempt=attempt, model=args.model, error_type=error["type"],
                  http_status=error["http_status"])
            raise
        write_json(folder / "ollama_response.json", answer)
        durations = ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration")
        event("scene_llm_response", attempt=attempt, model=answer.get("model"), done_reason=answer.get("done_reason"),
              **{name + "_ns": answer.get(name) for name in durations},
              prompt_eval_count=answer.get("prompt_eval_count"), eval_count=answer.get("eval_count"))
        raw = answer["response"]
        (folder / "response.txt").write_text(raw, encoding="utf-8")
        try:
            write_json(folder / "scene_spec.json", json.loads(raw))
        except ValueError:
            pass  # The exact original text is preserved even for malformed JSON.
        with phase("scene_validation_registration"):
            scene, report = register_spec(raw, SCENES_DIR)
        write_json(folder / "validation.json", report)
        event("scene_validation_result", attempt=attempt, accepted=bool(scene), registered_scene=scene,
              error_codes=sorted({issue["code"] for issue in report["errors"]}))
        print(f"Scene attempt {attempt}: {'registered ' + scene if scene else report['errors']}", flush=True)
        if scene:
            write_json(work / "scene_spec.json", read_json(Path(SCENES_DIR) / scene.partition(".")[2] / "scene_spec.json"))
            write_json(work / "validation.json", report)
            return scene
        feedback = raw, report
    return None


@timed("scene_motiondisco_search")
def solve(scene, output, nodes):
    registered = Path(SCENES_DIR) / scene.partition(".")[2]
    metadata = read_json(registered / "spec.json")
    command = [
        str(Path(sys.executable).with_name("motiondisco_launch")), "task=loco_manipulation",
        "variant=ollama_local", "database=island_small", "evolution=small_budget", "cluster=local",
        f"task.scene={scene}", f'task.description="{metadata["description"]}"',
        "task.score_mode=quality",
        "evo_config.init_program_path=examples/loco_manipulation/scene_generation/walking_seed.py",
        f"evo_config.num_generations={nodes}", "evo_config.max_api_costs=100",
        "++evo_config.evolve_prompts=false", "++evo_config.meta_rec_interval=null",
        "max_evaluation_jobs=1", "max_proposal_jobs=1", f"output_dir={output}",
    ]
    result = subprocess.run(command, cwd=ROOT, check=False)
    plans = [plan for plan in valid_plans(str(output)).values()
             if (output / plan["gen"] / "results" / "to_run.pkl").is_file()]
    return result.returncode, plans


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="command", required=True)
    generate_parser = modes.add_parser("generate", help="generate with Ollama and register after validation")
    generate_parser.add_argument("--out", type=Path, default=ROOT / "results/qwen_generated")
    generate_parser.add_argument("--model", default="qwen2.5-coder:14b")
    generate_parser.add_argument("--host", default="http://127.0.0.1:11434")
    generate_parser.add_argument("--attempts", type=int, default=5)
    generate_parser.add_argument("--request-timeout", type=float, default=600)
    generate_parser.add_argument("--seed", type=int)
    generate_parser.add_argument("--brief")
    generate_parser.add_argument("--solve", action="store_true")
    generate_parser.add_argument("--nodes", type=int, default=10)
    validate_parser = modes.add_parser("validate", help="validate a SceneSpec locally")
    validate_parser.add_argument("path", type=Path)
    solve_parser = modes.add_parser("solve", help="solve a previously registered SceneSpec")
    solve_parser.add_argument("scene")
    solve_parser.add_argument("--out", type=Path, required=True)
    solve_parser.add_argument("--nodes", type=int, default=10)
    args = parser.parse_args()
    if args.command == "validate":
        _, report = validate(args.path.read_bytes())
        print(json.dumps(report, indent=2))
        return 0 if report["pass"] else 1
    if args.nodes < 1:
        parser.error("--nodes must be positive")
    if args.command == "solve":
        from .spec import ID_PATTERN
        import re

        if not re.fullmatch(r"generated\." + ID_PATTERN.removeprefix("^"), args.scene):
            parser.error("Expected a registered scene name of the form generated.<scene_id>")
        registry = Path(SCENES_DIR) / args.scene.partition(".")[2]
        if not (registry / "scene_spec.json").is_file():
            parser.error("The scene must have been registered from a validated SceneSpec")
        args.out = args.out.resolve()
        args.out.mkdir(parents=True, exist_ok=True)
        work = args.out
        scene = args.scene
    else:
        if args.attempts < 1 or args.request_timeout <= 0:
            parser.error("--attempts and --request-timeout must be positive")
        if args.seed is not None and not 0 <= args.seed < SEED_LIMIT:
            parser.error(f"--seed must be an integer in [0, {SEED_LIMIT - 1}]")
        args.out.mkdir(parents=True, exist_ok=True)
        prefix = datetime.now(timezone.utc).strftime("qwen_%y%m%d_%H%M%S_")
        work = Path(mkdtemp(prefix=prefix, dir=args.out)).resolve()
        print(f"Run artifacts: {work}", flush=True)
        scene = None

    job_id = os.environ.get("MOTIONDISCO_JOB_ID") or os.environ.get("SLURM_JOB_ID")
    result = {"status": "started", "scene": scene, "job_id": job_id}
    with capture(work / "scene_generation_performance.jsonl", run_id=work.name):
        write_json(work / "result.json", result)
        try:
            solver_seed = configured_seed()
            if args.command == "generate":
                generation_seed_source = "--seed" if args.seed is not None else os.environ.get("MOTIONDISCO_SEED_SOURCE")
                if args.seed is None:
                    args.seed = solver_seed
                if tracing():
                    event("scene_generation_config", model=args.model, attempts=args.attempts, generation_seed=args.seed,
                          generation_seed_source=generation_seed_source, solver_seed=solver_seed,
                          python_hash_seed=os.environ.get("PYTHONHASHSEED"),
                          solve=args.solve, node_budget=args.nodes if args.solve else None,
                          motiondisco=source_revision(ROOT, "shinka", "examples/loco_manipulation", "scripts", "pyproject.toml"),
                          faro=source_revision(ROOT / "submodules/faro", "src", "extern", "pyproject.toml"))
                scene = generate(args, work)
                result.update(scene=scene, status="registered" if scene else "validation_exhausted")
            if scene and (args.command == "solve" or args.solve):
                output = work / "motiondisco"
                write_json(work / "result.json", {**result, "status": "solving", "solver_output": str(output)})
                code, plans = solve(scene, output, args.nodes)
                status = "solved" if plans else ("solver_failed" if code else "no_valid_trajectory")
                result.update(status=status,
                              launcher_exit_code=code, solver_output=str(output), valid_plans=plans)
        except (OSError, URLError, ValueError, KeyError, subprocess.SubprocessError) as exc:
            result.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        write_json(work / "result.json", result)
        event("scene_workflow_result", status=result["status"], registered_scene=scene,
              valid_trajectory_count=len(result.get("valid_plans", ())))
    print(json.dumps(result, indent=2), flush=True)
    return 0 if result["status"] in ("registered", "solved") else 1


if __name__ == "__main__":
    sys.exit(main())
