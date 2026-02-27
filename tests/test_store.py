import json
from pathlib import Path

import pytest

from eip.store.json_store import JsonStore


@pytest.fixture
def store(tmp_path: Path) -> JsonStore:
    return JsonStore(base_dir=tmp_path)


def test_save_and_load(store: JsonStore) -> None:
    data = {"id": "abc", "name": "test"}
    store.save("things", "abc", data)
    loaded = store.load("things", "abc")
    assert loaded == data


def test_load_missing_returns_none(store: JsonStore) -> None:
    assert store.load("things", "missing") is None


def test_list_collection(store: JsonStore) -> None:
    store.save("things", "a", {"id": "a"})
    store.save("things", "b", {"id": "b"})
    items = store.list("things")
    ids = {item["id"] for item in items}
    assert ids == {"a", "b"}


def test_list_empty_collection(store: JsonStore) -> None:
    assert store.list("things") == []


def test_delete(store: JsonStore) -> None:
    store.save("things", "abc", {"id": "abc"})
    store.delete("things", "abc")
    assert store.load("things", "abc") is None


def test_delete_missing_does_not_raise(store: JsonStore) -> None:
    store.delete("things", "nonexistent")  # should not raise
