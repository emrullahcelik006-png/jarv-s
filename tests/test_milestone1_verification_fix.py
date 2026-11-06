import pytest
from pathlib import Path
from tasks.models import RiskLevel, StepStatus, Task, TaskStep, TaskStatus
from tasks.service import TaskService
from agent.runner import AgentRunner

from core.paths import WORKSPACE_ROOT


@pytest.mark.asyncio
async def test_agent_runner_syntax_check_verification_passes_on_valid_code():
    """
    Milestone 1 regresyon testi:
    TOOL_RISK_MAP icinde 'syntax_check' tanimsiz oldugu icin varsayilan HIGH
    risk aliyordu ve dahili dogrulama cagrisi guvenlik kapisina takilip
    HER ZAMAN False donuyordu. agent/runner.py::_verify_step_output artik
    bypass_approval=True gonderiyor, bu testin PASS olmasi gerekir.
    """
    task_service = TaskService(storage_dir="storage/test_tasks")
    runner = AgentRunner(task_service=task_service)

    target_file = "storage/test_tasks/milestone1_valid_syntax.py"
    full_path = WORKSPACE_ROOT / target_file

    try:
        task = Task(
            goal="Milestone1 - Syntax Check Verification (Valid Code)",
            steps=[
                TaskStep(
                    id=1,
                    title="Gecerli Python Dosyasi Yaz",
                    description="Syntax check dogrulamasi icin gecerli kod yazar",
                    tool_name="file_write",
                    parameters={
                        "file_path": target_file,
                        "content": "def add(a, b):\n    return a + b\n",
                    },
                    risk_level=RiskLevel.HIGH,
                    requires_approval=False,
                    approved=True,
                    verification_method="syntax_check",
                ),
            ],
        )
        task_service.save_task(task)

        result = await runner.run_task(task.id)

        assert result.status == TaskStatus.COMPLETED, (
            f"Beklenen COMPLETED, gelen: {result.status}. "
            f"Step error: {result.steps[0].error}"
        )
        assert result.steps[0].status == StepStatus.COMPLETED
        assert result.steps[0].verified is True
        assert result.steps[0].error is None
    finally:
        # TEMIZLIK: Bu dosya gecerli syntax icerdigi icin baska testleri
        # bozma riski dusuk, ama tutarlilik icin yine de temizliyoruz.
        if full_path.exists():
            full_path.unlink()


@pytest.mark.asyncio
async def test_agent_runner_syntax_check_verification_fails_on_invalid_code():
    """
    Negatif kontrol: Guvenlik engeli kalktiktan sonra, syntax_check
    gercekten calisiyor mu ve hatali kodu dogru sekilde yakaliyor mu?
    Bu test, duzeltmenin 'her zaman True donen' bir sahte onaya
    donusmedigini kanitlar.

    ONEMLI: Bu test kasitli olarak bozuk syntax'li bir .py dosyasi
    workspace icine yazar. SelfCodeAnalysisTool gibi diger araclar
    workspace'i tarayip bu dosyayi 'syntax hatasi' olarak raporlayabilir.
    Bu yuzden test sonunda dosya MUTLAKA silinmelidir (finally bloku).
    """
    task_service = TaskService(storage_dir="storage/test_tasks")
    runner = AgentRunner(task_service=task_service)

    target_file = "storage/test_tasks/milestone1_invalid_syntax.py"
    full_path = WORKSPACE_ROOT / target_file

    try:
        task = Task(
            goal="Milestone1 - Syntax Check Verification (Invalid Code)",
            steps=[
                TaskStep(
                    id=1,
                    title="Hatali Python Dosyasi Yaz",
                    description="Syntax check dogrulamasinin hatayi yakaladigini test eder",
                    tool_name="file_write",
                    parameters={
                        "file_path": target_file,
                        "content": "def broken_function(:\n    pass",
                    },
                    risk_level=RiskLevel.HIGH,
                    requires_approval=False,
                    approved=True,
                    verification_method="syntax_check",
                    max_retries=0,
                ),
            ],
        )
        task_service.save_task(task)

        result = await runner.run_task(task.id)

        assert result.status == TaskStatus.FAILED
        assert result.steps[0].status == StepStatus.FAILED
        assert result.steps[0].verified is False
    finally:
        # ZORUNLU TEMIZLIK: Bu dosya bozuk syntax icerdigi icin
        # SelfCodeAnalysisTool gibi workspace-genelinde tarama yapan
        # araclari/testleri bozmamasi icin test basarili da olsa,
        # basarisiz da olsa MUTLAKA silinmelidir.
        if full_path.exists():
            full_path.unlink()
