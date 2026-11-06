from typing import Optional
from core.config import get_settings
from core.logger import setup_logger
from memory.vector_store import VectorMemoryStore

logger = setup_logger("RAGEngine")

# Eski surumlerin sohbetten otomatik kaydettigi satirlar ("User Query: '...' | Response: '...'") MODEL
# cevaplarini icerir ve halusinasyonlar dahil geri beslenirdi (hafiza zehirlenmesi).
CHAT_LOG_PREFIXES = ("user query:", "kullanici sorusu:", "kullanıcı sorusu:")

FAST_BYPASS_KEYWORDS = ["merhaba", "selam", "naber", "nasılsın", "nasilsin", "günaydın", "hey", "jarvis", "teşekkür"]


class RAGEngine:
    def __init__(self, vector_store: Optional[VectorMemoryStore] = None):
        self.vector_store = vector_store or VectorMemoryStore()

    async def augment_prompt(self, user_query: str, base_prompt: str) -> str:
        """Kullanici sorgusuna en yakin semantik hafizayi arayip prompt'a RAG baglami olarak ekler."""
        clean_q = user_query.strip().lower()

        # Fast Bypass for short greetings/simple chat to eliminate embedding search latency
        if len(clean_q) < 6 or any(clean_q.startswith(kw) for kw in FAST_BYPASS_KEYWORDS):
            return base_prompt

        # Sohbet kayitlarini elemek icin biraz fazla aday cek, sonra filtrele.
        candidates = await self.vector_store.search_similar(user_query, limit=8, threshold=0.40)
        if not get_settings().RAG_INCLUDE_CHAT_LOG:
            candidates = [
                m for m in candidates
                if not str(m.get("content", "")).strip().lower().startswith(CHAT_LOG_PREFIXES)
                and (m.get("metadata") or {}).get("source") != "chat"
            ]
        similar_memories = candidates[:2]
        if not similar_memories:
            return base_prompt

        context_str = "\n".join([f"• [{m['category'].upper()}] {m['content']}" for m in similar_memories])
        augmented = (
            f"{base_prompt}\n\n"
            f"=== J.A.R.V.I.S SEMANTİK GEÇMİŞ HAFIZA BAĞLAMI (RAG CONTEXT) ===\n"
            f"{context_str}\n"
            f"===============================================================\n"
            f"Kullanıcının sorusuna yanıt verirken yukarıdaki geçmiş semantik hafıza verilerini öncelikli dikkate al."
        )
        logger.info(f"RAG Baglami enjekte edildi ({len(similar_memories)} adet anlamsal baglam bulundu).")
        return augmented
