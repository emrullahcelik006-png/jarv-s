import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from core.types import RiskLevel


class TaskStatus(str, Enum):
    CREATED = "created"
    PLANNING = "planning"
    READY = "ready"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    RECOVERING = "recovering"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskStep(BaseModel):
    id: int
    title: str
    description: str
    tool_name: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.LOW
    requires_approval: bool = False
    approved: bool = False
    status: StepStatus = StepStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    verification_method: Optional[str] = None
    verified: bool = False
    retry_count: int = 0
    max_retries: int = 2


class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    goal: str
    context: Optional[str] = None
    status: TaskStatus = TaskStatus.CREATED
    steps: List[TaskStep] = Field(default_factory=list)
    step_outputs: Dict[str, Any] = Field(default_factory=dict)  # Adımlar arası veri aktarım havuzu
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    error_summary: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskCreateRequest(BaseModel):
    goal: str
    context: Optional[str] = None
    auto_plan: bool = True
    provider: Optional[str] = "ollama"
