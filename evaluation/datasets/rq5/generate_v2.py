"""Generate RQ5 tasks_v2 — controlled seeds, real acceptance tests, rejected features.

Does NOT overwrite tasks_v1.json.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "evaluation" / "datasets" / "rq5" / "tasks_v2.json"
MANIFEST = ROOT / "evaluation" / "datasets" / "rq5" / "tasks_v2_manifest.json"
DATASET_LABEL = "SYNTHETIC CONTROLLED BENCHMARK"
DATASET_ID = "vibeprompt-synthetic-bench/rq5"
DATASET_VERSION = "2.0.0"


def _tasks() -> list[dict]:
    return [
        {
            "id": "RQ5-V2-001",
            "task_id": "rest_echo_api",
            "problem_statement": "Build an echo function that returns JSON payloads unchanged.",
            "conversation": [
                "I need a simple echo API helper in Python.",
                "Implement echo(payload) that returns the same dict.",
                "Must support a health() function returning {'status': 'ok'}.",
                "Do not add Redis caching.",
                "Use only the Python standard library.",
            ],
            "gold_requirements": [
                "implement echo(payload) returning the same mapping",
                "implement health() returning status ok",
            ],
            "constraints": ["python 3.11+", "stdlib only", "no network in tests"],
            "rejected_features": ["Do not add Redis", "Do not call external APIs"],
            "acceptance_criteria": [
                "echo({'a': 1}) == {'a': 1}",
                "health()['status'] == 'ok'",
            ],
            "acceptance_tests": ["test_echo_returns_payload", "test_health_ok"],
            "build_command": "python -m compileall -q .",
            "test_command": "python -m pytest -v --tb=line --junitxml=junit.xml",
            "seed_files": {
                "README.md": "# rest_echo_api\nImplement app/echo_api.py\n",
                "app/__init__.py": "",
                "app/echo_api.py": (
                    "def echo(payload):\n"
                    "    raise NotImplementedError('implement echo')\n\n"
                    "def health():\n"
                    "    raise NotImplementedError('implement health')\n"
                ),
                "tests/test_echo_api.py": (
                    "from app.echo_api import echo, health\n\n"
                    "def test_echo_returns_payload():\n"
                    "    assert echo({'a': 1}) == {'a': 1}\n\n"
                    "def test_health_ok():\n"
                    "    assert health()['status'] == 'ok'\n"
                ),
            },
        },
        {
            "id": "RQ5-V2-002",
            "task_id": "auth_token_service",
            "problem_statement": "In-memory token auth helpers.",
            "conversation": [
                "Build a tiny auth helper.",
                "register(username, password) must store the user.",
                "login(username, password) must return a token string on success.",
                "Do not expose a DELETE user endpoint.",
                "No external database.",
            ],
            "gold_requirements": [
                "register(username, password) stores the user",
                "login(username, password) returns a token on success",
            ],
            "constraints": ["in-memory only", "python 3.11+"],
            "rejected_features": ["Do not expose a DELETE user endpoint", "Do not use an external database"],
            "acceptance_criteria": [
                "register then login returns a non-empty token",
                "login with wrong password fails",
            ],
            "acceptance_tests": ["test_register_and_login", "test_login_rejects_bad_password"],
            "build_command": "python -m compileall -q .",
            "test_command": "python -m pytest -v --tb=line --junitxml=junit.xml",
            "seed_files": {
                "README.md": "# auth_token_service\n",
                "app/__init__.py": "",
                "app/auth.py": (
                    "USERS = {}\n\n"
                    "def register(username, password):\n"
                    "    raise NotImplementedError\n\n"
                    "def login(username, password):\n"
                    "    raise NotImplementedError\n"
                ),
                "tests/test_auth.py": (
                    "import pytest\n"
                    "from app import auth\n\n"
                    "def setup_function():\n"
                    "    auth.USERS.clear()\n\n"
                    "def test_register_and_login():\n"
                    "    auth.register('ada', 'secret')\n"
                    "    token = auth.login('ada', 'secret')\n"
                    "    assert isinstance(token, str) and token\n\n"
                    "def test_login_rejects_bad_password():\n"
                    "    auth.register('ada', 'secret')\n"
                    "    with pytest.raises(Exception):\n"
                    "        auth.login('ada', 'wrong')\n"
                ),
            },
        },
        {
            "id": "RQ5-V2-003",
            "task_id": "crud_notes",
            "problem_statement": "In-memory notes CRUD without delete.",
            "conversation": [
                "Create an in-memory notes store.",
                "create_note(text) returns an id.",
                "list_notes() returns all notes.",
                "Do not implement delete_note.",
            ],
            "gold_requirements": [
                "create_note(text) returns an id",
                "list_notes() returns created notes",
            ],
            "constraints": ["in-memory", "python 3.11+"],
            "rejected_features": ["Do not implement delete_note", "Do not use Redis"],
            "acceptance_criteria": ["create then list contains the note"],
            "acceptance_tests": ["test_create_and_list"],
            "build_command": "python -m compileall -q .",
            "test_command": "python -m pytest -v --tb=line --junitxml=junit.xml",
            "seed_files": {
                "README.md": "# crud_notes\n",
                "app/__init__.py": "",
                "app/notes.py": (
                    "NOTES = {}\n\n"
                    "def create_note(text):\n"
                    "    raise NotImplementedError\n\n"
                    "def list_notes():\n"
                    "    raise NotImplementedError\n"
                ),
                "tests/test_notes.py": (
                    "from app import notes\n\n"
                    "def setup_function():\n"
                    "    notes.NOTES.clear()\n\n"
                    "def test_create_and_list():\n"
                    "    nid = notes.create_note('hello')\n"
                    "    items = notes.list_notes()\n"
                    "    assert any(n.get('id') == nid or n.get('text') == 'hello' for n in items)\n"
                ),
            },
        },
        {
            "id": "RQ5-V2-004",
            "task_id": "log_parser",
            "problem_statement": "Parse a syslog-like line into severity and timestamp.",
            "conversation": [
                "Parse lines like: '2024-01-01T00:00:00Z INFO boot'.",
                "parse_log(line) returns dict with severity and timestamp.",
                "Do not call an external log API.",
            ],
            "gold_requirements": [
                "parse_log extracts severity",
                "parse_log extracts timestamp",
            ],
            "constraints": ["stdlib only"],
            "rejected_features": ["Do not call an external log API"],
            "acceptance_criteria": ["parses sample line"],
            "acceptance_tests": ["test_parse_severity", "test_parse_timestamp"],
            "build_command": "python -m compileall -q .",
            "test_command": "python -m pytest -v --tb=line --junitxml=junit.xml",
            "seed_files": {
                "README.md": "# log_parser\n",
                "app/__init__.py": "",
                "app/parser.py": "def parse_log(line):\n    raise NotImplementedError\n",
                "tests/test_parser.py": (
                    "from app.parser import parse_log\n\n"
                    "SAMPLE = '2024-01-01T00:00:00Z INFO boot'\n\n"
                    "def test_parse_severity():\n"
                    "    assert parse_log(SAMPLE)['severity'] == 'INFO'\n\n"
                    "def test_parse_timestamp():\n"
                    "    assert parse_log(SAMPLE)['timestamp'] == '2024-01-01T00:00:00Z'\n"
                ),
            },
        },
        {
            "id": "RQ5-V2-005",
            "task_id": "csv_filter_cli",
            "problem_statement": "Filter CSV rows by column equality.",
            "conversation": [
                "Implement filter_rows(rows, column, value) for list-of-dicts CSV rows.",
                "Do not add SQL database support.",
            ],
            "gold_requirements": ["filter_rows keeps matching rows"],
            "constraints": ["pure function"],
            "rejected_features": ["Do not add SQL database support"],
            "acceptance_criteria": ["filters correctly"],
            "acceptance_tests": ["test_filter_rows"],
            "build_command": "python -m compileall -q .",
            "test_command": "python -m pytest -v --tb=line --junitxml=junit.xml",
            "seed_files": {
                "README.md": "# csv_filter_cli\n",
                "app/__init__.py": "",
                "app/csv_filter.py": "def filter_rows(rows, column, value):\n    raise NotImplementedError\n",
                "tests/test_csv_filter.py": (
                    "from app.csv_filter import filter_rows\n\n"
                    "def test_filter_rows():\n"
                    "    rows = [{'name': 'a', 'x': 1}, {'name': 'b', 'x': 2}]\n"
                    "    assert filter_rows(rows, 'name', 'a') == [{'name': 'a', 'x': 1}]\n"
                ),
            },
        },
        {
            "id": "RQ5-V2-006",
            "task_id": "word_count_pipeline",
            "problem_statement": "Count words in a string.",
            "conversation": [
                "Implement count_words(text) returning a dict of word→count.",
                "Do not download remote corpora.",
            ],
            "gold_requirements": ["count_words returns frequency dict"],
            "constraints": ["stdlib only"],
            "rejected_features": ["Do not download remote corpora"],
            "acceptance_criteria": ["counts words"],
            "acceptance_tests": ["test_count_words"],
            "build_command": "python -m compileall -q .",
            "test_command": "python -m pytest -v --tb=line --junitxml=junit.xml",
            "seed_files": {
                "README.md": "# word_count_pipeline\n",
                "app/__init__.py": "",
                "app/words.py": "def count_words(text):\n    raise NotImplementedError\n",
                "tests/test_words.py": (
                    "from app.words import count_words\n\n"
                    "def test_count_words():\n"
                    "    assert count_words('a a b') == {'a': 2, 'b': 1}\n"
                ),
            },
        },
        {
            "id": "RQ5-V2-007",
            "task_id": "todo_backend",
            "problem_statement": "Minimal todo store.",
            "conversation": [
                "add_todo(title) and complete_todo(id).",
                "Do not add multi-user auth.",
            ],
            "gold_requirements": ["add_todo creates a todo", "complete_todo marks done"],
            "constraints": ["in-memory"],
            "rejected_features": ["Do not add multi-user auth"],
            "acceptance_criteria": ["add and complete"],
            "acceptance_tests": ["test_add_todo", "test_complete_todo"],
            "build_command": "python -m compileall -q .",
            "test_command": "python -m pytest -v --tb=line --junitxml=junit.xml",
            "seed_files": {
                "README.md": "# todo_backend\n",
                "app/__init__.py": "",
                "app/todos.py": (
                    "TODOS = {}\n\n"
                    "def add_todo(title):\n"
                    "    raise NotImplementedError\n\n"
                    "def complete_todo(todo_id):\n"
                    "    raise NotImplementedError\n"
                ),
                "tests/test_todos.py": (
                    "from app import todos\n\n"
                    "def setup_function():\n"
                    "    todos.TODOS.clear()\n\n"
                    "def test_add_todo():\n"
                    "    tid = todos.add_todo('x')\n"
                    "    assert tid in todos.TODOS or any(True for _ in [tid])\n"
                    "    assert todos.TODOS\n\n"
                    "def test_complete_todo():\n"
                    "    tid = todos.add_todo('x')\n"
                    "    todos.complete_todo(tid)\n"
                    "    item = todos.TODOS[tid]\n"
                    "    assert item.get('done') is True or item.get('completed') is True\n"
                ),
            },
        },
        {
            "id": "RQ5-V2-008",
            "task_id": "url_shortener",
            "problem_statement": "Shorten and resolve URLs in memory.",
            "conversation": [
                "shorten(url) returns a code; resolve(code) returns the url.",
                "Do not use an external shortening API.",
            ],
            "gold_requirements": ["shorten returns a code", "resolve returns original url"],
            "constraints": ["in-memory"],
            "rejected_features": ["Do not use an external shortening API"],
            "acceptance_criteria": ["roundtrip"],
            "acceptance_tests": ["test_shorten_resolve"],
            "build_command": "python -m compileall -q .",
            "test_command": "python -m pytest -v --tb=line --junitxml=junit.xml",
            "seed_files": {
                "README.md": "# url_shortener\n",
                "app/__init__.py": "",
                "app/shortener.py": (
                    "STORE = {}\n\n"
                    "def shorten(url):\n"
                    "    raise NotImplementedError\n\n"
                    "def resolve(code):\n"
                    "    raise NotImplementedError\n"
                ),
                "tests/test_shortener.py": (
                    "from app.shortener import shorten, resolve\n\n"
                    "def test_shorten_resolve():\n"
                    "    code = shorten('https://example.com')\n"
                    "    assert resolve(code) == 'https://example.com'\n"
                ),
            },
        },
        {
            "id": "RQ5-V2-009",
            "task_id": "rate_limiter",
            "problem_statement": "Allow at most N calls per key.",
            "conversation": [
                "allow(key, limit) returns True until limit exceeded.",
                "Do not use Redis.",
            ],
            "gold_requirements": ["allow enforces per-key limit"],
            "constraints": ["in-memory"],
            "rejected_features": ["Do not use Redis"],
            "acceptance_criteria": ["third call blocked when limit=2"],
            "acceptance_tests": ["test_rate_limit"],
            "build_command": "python -m compileall -q .",
            "test_command": "python -m pytest -v --tb=line --junitxml=junit.xml",
            "seed_files": {
                "README.md": "# rate_limiter\n",
                "app/__init__.py": "",
                "app/limiter.py": (
                    "COUNTS = {}\n\n"
                    "def allow(key, limit):\n"
                    "    raise NotImplementedError\n"
                ),
                "tests/test_limiter.py": (
                    "from app import limiter\n\n"
                    "def setup_function():\n"
                    "    limiter.COUNTS.clear()\n\n"
                    "def test_rate_limit():\n"
                    "    assert limiter.allow('k', 2) is True\n"
                    "    assert limiter.allow('k', 2) is True\n"
                    "    assert limiter.allow('k', 2) is False\n"
                ),
            },
        },
        {
            "id": "RQ5-V2-010",
            "task_id": "file_checksum",
            "problem_statement": "SHA256 hex digest of file bytes.",
            "conversation": [
                "checksum(path) returns sha256 hex.",
                "Do not upload files to the cloud.",
            ],
            "gold_requirements": ["checksum returns sha256 hex digest"],
            "constraints": ["stdlib hashlib"],
            "rejected_features": ["Do not upload files to the cloud"],
            "acceptance_criteria": ["matches hashlib"],
            "acceptance_tests": ["test_checksum"],
            "build_command": "python -m compileall -q .",
            "test_command": "python -m pytest -v --tb=line --junitxml=junit.xml",
            "seed_files": {
                "README.md": "# file_checksum\n",
                "app/__init__.py": "",
                "app/checksum.py": "def checksum(path):\n    raise NotImplementedError\n",
                "tests/test_checksum.py": (
                    "import hashlib\nfrom pathlib import Path\nfrom app.checksum import checksum\n\n"
                    "def test_checksum(tmp_path):\n"
                    "    p = tmp_path / 'f.txt'\n"
                    "    p.write_bytes(b'abc')\n"
                    "    assert checksum(p) == hashlib.sha256(b'abc').hexdigest()\n"
                ),
            },
        },
        {
            "id": "RQ5-V2-011",
            "task_id": "json_schema_validator",
            "problem_statement": "Validate dict has required keys.",
            "conversation": [
                "validate(data, required_keys) returns True iff all keys present.",
                "Do not call a remote schema registry.",
            ],
            "gold_requirements": ["validate checks required keys"],
            "constraints": ["pure function"],
            "rejected_features": ["Do not call a remote schema registry"],
            "acceptance_criteria": ["accepts valid rejects invalid"],
            "acceptance_tests": ["test_validate_ok", "test_validate_missing"],
            "build_command": "python -m compileall -q .",
            "test_command": "python -m pytest -v --tb=line --junitxml=junit.xml",
            "seed_files": {
                "README.md": "# json_schema_validator\n",
                "app/__init__.py": "",
                "app/validate.py": "def validate(data, required_keys):\n    raise NotImplementedError\n",
                "tests/test_validate.py": (
                    "from app.validate import validate\n\n"
                    "def test_validate_ok():\n"
                    "    assert validate({'a': 1}, ['a']) is True\n\n"
                    "def test_validate_missing():\n"
                    "    assert validate({}, ['a']) is False\n"
                ),
            },
        },
        {
            "id": "RQ5-V2-012",
            "task_id": "metrics_aggregator",
            "problem_statement": "Aggregate numeric metrics.",
            "conversation": [
                "aggregate(values) returns {'count': n, 'mean': m}.",
                "Do not stream metrics to Kafka.",
            ],
            "gold_requirements": ["aggregate returns count and mean"],
            "constraints": ["pure function"],
            "rejected_features": ["Do not stream metrics to Kafka"],
            "acceptance_criteria": ["mean of 1,2,3 is 2"],
            "acceptance_tests": ["test_aggregate"],
            "build_command": "python -m compileall -q .",
            "test_command": "python -m pytest -v --tb=line --junitxml=junit.xml",
            "seed_files": {
                "README.md": "# metrics_aggregator\n",
                "app/__init__.py": "",
                "app/metrics.py": "def aggregate(values):\n    raise NotImplementedError\n",
                "tests/test_metrics.py": (
                    "from app.metrics import aggregate\n\n"
                    "def test_aggregate():\n"
                    "    out = aggregate([1, 2, 3])\n"
                    "    assert out['count'] == 3\n"
                    "    assert out['mean'] == 2\n"
                ),
            },
        },
    ]


def generate() -> tuple[Path, dict]:
    rows = []
    for t in _tasks():
        rows.append(
            {
                **t,
                "synthetic": True,
                "dataset_label": DATASET_LABEL,
                "dataset_id": DATASET_ID,
                "dataset_version": DATASET_VERSION,
            }
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(rows, indent=2) + "\n"
    OUT.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    manifest = {
        "dataset_id": DATASET_ID,
        "dataset_version": DATASET_VERSION,
        "dataset_hash": f"sha256:{digest}",
        "dataset_label": DATASET_LABEL,
        "n_tasks": len(rows),
        "task_ids": [r["task_id"] for r in rows],
        "path": str(OUT.relative_to(ROOT)),
        "frozen": True,
        "note": "Do not modify during a registered scientific RQ5 study.",
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return OUT, manifest


if __name__ == "__main__":
    path, meta = generate()
    print(json.dumps({"path": str(path), **meta}, indent=2))
