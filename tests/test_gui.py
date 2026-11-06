import pytest
from tools.gui_automation import KeyPressTool


@pytest.mark.asyncio
async def test_key_press_tool_syntax():
    tool = KeyPressTool()
    # Test ortaminda zararsiz bir esc tusuna bas
    res = await tool.execute(key_name="esc")
    assert res.success is True
    assert "esc" in res.output
