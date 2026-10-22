"""Whole-KB validation runs the same named rubric as entry validation (#956)."""

import json

import pytest
from typer.testing import CliRunner

from pyrite.cli import app
from pyrite.config import KBConfig, PyriteConfig, Settings, save_config
from pyrite.services.access_policy import UNSCOPED
from pyrite.services.qa_service import QAService
from pyrite.storage.database import PyriteDB
from pyrite.storage.index import IndexManager


@pytest.fixture
def world(tmp_path):
    opened = []

    def build(items, *, role=None, tagged=True):
        folder = tmp_path / "kb"
        folder.mkdir()
        (folder / "kb.yaml").write_text(
            json.dumps({"name": "notes", "evaluation_rubric": items}), encoding="utf-8"
        )
        role_line = f"role: {role}\n" if role else ""
        (folder / "a.md").write_text(
            "---\nid: a\ntype: note\ntitle: Harbour field survey\n"
            + ("tags: [survey]\n" if tagged else "")
            + role_line
            + "---\nA stub note.\n",
            encoding="utf-8",
        )
        config = PyriteConfig(
            knowledge_bases=[KBConfig(name="notes", path=folder, kb_type="generic")],
            settings=Settings(index_path=tmp_path / "index.db", auto_embed=False),
        )
        db = PyriteDB(config.settings.index_path)
        opened.append(db)
        IndexManager(db, config).index_all()
        return QAService(config, db), config

    yield build
    for db in opened:
        db.close()


HAS_ROLE = {"text": "Has a role", "checker": "has_field", "params": {"field": "role"}}


def test_kb_wide_named_failure_matches_single_entry_and_cli(world):
    qa, config = world([HAS_ROLE])
    folder = config.get_kb("notes").path
    before = {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}
    single = qa.validate_entry("a", "notes", readable_kbs=UNSCOPED)
    expected = [i for i in single["issues"] if i.get("rubric_item") == "Has a role"]
    assert len(expected) == 1
    all_entries = qa.validate_kb("notes", readable_kbs=UNSCOPED)
    assert [i for i in all_entries["issues"] if i.get("rubric_item") == "Has a role"] == expected
    save_config(config)
    result = CliRunner().invoke(app, ["qa", "validate", "notes", "--format", "json"])
    assert result.exit_code == 0, result.output
    assert "Has a role" in result.stdout
    assert {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()} == before


@pytest.mark.parametrize("role", ["researcher", None])
def test_named_pass_and_covered_items_do_not_invent_issues(world, role):
    item = dict(HAS_ROLE)
    if role is None:
        item["covered_by"] = "separate_checker"
    qa, _ = world([item], role=role)
    result = qa.validate_kb("notes", readable_kbs=UNSCOPED)
    assert not [i for i in result["issues"] if i.get("rubric_item") == "Has a role"]


@pytest.mark.parametrize(
    ("item", "rule"),
    [
        ({"text": "Unknown", "checker": "not_a_real_checker"}, "config_error"),
        (
            {"text": "Broken", "checker": "body_has_pattern", "params": {"pattern": "("}},
            "checker_failed",
        ),
    ],
)
def test_unchecked_or_broken_named_items_are_reported(world, item, rule):
    qa, _ = world([item])
    result = qa.validate_kb("notes", readable_kbs=UNSCOPED)
    assert any(i["rule"] == rule for i in result["issues"])


def test_bulk_and_named_checks_do_not_duplicate_the_same_finding(world):
    qa, _ = world([], tagged=False)
    result = qa.validate_kb("notes", readable_kbs=UNSCOPED)
    assert len([i for i in result["issues"] if i.get("field") == "tags"]) == 1
