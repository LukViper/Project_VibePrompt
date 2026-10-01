"""Deterministic smoke tasks for harness validation — NOT the scientific RQ5 benchmark.

Label every use as HARNESS TEST.
"""

from __future__ import annotations

SMOKE_DATASET_LABEL = "HARNESS TEST — not a scientific RQ5 result"


def smoke_tasks() -> list[dict]:
    return [
        {
            "id": "SMOKE-001",
            "task_id": "add_function",
            "dataset_label": SMOKE_DATASET_LABEL,
            "problem_statement": "Create a function add(a, b) that returns the sum of two integers.",
            "conversation": [
                "Please create a Python function add(a, b).",
                "It must return a+b.",
                "Include a simple unit test.",
            ],
            "gold_requirements": ["implement add(a, b) returning a+b", "include unit test for add"],
            "requirement_ids": ["REQ-001", "REQ-002"],
            "constraints": ["python 3", "stdlib only"],
            "acceptance_criteria": ["add(2,3)==5", "test_add passes"],
            "acceptance_tests": ["test_add", "test_add"],
            "rejected_features": [],
            "seed_files": {
                "README.md": "# add_function smoke task\n",
            },
            "build_command": "python -m compileall -q .",
            "test_command": "python -m pytest -v --tb=line --junitxml=junit.xml",
        },
        {
            "id": "SMOKE-002",
            "task_id": "echo_endpoint",
            "dataset_label": SMOKE_DATASET_LABEL,
            "problem_statement": "Add a function echo(payload) that returns the same dict.",
            "conversation": [
                "Add an echo API-style function.",
                "echo(payload) must return payload unchanged.",
            ],
            "gold_requirements": ["implement echo(payload) returning payload"],
            "requirement_ids": ["REQ-001"],
            "constraints": ["pure function", "no network"],
            "acceptance_criteria": ["echo({'x':1})=={'x':1}"],
            "acceptance_tests": ["test_echo"],
            "rejected_features": [],
            "seed_files": {"README.md": "# echo_endpoint smoke task\n"},
            "build_command": "python -m compileall -q .",
            "test_command": "python -m pytest -v --tb=line --junitxml=junit.xml",
        },
        {
            "id": "SMOKE-003",
            "task_id": "preserve_behavior",
            "dataset_label": SMOKE_DATASET_LABEL,
            "problem_statement": "Modify greet to accept an optional title while preserving greet('Ada') == 'Hello, Ada'.",
            "conversation": [
                "There is an existing greet(name) function.",
                "Add optional title but keep existing behavior.",
            ],
            "gold_requirements": [
                "preserve greet('Ada') == 'Hello, Ada'",
                "support optional title argument",
            ],
            "requirement_ids": ["REQ-001", "REQ-002"],
            "constraints": ["do not break existing tests"],
            "acceptance_criteria": ["existing greet behavior preserved", "title optional"],
            "acceptance_tests": ["test_greet_default", "test_greet_title"],
            "rejected_features": [],
            "seed_files": {
                "greet.py": "def greet(name):\n    return f'Hello, {name}'\n",
                "test_greet.py": "from greet import greet\n\ndef test_greet_default():\n    assert greet('Ada') == 'Hello, Ada'\n",
            },
            "build_command": "python -m compileall -q .",
            "test_command": "python -m pytest -v --tb=line --junitxml=junit.xml",
        },
        {
            "id": "SMOKE-004",
            "task_id": "clamp_feature",
            "dataset_label": SMOKE_DATASET_LABEL,
            "problem_statement": "Implement clamp(x, lo, hi) with lo <= result <= hi.",
            "conversation": [
                "Implement clamp with explicit bounds constraint.",
            ],
            "gold_requirements": ["implement clamp(x, lo, hi)"],
            "requirement_ids": ["REQ-001"],
            "constraints": ["result must satisfy lo <= result <= hi"],
            "acceptance_criteria": ["clamp(5,0,3)==3"],
            "acceptance_tests": ["test_clamp"],
            "rejected_features": [],
            "seed_files": {"README.md": "# clamp smoke task\n"},
            "build_command": "python -m compileall -q .",
            "test_command": "python -m pytest -v --tb=line --junitxml=junit.xml",
        },
        {
            "id": "SMOKE-005",
            "task_id": "reject_logging",
            "dataset_label": SMOKE_DATASET_LABEL,
            "problem_statement": "Implement multiply(a,b). Do NOT add logging.",
            "conversation": [
                "Implement multiply(a,b).",
                "Do not add a logging feature — that was rejected.",
            ],
            "gold_requirements": ["implement multiply(a, b)"],
            "requirement_ids": ["REQ-001"],
            "constraints": ["no logging"],
            "acceptance_criteria": ["multiply(3,4)==12"],
            "acceptance_tests": ["test_multiply"],
            "rejected_features": ["add logging", "logging module"],
            "seed_files": {"README.md": "# multiply smoke task\n"},
            "build_command": "python -m compileall -q .",
            "test_command": "python -m pytest -v --tb=line --junitxml=junit.xml",
        },
    ]
