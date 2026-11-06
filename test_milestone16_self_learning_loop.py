import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from agent.runner import AgentRunner
from core.config import get_settings
from memory.service import MemoryService
from tasks.models import Task, TaskStep, TaskStatus
from tasks.service import TaskService


@pytest.mark.asyncio
async def test_milestone16_self_learning_loop_discovers_and_caches_new_recipe(tmp_path, monkeypatch):
    """
    Milestone 16 Test: Onceden kaydedilmemis yeni bir ModuleNotFoundError
    alindiginda, AgentRunner dinamik olarak pip_installer'i calistirmali,
    hatayi duzeltmeli ve bu cozumu gelecekte kullanmak uzere SQLite
    solution_cache veritabanina OTONOM KANITLI olarak kaydetmelidir.

    IZOLASYON FIX (v2): pytest'in tmp_path fixture'i kullanilarak her test
    calistirmasinda tamamen benzersiz ve otomatik temizlenen bir DB dosyasi
    saglanir. Böylece ne diger testlerden ne de bu testin ONCEKI
    calistirmalarindan kalan veri bu testi etkileyemez.
    """
    # Otomatik pip kurulumu varsayilan KAPALI; bu test onu bilincli olarak acar.
    monkeypatch.setattr(get_settings(), "AUTO_PIP_INSTALL", True)
    db_path = tmp_path / "test_memory_m16.db"
    db = MemoryService(db_path=str(db_path))
    test_err_sig = "ModuleNotFoundError: No module named 'scikit_learn'"

    # Onceden veritabaninda bu recete YOK (garanti - yeni/bos DB)
    assert db.find_solution(test_err_sig) is None

    task_dir = tmp_path / "test_tasks_m16"
    task_service = TaskService(storage_dir=str(task_dir))
    runner = AgentRunner(task_service=task_service, memory_service=db)

    step1 = TaskStep(
        id=1,
        title="ML Script Execution",
        description="Machine learning betigi",
        tool_name="python_execute",
        parameters={"file_path": "ml_script.py"},
        risk_level="low"
    )
    task = Task(goal="Test Self Learning Loop", steps=[step1])
    task_service.save_task(task)

    with patch.object(runner.registry, "execute", new_callable=AsyncMock) as mock_exec:
        mock_exec.side_effect = [
            MagicMock(success=False, error=test_err_sig, output=None),
            MagicMock(success=True, output="Successfully installed scikit_learn", error=None),
            MagicMock(success=True, output="ML Execution OK", error=None)
        ]

        result_task = await runner.run_task(task.id)

        call_names = [call.args[0] for call in mock_exec.call_args_list]
        assert "pip_installer" in call_names

        learned_solution = db.find_solution(test_err_sig)
        assert learned_solution is not None
        assert learned_solution["tool_name"] == "pip_installer"
        assert "scikit_learn" in learned_solution["solution_fix"]

        assert result_task.status == TaskStatus.COMPLETED
