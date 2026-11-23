#!/usr/bin/env python3
# Modified by the MotionDisco authors from ShinkaEvolve (Sakana AI, Apache-2.0); see NOTICE.
import os
from pathlib import Path

import hydra
from omegaconf import DictConfig, OmegaConf
from shinka.env import load_shinka_dotenv
from shinka.core import ShinkaEvolveRunner
from shinka.configs import register_resolvers
from shinka.performance import capture, configured_seed, enabled, event, phase, seed_python_numpy, source_revision

# Register custom OmegaConf resolvers (e.g. ${py:...}) before
# @hydra.main composes any config that uses them. Idempotent.
register_resolvers()


def run_with_cfg(cfg: DictConfig) -> None:
    load_shinka_dotenv()
    seed = configured_seed()
    if seed is not None:
        seed_python_numpy(seed)
    if not enabled():
        _run_search(cfg)
        return

    run_dir = Path(cfg.output_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    scene = OmegaConf.select(cfg, "task.scene")
    root = Path(__file__).resolve().parents[1]
    with capture(run_dir / "run_performance.jsonl", scene=scene, run_id=run_dir.name):
        event(
            "run_config",
            seed=seed,
            seed_source=os.environ.get("MOTIONDISCO_SEED_SOURCE", "MOTIONDISCO_SEED") if seed is not None else None,
            seed_consumers=["python.random", "numpy.random"] if seed is not None else [],
            python_hash_seed=os.environ.get("PYTHONHASHSEED"),
            ollama_seed_enabled=os.environ.get("MOTIONDISCO_OLLAMA_SEED") == "1" and seed is not None,
            motiondisco=source_revision(root, "shinka", "examples/loco_manipulation", "scripts", "pyproject.toml"),
            faro=source_revision(root / "submodules/faro", "src", "extern", "pyproject.toml"),
            node_budget=OmegaConf.select(cfg, "evo_config.num_generations"),
            model_names=list(OmegaConf.select(cfg, "evo_config.llm_models") or []),
            initial_condition=OmegaConf.select(cfg, "task.initial_condition"),
        )
        with phase("search"):
            _run_search(cfg)


def _run_search(cfg: DictConfig) -> None:
    print("Experiment configurations:")
    print(OmegaConf.to_yaml(cfg, resolve=True))

    task_sys_msg = OmegaConf.select(cfg, "evo_config.task_sys_msg")
    if task_sys_msg:
        print("=" * 60)
        print("TASK SYSTEM PROMPT")
        print("=" * 60)
        print(task_sys_msg)
        print("=" * 60)

    job_cfg = hydra.utils.instantiate(cfg.job_config)
    db_cfg = hydra.utils.instantiate(cfg.db_config)
    evo_cfg = hydra.utils.instantiate(cfg.evo_config)
    max_evaluation_jobs = int(cfg.get("max_evaluation_jobs", 4))
    max_proposal_jobs = int(cfg.get("max_proposal_jobs", 6))
    max_db_workers = int(cfg.get("max_db_workers", 2))

    evo_runner = ShinkaEvolveRunner(
        evo_config=evo_cfg,
        job_config=job_cfg,
        db_config=db_cfg,
        verbose=cfg.verbose,
        max_evaluation_jobs=max_evaluation_jobs,
        max_proposal_jobs=max_proposal_jobs,
        max_db_workers=max_db_workers,
    )
    evo_runner.run()


@hydra.main(config_path="configs", config_name="config", version_base=None)
def main(cfg: DictConfig):
    run_with_cfg(cfg)


if __name__ == "__main__":
    main()
