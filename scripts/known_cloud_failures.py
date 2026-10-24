#!/usr/bin/env python3
"""Print the shared cloud brief; an empty list produces no warning."""

import json
import sys
from pathlib import Path


def render(path):
    failures = json.loads(Path(path).read_text(encoding="utf-8"))
    if not failures:
        return ""
    lines = ["Known cloud-only failures (not a CI waiver):"]
    for failure in failures:
        lines.append(f"- {failure['test']} ({failure['issue']}): {failure['reason']}")
    lines.append("Do not skip a changed test or claim a cloud failure passed. CI remains required.")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    path = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path(__file__).with_name("known-cloud-failures.json")
    )
    sys.stdout.write(render(path))
