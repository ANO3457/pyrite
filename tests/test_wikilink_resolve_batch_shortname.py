"""Tests for resolve_batch supporting shortname and prefix resolution in kb_name (#948 item 3).

`resolve_batch` must resolve a shortname passed as `kb_name` (e.g. `te` -> `test-events`),
so batch wikilink resolution filters correctly against the full KB name in the index.
"""

from pathlib import Path
from pyrite.config import KBConfig, KBType, PyriteConfig, Settings
from pyrite.services.access_policy import UNSCOPED
from pyrite.services.wikilink_service import WikilinkService
from pyrite.storage.database import PyriteDB


def test_resolve_batch_resolves_shortname_kb(tmp_path: Path):
    """resolve_batch resolves shortname and full name in kb_name (#948 item 3)."""
    db_path = tmp_path / "test.db"
    db = PyriteDB(db_path)

    kbs = [
        KBConfig(
            name="test-events", path=tmp_path / "events", kb_type=KBType.GENERIC, shortname="te"
        ),
        KBConfig(
            name="test-notes", path=tmp_path / "notes", kb_type=KBType.GENERIC, shortname="tn"
        ),
    ]
    config = PyriteConfig(knowledge_bases=kbs, settings=Settings(index_path=db_path))

    for kb in kbs:
        db.register_kb(kb.name, "generic", str(kb.path), kb.name)

    # Seed an entry in test-events
    db.upsert_entry(
        {
            "id": "event-1",
            "kb_name": "test-events",
            "entry_type": "event",
            "title": "Event 1",
            "body": "Body 1",
            "summary": "",
            "tags": [],
            "sources": [],
            "links": [],
            "metadata": {},
        }
    )

    # Seed an entry in test-notes
    db.upsert_entry(
        {
            "id": "note-1",
            "kb_name": "test-notes",
            "entry_type": "note",
            "title": "Note 1",
            "body": "Body 2",
            "summary": "",
            "tags": [],
            "sources": [],
            "links": [],
            "metadata": {},
        }
    )

    svc = WikilinkService(config, db)

    # 1. Full name works
    res_full = svc.resolve_batch(
        ["event-1", "note-1"], kb_name="test-events", readable_kbs=UNSCOPED
    )
    assert res_full["event-1"] is True
    assert res_full["note-1"] is False

    # 2. Shortname must resolve to the full name and find event-1 (#948 item 3)
    res_short = svc.resolve_batch(["event-1", "note-1"], kb_name="te", readable_kbs=UNSCOPED)
    assert res_short["event-1"] is True, (
        f"Expected event-1 to be found with shortname 'te', got: {res_short}"
    )
    assert res_short["note-1"] is False

    # 3. Unreadable or nonexistent shortname returns False for all
    res_none = svc.resolve_batch(
        ["event-1", "note-1"], kb_name="nonexistent", readable_kbs=UNSCOPED
    )
    assert res_none["event-1"] is False
    assert res_none["note-1"] is False

    db.close()
