import pytest
from tools.process_manager import ProcessKillTool


@pytest.mark.asyncio
async def test_process_kill_tool_syntax():
    tool = ProcessKillTool()
    # Var olmayan hayali bir sureci kapatmayı dene (Dürüstçe çalışmadığını bildirmeli)
    res = await tool.execute(target="non_existent_fake_app_12345")
    assert res.success is True
    assert "çalışmıyor" in res.output or "bulunamadı" in str(res.output)
