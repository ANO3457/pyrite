"""Guard the skills against naming symbols a refactor removed (#1033).

The 0.26 write-path sprint (#1028, #955) deleted the model emitter.  The
``pyrite-dev`` skill is the method a coding session follows, so a stale name
there sends a contributor looking for code that no longer exists.

This is an explicit list, not a general scanner: a symbol may be named in a
skill for a deliberate reason, and each removal should add one line here.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILLS = REPO / ".claude" / "skills"

REMOVED_SYMBOLS = (
    "to_markdown",
    "SiteCacheService",
    "extensions/cascade",
    "get_kb_by_shortname",
    "kb_name_for",
)


def test_the_skills_name_no_removed_symbol() -> None:
    assert SKILLS.is_dir(), f"missing skills directory: {SKILLS}"

    offenders: list[str] = []
    for path in sorted(SKILLS.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for symbol in REMOVED_SYMBOLS:
            if symbol not in text:
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                if symbol in line:
                    relative = path.relative_to(REPO).as_posix()
                    offenders.append(f"{relative}:{line_number}: {symbol}: {line.strip()}")

    assert not offenders, (
        "The skills name symbols removed by the 0.26 write-path refactor; "
        "update the skill or the explicit list:\n" + "\n".join(offenders)
    )
