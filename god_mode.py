import re
from core.config import get_settings, IS_COMPILED
from core.runtime_state import (
    activate_god_mode,
    deactivate_god_mode,
    is_god_mode_active,
    get_runtime_snapshot,
)
from core.types import ChatResponse, IntentType
from core.logger import setup_logger
from skills.base import BaseSkill, SkillContext

logger = setup_logger("GodModeSkill")
settings = get_settings()


class GodModeSkill(BaseSkill):
    """
    Milestone 15: Gizli gelistirici gecidi.
    Varsayilan kod: Settings.GOD_MODE_CODE (default '1001').
    Ornek: '1001', '1001 code', '1001 off'
    """
    name = "god_mode"
    description = "Developer override / GOD MODE activation gate."

    def _extract_code_intent(self, text: str):
        # SADECE tam eslesme. Serbest cumle icinde kod gecmesi ("1001 numarali model nedir")
        # God Mode'u asla acmaz.
        raw = " ".join((text or "").strip().lower().split())
        code = str(settings.GOD_MODE_CODE).strip().lower()
        if not code:
            return None
        if raw in (f"{code} off", f"{code} kapat", f"{code} disable", f"{code} exit", "god mode off"):
            return "deactivate"
        if raw in (code, f"{code} code", f"code {code}"):
            return "activate"
        return None

    async def can_handle(self, context: SkillContext) -> float:
        intent = self._extract_code_intent(context.user_text)
        return 1.0 if intent else 0.0

    async def execute(self, context: SkillContext) -> ChatResponse:
        intent = self._extract_code_intent(context.user_text)
        session_id = getattr(context.request, "session_id", "default")

        if intent == "deactivate":
            deactivate_god_mode()
            logger.info("GOD MODE deactivated")
            return ChatResponse(
                response="🔒 **GOD MODE KAPATILDI.** Standart güvenlik politikası yeniden aktif.",
                session_id=session_id,
                intent=IntentType.SYSTEM_QUERY,
                matched_tool="god_mode",
            )

        # activate
        activate_god_mode()
        logger.warning("GOD MODE ACTIVATED by operator")

        facts = {}
        try:
            if context.memory_service:
                facts = context.memory_service.get_all_user_facts() or {}
        except Exception as e:
            facts = {"error": str(e)}

        snap = get_runtime_snapshot()
        lines = [
            "🔓 **GOD MODE AKTİF — DEVELOPER OVERRIDE**",
            "",
            "### Çekirdek Durum",
            f"- **IS_COMPILED:** `{IS_COMPILED}`",
            f"- **ALLOW_SELF_MODIFICATION:** `{settings.ALLOW_SELF_MODIFICATION}`",
            f"- **JARVIS_ENV:** `{settings.JARVIS_ENV}`",
            f"- **God Mode Since:** `{snap.get('god_mode_activated_at')}`",
            f"- **Chat Model:** `{settings.DEFAULT_CHAT_MODEL}`",
            f"- **Fast Model:** `{settings.DEFAULT_FAST_MODEL}`",
            "",
            "### Kalıcı Bellek (user_facts)",
        ]
        if facts:
            for k, v in facts.items():
                lines.append(f"- **{k}:** `{v}`")
        else:
            lines.append("- (kayıt yok)")

        lines.extend([
            "",
            "### Notlar",
            "- GOD MODE path workspace kısıtını gevşetir; HIGH risk onayları hâlâ geçerlidir.",
            "- Derlenmiş (exe) sürümde kaynak kod yama yetenekleri kapalı tutulur.",
            f"- Oturum {settings.GOD_MODE_TTL_MINUTES} dakika sonra otomatik kapanır. Kapatmak için: `{settings.GOD_MODE_CODE} off`",
            "- Hassas dosyalar (.env, .ssh, tarayıcı profilleri vb.) God Mode açıkken de onay ister.",
        ])

        return ChatResponse(
            response="\n".join(lines),
            session_id=session_id,
            intent=IntentType.SYSTEM_QUERY,
            matched_tool="god_mode",
        )
