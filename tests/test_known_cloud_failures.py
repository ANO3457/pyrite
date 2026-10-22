"""The brief is executable, shared by cloud startup and worker guidance."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/known_cloud_failures.py"


def test_empty_registry_is_silent(tmp_path):
    registry = tmp_path / "empty.json"
    registry.write_text("[]", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(registry)], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


def test_default_brief_names_live_tests_and_does_not_waive_ci():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, result.stderr
    registry = json.loads((ROOT / "scripts/known-cloud-failures.json").read_text())
    for record in registry:
        file, function = record["test"].split("::")
        assert f"def {function}(" in (ROOT / file).read_text()
        assert record["test"] in result.stdout
        assert record["issue"] in result.stdout
    assert "not a CI waiver" in result.stdout
    assert (
        'python3 "$dir/scripts/known_cloud_failures.py"'
        in (ROOT / "scripts/cloud-session-start.sh").read_text()
    )
    for path in ("AGENTS.md", ".claude/skills/pyrite-dev/SKILL.md"):
        assert "scripts/known-cloud-failures.json" in (ROOT / path).read_text()


def test_memory_canary_points_at_its_open_tracking_issue():
    registry = json.loads((ROOT / "scripts/known-cloud-failures.json").read_text())
    canary = next(r for r in registry if "test_apps_a_test_builds" in r["test"])
    assert canary["issue"] == "https://github.com/pyrite-wiki/pyrite/issues/1110"
