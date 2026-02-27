import pytest
from unittest.mock import AsyncMock, patch

from eip.agent.browser import BrowserTool


@pytest.mark.asyncio
async def test_browse_page_returns_html() -> None:
    mock_page = AsyncMock()
    mock_page.content = AsyncMock(return_value="<html><body>Rendered</body></html>")
    mock_page.title = AsyncMock(return_value="Test Page")
    mock_page.screenshot = AsyncMock(return_value=b"fake_png_bytes")
    mock_page.url = "https://example.com"
    mock_page.close = AsyncMock()

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.close = AsyncMock()

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_browser.close = AsyncMock()

    with patch("eip.agent.browser.async_playwright") as mock_pw:
        mock_pw_instance = AsyncMock()
        mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw_instance.__aenter__ = AsyncMock(return_value=mock_pw_instance)
        mock_pw_instance.__aexit__ = AsyncMock(return_value=False)
        mock_pw.return_value = mock_pw_instance

        tool = BrowserTool()
        result = await tool.browse_page("https://example.com")

    assert "html" in result
    assert "Rendered" in result["html"]
    assert result["title"] == "Test Page"
    assert result["url"] == "https://example.com"


@pytest.mark.asyncio
async def test_browse_page_with_actions() -> None:
    mock_page = AsyncMock()
    mock_page.content = AsyncMock(return_value="<html><body>After Actions</body></html>")
    mock_page.title = AsyncMock(return_value="After Click")
    mock_page.screenshot = AsyncMock(return_value=b"fake_png_bytes")
    mock_page.url = "https://example.com/page2"
    mock_page.close = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()
    mock_page.click = AsyncMock()

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.close = AsyncMock()

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_browser.close = AsyncMock()

    with patch("eip.agent.browser.async_playwright") as mock_pw:
        mock_pw_instance = AsyncMock()
        mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw_instance.__aenter__ = AsyncMock(return_value=mock_pw_instance)
        mock_pw_instance.__aexit__ = AsyncMock(return_value=False)
        mock_pw.return_value = mock_pw_instance

        tool = BrowserTool()
        result = await tool.browse_page(
            "https://example.com",
            actions=[
                {"action": "wait_for_selector", "selector": ".content"},
                {"action": "click", "selector": ".load-more"},
            ],
        )

    assert "After Actions" in result["html"]
    mock_page.wait_for_selector.assert_called_once_with(".content", timeout=10000)
    mock_page.click.assert_called_once_with(".load-more")


@pytest.mark.asyncio
async def test_browse_page_error_handling() -> None:
    with patch("eip.agent.browser.async_playwright") as mock_pw:
        mock_pw_instance = AsyncMock()
        mock_pw_instance.chromium.launch = AsyncMock(side_effect=Exception("Browser crashed"))
        mock_pw_instance.__aenter__ = AsyncMock(return_value=mock_pw_instance)
        mock_pw_instance.__aexit__ = AsyncMock(return_value=False)
        mock_pw.return_value = mock_pw_instance

        tool = BrowserTool()
        result = await tool.browse_page("https://example.com")

    assert "error" in result
    assert "Browser crashed" in result["error"]
