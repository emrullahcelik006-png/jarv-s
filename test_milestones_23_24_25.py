import pytest
from tools.notification import NotificationTool
from tools.docker_control import DockerControlTool


@pytest.mark.asyncio
async def test_toast_notification_tool():
    tool = NotificationTool()
    res = await tool.execute(title="Test", message="Test Mesaji")
    assert res.success is True
    assert "Bildirimi" in res.output or "fırlatıldı" in res.output


@pytest.mark.asyncio
async def test_docker_control_tool_ps():
    tool = DockerControlTool()
    res = await tool.execute(action="ps")
    # Docker sistemde kurulu olmasa bile hatasiz donmeli
    assert res.success is True or "Docker" in str(res.error)
