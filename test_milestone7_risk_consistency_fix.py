import pytest
from tools.registry import ToolRegistry
from tools.filesystem import FileWriteTool
from tools.advanced_os import DeepFileSearchTool
from core.policy import TOOL_RISK_MAP
from tasks.models import RiskLevel


def test_list_tools_reports_effective_risk_not_class_attribute():
    """
    Milestone 7 regresyon testi: list_tools(), tool sinifinin kendi
    risk_level beyanini DEGIL, gercek uygulanan TOOL_RISK_MAP degerini
    dondurmeli. FileWriteTool sinifi MEDIUM der ama gercek risk HIGH'tir.
    """
    registry = ToolRegistry()
    registry.register(FileWriteTool())

    tools = registry.list_tools()
    file_write_info = next(t for t in tools if t["name"] == "file_write")

    assert FileWriteTool.risk_level == RiskLevel.MEDIUM  # sinifin kendi (eski) beyani
    assert file_write_info["risk_level"] == RiskLevel.HIGH.value  # gercek uygulanan (dogru)


def test_deep_file_search_risk_corrected_to_medium():
    """
    Milestone 7 fix: deep_file_search onceden TOOL_RISK_MAP'te LOW idi,
    ama tum C:\\ suruculu taradigi icin gelistiricinin niyeti MEDIUM idi.
    Bu artik duzeltilmis olmali (onay gerektiren bir seviyeye yukseltildi).
    """
    assert TOOL_RISK_MAP["deep_file_search"] == RiskLevel.MEDIUM


def test_list_tools_consistent_with_evaluate_risk():
    """
    list_tools()'un gosterdigi risk ile evaluate_risk()'in gercekte
    uyguladigi risk HER ZAMAN ayni olmali (tek dogru kaynak ilkesi).
    """
    from core.policy import SecurityPolicyEngine

    registry = ToolRegistry()
    registry.register(DeepFileSearchTool())

    tools = registry.list_tools()
    info = next(t for t in tools if t["name"] == "deep_file_search")

    actual_risk, _ = SecurityPolicyEngine.evaluate_risk("deep_file_search", {})
    assert info["risk_level"] == actual_risk.value
