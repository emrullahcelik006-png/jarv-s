import pytest
from tasks.models import RiskLevel, TaskCreateRequest, TaskStatus
from tasks.planner import TaskPlanner
from tasks.service import TaskService


@pytest.mark.asyncio
async def test_task_planner_generates_steps_ollama():
    planner = TaskPlanner()
    steps = await planner.create_plan(
        goal="Python dosyasindaki syntax hatasini bul ve duzelt",
        context="Proje root klasorunde"
    )
    assert len(steps) >= 2
    assert any(s.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH] for s in steps)
    assert steps[0].id == 1


@pytest.mark.asyncio
async def test_task_service_lifecycle_and_persistence():
    service = TaskService(storage_dir="storage/test_tasks")
    
    # 1. Olustur ve Planla
    task = await service.create_task(
        TaskCreateRequest(
            goal="Test Gorevi - README dosyasini guncelle",
            auto_plan=True,
            provider="ollama"
        )
    )
    assert task.id is not None
    assert task.status in [TaskStatus.READY, TaskStatus.PLANNING]
    assert len(task.steps) > 0

    # 2. Get Task
    fetched = service.get_task(task.id)
    assert fetched is not None
    assert fetched.goal == task.goal

    # 3. Status Guncelleme
    updated = service.update_task_status(task.id, TaskStatus.RUNNING)
    assert updated.status == TaskStatus.RUNNING
