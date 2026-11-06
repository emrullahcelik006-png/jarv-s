import pytest
from pathlib import Path
from tools.screen import ScreenCaptureTool


@pytest.mark.asyncio
async def test_screen_capture_tool():
    tool = ScreenCaptureTool()
    res = await tool.execute(output_file="storage/test_screen.png")
    assert res.success is True
    assert Path("storage/test_screen.png").exists()
    assert Path("storage/test_screen.png").stat().st_size > 0

