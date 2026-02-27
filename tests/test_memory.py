from pathlib import Path

from eip.agent.memory import AgentMemory
from eip.store.json_store import JsonStore


def test_remember_and_recall(tmp_path: Path) -> None:
    store = JsonStore(base_dir=tmp_path)
    memory = AgentMemory(store=store)
    memory.remember("example.com", "site_profile", "React SPA, needs JS rendering")
    entries = memory.recall("example.com")
    assert len(entries) == 1
    assert entries[0]["key"] == "site_profile"
    assert entries[0]["value"] == "React SPA, needs JS rendering"
    assert "created_at" in entries[0]


def test_recall_empty_domain(tmp_path: Path) -> None:
    store = JsonStore(base_dir=tmp_path)
    memory = AgentMemory(store=store)
    entries = memory.recall("unknown.com")
    assert entries == []


def test_remember_appends(tmp_path: Path) -> None:
    store = JsonStore(base_dir=tmp_path)
    memory = AgentMemory(store=store)
    memory.remember("example.com", "tier_1_failure", "CSS selectors returned 0 items")
    memory.remember("example.com", "tier_2_success", "Playwright worked, found 15 items")
    entries = memory.recall("example.com")
    assert len(entries) == 2
    assert entries[0]["key"] == "tier_1_failure"
    assert entries[1]["key"] == "tier_2_success"


def test_recall_formats_for_prompt(tmp_path: Path) -> None:
    store = JsonStore(base_dir=tmp_path)
    memory = AgentMemory(store=store)
    memory.remember("example.com", "site_profile", "Static HTML site")
    text = memory.recall_as_text("example.com")
    assert "site_profile" in text
    assert "Static HTML site" in text


def test_recall_as_text_empty(tmp_path: Path) -> None:
    store = JsonStore(base_dir=tmp_path)
    memory = AgentMemory(store=store)
    text = memory.recall_as_text("unknown.com")
    assert text == ""
