"""Frontmatter Pyrite cannot model is refused for writes and reported, with the line (#760 (b)).

Maintainer decision, 2026-10-15: a file whose frontmatter ``apply()`` cannot
model (a tagged key, a complex key, a duplicate key) gets no write through
Pyrite, body included; the update is refused with ``apply()``'s reason
(`VALIDATION_FAILED`). Such a file must not be invisible: ``index health``
and ``qa validate`` list "frontmatter Pyrite cannot model: N files", each
with its path, the line and the reason.

The oracle for the line is the fixture text: the offending key is on a line
written by hand here, never computed from the module under test.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from pyrite.cli import app
from pyrite.config import KBConfig, PyriteConfig, Settings
from pyrite.exceptions import ValidationError
from pyrite.services.access_policy import UNSCOPED
from pyrite.services.kb_service import KBService
from pyrite.services.qa_service import QAService
from pyrite.storage.database import PyriteDB
from pyrite.storage.file_operations import FrontmatterSpan
from pyrite.storage.index import IndexManager
from pyrite.utils.frontmatter import Frontmatter, split_frontmatter

KB = "shapes"

#: name -> (file text, 1-based line of the key Pyrite cannot model, a word of the reason)
SHAPES: dict[str, tuple[str, int, str]] = {
    "tagged-key": (
        "---\nid: tagged\ntitle: Tagged\ntype: note\n!!str flag: 1\n---\n\nText.\n",
        5,
        "tagged key",
    ),
    "complex-key": (
        "---\nid: complex\ntitle: Complex\ntype: note\n? [a, b]\n: 1\n---\n\nText.\n",
        5,
        "complex key",
    ),
    "duplicate-key": (
        "---\nid: dup\ntitle: Dup\ntype: note\nyear: 2025\nyear: 2026\n---\n\nText.\n",
        6,
        "duplicate key",
    ),
}

GOOD = "---\nid: good\ntitle: Good\ntype: note\n---\n\nText.\n"


def _env(tmp_path: Path, names: list[str]) -> tuple[PyriteConfig, dict[str, Path]]:
    kb_path = tmp_path / "kb"
    (kb_path / "notes").mkdir(parents=True)
    (kb_path / "notes" / "good.md").write_text(GOOD, encoding="utf-8")
    paths = {}
    for name in names:
        text, _line, _word = SHAPES[name]
        paths[name] = kb_path / "notes" / f"{name}.md"
        paths[name].write_text(text, encoding="utf-8")
    config = PyriteConfig(
        knowledge_bases=[KBConfig(name=KB, path=kb_path, kb_type="generic")],
        settings=Settings(index_path=tmp_path / "index.db", auto_embed=False),
    )
    db = PyriteDB(config.settings.index_path)
    try:
        IndexManager(db, config).index_all()
    finally:
        db.close()
    return config, paths


@pytest.mark.parametrize("name", sorted(SHAPES))
def test_index_health_lists_the_file_with_its_line_and_reason(tmp_path: Path, name: str):
    config, paths = _env(tmp_path, [name])
    _text, line, word = SHAPES[name]
    db = PyriteDB(config.settings.index_path)
    try:
        health = IndexManager(db, config).check_health()
    finally:
        db.close()

    rows = health["unmodellable_frontmatter"]
    assert [Path(r["path"]).name for r in rows] == [f"{name}.md"], rows
    assert rows[0]["kb"] == KB
    assert rows[0]["line"] == line
    assert word in rows[0]["reason"]


def test_index_health_cli_counts_them_and_warns(tmp_path: Path):
    config, _paths = _env(tmp_path, sorted(SHAPES))
    with (
        patch("pyrite.cli.context.load_config", return_value=config),
        patch("pyrite.cli.load_config", return_value=config),
    ):
        result = CliRunner().invoke(app, ["index", "health", "-k", KB, "--format", "json"])
    payload = json.loads(result.output[result.output.index("{") :])
    assert len(payload["unmodellable_frontmatter"]) == 3, payload
    assert payload["status"] in ("warning", "unhealthy"), payload["status"]
    for row in payload["unmodellable_frontmatter"]:
        assert set(row) >= {"kb", "path", "line", "reason"}, row

    with (
        patch("pyrite.cli.context.load_config", return_value=config),
        patch("pyrite.cli.load_config", return_value=config),
    ):
        rich = CliRunner().invoke(app, ["index", "health", "-k", KB, "--format", "rich"])
    assert "3 file(s) whose frontmatter Pyrite cannot model" in rich.output, rich.output
    assert ":5" in rich.output and ":6" in rich.output, rich.output


@pytest.mark.parametrize("name", sorted(SHAPES))
def test_qa_validate_reports_the_file_with_its_line(tmp_path: Path, name: str):
    config, paths = _env(tmp_path, [name])
    _text, line, word = SHAPES[name]
    db = PyriteDB(config.settings.index_path)
    try:
        report = QAService(config, db).validate_kb(KB, readable_kbs=UNSCOPED)
    finally:
        db.close()

    found = [i for i in report["issues"] if i.get("rule") == "frontmatter_unmodellable"]
    assert len(found) == 1, report["issues"]
    issue = found[0]
    assert issue["severity"] == "error"
    assert issue["line"] == line
    assert word in issue["message"] and f"line {line}" in issue["message"]
    assert Path(issue["path"]).name == f"{name}.md"


@pytest.mark.parametrize("name", ["tagged-key", "complex-key"])
def test_an_update_of_such_a_file_is_refused_with_the_reason_and_nothing_written(
    tmp_path: Path, name: str
):
    """A duplicate key cannot be addressed by id at all (the loader refuses
    the file), so only the two loadable shapes reach the write."""
    config, paths = _env(tmp_path, [name])
    before = paths[name].read_bytes()
    entry_id = {"tagged-key": "tagged", "complex-key": "complex"}[name]
    db = PyriteDB(config.settings.index_path)
    try:
        with pytest.raises(ValidationError) as info:
            KBService(config, db).update(entry_id, KB, {"body": "new body"})
    finally:
        db.close()
    assert SHAPES[name][2] in str(info.value)
    assert info.value.error_code == "VALIDATION_FAILED"
    assert paths[name].read_bytes() == before


def _span(text: str) -> FrontmatterSpan:
    split = split_frontmatter(text)
    assert isinstance(split, Frontmatter)
    return FrontmatterSpan(split.yaml_start, split.close_start, split.close_end)


def unmodellable_reason(text: str, span: FrontmatterSpan):
    # Imported here, not at the top: the file must collect without the
    # change, so that every other test in it is red for its own reason.
    from pyrite.storage.file_operations import unmodellable_reason as rule

    return rule(text, span)


@pytest.mark.parametrize("name", sorted(SHAPES))
def test_unmodellable_reason_names_the_shape_and_its_line(name: str):
    text, line, word = SHAPES[name]
    got = unmodellable_reason(text, _span(text))
    assert got is not None
    assert word in got[0] and got[1] == line


@pytest.mark.parametrize(
    "text",
    [
        GOOD,
        "\ufeff---\r\nid: g\r\ntitle: G\r\nflag: no\r\n---\r\n\r\nText.\r\n",
        "---\nid: g\nbase: &b 1\nref: *b\n---\n",  # an anchor is a per-key refusal, not a file's
        "---\nid: g\ntitle: 'unterminated\n---\n",  # malformed: the reader's to report
    ],
)
def test_frontmatter_pyrite_can_model_or_cannot_parse_is_not_listed(text: str):
    assert unmodellable_reason(text, _span(text)) is None


def test_a_tagged_key_deeper_in_the_file_is_found_with_its_own_line():
    text = "---\nid: g\ntitle: G\nmeta:\n  !!str inner: 1\n---\n\nText.\n"
    got = unmodellable_reason(text, _span(text))
    assert got is not None and got[1] == 5, got
