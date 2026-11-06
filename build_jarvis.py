import os
from pathlib import Path

# Kurulacak dosyalar ve içerikleri
files = {
    "services/diagnostic_service.py": """import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from core.logger import setup_logger

logger = setup_logger("DiagnosticService")

class DiagnosticService:
    DIAGNOSTICS_DIR = Path("C:/JARVIS/storage/diagnostics")
    @classmethod
    def create_report(cls, event_type: str, user_prompt: str, error_message: str, tool_name: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> str:
        cls.DIAGNOSTICS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filepath = cls.DIAGNOSTICS_DIR / f"DIAG_{timestamp}_{event_type.upper()}.md"
        report_content = f"# ⚠️ J.A.R.V.I.S — SYSTEM DIAGNOSTIC REPORT\n**Tarih:** {datetime.now(timezone.utc)}\n**Olay:** {event_type}\n**Arac:** {tool_name}\n\n## 💬 PROMPT\n> {user_prompt}\n\n## ❌ HATA\n```text\n{error_message}\n```"
        with open(filepath, "w", encoding="utf-8") as f: f.write(report_content)
        return str(filepath)
""",
    "core/identity.py": """from typing import List
class JARVISIdentity:
    @staticmethod
    def get_system_prompt(registered_tools: List[str]) -> str:
        return f"You are J.A.R.V.I.S., a real AI Agent running on Windows 11. Tools: {registered_tools}. Never hallucinate facts."
""",
    "api/routes/chat.py": """from fastapi import APIRouter, HTTPException
from agent.dispatcher import ActionDispatcher
from agent.runner import AgentRunner
from core.types import ChatRequest, ChatResponse, IntentType
from memory.service import MemoryService
from services.chat_service import ChatService
from services.diagnostic_service import DiagnosticService
from tasks.models import RiskLevel, TaskCreateRequest
from tasks.service import TaskService

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])
intent_router = IntentRouter()
chat_service = ChatService()
task_service = TaskService()
agent_runner = AgentRunner(task_service=task_service)
memory_service = MemoryService()
action_dispatcher = ActionDispatcher(registry=agent_runner.registry)

@router.post("", response_model=ChatResponse)
async def handle_chat_message(request: ChatRequest):
    try:
        user_text = request.message.strip()
        dispatch_res = await action_dispatcher.dispatch(user_text)
        if dispatch_res["matched"]:
            tool_name, args = dispatch_res["tool_name"], dispatch_res["arguments"]
            tool_result = await agent_runner.registry.execute(tool_name, **args)
            if tool_result.success:
                return ChatResponse(response=f"⚡ **[EYLEM İCRA EDİLDİ]**\\n\\n{tool_result.output}", intent=IntentType.TASK, provider_used="ollama", model_used=tool_name)
            else:
                diag = DiagnosticService.create_report("FAILURE", user_text, str(tool_result.error), tool_name)
                return ChatResponse(response=f"⚠️ Hata: {tool_result.error}. Rapor: {diag}", intent=IntentType.TASK, provider_used="diag", model_used="diag")
        
        # Basit Hafiza Sorgusu
        if "ben kimim" in user_text.lower():
            f = memory_service.get_all_user_facts()
            return ChatResponse(response=f"Siz Sayın {f.get('user_name','Patron')}siniz.", intent=IntentType.CHAT, provider_used="db", model_used="sqlite")

        reply = await chat_service.reply(user_text)
        return ChatResponse(response=reply, intent=IntentType.CHAT, provider_used="ollama", model_used="qwen")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
"""
}

for rel_path, content in files.items():
    p = Path(f"C:/JARVIS/{rel_path}")
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content.strip())
    print(f"Başarıyla Oluşturuldu: {p}")
