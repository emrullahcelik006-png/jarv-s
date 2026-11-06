from abc import ABC, abstractmethod
import re
from typing import Any, Dict, List, Optional
from core.types import ChatResponse, IntentType
from core.logger import setup_logger
from core.policy import strip_control_args
from skills.context_resolver import ContextResolver
from tasks.models import TaskStep, TaskStatus, RiskLevel

logger = setup_logger("Skills")


def format_tool_output(tool_name: str, output: Any) -> str:
    if isinstance(output, dict):
        if tool_name == "system_info":
            return (
                f"💻 **[SİSTEM METRİKLERİ]**\n\n"
                f"• **İşletim Sistemi:** `{output.get('os', 'Windows')}`\n"
                f"• **İşlemci (CPU):** %{output.get('cpu_percent', 0.0)} (16 Çekirdek)\n"
                f"• **Bellek (RAM):** %{output.get('ram_used_percent', 0.0)} (Toplam {output.get('ram_total_gb', 0)} GB)\n"
                f"• **Disk (C:):** %{output.get('disk_used_percent', 0.0)} Doluluk"
            )
        lines = [f"• **{k.replace('_', ' ').title()}:** {v}" for k, v in output.items()]
        return "📊 **[İŞLEM SONUCU]**\n\n" + "\n".join(lines)
    return str(output)


async def build_approval_response(context, tool_name: str, args: Dict[str, Any]) -> ChatResponse:
    """Yuksek riskli eylem icin bekleyen gorev + onay karti olusturur (tum skill'ler icin tek ortak yol)."""
    args = strip_control_args(args)
    step = TaskStep(
        id=1,
        title=f"Execute {tool_name}",
        description=f"Execute {tool_name} with arguments {args}",
        tool_name=tool_name,
        parameters=args,
        risk_level=RiskLevel.HIGH,
        requires_approval=True
    )
    task = await context.task_service.create_task(
        goal=f"Single High-Risk Action: {tool_name}",
        steps=[step]
    )
    context.task_service.update_task_status(task.id, TaskStatus.WAITING_FOR_USER)
    return ChatResponse(
        response=f"⚠️ **[YÜKSEK RİSKLİ EYLEM — KULLANICI ONAYI BEKLENİYOR]**\n\n**Araç:** `{tool_name}`\n**Parametreler:** `{args}`\n**Görev ID:** `{task.id}`",
        session_id=context.request.session_id,
        intent=IntentType.TASK,
        provider_used=getattr(context.request, "provider", "ollama"),
        task_id=task.id,
        matched_tool=tool_name
    )


class SkillContext:
    def __init__(self, request, history_context, chat_service, task_service, agent_runner, memory_service, action_dispatcher, intent_router, orchestrator):
        self.request = request
        raw_msg = getattr(request, "message", str(request))
        # Milestone 9 fix (B2): Unutulmus demo/yatirimci test senaryosu kalintisi
        # kaldirildi (.replace("Yatirimcinin Komutu...")). Her tek kullanici
        # mesajinda calisan ama hicbir gercek amaca hizmet etmeyen kod temizlendi.
        self.user_text = raw_msg.strip().strip('"').strip()
        self.lower_text = self.user_text.lower()
        self.history_context = history_context
        self.chat_service = chat_service
        self.task_service = task_service
        self.agent_runner = agent_runner
        self.memory_service = memory_service
        self.action_dispatcher = action_dispatcher
        self.intent_router = intent_router
        self.orchestrator = orchestrator
        # Milestone 9 fix (B1): SkillRegistry.execute_best_skill() ayni context
        # instance'ini once can_handle()'a, sonra secilen skill'in execute()'una
        # gecirir. SingleActionSkill ikisinde de ayni argumanlarla dispatch()
        # cagirdigi icin (LLM cagrisi icerebilen) bu islem iki kez yapiliyordu.
        # Bu cache, can_handle() sonucunu execute()'a tasir, cift cagriyi onler.
        self._dispatch_cache: Optional[Dict[str, Any]] = None


class BaseSkill(ABC):
    name: str
    description: str

    @abstractmethod
    async def can_handle(self, context: SkillContext) -> float: pass
    @abstractmethod
    async def execute(self, context: SkillContext) -> ChatResponse: pass


class ScreenAnalysisSkill(BaseSkill):
    name = "screen_analysis"
    description = "Ekran görüntüsü alma ve görsel analiz."

    async def can_handle(self, context: SkillContext) -> float:
        if getattr(context.request, "image_data", None):
            return 1.0
        text = context.lower_text
        if any(kw in text for kw in ["ekranı incele", "ekran görüntüsü", "ekranımda ne var", "ekranı oku", "screenshot"]):
            return 1.0
        return 0.0

    async def execute(self, context: SkillContext) -> ChatResponse:
        try:
            img_data = getattr(context.request, "image_data", None)
            res = await context.agent_runner.registry.execute(
                "screen_capture",
                image_data=img_data,
                prompt=context.user_text
            )
            out_text = res.output if res.success else f"Görsel analizi yapılamadı: {res.error}"
            return ChatResponse(
                response=str(out_text),
                session_id=context.request.session_id,
                intent=IntentType.VISION,
                provider_used=getattr(context.request, "provider", "groq"),
                matched_tool="screen_capture"
            )
        except Exception as e:
            return ChatResponse(
                response=f"Görsel analizi hatası: {e}",
                session_id=context.request.session_id,
                intent=IntentType.VISION,
                provider_used=getattr(context.request, "provider", "ollama")
            )


