"""Files alone must rebuild the index left by a normal incremental session (#1155)."""

import json
import sqlite3

from pyrite.config import KBConfig, PyriteConfig, Settings
from pyrite.services.kb_service import KBService
from pyrite.storage.database import PyriteDB
from pyrite.storage.index import IndexManager

# Only volatile bookkeeping is ignored. Content, identity, metadata and file
# identity columns are compared; JSON object order is not semantic.
IGNORE = {"indexed_at", "created_at", "updated_at"}
JSON_COLUMNS = {"metadata", "aliases", "coordinates"}


def snapshot(path):
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        result = {}
        for table in ("entry", "entry_tag", "link", "source", "entry_ref", "block"):
            columns = [
                row[1]
                for row in connection.execute(f"PRAGMA table_info({table})")
                if row[1] not in IGNORE and not (table != "entry" and row[1] == "id")
            ]
            rows = []
            query = (
                "SELECT et.entry_id, et.kb_name, t.name AS tag FROM entry_tag et JOIN tag t ON t.id = et.tag_id"
                if table == "entry_tag"
                else f"SELECT * FROM {table}"
            )
            if table == "entry_tag":
                columns = ["entry_id", "kb_name", "tag"]
            for row in connection.execute(query):
                values = dict(row)
                for column in JSON_COLUMNS & values.keys():
                    if values[column]:
                        values[column] = json.loads(values[column])
                rows.append({key: values[key] for key in columns})
            result[table] = sorted(rows, key=lambda row: json.dumps(row, sort_keys=True))
        return result


def test_incremental_session_equals_a_files_only_rebuild(tmp_path):
    root = tmp_path / "kb"
    root.mkdir()
    (root / "kb.yaml").write_text("name: demo\n", encoding="utf-8")
    path = tmp_path / "index.db"
    config = PyriteConfig(
        knowledge_bases=[KBConfig(name="demo", path=root)],
        settings=Settings(index_path=path, auto_embed=False),
    )
    db = PyriteDB(path)
    try:
        IndexManager(db, config).index_all()
        service = KBService(config, db)
        service.create_entry("demo", "target", "Target", "note", body="Destination", tags=["one"])
        service.create_entry(
            "demo", "source", "Source", "note", body="See [[target]]", tags=["two"]
        )
        service.create_entry("demo", "discard", "Discard", "note", body="Delete me")
        service.update_entry(
            "target",
            "demo",
            title="Updated target",
            tags=["one", "changed"],
            metadata={"custom": "kept"},
        )
        service.rename_entry("target", "renamed", "demo")
        service.delete_entry("discard", "demo")
        incremental = snapshot(path)
        assert {row["id"] for row in incremental["entry"]} == {"renamed", "source"}
        assert incremental["entry_tag"]
        assert incremental["link"]
    finally:
        db.close()
    # The fresh database has no access to the previous rows or write history.
    path.unlink()
    fresh = PyriteDB(path)
    try:
        IndexManager(fresh, config).index_all()
        assert snapshot(path) == incremental
    finally:
        fresh.close()
