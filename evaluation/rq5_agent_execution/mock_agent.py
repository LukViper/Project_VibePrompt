"""Deterministic mock coding agent for HARNESS TEST only — implements tasks_v2 stubs."""

from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> int:
    task_dir = Path(os.environ["VIBEPROMPT_TASK_DIR"])
    task_id = os.environ.get("VIBEPROMPT_TASK_ID", "")
    meta_path = task_dir / "VIBEPROMPT_META.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    tid = task_id or meta.get("task_id") or ""

    writers = {
        "rest_echo_api": _echo,
        "auth_token_service": _auth,
        "crud_notes": _notes,
        "log_parser": _parser,
        "csv_filter_cli": _csv,
        "word_count_pipeline": _words,
        "todo_backend": _todos,
        "url_shortener": _shortener,
        "rate_limiter": _limiter,
        "file_checksum": _checksum,
        "json_schema_validator": _validate,
        "metrics_aggregator": _metrics,
        # legacy smoke ids
        "add_function": _legacy_add,
        "echo_endpoint": _legacy_echo,
        "preserve_behavior": _legacy_greet,
        "clamp_feature": _legacy_clamp,
        "reject_logging": _legacy_multiply,
    }
    fn = writers.get(tid)
    if fn:
        fn(task_dir)
    else:
        (task_dir / "agent_done.txt").write_text(f"mock completed task_id={tid}\n", encoding="utf-8")

    print(f"mock_agent completed task_id={tid} label=HARNESS_TEST")
    return 0


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _echo(d: Path) -> None:
    _write(
        d / "app/echo_api.py",
        "def echo(payload):\n    return payload\n\ndef health():\n    return {'status': 'ok'}\n",
    )


def _auth(d: Path) -> None:
    _write(
        d / "app/auth.py",
        "USERS = {}\n\n"
        "def register(username, password):\n"
        "    USERS[username] = password\n\n"
        "def login(username, password):\n"
        "    if USERS.get(username) != password:\n"
        "        raise ValueError('bad credentials')\n"
        "    return f'token-{username}'\n",
    )


def _notes(d: Path) -> None:
    _write(
        d / "app/notes.py",
        "NOTES = {}\n_id = 0\n\n"
        "def create_note(text):\n"
        "    global _id\n"
        "    _id += 1\n"
        "    NOTES[_id] = {'id': _id, 'text': text}\n"
        "    return _id\n\n"
        "def list_notes():\n"
        "    return list(NOTES.values())\n",
    )


def _parser(d: Path) -> None:
    _write(
        d / "app/parser.py",
        "def parse_log(line):\n"
        "    parts = line.split()\n"
        "    return {'timestamp': parts[0], 'severity': parts[1], 'message': ' '.join(parts[2:])}\n",
    )


def _csv(d: Path) -> None:
    _write(
        d / "app/csv_filter.py",
        "def filter_rows(rows, column, value):\n"
        "    return [r for r in rows if r.get(column) == value]\n",
    )


def _words(d: Path) -> None:
    _write(
        d / "app/words.py",
        "def count_words(text):\n"
        "    counts = {}\n"
        "    for w in text.split():\n"
        "        counts[w] = counts.get(w, 0) + 1\n"
        "    return counts\n",
    )


def _todos(d: Path) -> None:
    _write(
        d / "app/todos.py",
        "TODOS = {}\n_id = 0\n\n"
        "def add_todo(title):\n"
        "    global _id\n"
        "    _id += 1\n"
        "    TODOS[_id] = {'title': title, 'done': False}\n"
        "    return _id\n\n"
        "def complete_todo(todo_id):\n"
        "    TODOS[todo_id]['done'] = True\n",
    )


def _shortener(d: Path) -> None:
    _write(
        d / "app/shortener.py",
        "STORE = {}\n_n = 0\n\n"
        "def shorten(url):\n"
        "    global _n\n"
        "    _n += 1\n"
        "    code = f'c{_n}'\n"
        "    STORE[code] = url\n"
        "    return code\n\n"
        "def resolve(code):\n"
        "    return STORE[code]\n",
    )


def _limiter(d: Path) -> None:
    _write(
        d / "app/limiter.py",
        "COUNTS = {}\n\n"
        "def allow(key, limit):\n"
        "    COUNTS[key] = COUNTS.get(key, 0) + 1\n"
        "    return COUNTS[key] <= limit\n",
    )


def _checksum(d: Path) -> None:
    _write(
        d / "app/checksum.py",
        "import hashlib\nfrom pathlib import Path\n\n"
        "def checksum(path):\n"
        "    data = Path(path).read_bytes()\n"
        "    return hashlib.sha256(data).hexdigest()\n",
    )


def _validate(d: Path) -> None:
    _write(
        d / "app/validate.py",
        "def validate(data, required_keys):\n"
        "    return all(k in data for k in required_keys)\n",
    )


def _metrics(d: Path) -> None:
    _write(
        d / "app/metrics.py",
        "def aggregate(values):\n"
        "    values = list(values)\n"
        "    return {'count': len(values), 'mean': sum(values) / len(values)}\n",
    )


def _legacy_add(d: Path) -> None:
    _write(d / "add_mod.py", "def add(a, b):\n    return a + b\n")
    _write(d / "test_add.py", "from add_mod import add\n\ndef test_add():\n    assert add(2, 3) == 5\n")


def _legacy_echo(d: Path) -> None:
    _write(d / "echo_mod.py", "def echo(payload):\n    return payload\n")
    _write(d / "test_echo.py", "from echo_mod import echo\n\ndef test_echo():\n    assert echo({'x': 1}) == {'x': 1}\n")


def _legacy_greet(d: Path) -> None:
    _write(
        d / "greet.py",
        "def greet(name, title=None):\n"
        "    if title:\n"
        "        return f'Hello, {title} {name}'\n"
        "    return f'Hello, {name}'\n",
    )
    _write(
        d / "test_greet.py",
        "from greet import greet\n\n"
        "def test_greet_default():\n    assert greet('Ada') == 'Hello, Ada'\n\n"
        "def test_greet_title():\n    assert greet('Ada', title='Dr') == 'Hello, Dr Ada'\n",
    )


def _legacy_clamp(d: Path) -> None:
    _write(d / "clamp_mod.py", "def clamp(x, lo, hi):\n    return max(lo, min(hi, x))\n")
    _write(d / "test_clamp.py", "from clamp_mod import clamp\n\ndef test_clamp():\n    assert clamp(5, 0, 3) == 3\n")


def _legacy_multiply(d: Path) -> None:
    _write(d / "multiply_mod.py", "def multiply(a, b):\n    return a * b\n")
    _write(
        d / "test_multiply.py",
        "from multiply_mod import multiply\n\ndef test_multiply():\n    assert multiply(3, 4) == 12\n",
    )


if __name__ == "__main__":
    raise SystemExit(main())
