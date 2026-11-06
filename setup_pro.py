import os
from pathlib import Path

files = {}

# 1. OS CONTROL (AppOpener Entegrasyonu)
files["tools/os_control.py"] = """import os
import re
import AppOpener
from core.logger import setup_logger
from tasks.models import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("OSControlTools")


class AppLauncherTool(BaseTool):
    name = "app_launcher"
    description = "Bilgisayardaki TUM uygulamalari (Spotify, Chrome, Edge, Discord, Steam vb.) AppOpener ile %100 dogru acar ve kapatir."
    risk_level = RiskLevel.MEDIUM

    async def execute(self, target: str, action_type: str = "open", dry_run: bool = False, **kwargs) -> ToolResult:
        try:
            clean_target = target.lower().replace("aç", "").replace("kapat", "").replace("launch", "").replace("open", "").strip()
            clean_target = re.sub(r"['’][a-zçığöşü]+", "", clean_target).strip()

            if dry_run or os.getenv("JARVIS_TEST_MODE") == "true":
                return ToolResult(success=True, output=f"[TEST MODU] Uygulama eylemi simule edildi: {clean_target}")

            if action_type == "close":
                try:
                    AppOpener.close(clean_target, match_closest=True, output=False)
                    return ToolResult(success=True, output=f"🛑 **[APPOPENER]**: '{clean_target.upper()}' uygulamasi kapatildi.")
                except Exception as e:
                    return ToolResult(success=False, output=None, error=f"Uygulama kapatilamadi: {e}")

            # Uygulama Ac
            try:
                AppOpener.open(clean_target, match_closest=True, output=False)
                return ToolResult(
                    success=True,
                    output=f"🚀 **[APPOPENER]**: '{clean_target.upper()}' uygulamasi basariyla baslatildi.",
                    metadata={"target": clean_target}
                )
            except Exception:
                # Fallback os.startfile
                os.startfile(clean_target)
                return ToolResult(success=True, output=f"🚀 **[OS STARTFILE]**: '{clean_target}' baslatildi.")

        except Exception as e:
            logger.error(f"AppLauncher hatasi: {e}")
            return ToolResult(success=False, output=None, error=str(e))
"""

# 2. WINDOW MANAGER (pygetwindow Entegrasyonu)
files["tools/window_manager.py"] = """import pygetwindow as gw
from typing import List, Dict, Any
from core.logger import setup_logger
from tasks.models import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("WindowManagerTools")


class WindowManagerTool(BaseTool):
    name = "window_manager"
    description = "pygetwindow kullanarak acik tum pencereleri listeler (list_windows) veya istenen pencereyi ene getirir (focus_window)."
    risk_level = RiskLevel.MEDIUM

    async def execute(self, action: str = "list_windows", target_title: str = "", **kwargs) -> ToolResult:
        try:
            act = action.lower().strip()
            all_windows = gw.getAllWindows()
            visible_windows = [w for w in all_windows if w.title and w.title.strip() and w.visible]

            if act in ("list_windows", "pencereleri_listele", "listele"):
                titles_list = [f"• `{w.title}`" for w in visible_windows if w.title not in ("Program Manager", "Settings")]
                return ToolResult(
                    success=True,
                    output=f"🖥️ **[BİLGİSAYARDA AÇIK OLAN PENCERELER]** ({len(titles_list)} adet bulundu):\\n\\n" + "\\n".join(titles_list),
                    metadata={"windows": [w.title for w in visible_windows]}
                )

            elif act in ("focus_window", "öneyüz", "one_getir", "focus"):
                clean_target = target_title.lower().strip()
                matched_window = None

                for w in visible_windows:
                    if clean_target in w.title.lower():
                        matched_window = w
                        break

                if matched_window:
                    try:
                        if matched_window.isMinimized:
                            matched_window.restore()
                        matched_window.activate()
                        return ToolResult(
                            success=True,
                            output=f"🖥️ **[PENCERE ÖNE GETİRİLDİ]**: '{matched_window.title}' penceresi öne taşındı ve aktif yapıldı.",
                            metadata={"title": matched_window.title}
                        )
                    except Exception as ex:
                        return ToolResult(success=False, output=None, error=f"Pencere aktif yapilamadi: {ex}")

                return ToolResult(success=False, output=None, error=f"Açık pencereler arasında '{target_title}' bulunamadı.")

            return ToolResult(success=False, output=None, error=f"Bilinmeyen pencere eylemi: {action}")

        except Exception as e:
            logger.error(f"WindowManager hatasi: {e}")
            return ToolResult(success=False, output=None, error=str(e))
"""

