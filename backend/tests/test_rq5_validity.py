"""RQ5 validity-repair tests — mock agent only; no scientific execution."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))


@pytest.fixture(scope="module")
def tasks_v2():
    from evaluation.datasets.rq5.generate_v2 import generate

    path, manifest = generate()
    tasks = json.loads(path.read_text(encoding="utf-8"))
    return tasks, manifest


def test_rq5_c_uses_real_vibeprompt_pipeline(tasks_v2):
    tasks, _ = tasks_v2
    from evaluation.rq5_agent_execution.c_pipeline import run_vibeprompt_c_pipeline

    task = tasks[0]
    out = run_vibeprompt_c_pipeline(task["conversation"], task=task)
    pipe = out["provenance"]["pipeline"]
    assert pipe[0] == "conversation"
    assert "apply_analysis_to_state" in pipe
    assert "compilation_gate" in pipe
    assert "render_prompt" in pipe
    assert out["method"] == "vibeprompt_c_pipeline"
    assert "ProjectState" in pipe


def test_rq5_c_compiles_project_state(tasks_v2):
    tasks, _ = tasks_v2
    from evaluation.rq5_agent_execution.prompts import build_prompts_with_provenance

    bundle = build_prompts_with_provenance(tasks[0])["C_vibeprompt"]
    assert bundle["provenance"]["gate"] is not None
    assert bundle["prompt"]
    assert len(bundle["prompt"]) > 40


def test_rq5_c_excludes_non_compilable_requirements(tasks_v2):
    tasks, _ = tasks_v2
    from evaluation.rq5_agent_execution.c_pipeline import run_vibeprompt_c_pipeline
    from app.services.assertion_lifecycle import requirement_is_compilable

    out = run_vibeprompt_c_pipeline(tasks[0]["conversation"], task=tasks[0])
    for item in out["provenance"]["gate"].get("included_requirements") or []:
        assert requirement_is_compilable(
            {
                "status": "active",
                "assertion_status": item.get("assertion_status") or "CONFIRMED",
            }
        )
    for item in out["provenance"].get("excluded_non_compilable") or []:
        assert not requirement_is_compilable(
            {
                "status": "active",
                "assertion_status": item.get("assertion_status") or "PROPOSED",
            }
        )


def test_rq5_seed_repository_is_identical_across_variants(tasks_v2, tmp_path):
    tasks, _ = tasks_v2
    from evaluation.rq5_agent_execution.workspace import create_workspace

    task = tasks[0]
    trees = []
    for variant in ("A_raw", "B_structured", "C_vibeprompt"):
        ws = create_workspace(
            root=tmp_path / variant,
            task_id=task["task_id"],
            system_variant=variant,
            prompt_text=f"prompt-{variant}",
            seed_files=task["seed_files"],
        )
        tree = tuple(
            sorted(
                p.relative_to(ws.path).as_posix()
                for p in ws.path.rglob("*")
                if p.is_file()
                and p.name not in {"TASK.md", "VIBEPROMPT_META.json"}
                and ".git" not in p.parts
            )
        )
        trees.append((ws.seed_commit, tree))
    assert trees[0][1] == trees[1][1] == trees[2][1]
    assert all(t[0] for t in trees)


def test_rq5_acceptance_tests_are_real(tasks_v2):
    tasks, _ = tasks_v2
    for task in tasks:
        assert task.get("acceptance_tests")
        seed = task["seed_files"]
        test_files = [k for k in seed if k.startswith("tests/") and k.endswith(".py")]
        assert test_files, f"no real tests for {task['task_id']}"
        body = "\n".join(seed[k] for k in test_files)
        for name in task["acceptance_tests"]:
            assert f"def {name}" in body, f"{name} missing in {task['task_id']}"
        impl = "\n".join(v for k, v in seed.items() if k.startswith("app/") and k.endswith(".py"))
        assert "NotImplementedError" in impl


def test_rq5_rejected_features_are_evaluable(tasks_v2):
    tasks, _ = tasks_v2
    from evaluation.rq5_agent_execution.verifier import unsupported_feature_signals

    for task in tasks:
        assert task.get("rejected_features"), task["task_id"]
    redis_task = next(t for t in tasks if any("Redis" in f for f in t["rejected_features"]))
    hits = unsupported_feature_signals(redis_task, "import redis\nclient=redis.Redis()\n", [])
    assert hits


def test_rq5_captures_untracked_files(tmp_path):
    from evaluation.rq5_agent_execution.workspace import capture_git_state, create_workspace

    ws = create_workspace(
        root=tmp_path,
        task_id="t",
        system_variant="A_raw",
        prompt_text="p",
        seed_files={"README.md": "seed\n"},
    )
    (ws.path / "brand_new_agent_file.py").write_text("x=1\n", encoding="utf-8")
    state = capture_git_state(ws)
    names = set(state["created_files"]) | set(state.get("untracked_files") or [])
    assert "brand_new_agent_file.py" in names
    assert "brand_new_agent_file" in state["git_diff"]


def test_rq5_excludes_infrastructure_failures_from_quality_means():
    from evaluation.rq5_agent_execution.metrics import compute_rq5_metrics

    runs = [
        {
            "system_variant": "A_raw",
            "execution_status": "FAILED_INFRASTRUCTURE",
            "requirement_verifications": [{"status": "FAIL"}],
            "unsupported_features": [],
            "constraint_violations": [],
            "scope_violations": [],
            "build_status": "FAIL",
            "test_status": "FAIL",
        },
        {
            "system_variant": "A_raw",
            "execution_status": "EXECUTED_WITH_VALIDATION",
            "requirement_verifications": [{"status": "PASS"}, {"status": "PASS"}],
            "unsupported_features": [],
            "constraint_violations": [],
            "scope_violations": [],
            "build_status": "PASS",
            "test_status": "PASS",
        },
    ]
    m = compute_rq5_metrics(runs)
    assert m["failed_runs"] == 1
    assert m["successful_runs"] == 1
    assert m["completed_agent_quality"]["requirement_coverage"]["mean"] == 1.0
    assert m["completed_agent_quality"]["n"] == 1
    assert m["full_execution_grid"]["n"] == 2


def test_rq5_reports_full_execution_grid():
    from evaluation.rq5_agent_execution.metrics import compute_rq5_metrics

    runs = [
        {
            "system_variant": "B_structured",
            "execution_status": "EXECUTED",
            "requirement_verifications": [{"status": "UNVERIFIED"}],
            "unsupported_features": [],
            "build_status": "NOT_CONFIGURED",
            "test_status": "NOT_CONFIGURED",
        }
    ]
    m = compute_rq5_metrics(runs)
    assert "full_execution_grid" in m
    assert "completed_agent_quality" in m


def test_rq5_reports_per_variant_metrics():
    from evaluation.rq5_agent_execution.metrics import compute_rq5_metrics

    runs = []
    for v in ("A_raw", "B_structured", "C_vibeprompt"):
        runs.append(
            {
                "system_variant": v,
                "execution_status": "EXECUTED_WITH_VALIDATION",
                "requirement_verifications": [{"status": "PASS"}],
                "unsupported_features": [],
                "build_status": "PASS",
                "test_status": "PASS",
            }
        )
    m = compute_rq5_metrics(runs)
    for v in ("A_raw", "B_structured", "C_vibeprompt"):
        assert v in m
        assert m[v]["requirement_coverage"]["n"] == 1
        assert "ci95_low" in m[v]["requirement_coverage"]


def test_rq5_top_level_status_reflects_failures():
    from evaluation.rq5_agent_execution.metrics import aggregate_experiment_status

    assert aggregate_experiment_status([], agent_available=False) == "NOT_EXECUTED"
    mixed = [
        {"execution_status": "FAILED_INFRASTRUCTURE"},
        {"execution_status": "EXECUTED_WITH_VALIDATION"},
    ]
    assert aggregate_experiment_status(mixed, agent_available=True) == "EXECUTED_WITH_FAILURES"
    all_ok = [{"execution_status": "EXECUTED_WITH_VALIDATION"} for _ in range(3)]
    assert aggregate_experiment_status(all_ok, agent_available=True) == "EXECUTED_COMPLETE"


def test_rq5_dataset_hash_is_recorded(tasks_v2):
    _, manifest = tasks_v2
    assert manifest["dataset_hash"].startswith("sha256:")
    raw = (ROOT / "evaluation/datasets/rq5/tasks_v2.json").read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert manifest["dataset_hash"] == f"sha256:{digest}"
    assert manifest["n_tasks"] == 12
    assert len(manifest["task_ids"]) == 12
