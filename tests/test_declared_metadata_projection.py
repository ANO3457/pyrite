"""Reading collection fields must not write them into the entry's metadata bag."""

from copy import deepcopy

import pytest

from pyrite.utils.metadata import declared_over_bag


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("query", "type:note"),
        ("folder_path", "notes"),
        ("view_config", {"columns": ["title"]}),
        ("entry_filter", {}),
        ("limit", 0),
        ("enabled", False),
    ],
)
def test_projection_leaves_the_complete_entry_unchanged(key, value):
    entry = {"id": "collection-1", key: value, "metadata": {"custom": "keep"}}
    before = deepcopy(entry)
    projection = declared_over_bag(entry, (key,))
    assert projection[key] == value
    assert projection["custom"] == "keep"
    assert entry == before


def test_declared_precedence_does_not_overwrite_a_legacy_bag_in_place():
    entry = {"query": "type:note", "metadata": {"query": "old", "custom": 3}}
    projection = declared_over_bag(entry, ("query",))
    assert projection == {"query": "type:note", "custom": 3}
    assert entry["metadata"] == {"query": "old", "custom": 3}


def test_even_an_empty_projection_does_not_return_the_callers_dictionary():
    entry = {"metadata": {"custom": "keep"}}
    projection = declared_over_bag(entry, ())
    projection.pop("custom")
    assert entry == {"metadata": {"custom": "keep"}}


def test_repeated_reads_of_different_declared_fields_are_independent():
    entry = {"query": "type:note", "icon": "book", "metadata": {}}
    first = declared_over_bag(entry, ("query",))
    second = declared_over_bag(entry, ("icon",))
    assert first == {"query": "type:note"}
    assert second == {"icon": "book"}
    assert entry["metadata"] == {}


@pytest.mark.parametrize("raw", ['{"custom": 4}', None, "invalid"])
def test_json_and_missing_bags_still_accept_declared_fields(raw):
    entry = {"query": "type:note", "metadata": raw}
    projection = declared_over_bag(entry, ("query",))
    assert projection["query"] == "type:note"
    assert entry["metadata"] == raw
