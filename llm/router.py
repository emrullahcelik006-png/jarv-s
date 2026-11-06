from typing import Optional
from core.config import get_settings
from core.json_utils import parse_json_safely
from core.logger import setup_logger
from core.types import IntentResult, IntentType
from llm.base import BaseLLMProvider, LLMMessage
from llm.ollama_provider import OllamaProvider

logger = setup_logger("IntentRouter")
settings = get_settings()

ROUTER_SYSTEM_PROMPT = """You are the Intent Classification Engine of JARVIS AI Agent.
Analyze user input and classify into EXACTLY ONE category: "chat", "task", "system_query".

Reply ONLY with a JSON object:
{
    "intent": "chat" | "task" | "system_query",
    "confidence": 0.9,
    "reasoning": "brief explanation",
    "extracted_goal": "core goal"
}"""


class IntentRouter:
    def __init__(self, provider: Optional[BaseLLMProvider] = None):
        self.provider = provider or OllamaProvider(default_model=settings.DEFAULT_FAST_MODEL)

    async def classify(self, user_input: str) -> IntentResult:
        user_input_trimmed = user_input.strip()
        if not user_input_trimmed:
            return IntentResult(intent=IntentType.CHAT, confidence=1.0, reasoning="Empty input")

        messages = [
            LLMMessage(role="system", content=ROUTER_SYSTEM_PROMPT),
            LLMMessage(role="user", content=f"Input: {user_input_trimmed}"),
        ]

        try:
            response = await self.provider.chat(messages=messages, temperature=0.0)
            data = parse_json_safely(response.content)
            intent_str = data.get("intent", "chat").lower()

            if intent_str not in [e.value for e in IntentType]:
                intent_str = IntentType.CHAT.value

            return IntentResult(
                intent=IntentType(intent_str),
                confidence=float(data.get("confidence", 0.8)),
                reasoning=data.get("reasoning", "Classified by LLM"),
                extracted_goal=data.get("extracted_goal"),
            )
        except Exception as e:
            logger.warning(f"Intent siniflandirma hatasi ({e}), kural tabanli fallback uygulanıyor.")
            return self._rule_based_fallback(user_input_trimmed)

    def _rule_based_fallback(self, text: str) -> IntentResult:
        lower = text.lower()
        if any(kw in lower for kw in ["düzelt", "yaz", "incele", "fix", "create", "dosya", "kod", "test", "rapor", "tara"]):
            return IntentResult(intent=IntentType.TASK, confidence=0.75, reasoning="Rule fallback task", extracted_goal=text)
        return IntentResult(intent=IntentType.CHAT, confidence=0.70, reasoning="Rule fallback chat", extracted_goal=None)
