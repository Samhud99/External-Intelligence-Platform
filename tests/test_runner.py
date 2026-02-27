import pytest

from eip.runner.automated_runner import extract_items


SAMPLE_HTML = """
<html><body>
<div class="articles">
  <div class="article">
    <h2><a href="/news/first-article">First Article</a></h2>
    <span class="date">2026-02-27</span>
    <p class="summary">Summary of the first article.</p>
  </div>
  <div class="article">
    <h2><a href="/news/second-article">Second Article</a></h2>
    <span class="date">2026-02-26</span>
    <p class="summary">Summary of the second article.</p>
  </div>
</div>
</body></html>
"""


def test_extract_items_with_css_selectors() -> None:
    config = {
        "strategy": "css_selector",
        "selectors": {
            "item_container": ".articles .article",
            "title": "h2 a",
            "date": ".date",
            "summary": ".summary",
            "link": "h2 a@href",
        },
        "base_url": "https://example.com",
    }
    items = extract_items(SAMPLE_HTML, config)
    assert len(items) == 2
    assert items[0]["title"] == "First Article"
    assert items[0]["date"] == "2026-02-27"
    assert items[0]["summary"] == "Summary of the first article."
    assert items[0]["url"] == "https://example.com/news/first-article"


def test_extract_items_absolute_url_preserved() -> None:
    html = """
    <div class="items"><div class="item">
      <a href="https://other.com/page">Link</a>
    </div></div>
    """
    config = {
        "strategy": "css_selector",
        "selectors": {
            "item_container": ".items .item",
            "title": "a",
            "link": "a@href",
        },
        "base_url": "https://example.com",
    }
    items = extract_items(html, config)
    assert items[0]["url"] == "https://other.com/page"


def test_extract_items_empty_html_returns_empty() -> None:
    config = {
        "strategy": "css_selector",
        "selectors": {
            "item_container": ".nonexistent",
            "title": "h2",
        },
        "base_url": "https://example.com",
    }
    items = extract_items("<html><body></body></html>", config)
    assert items == []
