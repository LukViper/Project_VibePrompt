"""Tests for RQ5 run-matrix pilot subset selection (no full experiment)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="module")
def tasks_v2():
    from evaluation.datasets.rq5.generate_v2 import generate

    path, _manifest = generate()
    return json.loads(path.read_text(encoding="utf-8"))


def test_rq5_selection_no_arguments_is_full_grid(tasks_v2):
    from evaluation.rq5_agent_execution.prompts import VARIANTS
    from evaluation.rq5_agent_execution.run import select_run_matrix

    selected_tasks, selected_variants, meta = select_run_matrix(tasks_v2)
    assert len(selected_tasks) == 12
    assert selected_variants == tuple(VARIANTS)
    assert len(selected_variants) == 3
    assert meta["n_runs_planned"] == 36
    assert meta["n_runs_full_grid"] == 36
    assert meta["is_full_scientific_grid"] is True
    assert meta["selection_mode"] == "FULL_SCIENTIFIC"
    assert meta["filter_task_id"] is None
    assert meta["filter_variant"] is None


def test_rq5_selection_task_only_is_one_by_three(tasks_v2):
    from evaluation.rq5_agent_execution.prompts import VARIANTS
    from evaluation.rq5_agent_execution.run import select_run_matrix

    selected_tasks, selected_variants, meta = select_run_matrix(
        tasks_v2, task_id="rest_echo_api"
    )
    assert len(selected_tasks) == 1
    assert selected_tasks[0]["task_id"] == "rest_echo_api"
    assert selected_variants == tuple(VARIANTS)
    assert meta["n_runs_planned"] == 3
    assert meta["is_full_scientific_grid"] is False
    assert meta["selection_mode"] == "PILOT_SUBSET"
    assert set(meta["selected_variants"]) == set(VARIANTS)


def test_rq5_selection_variant_only_is_twelve_by_one(tasks_v2):
    from evaluation.rq5_agent_execution.run import select_run_matrix

    selected_tasks, selected_variants, meta = select_run_matrix(
        tasks_v2, variant="B_structured"
    )
    assert len(selected_tasks) == 12
    assert selected_variants == ("B_structured",)
    assert meta["n_runs_planned"] == 12
    assert meta["is_full_scientific_grid"] is False


def test_rq5_selection_task_and_variant_is_one_by_one(tasks_v2):
    from evaluation.rq5_agent_execution.run import select_run_matrix

    selected_tasks, selected_variants, meta = select_run_matrix(
        tasks_v2, task_id="rest_echo_api", variant="C_vibeprompt"
    )
    assert len(selected_tasks) == 1
    assert selected_variants == ("C_vibeprompt",)
    assert meta["n_runs_planned"] == 1
    assert meta["is_full_scientific_grid"] is False
    assert meta["filter_task_id"] == "rest_echo_api"
    assert meta["filter_variant"] == "C_vibeprompt"


def test_rq5_selection_comma_separated_intersection(tasks_v2):
    from evaluation.rq5_agent_execution.run import select_run_matrix

    selected_tasks, selected_variants, meta = select_run_matrix(
        tasks_v2,
        task_id="rest_echo_api,auth_token_service",
        variant="A_raw,C_vibeprompt",
    )
    assert [t["task_id"] for t in selected_tasks] == [
        "rest_echo_api",
        "auth_token_service",
    ]
    assert selected_variants == ("A_raw", "C_vibeprompt")
    assert meta["n_runs_planned"] == 4
    assert meta["is_full_scientific_grid"] is False
    assert meta["selection_mode"] == "PILOT_SUBSET"


def test_rq5_selection_invalid_task(tasks_v2):
    from evaluation.rq5_agent_execution.run import select_run_matrix

    with pytest.raises(ValueError, match="Invalid task-id"):
        select_run_matrix(tasks_v2, task_id="not_a_real_task")


def test_rq5_selection_invalid_variant(tasks_v2):
    from evaluation.rq5_agent_execution.run import select_run_matrix

    with pytest.raises(ValueError, match="Invalid variant"):
        select_run_matrix(tasks_v2, task_id="rest_echo_api", variant="D_fantasy")


def test_rq5_selection_invalid_in_csv_list(tasks_v2):
    from evaluation.rq5_agent_execution.run import select_run_matrix

    with pytest.raises(ValueError, match="Invalid task-id"):
        select_run_matrix(tasks_v2, task_id="rest_echo_api,nope")


def test_rq5_cli_invalid_task_exits_nonzero(tasks_v2, monkeypatch, capsys):
    from evaluation.rq5_agent_execution import run as rq5

    monkeypatch.setattr(
        sys,
        "argv",
        ["run", "--task-id", "totally_invalid_task"],
    )
    with pytest.raises(SystemExit) as exc:
        # Simulate __main__ path
        args = rq5.parse_args(["--task-id", "totally_invalid_task"])
        try:
            rq5.main(task_id=args.task_id, variant=args.variant)
        except ValueError as err:
            print(f"ERROR: {err}", file=sys.stderr)
            raise SystemExit(2) from err
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "Invalid task-id" in err


def test_rq5_filtered_metadata_not_full_grid(tasks_v2, monkeypatch, tmp_path):
    from evaluation.rq5_agent_execution import run as rq5
    import evaluation.common.reporting as reporting

    monkeypatch.delenv("VIBEPROMPT_AGENT_CMD", raising=False)
    monkeypatch.setattr(reporting, "new_run_dir", lambda prefix=None: tmp_path / f"run_{prefix}")
    monkeypatch.setattr(rq5, "new_run_dir", lambda prefix=None: tmp_path / f"run_{prefix}")
    payload = rq5.main(task_id="rest_echo_api")
    subset = payload["run_subset"]
    assert subset["is_full_scientific_grid"] is False
    assert subset["selection_mode"] == "PILOT_SUBSET"
    assert subset["n_runs_planned"] == 3
    assert (tmp_path / "run_rq5" / "rq5" / "run_subset.json").exists()
    written = json.loads((tmp_path / "run_rq5" / "rq5" / "run_subset.json").read_text())
    assert written["is_full_scientific_grid"] is False
    cfg = json.loads((tmp_path / "run_rq5" / "rq5" / "config.json").read_text())
    params = cfg.get("parameters") or cfg
    # config.json must not look like a full 12-task scientific study
    assert params["mode"] == "PILOT_SUBSET"
    assert params["n_tasks"] == 1
    assert params["task_ids"] == ["rest_echo_api"]
    assert params["is_full_scientific_grid"] is False
    assert params["dataset_n_tasks"] == 12


def test_rq5_full_grid_requires_explicit_ack(tasks_v2, monkeypatch):
    from evaluation.rq5_agent_execution.run import _enforce_full_grid_ack

    meta = {"is_full_scientific_grid": True, "n_runs_planned": 36}
    monkeypatch.delenv("VIBEPROMPT_RQ5_ALLOW_FULL_GRID", raising=False)
    with pytest.raises(ValueError, match="ALLOW_FULL_GRID"):
        _enforce_full_grid_ack(meta, agent_available=True)
    # Unavailable agent: NOT_EXECUTED path must still work without ack
    _enforce_full_grid_ack(meta, agent_available=False)
    monkeypatch.setenv("VIBEPROMPT_RQ5_ALLOW_FULL_GRID", "1")
    _enforce_full_grid_ack(meta, agent_available=True)
