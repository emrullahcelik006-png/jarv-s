import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class IntentType(str, Enum):
    CHAT = "chat"
    TASK = "task"
    SYSTEM_QUERY = "system_query"
    VISION = "vision"


class IntentResult(BaseModel):
    intent: IntentType
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    suggested_model: Optional[str] = None
    extracted_goal: Optional[str] = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    stream: bool = False
    provider: Optional[str] = "ollama"
    image_data: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: Optional[str] = "default"
    intent: Optional[IntentType] = IntentType.CHAT
    provider_used: Optional[str] = "ollama"
    model_used: Optional[str] = "default"
    task_id: Optional[str] = None
    matched_tool: Optional[str] = None
