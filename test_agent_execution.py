import pytest
from pathlib import Path
from agent.runner import AgentRunner
from tasks.models import RiskLevel, StepStatus, Task, TaskStep, TaskStatus
from tasks.service import TaskService
from tools.filesystem import DirectoryScanTool, FileReadTool, FileWriteTool, _resolve_global_path
from tools.system import SystemInfoTool
from tools.code_runner import PythonSyntaxCheckTool


@pytest.mark.asyncio
async def test_tools_system_info():
    tool = SystemInfoTool()
    res = await tool.execute()
    assert res.success is True
    assert "cpu_cores" in res.output


@pytest.mark.asyncio
async def test_tools_filesystem_and_sandbox():
    write_tool = FileWriteTool()
    read_tool = FileReadTool()
    scan_tool = DirectoryScanTool()

    # 1. Dosya Yaz
    w_res = await write_tool.execute(file_path="storage/test_file.txt", content="JARVIS LIVE TEST")
    assert w_res.success is True

    # 2. Dosya Oku
    r_res = await read_tool.execute(file_path="storage/test_file.txt")
    assert r_res.success is True
    assert "JARVIS LIVE TEST" in r_res.output

    # 3. Sistem Dizinlerine İzinsiz Yazma Engeli Kontrolü (Windows OS Yetki Koruması)
    evil_res = await write_tool.execute(file_path="C:/Windows/System32/evil.txt", content="bad")
    assert evil_res.success is False
    assert evil_res.error is not None

    # 4. Directory Scan
    s_res = await scan_tool.execute(dir_path="storage")
    assert s_res.success is True
    assert len(s_res.output) > 0


@pytest.mark.asyncio
async def test_tools_syntax_checker():
    tool = PythonSyntaxCheckTool()

    # Gecerli kod
    valid_res = await tool.execute(code_snippet="def add(a, b):\n    return a + b\n")
    assert valid_res.success is True

    # Hatali kod
    invalid_res = await tool.execute(code_snippet="def bad_function(:\n    pass")
    assert invalid_res.success is False
    assert "Syntax Hatasi" in invalid_res.error


@pytest.mark.asyncio
async def test_agent_runner_approval_and_execution_lifecycle():
    task_service = TaskService(storage_dir="storage/test_tasks")
    runner = AgentRunner(task_service=task_service)

    # 1. Test gorevi olustur (1 Low Risk + 1 High Risk onay gerektiren adim)
    task = Task(
        goal="Test Agent Execution & Approval",
        steps=[
            TaskStep(
                id=1,
                title="Sistem Bilgisini Oku",
                description="Sistem durumunu denetle",
                tool_name="system_info",
                risk_level=RiskLevel.LOW,
                requires_approval=False,
            ),
            TaskStep(
                id=2,
                title="Rapor Dosyasi Olustur",
                description="Test sonucunu diske yaz",
                tool_name="file_write",
                parameters={"file_path": "storage/agent_test_report.txt", "content": "AGENT EXECUTED SUCCESSFULLY"},
                risk_level=RiskLevel.HIGH,
                requires_approval=True,
                verification_method="output_check",
            ),
        ]
    )
    task_service.save_task(task)

    # 2. Ilk calistirma -> Adim 1 tamamlanmali, Adim 2'de WAITING_FOR_USER olmali
    t_after_run = await runner.run_task(task.id)
    assert t_after_run.status == TaskStatus.WAITING_FOR_USER
    assert t_after_run.steps[0].status == StepStatus.COMPLETED
    assert t_after_run.steps[1].status == StepStatus.WAITING_APPROVAL

    # 3. Adim 2'yi Onayla -> Tamamlanmali ve COMPLETED olmali
    t_final = await runner.approve_step(task.id, step_id=2)
    assert t_final.status == TaskStatus.COMPLETED
    assert t_final.steps[1].status == StepStatus.COMPLETED
    assert t_final.steps[1].verified is True
