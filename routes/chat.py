from fastapi import APIRouter, HTTPException
from agent.dispatcher import ActionDispatcher
from agent.runner import AgentRunner
from agent.orchestrator import orchestrator
from core.types import ChatRequest, ChatResponse
from llm.router import IntentRouter
from memory.service import MemoryService
from services.chat_service import ChatService
from services.diagnostic_service import DiagnosticService
from tasks.service import TaskService
from skills.base import SkillContext
from skills.registry import SkillRegistry

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

intent_router = IntentRouter()
chat_service = ChatService()
task_service = TaskService()
agent_runner = AgentRunner(task_service=task_service)
memory_service = MemoryService()
action_dispatcher = ActionDispatcher(registry=agent_runner.registry)
skill_registry = SkillRegistry()


@router.post("", response_model=ChatResponse)
async def handle_chat_message(request: ChatRequest):
    try:
        history_context = chat_service.get_recent_history_text(request.session_id)

        context = SkillContext(
            request=request,
            history_context=history_context,
            chat_service=chat_service,
            task_service=task_service,
            agent_runner=agent_runner,
            memory_service=memory_service,
            action_dispatcher=action_dispatcher,
            intent_router=intent_router,
            orchestrator=orchestrator
        )

        response = await skill_registry.execute_best_skill(context)
        return response

    except Exception as e:
        diag = DiagnosticService.create_report("CHAT_ROUTE_EXCEPTION", request.message, str(e), context={"provider": request.provider})
        raise HTTPException(status_code=500, detail=f"Sistem Hatası: {diag}")
