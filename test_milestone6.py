import pytest
from memory.service import MemoryService
from services.audit_service import SystemAuditService
from tools.dev_mode import SelfCodeAnalysisTool
from tools.filesystem import DirectoryScanTool
from tools.os_control import AppLauncherTool
from tools.web import DeepWebReaderTool


@pytest.mark.asyncio
async def test_memory_service_persistence():
    memory = MemoryService(db_path="storage/db/test_memory.db")
    memory.set_fact("developer", "Cilek")
    val = memory.get_fact("developer")
    assert val == "Cilek"


@pytest.mark.asyncio
async def test_self_code_analysis_tool():
    tool = SelfCodeAnalysisTool()
    res = await tool.execute()
    assert res.success is True
    assert res.output["total_python_files"] > 5
    assert len(res.output["syntax_errors"]) == 0


@pytest.mark.asyncio
async def test_os_launcher_dynamic_scan():
    tool = AppLauncherTool()
    res = await tool.execute(target="edge")
    assert res.success is True


@pytest.mark.asyncio
async def test_global_directory_scan():
    tool = DirectoryScanTool()
    res = await tool.execute(dir_path="desktop")
    assert res.success is True


@pytest.mark.asyncio
async def test_system_audit_service_report():
    report = await SystemAuditService.generate_full_report()
    assert "# 🛡️ J.A.R.V.I.S — SYSTEM & ENVIRONMENT AUDIT REPORT" in report

