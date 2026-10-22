"""A Postgres database from before #1001 takes entry aliases after `ensure_schema()`.

`entry.aliases` is new in #1001, and index queries/upserts reference it.
`create_all` creates a missing table but never alters an existing one, so
`ensure_schema()`, which every Postgres startup runs, is what must add the
column (#1011). Without it, an existing database fails when queried for aliases.
"""

from unittest.mock import MagicMock
from sqlalchemy import text
from pyrite.storage.backends.postgres_backend import ensure_schema


def test_ensure_schema_executes_alter_table_entry_add_aliases():
    """Verify ensure_schema issues ALTER TABLE entry ADD COLUMN IF NOT EXISTS aliases TEXT."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    ensure_schema(mock_engine)

    executed_statements = [
        str(call.args[0]) for call in mock_conn.execute.call_args_list if call.args
    ]
    matching = [
        stmt
        for stmt in executed_statements
        if "ALTER TABLE entry ADD COLUMN IF NOT EXISTS aliases" in stmt
    ]
    assert len(matching) == 1, (
        f"Expected ALTER TABLE entry ADD COLUMN IF NOT EXISTS aliases, got: {executed_statements}"
    )
