"""An index that is not a SQLite database refuses in one structured shape (#922).

The index is derived from the KB files, so an unreadable one loses nothing.
Every command used to meet the driver itself -- a Rich traceback for `get`,
`backlinks` and `index sync`, a JSON document with the driver's text for
`search`, and an "unknown outcome" for `create`. The refusal is raised once,
from the first connection in `ConnectionMixin._init_connection`, and names the
index path and the command that rebuilds it.

A fresh empty file is a *new* index and must keep working; only a file (or
path) that is not a database is refused. A real index corrupted during a
search still falls back to file search (`test_fields_acceptors.py`), so this
file covers the open-time refusal alone.
"""

import json
from pathlib import Path

import pytest

from pyrite.exceptions import IndexUnreadableError
from pyrite.storage.database import PyriteDB

KB = "test-kb"

COMMANDS = [
    pytest.param(("get", "hi", "-k", KB), id="get"),
    pytest.param(("backlinks", "hi", "-k", KB), id="backlinks"),
    pytest.param(("search", "hi", "-k", KB), id="search"),
    pytest.param(("create", "-k", KB, "-t", "note", "--title", "hi", "-b", "x"), id="create"),
    pytest.param(("index", "sync", "-k", KB), id="index-sync"),
    pytest.param(("index", "build"), id="index-build"),
    pytest.param(("index", "health"), id="index-health"),
]


@pytest.fixture
def world(cli_world):
    """A real config and index, closed so the test can damage the file."""
    world = cli_world()
    world.close()
    return world


def _corrupt(world, data: bytes = b"not a database" * 100) -> Path:
    path = world.config.settings.index_path
    path.write_bytes(data)
    return path


@pytest.mark.parametrize("args", COMMANDS)
def test_every_command_refuses_an_unreadable_index_with_one_structured_error(world, args):
    path = _corrupt(world)

    result = world.cli(*args)

    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert payload["error_code"] == "STORAGE_ERROR"
    assert "pyrite index build" in payload["suggestion"]
    assert str(path) in payload["error"]
    for raw in ("Traceback", "sqlalche.me", "sqlite3", "file is not a database"):
        assert raw not in result.stdout, raw


def test_a_damaged_real_index_is_refused_the_same_way(world):
    path = world.config.settings.index_path
    real = path.read_bytes()
    assert len(real) > 100
    path.write_bytes(real[:100])

    result = world.cli("get", "hi", "-k", KB)

    assert result.exit_code == 1, result.output
    assert json.loads(result.stdout)["error_code"] == "STORAGE_ERROR"


def test_a_directory_at_the_index_path_is_refused(world):
    path = world.config.settings.index_path
    path.unlink()
    path.mkdir()

    result = world.cli("index", "health")

    assert result.exit_code == 1, result.output
    assert json.loads(result.stdout)["error_code"] == "STORAGE_ERROR"


def test_a_zero_byte_index_is_a_new_index_and_still_works(world):
    _corrupt(world, b"")

    result = world.cli("index", "build")

    assert result.exit_code == 0, result.output


def test_the_refusal_is_raised_where_the_database_is_opened():
    """A new command cannot open the index another way and miss the refusal.

    `db_commands` is the one exception: `db backup`/`db restore` open the files
    the user names, not the configured index.
    """
    import pyrite.cli as cli_package

    cli_dir = Path(cli_package.__file__).parent
    offenders = sorted(
        str(path.relative_to(cli_dir))
        for path in cli_dir.rglob("*.py")
        if path.name != "context.py"
        and any(
            needle in path.read_text(encoding="utf-8")
            for needle in ("PyriteDB(", "create_engine(", "sqlite3.connect(")
        )
    )
    assert offenders == ["db_commands.py"]
    for surface in (cli_dir.parent / "admin_cli.py", cli_dir.parent / "read_cli.py"):
        text = surface.read_text(encoding="utf-8")
        assert not any(needle in text for needle in ("PyriteDB(", "create_engine("))


def test_the_index_is_unreadable_only_for_the_file_itself(tmp_path):
    """A lock or a busy database is not "rebuild the index"; the refusal names
    the file problems alone."""
    from pyrite.storage.connection import _index_is_unreadable

    class DriverError(Exception):
        sqlite_errorcode = 5  # SQLITE_BUSY

    assert not _index_is_unreadable(DriverError("database is locked"))

    path = tmp_path / "index.db"
    path.write_bytes(b"not a database" * 100)
    with pytest.raises(IndexUnreadableError):
        PyriteDB(path)
