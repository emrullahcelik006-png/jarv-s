import json
import re
from typing import Any, Dict, Optional, Tuple
from core.config import get_settings
from core.json_utils import parse_json_safely
from core.logger import setup_logger
from core.policy import SecurityPolicyEngine, strip_control_args
from llm.base import BaseLLMProvider, LLMMessage
from llm.ollama_provider import OllamaProvider
from llm.groq_provider import GroqProvider
from tasks.models import RiskLevel
from tools.registry import ToolRegistry

logger = setup_logger("ActionDispatcher")
settings = get_settings()

PURE_CHAT_PATTERNS = [
    r"^(?:merhaba|selam|naber|nasılsın|nasilsin|günaydın|gunaydin|hey|jarvis|hi|hello)\b",
    r"^(?:ne\s+haber|naptın|ne\s+yapıyorsun|kimsin|adın\s+ne|sen\s+kimsin)\b",
    r"^(?:ne\s+yapabilirsin|yeteneklerin\s+neler|neler\s+yapabilirsin|neyi\s+yapabilirsin|yardım|help)\b",
    r"^(?:teşekkür\w*|sağol\w*|harikasın|tamam|anlamadım|anlamadim|ok|okay)\b",
]

def tr_lower(text: str) -> str:
    """Python lower() Turkce 'I/İ' icin hatali sonuc verir ('İ' -> 'i' + birlestirici nokta,
    'I' -> 'i' yerine ayni kalir). Eslesmeler sessizce kacmasin diye once I/İ -> i cevrilir."""
    return str(text).replace("İ", "i").replace("I", "i").lower()


# Kelime-siniri duyarli kaliplar: "arabam" -> 'ara', "aramizda" -> 'ara' sanilmasin.
_ACTION_WORDS_RE = re.compile(
    r"\b(?:aç\w*|kapat\w*|ara|araştır\w*|sil|siler\w*|kur|kurul\w*|yükle\w*|liste\w*)\b"
)
_SEARCH_INTENT_RE = re.compile(r"\b(?:ara|arama|araştır\w*|arat\w*|search|google\w*|internette)\b")
# Uygulama adinin icinde bu oneklerle baslayan sozcuk varsa "uygulama ac" kisayolu kullanilmaz.
_LAUNCH_EXCLUDED_PREFIXES = ("ses", "ekran", "pencere", "bildirim", "hafıza", "rapor", "kütüphane", "internette")

TURKISH_STOP_WORDS_PATTERN = r"\b(lütfen|lutfe|aç\w*|başlat\w*|çalıştır\w*|oyun\w*|uygulama\w*|program\w*|gir\w*|bak\w*|ara\w*|özetle\w*)\b"

DISPATCHER_SYSTEM_PROMPT = r"""You are the Lead Action Dispatcher of the JARVIS AI Agent operating on a Turkish Windows PC.
Analyze the user's Turkish natural language input and select EXACTLY ONE tool ONLY IF the user intends to execute a computer action.

AVAILABLE TOOLS SCHEMA:
{tools_schema}

MUST REPLY ONLY WITH A VALID JSON OBJECT:
{{
    "requires_tool": true,
    "tool_name": "exact_tool_name",
    "arguments": {{ "param_name": "value" }},
    "reasoning": "brief explanation"
}}"""


def _detect_pip_intent(text: str) -> Tuple[bool, str]:
    lower = text.lower()

    negative_patterns = [
        r"\b(bozkurt|kurt|kural|kurgu|kuruluş|kurum|kuruş|okur|okul|kurban|kurs|kurye)\b",
        r"\b(uygulama|oyun|pencere|ekran|ses|program|dosya|klasör|site|video|film|müzik)\b",
        r"\b(ne\s+demek|anlamı|nedir|kimdir|hakkında|mitoloji|tarih|kültür|sembol)\b",
        r"\b(aç|başlat|çalıştır|göster|getir|bul|ara)\b"
    ]

    for pat in negative_patterns:
        if re.search(pat, lower):
            return False, ""

    m = re.search(r"\bpip\s+install\s+([a-zA-Z0-9_\-]+)", lower)
    if m:
        return True, m.group(1)

    m = re.search(r"\b([a-zA-Z0-9_\-]+)\s+(?:kütüphane|kutuphane|paket|modül|modul)\w*\s*(?:kur|yukle|yükle|indir)", lower)
    if m:
        return True, m.group(1)

    m = re.search(r"(?:kütüphane|kutuphane|paket|modül|modul)\s+([a-zA-Z0-9_\-]+)\s*(?:kur|yukle|yükle|indir)", lower)
    if m:
        return True, m.group(1)

    m = re.search(r"\bpip\s+(?:ile\s+)?([a-zA-Z0-9_\-]+)\s*(?:kur|yukle|yükle|indir)", lower)
    if m:
        return True, m.group(1)

    return False, ""


