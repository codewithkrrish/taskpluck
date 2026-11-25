"""End-to-end CLI tests (taskpluck.cli via subprocess)."""

import json
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_ARGS = ["--base-date", "2026-11-25"]

NOTES = """# Standup — 25 Nov 2026

## Action items

- [ ] Krrish to send the Q3 report by Friday
- [ ] Asha will review the onboarding copy by Dec 2
- [ ] Book the demo room for Thursday

TODO: chase the vendor invoice by 2026-12-01
"""


def run_cli(args, input_text=None, cwd=None):
    env = dict(os.environ, PYTHONPATH=REPO_ROOT)
    return subprocess.run(
        [sys.executable, "-m", "taskpluck", *args],
        input=input_text,
        capture_output=True,
        text=True,
        cwd=cwd or REPO_ROOT,
        env=env,
    )


@pytest.fixture()
def notes_file(tmp_path):
    path = tmp_path / "notes.md"
    path.write_text(NOTES, encoding="utf-8")
    return str(path)


def test_cli_markdown_stdout(notes_file):
    result = run_cli([*BASE_ARGS, notes_file])
    assert result.returncode == 0, result.stderr
    assert "## Krrish" in result.stdout
    assert "- [ ] send the Q3 report — due 2026-11-27" in result.stdout
    assert "- [ ] review the onboarding copy — due 2026-12-02" in result.stdout
    assert "- [ ] Book the demo room — due 2026-11-26" in result.stdout
    assert "- [ ] chase the vendor invoice — due 2026-12-01" in result.stdout


def test_cli_stdin(notes_file):
    with open(notes_file, encoding="utf-8") as handle:
        text = handle.read()
    result = run_cli([*BASE_ARGS, "-"], input_text=text)
    assert result.returncode == 0, result.stderr
    assert "send the Q3 report" in result.stdout


def test_cli_json_format(notes_file):
    result = run_cli([*BASE_ARGS, "--format", "json", notes_file])
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert len(payload) == 4
    by_task = {entry["task"]: entry for entry in payload}
    assert by_task["send the Q3 report"]["owner"] == "Krrish"
    assert by_task["send the Q3 report"]["due"] == "2026-11-27"
    assert by_task["Book the demo room"]["owner"] is None


def test_cli_no_items_exit_code_1(tmp_path):
    empty = tmp_path / "empty.md"
    empty.write_text("Just a normal meeting.\nNothing to do here.\n", encoding="utf-8")
    result = run_cli([str(empty)])
    assert result.returncode == 1
    assert "no action items found" in result.stderr


def test_cli_missing_file_exit_code_2():
    result = run_cli(["does-not-exist.md"])
    assert result.returncode == 2
    assert "no such file" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_bad_flag_exit_code_2():
    result = run_cli(["--nope"])
    assert result.returncode == 2


def test_cli_bad_date_exit_code_2(notes_file):
    result = run_cli(["--since", "25-11-2026", notes_file])
    assert result.returncode == 2
    assert "YYYY-MM-DD" in result.stderr


def test_cli_output_file_and_no_overwrite(notes_file, tmp_path):
    out = tmp_path / "todos.md"
    result = run_cli([*BASE_ARGS, notes_file, "-o", str(out)])
    assert result.returncode == 0, result.stderr
    assert out.read_text(encoding="utf-8").startswith("# Action items")
    # Second run without --force must refuse, and leave the file alone.
    before = out.read_text(encoding="utf-8")
    result = run_cli([*BASE_ARGS, notes_file, "-o", str(out)])
    assert result.returncode == 2
    assert "already exists" in result.stderr
    assert out.read_text(encoding="utf-8") == before
    # --force overwrites.
    result = run_cli([*BASE_ARGS, notes_file, "-o", str(out), "--force"])
    assert result.returncode == 0, result.stderr


def test_cli_dry_run_writes_nothing(notes_file, tmp_path):
    out = tmp_path / "todos.md"
    result = run_cli([*BASE_ARGS, notes_file, "-o", str(out), "--dry-run"])
    assert result.returncode == 0, result.stderr
    assert not out.exists()
    assert "send the Q3 report" in result.stdout
    assert "dry run" in result.stderr


def test_cli_since_filter(notes_file):
    result = run_cli([*BASE_ARGS, "--since", "2026-12-01", notes_file])
    assert result.returncode == 0, result.stderr
    # Dec 2 is on/after Dec 1, so it stays; the November items must go.
    assert "send the Q3 report" not in result.stdout
    assert "Book the demo room" not in result.stdout
    assert "review the onboarding copy" in result.stdout
    assert "chase the vendor invoice" in result.stdout


def test_cli_owner_filter(notes_file):
    result = run_cli([*BASE_ARGS, "--owner", "asha", notes_file])
    assert result.returncode == 0, result.stderr
    assert "review the onboarding copy" in result.stdout
    assert "send the Q3 report" not in result.stdout


def test_cli_rollup_week(notes_file):
    result = run_cli([*BASE_ARGS, "--rollup", "week", notes_file])
    assert result.returncode == 0, result.stderr
    assert "## Week of 2026-11-23" in result.stdout
    assert "## Week of 2026-11-30" in result.stdout


def test_cli_multiple_files_dedup(tmp_path):
    first = tmp_path / "a.md"
    second = tmp_path / "b.md"
    first.write_text("- [ ] Send the Q3 report by Friday\n", encoding="utf-8")
    second.write_text("- [ ] send the Q3 report by Friday\n", encoding="utf-8")
    result = run_cli([*BASE_ARGS, "--format", "json", str(first), str(second)])
    assert result.returncode == 0, result.stderr
    assert len(json.loads(result.stdout)) == 1


def test_cli_corrupt_input_does_not_crash(tmp_path):
    # Binary garbage decodes with replacement characters instead of dying.
    raw = tmp_path / "raw.md"
    raw.write_bytes(b"- [ ] send the report by Friday\n\xff\xfe\x00binary junk\n")
    result = run_cli([*BASE_ARGS, str(raw)])
    assert result.returncode == 0, result.stderr
    assert "send the report" in result.stdout


def test_cli_version():
    result = run_cli(["--version"])
    assert result.returncode == 0
    assert "taskpluck 1.0.0" in result.stdout
