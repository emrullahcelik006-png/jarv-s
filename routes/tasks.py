from typing import List
from fastapi import APIRouter, HTTPException
from agent.runner import AgentRunner
from tasks.models import Task, TaskCreateRequest, TaskStep
from tasks.planner import TaskPlanner
from tasks.service import default_task_service

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

task_service = default_task_service
planner = TaskPlanner()
runner = AgentRunner(task_service=task_service)


@router.post("", response_model=Task)
async def create_task(request: TaskCreateRequest):
    try:
        steps: List[TaskStep] = await planner.create_plan(goal=request.goal, context=request.context)
        task = await task_service.create_task(goal=request.goal, steps=steps)
        return task
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Task creation error: {str(e)}")


@router.get("", response_model=List[Task])
async def list_tasks():
    return task_service.list_tasks()


@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: str):
    task = task_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/{task_id}/run", response_model=Task)
async def run_task(task_id: str):
    try:
        return await runner.run_task(task_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")


@router.post("/{task_id}/approve/{step_id}", response_model=Task)
async def approve_step(task_id: str, step_id: int):
    try:
        return await runner.approve_step(task_id, step_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Approval error: {str(e)}")
