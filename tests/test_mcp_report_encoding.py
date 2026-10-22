"""A successful setup must remain reportable on real terminal encodings (#841.2)."""

import io

import pytest
from rich.console import Console

from pyrite.cli.mcp_setup_command import _print_report


@pytest.mark.parametrize(
    ("encoding", "value"),
    [
        pytest.param(
            encoding,
            value,
            marks=(
                pytest.mark.control(reason="already encodable text remains unchanged")
                if (encoding, value) in {("utf-8", "日本語"), ("utf-8", "café"), ("cp1252", "café")}
                else ()
            ),
        )
        for encoding in ("utf-8", "ascii", "cp1252")
        for value in ("bad\ud800argument", "日本語", "café")
    ],
)
def test_changed_client_report_escapes_unencodable_values(encoding, value):
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding=encoding, errors="strict")
    console = Console(file=stream, color_system=None, force_terminal=False, width=200)
    report = {
        "new_entry": {"tools": None, "tier": "write", "command": ["pyrite", "mcp"]},
        "clients": [
            {
                "label": "Client",
                "status": "changed",
                "location": "config.json",
                "discarded": [value],
                "notes": [],
            }
        ],
        "notes": [],
    }
    _print_report(console, report)
    stream.flush()
    text = buffer.getvalue().decode(encoding)
    assert "Client: changed" in text
    assert "discarded:" in text
    assert value.encode(encoding, errors="backslashreplace").decode(encoding) in text
    assert "Restart the client" in text
