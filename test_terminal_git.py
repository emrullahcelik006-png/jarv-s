import pytest
from tools.terminal import TerminalExecuteTool
from tools.git_control import GitControlTool


@pytest.mark.asyncio
async def test_terminal_execute_tool():
    tool = TerminalExecuteTool()
    res = await tool.execute(command="echo JARVIS TERMINAL TEST")
    assert res.success is True
    assert "JARVIS TERMINAL TEST" in res.output


@pytest.mark.asyncio
async def test_git_control_tool_status():
    tool = GitControlTool()
    res = await tool.execute(action="status")
    assert res.success is True
    assert "On branch" in res.output or "HEAD" in res.output or "git" in res.output.lower()
