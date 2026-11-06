import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Union, Any
from core.logger import setup_logger
from tasks.models import Task, TaskStatus, TaskStep, TaskCreateRequest
from tasks.planner import TaskPlanner

logger = setup_logger("TaskService")
from core.paths import WORKSPACE_ROOT


class TaskService:
    def __init__(self, storage_dir: str = "storage/tasks"):
        self.storage_dir = (WORKSPACE_ROOT / storage_dir).resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    async def create_task(
        self,
        goal: Union[str, TaskCreateRequest, Any],
        steps: Optional[List[TaskStep]] = None
    ) -> Task:
        actual_goal = ""
        auto_plan = False
        context = None

        if isinstance(goal, TaskCreateRequest):
            actual_goal = goal.goal
            auto_plan = goal.auto_plan
            context = goal.context
        elif hasattr(goal, "goal"):
            actual_goal = getattr(goal, "goal")
            auto_plan = getattr(goal, "auto_plan", False)
            context = getattr(goal, "context", None)
        else:
            actual_goal = str(goal)

        if auto_plan and not steps:
            planner = TaskPlanner()
            steps = await planner.create_plan(goal=actual_goal, context=context)

        task_id = str(uuid.uuid4())[:8]
        initial_status = TaskStatus.READY if steps else TaskStatus.CREATED

        task = Task(
            id=task_id,
            goal=actual_goal,
            steps=steps or [],
            status=initial_status
        )
        self.save_task(task)
        logger.info(f"Task created: '{actual_goal}' (ID: {task_id}, Status: {initial_status.value})")
        return task

    def save_task(self, task: Task):
        file_path = self.storage_dir / f"{task.id}.json"
        # Atomik yazim: yarida kesilen yazma gorev dosyasini bozmasin.
        tmp_path = file_path.with_suffix(".json.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(task.model_dump_json(indent=2))
        os.replace(tmp_path, file_path)

    def get_task(self, task_id: str) -> Optional[Task]:
        # Yol gecisi (../) engeli: gorev kimligi yalnizca guvenli karakterler icerebilir.
        if not re.fullmatch(r"[A-Za-z0-9_\-]{1,64}", str(task_id or "")):
            return None
        file_path = self.storage_dir / f"{task_id}.json"
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Task(**data)
        except Exception as e:
            logger.error(f"Error reading task {task_id}: {e}")
            return None

    def update_task_status(self, task_id: str, status: TaskStatus) -> Optional[Task]:
        task = self.get_task(task_id)
        if not task:
            return None
        task.status = status
        self.save_task(task)
        logger.info(f"Task {task_id} status updated to: {status.value}")
        return task

    def list_tasks(self) -> List[Task]:
        tasks = []
        for file_path in self.storage_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                tasks.append(Task(**data))
            except Exception as e:
                logger.error(f"Error loading task file {file_path}: {e}")
        return tasks


    def expire_stale_tasks(self, max_age_hours: float = 24.0) -> int:
        """Suresi dolan bekleyen (onay/hazir) gorevleri iptal eder; eski onay kartlari sonradan
        calistirilamasin. Donus: iptal edilen gorev sayisi."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        pending = (TaskStatus.WAITING_FOR_USER, TaskStatus.CREATED, TaskStatus.READY)
        cancelled = 0
        for task in self.list_tasks():
            created = task.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if task.status in pending and created < cutoff:
                task.status = TaskStatus.CANCELLED
                task.error_summary = "Onay suresi doldu (otomatik iptal)."
                self.save_task(task)
                cancelled += 1
        if cancelled:
            logger.info(f"{cancelled} suresi dolmus bekleyen gorev iptal edildi.")
        return cancelled


# Singleton Instance for Global Task Lifecycle
default_task_service = TaskService()
