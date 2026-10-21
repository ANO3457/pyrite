"""An ambiguous implicit ADR KB is a validation refusal, not a missing name."""

from pyrite.config import KBConfig
from pyrite.plugins import get_registry
from pyrite_software_kb.plugin import SoftwareKBPlugin


def test_sw_create_adr_blank_name_does_not_report_a_missing_kb(cli_world, tmp_path):
    get_registry().register(SoftwareKBPlugin())
    world = cli_world(
        kbs=[
            KBConfig(name="one", path=tmp_path / "one", kb_type="generic"),
            KBConfig(name="two", path=tmp_path / "two", kb_type="generic"),
        ]
    )
    result = world.mcp()._dispatch_tool("sw_create_adr", {"title": "Decision", "kb_name": ""})
    assert result["error_code"] == "VALIDATION_FAILED", result
    assert result.get("created") is not True
