"""Tests for CLI startup performance and lazy import boundaries (#1046).

`import pyrite.cli` must not eagerly import heavy dependencies like SQLAlchemy
or httpx before any command is executed.
"""

from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_import_pyrite_cli_does_not_import_sqlalchemy():
    """Verify that importing pyrite.cli does not load sqlalchemy into sys.modules."""
    code = """
import sys
import pyrite.cli
assert 'sqlalchemy' not in sys.modules, f"sqlalchemy was eagerly imported: {sys.modules.get('sqlalchemy')}"
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, f"Import check failed: {result.stderr}"


def test_import_pyrite_cli_does_not_import_httpx():
    """Verify that importing pyrite.cli does not load httpx into sys.modules."""
    code = """
import sys
import pyrite.cli
assert 'httpx' not in sys.modules, f"httpx was eagerly imported: {sys.modules.get('httpx')}"
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, f"Import check failed: {result.stderr}"


def test_cli_context_exposes_real_pyrite_db_class_via_getattr():
    """Verify that pyrite.cli.context.PyriteDB lazily resolves to the real class for subclassing."""
    import pyrite.cli.context as cli_context

    real_db_class = cli_context.PyriteDB

    class TrackingDB(real_db_class):
        pass

    assert issubclass(TrackingDB, real_db_class)


def test_storage_error_helpers_do_not_import_database():
    code = "import sys; import pyrite.storage.errors; assert 'sqlalchemy' not in sys.modules"
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr
