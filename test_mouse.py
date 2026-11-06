import pytest
from tools.mouse_control import MouseControlTool


@pytest.mark.asyncio
async def test_mouse_control_tool_syntax():
    tool = MouseControlTool()
    # Zararsiz ekran kaydirma testi
    res = await tool.execute(action="scroll", scroll_amount=-100)
    assert res.success is True
    assert "SAYFA KAYDIRILDI" in res.output
