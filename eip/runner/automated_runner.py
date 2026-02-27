from typing import Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def extract_items(html: str, config: dict) -> List[Dict]:
    """Extract structured items from HTML using CSS selectors.

    Args:
        html: Raw HTML string to parse.
        config: Extraction configuration with keys:
            - strategy: Currently only "css_selector" is supported.
            - selectors: Mapping of field names to CSS selectors.
              Use "item_container" for the repeating element.
              Append ``@attr`` to a selector to extract an attribute
              instead of text (e.g. ``"a@href"``).
            - base_url: Base URL used to resolve relative links.

    Returns:
        A list of dicts, one per matched container.
    """
    soup = BeautifulSoup(html, "html.parser")
    selectors = config.get("selectors", {})
    base_url = config.get("base_url", "")

    container_selector = selectors.get("item_container", "")
    if not container_selector:
        return []

    containers = soup.select(container_selector)
    items: List[Dict] = []

    for container in containers:
        item: Dict = {}
        for field, selector in selectors.items():
            if field == "item_container":
                continue

            # Handle @attr syntax for extracting attributes (e.g. "a@href")
            attr: Optional[str] = None
            if "@" in selector:
                selector, attr = selector.rsplit("@", 1)

            el = container.select_one(selector)
            if el is None:
                continue

            if attr:
                value = el.get(attr, "")
            else:
                value = el.get_text(strip=True)

            # Resolve relative URLs for link fields
            if field == "link" and value and not value.startswith(("http://", "https://")):
                value = urljoin(base_url, value)

            # Store link fields as "url" in output
            if field == "link":
                item["url"] = value
            else:
                item[field] = value

        if item:
            items.append(item)

    return items
