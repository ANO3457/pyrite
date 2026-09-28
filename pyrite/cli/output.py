"""CLI output formatting utilities."""

import typer


def validate_output_format(value: str) -> str:
    """Validate a CLI output format before the command starts.

    ``rich`` is handled by the CLI rather than the format registry; all other
    formats must have a registered serializer. Raising ``BadParameter`` here
    makes an unknown format a usage error (exit 2), instead of allowing a
    late ``ValueError`` from the serializer to escape as a traceback.
    """
    from ..formats import get_format_registry

    registry = get_format_registry()
    if value == "rich" or registry.get(value) is not None:
        return value

    available = ["rich", *registry.available_formats()]
    raise typer.BadParameter(f"unknown format {value!r}; choose one of: {', '.join(available)}")


def format_output(data: dict, fmt: str) -> str | None:
    """Format data using the format registry. Returns None for default (rich) output."""
    if fmt == "rich":
        return None
    from ..formats import format_response

    content, _ = format_response(data, fmt)
    return content