# 3. ACTION DISPATCHER (Bağlam ve Referans Çözücü)
files["agent/dispatcher.py"] = """import json
import re
from typing import Any, Dict, List, Optional
from core.config import get_settings
from core.json_utils import parse_json_safely
from core.logger import setup_logger
from llm.base import BaseLLMProvider, LLMMessage
from llm.ollama_provider import OllamaProvider
from llm.groq_provider import GroqProvider
from tools.registry import ToolRegistry

logger = setup_logger("ActionDispatcher")
settings = get_settings()

DISPATCHER_SYSTEM_PROMPT = \"\"\"You are the Action Dispatcher of the JARVIS AI Agent.
Analyze the user's input AND the recent conversation context to select ONE tool if applicable.

REFERENCE RESOLUTION RULE:
- If the user refers to a previous list (e.g., "listede söylediğin ilk pencereyi öne getir", "ikinci dosyayı aç"), look at the recent context, find the EXACT item name, and supply it to the tool!

AVAILABLE TOOLS SCHEMA:
{tools_schema}

MUST REPLY ONLY WITH A VALID JSON OBJECT:
{{
    "requires_tool": true | false,
    "tool_name": "exact_tool_name" | null,
    "arguments": {{ "param_name": "value" }},
    "reasoning": "brief explanation"
}}\"\"\"


class ActionDispatcher:
    def __init__(self, registry: ToolRegistry, provider: Optional[BaseLLMProvider] = None):
        self.registry = registry
        self.provider = provider or OllamaProvider(default_model=settings.DEFAULT_FAST_MODEL)

    async def dispatch(self, user_input: str, history_context: str = "", provider_override: Optional[str] = None) -> Dict[str, Any]:
        active_provider = self.provider
        if provider_override == "groq":
            active_provider = GroqProvider()

        clean_input = user_input.replace('"', '').replace("'", "").strip()
        lower = clean_input.lower()

        # Coklu Rapor Istekleri
        if any(kw in lower for kw in ["rapor oluştur", "rapor yaz", "rapor hazirla", "tara ve", "kaydet ve"]):
            return {"matched": False, "tool_name": None, "arguments": {}}

        tools_schema_str = json.dumps(self.registry.list_tools(), indent=2, ensure_ascii=False)
        system_prompt = DISPATCHER_SYSTEM_PROMPT.format(tools_schema=tools_schema_str)

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="system", content=f"Recent Context/History: {history_context[:1000]}"),
            LLMMessage(role="user", content=f"User Input: {clean_input}"),
        ]

        try:
            response = await active_provider.chat(messages=messages, temperature=0.0)
            data = parse_json_safely(response.content)
            tool_name = data.get("tool_name")

            if data.get("requires_tool") and tool_name and self.registry.get(tool_name):
                args = data.get("arguments", {})
                return {
                    "matched": True,
                    "tool_name": tool_name,
                    "arguments": args,
                    "reasoning": data.get("reasoning", "Selected by LLM Dispatcher"),
                }

        except Exception as e:
            logger.warning(f"ActionDispatcher LLM hatasi ({e}), kural tabanli fallback deneniyor.")

        # Fallback Kurallari
        if "pencere" in lower or "pencereleri" in lower:
            if "listele" in lower or "açık" in lower or "hangi" in lower:
                return {"matched": True, "tool_name": "window_manager", "arguments": {"action": "list_windows"}, "reasoning": "List windows"}
            elif "öne" in lower or "getir" in lower:
                target_title = lower.replace("penceresini", "").replace("penceresi", "").replace("öne getir", "").strip()
                return {"matched": True, "tool_name": "window_manager", "arguments": {"action": "focus_window", "target_title": target_title}, "reasoning": "Focus window"}

        return {"matched": False, "tool_name": None, "arguments": {}}
"""

