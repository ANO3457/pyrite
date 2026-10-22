"""Markdown exports must carry parseable, lossless YAML metadata."""

from copy import deepcopy

import pytest
import yaml

from pyrite.formats.markdown_fmt import markdown_serialize


@pytest.mark.parametrize(
    "title", ["Meeting: notes", "# heading", "yes", "a\n---\nb", "[not a list]"]
)
def test_special_titles_and_tags_round_trip_without_mutating_the_record(title):
    entry = {
        "id": "sample",
        "title": title,
        "entry_type": "note",
        "tags": ["a, b", "no", "x]"],
        "body": "Body\n---\nkept exactly\n",
    }
    before = deepcopy(entry)
    text = markdown_serialize(entry)
    front, body = text[4:].split("\n---\n\n", 1)
    assert yaml.safe_load(front) == {
        "id": "sample",
        "title": title,
        "type": "note",
        "tags": entry["tags"],
    }
    assert body == entry["body"]
    assert entry == before
