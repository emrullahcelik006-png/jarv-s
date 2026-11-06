import pytest
from tools.window_manager import WindowManagerTool


@pytest.mark.asyncio
async def test_window_manager_list_windows():
    tool = WindowManagerTool()
    res = await tool.execute(action="list_windows")
    assert res.success is True
    assert "AÇIK OLAN PENCERELER" in res.output
    assert res.metadata["count"] >= 0
