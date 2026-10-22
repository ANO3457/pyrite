"""Tests for CLI startup performance and lazy import boundaries (#1046).

`import pyrite.cli` must not eagerly import heavy dependencies like SQLAlchemy
or httpx before any command is executed.
"""

import subprocess
import sys


def test_import_pyrite_cli_does_not_import_sqlalchemy():
    """Verify that importing pyrite.cli does not load sqlalchemy into sys.modules."""
    code = """
import sys
import pyrite.cli
assert 'sqlalchemy' not in sys.modules, f"sqlalchemy was eagerly imported: {sys.modules.get('sqlalchemy')}"
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, f"Import check failed: {result.stderr}"


def test_import_pyrite_cli_does_not_import_httpx():
    """Verify that importing pyrite.cli does not load httpx into sys.modules."""
    code = """
import sys
import pyrite.cli
assert 'httpx' not in sys.modules, f"httpx was eagerly imported: {sys.modules.get('httpx')}"
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, f"Import check failed: {result.stderr}"
