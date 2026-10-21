"""REST must refuse fields it cannot write, before changing an entry."""

import os
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "unknown",
    [{"status": "accepted"}, {"date": "2026-10-21"}, {"typo": None, "status": "accepted"}],
)
def test_put_refuses_unknown_keys_without_writing(unknown, make_client):
    client, config, _ = make_client()
    path = Path(config.knowledge_bases[0].path) / "entry.md"
    original = b"---\nid: entry\ntitle: Original\ntype: note\n---\nOriginal body\n"
    path.write_bytes(original)
    result = client.put("/api/entries/entry", json={"kb": "test-kb", "title": "Changed", **unknown})
    assert result.status_code == 400
    detail = result.json()["detail"]
    assert detail["code"] == "VALIDATION_FAILED"
    assert detail["retryable"] is False
    for name in unknown:
        assert name in detail["message"]
    assert path.read_bytes() == original


@pytest.mark.skipif(os.name == "nt", reason="Real entry publication requires POSIX")
def test_declared_put_fields_and_create_metadata_keep_working(make_client):
    client, config, _ = make_client()
    kb = Path(config.knowledge_bases[0].path)
    (kb / "kb.yaml").write_text(
        "name: test-kb\ntypes:\n  note:\n    fields:\n      status: {type: select, options: [draft, accepted]}\n",
        encoding="utf-8",
    )
    created = client.post(
        "/api/entries",
        json={
            "kb": "test-kb",
            "title": "Example",
            "entry_type": "note",
            "body": "Body",
            "metadata": {"status": "accepted"},
        },
    )
    assert created.status_code == 200, created.text
    entry_id = created.json()["id"]
    original = client.get(f"/api/entries/{entry_id}", params={"kb": "test-kb"})
    assert original.status_code == 200
    assert original.json()["metadata"]["status"] == "accepted"
    result = client.put(
        f"/api/entries/{entry_id}",
        json={
            "kb": "test-kb",
            "title": "Updated",
            "body": "Updated body",
            "body_truncated": False,
            "tags": ["checked"],
            "metadata": {"status": "draft"},
        },
    )
    assert result.status_code == 200, result.text
    read = client.get(f"/api/entries/{entry_id}", params={"kb": "test-kb"})
    assert read.status_code == 200
    entry = read.json()
    assert entry["title"] == "Updated"
    assert entry["body"] == "Updated body"
    assert entry["tags"] == ["checked"]
    assert entry["metadata"]["status"] == "draft"


@pytest.mark.skipif(os.name == "nt", reason="Real entry publication requires POSIX")
def test_post_writes_declared_adr_status_from_metadata(make_client):
    client, config, _ = make_client()
    created = client.post(
        "/api/entries",
        json={
            "kb": "test-kb",
            "title": "Decision",
            "entry_type": "adr",
            "allow_undeclared": True,
            "metadata": {"status": "accepted"},
        },
    )
    assert created.status_code == 200, created.text
    from pyrite.utils.frontmatter import load_frontmatter

    path = next(Path(config.knowledge_bases[0].path).rglob("*decision*.md"))
    frontmatter, _ = load_frontmatter(path.read_text(encoding="utf-8"))
    assert frontmatter["status"] == "accepted"
