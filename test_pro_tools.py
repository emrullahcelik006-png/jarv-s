import pytest
from tools.os_control import AppLauncherTool
from tools.window_manager import WindowManagerTool

@pytest.mark.asyncio
async def test_app_launcher_appopener_dry_run():
    tool = AppLauncherTool()
    res = await tool.execute(target="spotify", dry_run=True)
    assert res.success is True

@pytest.mark.asyncio
async def test_window_manager_list_windows():
    tool = WindowManagerTool()
    res = await tool.execute(action="list_windows")
    assert res.success is True
    assert "AÇIK OLAN PENCERELER" in res.output
