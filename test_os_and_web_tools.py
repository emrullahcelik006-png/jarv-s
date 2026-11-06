import os
import pytest
from tools.os_control import AppLauncherTool
from tools.web import BrowserDiscoveryTool, WebSearchTool

os.environ["JARVIS_TEST_MODE"] = "true"


@pytest.mark.asyncio
async def test_app_launcher_tool_syntax():
    tool = AppLauncherTool()
    res = await tool.execute(target="edge", dry_run=True)
    assert res.success is True


@pytest.mark.asyncio
async def test_web_search_tool():
    tool = WebSearchTool()
    res = await tool.execute(query="Dinamik Arama Testi", dry_run=True)
    assert res.success is True
    assert "Dinamik Arama Testi" in res.output


@pytest.mark.asyncio
async def test_browser_discovery_tool():
    tool = BrowserDiscoveryTool()
    res = await tool.execute()
    assert res.success is True
    assert len(res.output) > 0  # En az 1 adet tarayici (Edge/Chrome/Opera vb.) bulunmali
