import pytest
from agent.dispatcher import ActionDispatcher
from tools.registry import ToolRegistry
from tools.web import WebSearchTool
from tools.system import SystemInfoTool


@pytest.mark.asyncio
async def test_smart_dispatcher_tool_selection():
    registry = ToolRegistry()
    registry.register(WebSearchTool())
    registry.register(SystemInfoTool())

    dispatcher = ActionDispatcher(registry=registry)

    # LLM dinamik olarak web_search aracini ve arama sorgusunu secmeli
    res = await dispatcher.dispatch("Yapay zeka alanindaki son gelismeleri internette ara")
    assert res["matched"] is True
    assert res["tool_name"] == "web_search"
    assert "query" in res["arguments"] or "search" in str(res["arguments"])


@pytest.mark.asyncio
async def test_smart_dispatcher_no_tool_for_pure_chat():
    registry = ToolRegistry()
    registry.register(WebSearchTool())

    dispatcher = ActionDispatcher(registry=registry)

    # Saf sohbet cümlesinde araç seçilmemeli
    res = await dispatcher.dispatch("Merhaba JARVIS, nasılsın?")
    assert res["matched"] is False
