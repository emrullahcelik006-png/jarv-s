import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from agent.runner import AgentRunner
from core.config import get_settings
from memory.service import MemoryService
from tasks.models import Task, TaskStep, TaskStatus, StepStatus
from tasks.service import TaskService


@pytest.mark.asyncio
async def test_milestone14_agent_runner_triggers_self_healing_from_solution_cache(monkeypatch):
    """
    Milestone 14 Test: AgentRunner adim yürütülürken hata verdiginde,
    MemoryService.find_solution() ile SQLite'dan receteyi bulmali ve
    otonom olarak fix tool'unu calistirmalidir.
    """
    # Otomatik pip kurulumu varsayilan KAPALI; bu test onu bilincli olarak acar.
    monkeypatch.setattr(get_settings(), "AUTO_PIP_INSTALL", True)
    db = MemoryService()
    test_err_sig = "ModuleNotFoundError: No module named 'requests'"
    
    # Receteyi SQLite veritabanina kaydedelim
    db.save_solution(
        error_signature=test_err_sig,
        tool_name="pip_installer",
        solution_fix="pip_installer(package_name='requests')"
    )

    task_service = TaskService(storage_dir="storage/test_tasks_m14")
    runner = AgentRunner(task_service=task_service, memory_service=db)

    # Adim olustur (Low risk ama hatali tool parametresi simule edilecek)
    step1 = TaskStep(
        id=1,
        title="Python Script Execute",
        description="Hatali betik calistir",
        tool_name="python_execute",
        parameters={"file_path": "non_existent_file.py"},
        risk_level="low"
    )
    task = Task(goal="Test Self Healing", steps=[step1])
    task_service.save_task(task)

    # python_execute ilk denemede hata versin, recete tetiklensin
    with patch.object(runner.registry, "execute", new_callable=AsyncMock) as mock_exec:
        # 1. cagri (python_execute) -> Hata dönsün
        # 2. cagri (pip_installer - self healing) -> Başarı dönsün
        # 3. cagri (python_execute tekrar) -> Başarı dönsün
        mock_exec.side_effect = [
            MagicMock(success=False, error=test_err_sig, output=None),
            MagicMock(success=True, output="Installed", error=None),
            MagicMock(success=True, output="Execution OK", error=None)
        ]

        result_task = await runner.run_task(task.id)

        # KANIT 1: Self-healing fix tool (pip_installer) otonom tetiklendi mi?
        call_names = [call.args[0] for call in mock_exec.call_args_list]
        assert "pip_installer" in call_names
        
        # KANIT 2: Task en sonunda basariyla tamamlandi mi?
        assert result_task.status == TaskStatus.COMPLETED
