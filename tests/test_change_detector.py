from eip.runner.change_detector import detect_changes


def test_all_new_when_no_previous() -> None:
    current = [
        {"title": "Article A", "url": "https://example.com/a"},
        {"title": "Article B", "url": "https://example.com/b"},
    ]
    result = detect_changes(current, previous=None)
    assert all(item["is_new"] for item in result)
    assert len(result) == 2


def test_detect_new_items() -> None:
    previous = [
        {"title": "Article A", "url": "https://example.com/a"},
    ]
    current = [
        {"title": "Article A", "url": "https://example.com/a"},
        {"title": "Article B", "url": "https://example.com/b"},
    ]
    result = detect_changes(current, previous)
    new_items = [i for i in result if i["is_new"]]
    old_items = [i for i in result if not i["is_new"]]
    assert len(new_items) == 1
    assert new_items[0]["title"] == "Article B"
    assert len(old_items) == 1


def test_no_changes() -> None:
    items = [{"title": "A", "url": "https://example.com/a"}]
    result = detect_changes(items, items)
    assert not any(item["is_new"] for item in result)


def test_uses_url_for_comparison_when_available() -> None:
    previous = [{"title": "Old Title", "url": "https://example.com/a"}]
    current = [{"title": "New Title", "url": "https://example.com/a"}]
    result = detect_changes(current, previous)
    assert not result[0]["is_new"]


def test_falls_back_to_title_hash() -> None:
    previous = [{"title": "Article A"}]
    current = [{"title": "Article A"}, {"title": "Article B"}]
    result = detect_changes(current, previous)
    new_items = [i for i in result if i["is_new"]]
    assert len(new_items) == 1
    assert new_items[0]["title"] == "Article B"
