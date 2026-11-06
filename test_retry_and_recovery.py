import pytest
from agent.runner import AgentRunner
from tasks.models import RiskLevel, StepStatus, Task, TaskStep, TaskStatus
from tasks.service import TaskService


@pytest.mark.asyncio
async def test_agent_runner_retry_mechanism():
    task_service = TaskService(storage_dir="storage/test_tasks")
    runner = AgentRunner(task_service=task_service)

    task = Task(
        goal="Test Retry Mechanism",
        steps=[
            TaskStep(
                id=1,
                title="Gecersiz Arac Cagrisi",
                description="Hata verecek arac",
                tool_name="non_existent_tool_xyz",
                risk_level=RiskLevel.LOW,
                max_retries=1,
            )
        ]
    )
    task_service.save_task(task)

    t_result = await runner.run_task(task.id)
    assert t_result.status == TaskStatus.FAILED
    assert t_result.steps[0].retry_count == 2  # İlk deneme + 1 retry
    assert t_result.steps[0].status == StepStatus.FAILED


@pytest.mark.asyncio
async def test_agent_runner_step_outputs_propagation():
    task_service = TaskService(storage_dir="storage/test_tasks")
    runner = AgentRunner(task_service=task_service)

    task = Task(
        goal="Test Step Outputs",
        steps=[
            TaskStep(
                id=1,
                title="Sistem Bilgisi Oku",
                description="Sistem metrikleri",
                tool_name="system_info",
                risk_level=RiskLevel.LOW,
            )
        ]
    )
    task_service.save_task(task)

    t_result = await runner.run_task(task.id)
    assert t_result.status == TaskStatus.COMPLETED
    assert "step_1" in t_result.step_outputs
    assert "cpu_cores" in t_result.step_outputs["step_1"]
