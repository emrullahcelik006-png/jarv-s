import pytest
from pathlib import Path
from services.diagnostic_service import DiagnosticService
from tasks.models import TaskCreateRequest
from tasks.service import TaskService


@pytest.mark.asyncio
async def test_diagnostic_service_creates_report():
    report_file = DiagnosticService.create_report(
        event_type="TEST_FAILURE",
        user_prompt="Masaüstünü tara",
        error_message="Test Hata Mesaji",
        tool_name="directory_scan",
        context={"env": "pytest"}
    )
    assert Path(report_file).exists()
    with open(report_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert "TEST_FAILURE" in content
    assert "Test Hata Mesaji" in content


@pytest.mark.asyncio
async def test_auto_run_low_risk_tasks():
    task_service = TaskService(storage_dir="storage/test_tasks")
    task = await task_service.create_task(
        TaskCreateRequest(
            goal="Sistem bilgisini kontrol et",
            auto_plan=True,
            provider="ollama"
        )
    )
    assert task.id is not None
    assert len(task.steps) > 0