# 4. CHAT ROUTE (Şeffaf Çıktı & Bağlam Aktarımı)
files["api/routes/chat.py"] = """import re
from fastapi import APIRouter, HTTPException
from agent.dispatcher import ActionDispatcher
from agent.runner import AgentRunner
from agent.orchestrator import orchestrator
from core.types import ChatRequest, ChatResponse, IntentType
from llm.router import IntentRouter
from memory.service import MemoryService
from services.audit_service import SystemAuditService
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
        user_text_clean = user_text.replace("💬 Yatırımcının Komutu (Chat'e yazılacak):", "").strip().strip('"')
        lower_text = user_text_clean.lower()

        # Geçmiş sohbet bağlamını çek
        history_context = chat_service.get_recent_history_text(request.session_id)

        # 1. EKRAN VE VISION
        if "ekran" in lower_text and any(k in lower_text for k in ["görüntüsü", "goruntusu", "al", "çek", "incele", "foto"]):
            screen_res = await agent_runner.registry.execute("screen_capture")
            if screen_res.success:
                chat_service.inject_context(f"Ekran analizi: {screen_res.output}", request.session_id)
                return ChatResponse(response=f"👁️ **[EKRAN GÖRÜŞÜ VE VISION ANALİZİ]**\\n\\n{screen_res.output}", intent=IntentType.TASK, provider_used="groq-vision", model_used="llama-3.2-vision")

        # 2. ACTION DISPATCHER (Bağlam Destekli)
        dispatch_res = await action_dispatcher.dispatch(user_text_clean, history_context=history_context, provider_override=request.provider)
        if dispatch_res["matched"]:
            tool_name = dispatch_res["tool_name"]
            args = dispatch_res["arguments"]

            tool_result = await agent_runner.registry.execute(tool_name, **args)
            if tool_result.success:
                chat_service.inject_context(f"'{tool_name}' calistirildi: {tool_result.output}", request.session_id)
                # ÇIKTIYI DOĞRUDAN VE ŞEFFAF SUN!
                return ChatResponse(
                    response=f"{tool_result.output}",
                    intent=IntentType.TASK,
                    provider_used=request.provider or "ollama",
                    model_used=f"dispatcher->{tool_name}",
                    task_id=None,
                )
            else:
                # OTONOM KURTARMA: Pencere yoksa uygulamayı sıfırdan aç!
                if tool_name == "window_manager" and args.get("action") == "focus_window":
                    target_app = args.get("target_title", user_text_clean)
                    chat_service.inject_context(f"'{target_app}' penceresi acik degildi, otonom baslatiliyor.", request.session_id)
                    app_res = await agent_runner.registry.execute("app_launcher", target=target_app)
                    return ChatResponse(response=f"ℹ️ **[OTONOM MÜDAHALE]**: '{target_app}' penceresi açık değildi, Sizin için başlatıldı.\\n\\n{app_res.output}", intent=IntentType.TASK, provider_used="auto-recovery", model_used="app_launcher")

                diag_file = DiagnosticService.create_report("TOOL_EXECUTION_FAILURE", user_text_clean, str(tool_result.error), tool_name, {"arguments": args})
                return ChatResponse(response=f"⚠️ **[EYLEM ENGELİ TESPİT EDİLDİ]**: `{tool_name}` aracı çalıştırılırken sorun oluştu.\\n\\nHata: {tool_result.error}\\n📝 Teşhis Raporu: `{diag_file}`", intent=IntentType.TASK, provider_used="diagnostic-engine", model_used="auto-diagnostics")

        # 3. CHAT SERVICE YANITI
        reply_text = await chat_service.reply(user_text_clean, session_id=request.session_id, provider_name=request.provider or "ollama")
        return ChatResponse(response=reply_text, intent=IntentType.CHAT, provider_used=request.provider or "ollama", model_used="chat")

    except Exception as e:
        diag = DiagnosticService.create_report("CHAT_ROUTE_EXCEPTION", request.message, str(e))
        raise HTTPException(status_code=500, detail=f"Sistem Hatası: {diag}")
"""

