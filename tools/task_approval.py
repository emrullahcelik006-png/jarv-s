import asyncio
from typing import Optional
from core.logger import setup_logger
from core.types import RiskLevel
from tasks.models import TaskStatus, StepStatus
from tasks.service import default_task_service
from tools.base import BaseTool, ToolResult

logger = setup_logger("TaskApprovalTool")


class ApprovePendingTaskTool(BaseTool):
    name = "approve_pending_task"
    description = "Finds and executes the most recent pending high-risk task approved by the user."
    risk_level = RiskLevel.LOW

    async def execute(self, task_id: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            service = default_task_service
            tasks = service.list_tasks()

            # Find ANY task that has an unapproved step or is waiting for user
            pending_tasks = []
            for t in tasks:
                if t.status in (TaskStatus.WAITING_FOR_USER, TaskStatus.CREATED, TaskStatus.READY):
                    # Check if there's any step requiring approval that isn't finished
                    for step in t.steps:
                        if not step.approved or step.status in (StepStatus.WAITING_APPROVAL, StepStatus.PENDING):
                            pending_tasks.append(t)
                            break

            if not pending_tasks:
                return ToolResult(
                    success=False,
                    output=None,
                    error="Onay bekleyen aktif bir görev bulunamadı."
                )

            # Pick the most recent created task
            target_task = sorted(pending_tasks, key=lambda x: getattr(x, "created_at", 0))[-1]

            # Find the step to approve
            step_to_approve = None
            for step in target_task.steps:
                if not step.approved or step.status in (StepStatus.WAITING_APPROVAL, StepStatus.PENDING):
                    step_to_approve = step
                    break

            if not step_to_approve:
                return ToolResult(success=False, output=None, error="Onaylanacak adım bulunamadı.")

            logger.info(f"Approving task {target_task.id}, step {step_to_approve.id} ({step_to_approve.tool_name})...")

            from agent.runner import AgentRunner
            runner = AgentRunner(task_service=service)
            updated_task = await runner.approve_step(target_task.id, step_to_approve.id)

            step_out = updated_task.step_outputs.get(f"step_{step_to_approve.id}")
            if not step_out and updated_task.error_summary:
                return ToolResult(success=False, output=None, error=updated_task.error_summary)

            return ToolResult(
                success=True,
                output=f"⚡ **[ONAYLANDI VE İCRA EDİLDİ]**: `{step_to_approve.tool_name}` eylemi başarıyla tamamlandı:\n\n{step_out or 'İşlem tamamlandı.'}"
            )

        except Exception as e:
            logger.error(f"Task approval error: {e}")
            return ToolResult(success=False, output=None, error=str(e))