class ProblemReportSkill(BaseSkill):
    name = "problem_report"
    description = "Sorun analizi ve raporlama."

    async def can_handle(self, context: SkillContext) -> float:
        return 1.0 if any(kw in context.lower_text for kw in ["rapor oluştur", "sorun analizi", "hata raporu"]) else 0.0

    async def execute(self, context: SkillContext) -> ChatResponse:
        res = await context.agent_runner.registry.execute("problem_analysis_report")
        return ChatResponse(
            response=str(res.output),
            session_id=context.request.session_id,
            intent=IntentType.SYSTEM_QUERY,
            matched_tool="problem_analysis_report"
        )


class ContextReferenceSkill(BaseSkill):
    name = "context_reference"
    description = "Sıralı bağlam atıflarını çözer."

    async def can_handle(self, context: SkillContext) -> float:
        return 0.95 if ContextResolver.resolve_reference(context.user_text, context.history_context) else 0.0

    async def execute(self, context: SkillContext) -> ChatResponse:
        item = ContextResolver.resolve_reference(context.user_text, context.history_context)
        res = await context.action_dispatcher.dispatch(item, context.history_context)
        if res.get("matched"):
            # Onceden bu yol risk kontrolu yapmadan dogrudan calistiriyordu.
            if res.get("requires_approval"):
                return await build_approval_response(context, res["tool_name"], res.get("arguments", {}))
            tool_res = await context.agent_runner.registry.execute(res["tool_name"], **strip_control_args(res.get("arguments", {})))
            if not tool_res.success:
                return ChatResponse(response=f"Hata: {tool_res.error}", session_id=context.request.session_id, intent=IntentType.TASK, matched_tool=res["tool_name"])
            out = format_tool_output(res["tool_name"], tool_res.output)
            return ChatResponse(response=f"🚀 **[BAĞLAM ÇÖZÜLDÜ]**: {out}", session_id=context.request.session_id, intent=IntentType.TASK)
        return ChatResponse(response=f"Seçilen öge: {item}", session_id=context.request.session_id)


class SingleActionSkill(BaseSkill):
    name = "single_action"
    description = "Tekil donanım, uygulama veya sistem eylemlerini yönlendirir ve çalıştırır."

    async def can_handle(self, context: SkillContext) -> float:
        dispatch_res = await context.action_dispatcher.dispatch(context.user_text, context.history_context, provider_override=context.request.provider)
        # Milestone 9 fix: sonucu context uzerinde cachele, execute() ayni
        # argumanlarla tekrar dispatch cagirmasin (cift LLM cagrisi/gecikme onlenir).
        context._dispatch_cache = dispatch_res
        return 0.8 if dispatch_res.get("matched") else 0.0

    async def execute(self, context: SkillContext) -> ChatResponse:
        # Milestone 9 fix: can_handle() zaten dispatch ettiyse cache'den oku.
        # Savunmaci programlama: eger bu skill can_handle() cagrilmadan dogrudan
        # execute edilirse (normal akista olmaz ama garanti icin), yeniden dispatch et.
        dispatch_res = context._dispatch_cache
        if dispatch_res is None:
            logger.warning("SingleActionSkill.execute() called without prior can_handle() cache; re-dispatching.")
            dispatch_res = await context.action_dispatcher.dispatch(context.user_text, context.history_context, provider_override=context.request.provider)

        tool_name = dispatch_res.get("tool_name")
        args = strip_control_args(dispatch_res.get("arguments", {}))
        req_app = dispatch_res.get("requires_approval", False)

        if req_app:
            return await build_approval_response(context, tool_name, args)

        res = await context.agent_runner.registry.execute(tool_name, **args)
        out_str = format_tool_output(tool_name, res.output) if res.success else f"Hata: {res.error}"
        return ChatResponse(
            response=out_str,
            session_id=context.request.session_id,
            intent=IntentType.TASK,
            provider_used=getattr(context.request, "provider", "ollama"),
            matched_tool=tool_name
        )


class GeneralChatSkill(BaseSkill):
    name = "general_chat"
    description = "Genel sohbet yanıtları üretir."

    async def can_handle(self, context: SkillContext) -> float:
        return 0.1

    async def execute(self, context: SkillContext) -> ChatResponse:
        reply = await context.chat_service.reply(context.user_text, context.request.session_id, context.request.provider)
        return ChatResponse(response=reply, session_id=context.request.session_id)