class ActionDispatcher:
    def __init__(self, registry: ToolRegistry, provider: Optional[BaseLLMProvider] = None):
        self.registry = registry
        self.provider = provider or OllamaProvider(default_model=settings.DEFAULT_FAST_MODEL)

    async def dispatch(self, user_input: str, history_context: str = "", provider_override: Optional[str] = None) -> Dict[str, Any]:
        clean_input = user_input.replace('"', '').replace("'", "").strip()
        lower = tr_lower(clean_input)

        is_pip, pkg_name = _detect_pip_intent(clean_input)
        if is_pip and pkg_name:
            clean_pkg = re.sub(r"[^a-z0-9_\-.]", "", pkg_name.lower())
            if clean_pkg:
                risk, req_app = SecurityPolicyEngine.evaluate_risk("pip_installer", {"package_name": clean_pkg})
                logger.info(f"Explicit PIP install matched: '{clean_pkg}'")
                return {
                    "matched": True,
                    "tool_name": "pip_installer",
                    "arguments": {"package_name": clean_pkg},
                    "risk_level": risk,
                    "requires_approval": req_app,
                    "reasoning": f"Direct PIP install trigger for '{clean_pkg}'"
                }

        if any(re.search(pat, lower) for pat in PURE_CHAT_PATTERNS) and not _ACTION_WORDS_RE.search(lower):
            return {"matched": False, "tool_name": None, "arguments": {}}

        _mem_negative = ["kuantum", "ram", "rom", "bellek kartı", "hafıza kartı", "cache", "önbellek", "profesör", "doktor", "motor", "teori", "makale"]
        _mem_positive = ["hafızadaki bilgi", "benim hakkımda ne biliyorsun", "bilgilerimi listele", "kullanıcı bilgilerimi", "beni hatırlıyor musun", "hafızamda ne var"]
        _is_mem_query = (not any(n in lower for n in _mem_negative)) and any(p in lower for p in _mem_positive)
        if _is_mem_query:
            return {
                "matched": True,
                "tool_name": "memory_inspector",
                "arguments": {"action": "list"},
                "risk_level": RiskLevel.LOW,
                "requires_approval": False,
                "reasoning": "Direct Memory Inspection"
            }

        if any(kw in lower for kw in ["sesi kapat", "ses kapat", "sessize al", "mute"]):
            return {"matched": True, "tool_name": "system_hardware_control", "arguments": {"action": "volume_mute"}, "risk_level": RiskLevel.LOW, "requires_approval": False, "reasoning": "Mute"}

        vol_match = re.search(r"ses[iı]?\s*(\d+)\s*(yükselt\w*|arttır\w*|aç\w*|kıs\w*|azalt\w*)", lower)
        if vol_match:
            amount = int(vol_match.group(1))
            verb = vol_match.group(2)
            act = "volume_up" if any(v in verb for v in ["yükselt", "arttır", "aç"]) else "volume_down"
            return {"matched": True, "tool_name": "system_hardware_control", "arguments": {"action": act, "value": amount}, "risk_level": RiskLevel.LOW, "requires_approval": False, "reasoning": f"Volume {act}"}

        launch_match = re.search(r"^(?:lütfen\s+)?(.+?)\s+(?:aç\w*|başlat\w*|çalıştır\w*)$", lower)
        if launch_match:
            target = launch_match.group(1).strip()
            if not any(tok.startswith(_LAUNCH_EXCLUDED_PREFIXES) for tok in target.split()):
                return {"matched": True, "tool_name": "universal_launcher", "arguments": {"target": target}, "risk_level": RiskLevel.LOW, "requires_approval": False, "reasoning": "App Launch"}

        active_provider = GroqProvider() if provider_override == "groq" else self.provider
        tools_schema_str = json.dumps(self.registry.list_tools(), indent=2, ensure_ascii=False)
        system_prompt = f"Select ONE tool for input: {user_input}. Tools: {tools_schema_str}. Reply valid JSON only."

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_input.strip())
        ]

        try:
            response = await active_provider.chat(messages=messages, temperature=0.0)
            data = parse_json_safely(response.content)
            tool_name = data.get("tool_name")

            if data.get("requires_tool") and tool_name and self.registry.get(tool_name):
                args = strip_control_args(data.get("arguments", {}))
                risk, req_app = SecurityPolicyEngine.evaluate_risk(tool_name, args)
                return {
                    "matched": True, "tool_name": tool_name, "arguments": args,
                    "risk_level": risk, "requires_approval": req_app, "reasoning": data.get("reasoning")
                }
        except Exception as exc:
            logger.warning(f"Dispatcher LLM secimi basarisiz, kural tabanli yedek kullanilacak: {exc}")

        if _SEARCH_INTENT_RE.search(lower):
            clean_q = re.sub(r"\b(internette|google|arama\s+yap|ara)\b", "", lower, flags=re.IGNORECASE).strip() or clean_input
            selected_tool = "web_search" if self.registry.get("web_search") else "autonomous_research"
            if self.registry.get(selected_tool):
                return {
                    "matched": True,
                    "tool_name": selected_tool,
                    "arguments": {"query": clean_q},
                    "risk_level": RiskLevel.LOW,
                    "requires_approval": False,
                    "reasoning": f"Rule fallback for {selected_tool}"
                }

        return {"matched": False, "tool_name": None, "arguments": {}}

