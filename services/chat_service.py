from typing import List, Dict, Any, Optional
from core.config import get_settings
from core.logger import setup_logger
from llm.base import BaseLLMProvider, LLMMessage
from llm.ollama_provider import OllamaProvider
from llm.groq_provider import GroqProvider
from memory.rag_engine import RAGEngine
from memory.service import MemoryService

logger = setup_logger("ChatService")
settings = get_settings()

SYSTEM_IDENTITY_PROMPT = """You are JARVIS, a highly advanced local AI personal agent operating directly on the user's computer.
Your system is built on Python, FastAPI, and local automation tools. You have direct access to the local filesystem, terminal, and system commands through your Agent Runner.

CRITICAL RULES:
- NEVER claim to be developed by OpenAI, ChatGPT, or any generic web service. You are a custom, independent personal AI agent named JARVIS.
- NEVER claim you have no memory, or that you cannot remember past messages. You have a local SQLite database (MemoryService) and a semantic RAG memory store.
- NEVER claim you cannot access local files, run scripts, or perform system actions. You can and do perform these actions via tools.
- Answer questions directly, accurately, and concisely in Turkish unless requested otherwise.
- Keep a professional, capable, yet supportive tone. Avoid generic AI boilerplate language."""

MAX_HISTORY_MESSAGES = 20
# Bellekte tutulan toplam mesaj siniri (system haric). Eskiden yalnizca gonderirken pencereleniyor,
# liste ise oturum boyunca sinirsiz buyuyordu.
MAX_STORED_MESSAGES = 60

# Milestone 3 Guvenlik Katmani: Gelecekte hassas bir bilgi (sifre, API key,
# token vb.) memory'e kaydedilirse, bu bilginin sessizce her mesajda LLM
# system prompt'una enjekte edilmesini engeller. Mevcut facts (user_name,
# user_os, favorite_editor vb.) bu listeyle eslesmedigi icin davranis
# degismez (bkz. test_milestone12 - geriye uyumlu).
SENSITIVE_FACT_KEY_PATTERNS = (
    "password", "passwd", "pwd",
    "api_key", "apikey", "api-key",
    "token", "secret", "credential",
    "private_key", "privatekey",
    "session", "cookie",
)


def _is_sensitive_fact_key(key: str) -> bool:
    lower_key = str(key).lower()
    return any(pattern in lower_key for pattern in SENSITIVE_FACT_KEY_PATTERNS)


class ChatService:
    def __init__(self, memory_service: Optional[MemoryService] = None):
        self.sessions: Dict[str, List[LLMMessage]] = {}
        self.rag_engine = RAGEngine()
        # Milestone 3 Fix: Dependency Injection destegi eklendi.
        # Parametre verilmezse ONCEKI davranis birebir korunur (MemoryService()).
        # Bu sayede testler production DB yerine izole bir DB enjekte edebilir.
        self.memory_service = memory_service or MemoryService()

    def get_session_history(self, session_id: str) -> List[LLMMessage]:
        if session_id not in self.sessions:
            self.sessions[session_id] = [
                LLMMessage(role="system", content=SYSTEM_IDENTITY_PROMPT)
            ]
        return self.sessions[session_id]

    def get_recent_history_text(self, session_id: str, max_messages: int = 6) -> str:
        history = self.get_session_history(session_id)
        recent = history[-max_messages:]
        text_lines = []
        for msg in recent:
            if msg.role != "system":
                text_lines.append(f"{msg.role.upper()}: {msg.content}")
        return "\n".join(text_lines)

    def _build_windowed_history(self, history: List[LLMMessage]) -> List[LLMMessage]:
        if not history:
            return history

        system_messages = [m for m in history if m.role == "system"]
        non_system_messages = [m for m in history if m.role != "system"]

        windowed_non_system = non_system_messages[-MAX_HISTORY_MESSAGES:]
        return system_messages[:1] + windowed_non_system

    @staticmethod
    def _trim_stored_history(history: List[LLMMessage]) -> None:
        """Oturum listesini yerinde kisaltir (ilk system mesaji korunur)."""
        non_system_idx = [i for i, m in enumerate(history) if m.role != "system"]
        excess = len(non_system_idx) - MAX_STORED_MESSAGES
        if excess > 0:
            drop = set(non_system_idx[:excess])
            history[:] = [m for i, m in enumerate(history) if i not in drop]

    async def generate_response(
        self,
        message: str,
        session_id: str = "default",
        provider_name: Optional[str] = None
    ) -> str:
        history = self.get_session_history(session_id)

        try:
            system_context = await self.rag_engine.augment_prompt(user_query=message, base_prompt=SYSTEM_IDENTITY_PROMPT)
        except Exception as rag_err:
            logger.warning(f"RAG Augmentation bypass: {rag_err}")
            system_context = SYSTEM_IDENTITY_PROMPT

        try:
            user_facts = self.memory_service.get_all_user_facts()
            # Milestone 3 Fix: Hassas anahtarlar asla system prompt'a eklenmez.
            safe_facts = {
                k: v for k, v in user_facts.items()
                if not _is_sensitive_fact_key(k)
            }
            if safe_facts:
                facts_lines = [f"- {k}: {v}" for k, v in safe_facts.items()]
                facts_block = "\n".join(facts_lines)
                system_context = (
                    f"{system_context}\n\n"
                    f"=== J.A.R.V.I.S KALICI BELLEK VERİLERİ (SQLITE USER_FACTS) ===\n"
                    f"{facts_block}\n"
                    f"==========================================================="
                )
        except Exception as db_err:
            logger.warning(f"Failed to inject user facts from SQLite: {db_err}")

        if not history or history[0].role != "system":
            history.insert(0, LLMMessage(role="system", content=system_context))
        else:
            history[0] = LLMMessage(role="system", content=system_context)

        history.append(LLMMessage(role="user", content=message))
        self._trim_stored_history(history)
        windowed_history = self._build_windowed_history(history)

        provider: BaseLLMProvider = OllamaProvider(default_model=settings.DEFAULT_CHAT_MODEL)
        if provider_name == "groq":
            provider = GroqProvider()

        try:
            response = await provider.chat(messages=windowed_history, temperature=0.2)
            reply = response.content.strip()
            history.append(LLMMessage(role="assistant", content=reply))
            return reply
        except Exception as e:
            if provider_name != "groq":
                # Birincil saglayici zaten yerel Ollama idi; ayni cagriyi tekrarlamak bekleme suresini ikiye katlar.
                logger.error(f"Ollama yanit hatasi: {e}")
                return f"Bir yanıt oluştururken hata oluştu: {str(e)}"
            logger.warning(f"Primary provider error ({e}), executing local Ollama fallback...")
            try:
                local_provider = OllamaProvider(default_model=settings.DEFAULT_CHAT_MODEL)
                response = await local_provider.chat(messages=windowed_history, temperature=0.2)
                reply = response.content.strip()
                history.append(LLMMessage(role="assistant", content=reply))
                return reply
            except Exception as ex:
                logger.error(f"ChatService fallback generation error: {ex}")
                return f"Bir yanıt oluştururken hata oluştu: {str(ex)}"

    async def reply(
        self,
        user_message: str,
        session_id: str = "default",
        provider_name: Optional[str] = None
    ) -> str:
        return await self.generate_response(
            message=user_message,
            session_id=session_id,
            provider_name=provider_name
        )