# 5. CHAT SERVICE (Get Recent History Text Desteği)
files["services/chat_service.py"] = """from typing import Dict, List, Optional
from core.config import get_settings
from core.logger import setup_logger
from llm.base import BaseLLMProvider, LLMMessage
from llm.ollama_provider import OllamaProvider
from llm.groq_provider import GroqProvider

logger = setup_logger("ChatService")
settings = get_settings()

JARVIS_CHAT_SYSTEM_PROMPT = '''You are J.A.R.V.I.S., a REAL, fully-integrated, autonomous AI Agent Operating Layer running LOCALLY on the user's Windows machine.
CRITICAL OPERATING RULES:
1. YOU HAVE DIRECT OS & FILE ACCESS. Never say you are just an AI.
2. If the context contains recent tool results or actions, USE THEM to answer the user!
3. Answer clearly, professionally, and directly in Turkish.'''

class ChatService:
    def __init__(self):
        self.ollama = OllamaProvider(default_model=settings.DEFAULT_CHAT_MODEL)
        self.groq = GroqProvider(default_model=settings.GROQ_MODEL)
        self._history: Dict[str, List[LLMMessage]] = {}

    def _get_provider(self, provider_name: Optional[str] = "ollama") -> BaseLLMProvider:
        if (provider_name or "ollama").lower() == "groq": return self.groq
        return self.ollama

    async def reply(self, user_message: str, session_id: str = "default", provider_name: str = "ollama") -> str:
        provider = self._get_provider(provider_name)
        if session_id not in self._history:
            self._history[session_id] = [LLMMessage(role="system", content=JARVIS_CHAT_SYSTEM_PROMPT)]
        
        self._history[session_id].append(LLMMessage(role="user", content=user_message))
        if len(self._history[session_id]) > 25:
            self._history[session_id] = [self._history[session_id][0]] + self._history[session_id][-24:]

        try:
            response = await provider.chat(messages=self._history[session_id])
            self._history[session_id].append(LLMMessage(role="assistant", content=response.content))
            return response.content
        except Exception as e:
            logger.error(f"ChatService hatasi: {e}")
            raise RuntimeError(f"Chat provider hatasi: {e}")

    def inject_context(self, text: str, session_id: str = "default"):
        if session_id not in self._history:
            self._history[session_id] = [LLMMessage(role="system", content=JARVIS_CHAT_SYSTEM_PROMPT)]
        self._history[session_id].append(LLMMessage(role="system", content=f"[SİSTEM/ARAÇ BİLGİSİ]: {text}"))

    def get_recent_history_text(self, session_id: str = "default") -> str:
        if session_id not in self._history:
            return ""
        recent = self._history[session_id][-10:]
        return "\n".join([f"{m.role.upper()}: {m.content}" for m in recent])
"""

# 6. TESTS (AppOpener ve pygetwindow için birim testi)
files["tests/test_pro_tools.py"] = """import pytest
from tools.os_control import AppLauncherTool
from tools.window_manager import WindowManagerTool

@pytest.mark.asyncio
async def test_app_launcher_appopener_dry_run():
    tool = AppLauncherTool()
    res = await tool.execute(target="spotify", dry_run=True)
    assert res.success is True

@pytest.mark.asyncio
async def test_window_manager_list_windows():
    tool = WindowManagerTool()
    res = await tool.execute(action="list_windows")
    assert res.success is True
    assert "AÇIK OLAN PENCERELER" in res.output
"""

for rel_path, content in files.items():
    p = Path(f"C:/JARVIS/{rel_path}")
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    print(f"Başarıyla Yazıldı: {p}")
