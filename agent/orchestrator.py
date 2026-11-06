import json
import re
from typing import List, Dict, Any, Optional
from core.logger import setup_logger
from llm.base import LLMMessage
from llm.groq_provider import GroqProvider
from llm.ollama_provider import OllamaProvider

logger = setup_logger("Orchestrator")

class AgentOrchestrator:
    def __init__(self):
        self.main_brain = GroqProvider() # Karar verici olarak güçlü Groq
        self.sub_brain = OllamaProvider() # Analizler için yerel Ollama

    async def collaborate(self, user_goal: str, context: str = "") -> str:
        """Birden fazla ajanı bir araya getirerek en dogru cozumu uretir."""
        logger.info(f"Orkestrasyon basladi: {user_goal}")

        # 1. ADIM: CODER (Kodcu) cozum uretir
        coder_msg = [
            LLMMessage(role="system", content="Sen JARVIS Coder ajanisin. Sadece Python kodu veya teknik cozum uret."),
            LLMMessage(role="user", content=f"Hedef: {user_goal}\nBaglam: {context}")
        ]
        coder_res = await self.main_brain.chat(coder_msg)
        proposed_solution = coder_res.content

        # 2. ADIM: AUDITOR (Denetci) cozumu elestirir ve hatalari bulur
        auditor_msg = [
            LLMMessage(role="system", content="Sen JARVIS Auditor ajanisin. Kodlari ve planlari denetle, eksik import veya mantik hatasi varsa uyar."),
            LLMMessage(role="user", content=f"Coder'in onerisi su: {proposed_solution}\n\nLutfen bu cozumu denetle ve hata varsa soyle yoksa 'TEMIZ' de.")
        ]
        auditor_res = await self.sub_brain.chat(auditor_msg)
        audit_feedback = auditor_res.content

        # 3. ADIM: MASTER (Sentez) Son karari verir
        # Eski kontrol "TEMIZ" alt dizgesini ariyordu: "Kod TEMIZ DEGIL" da temiz sayiliyordu.
        _verdict = re.sub(r"[^A-Z]", "", audit_feedback.upper().replace("İ", "I").replace("Ğ", "G"))
        if _verdict != "TEMIZ":
            logger.warning("Auditor hata buldu, Coder cozumu revize ediyor...")
            final_msg = [
                LLMMessage(role="system", content="Onerilen cozumde hatalar bulundu. Feedback'i dikkate alarak son cozumu uret."),
                LLMMessage(role="user", content=f"Feedback: {audit_feedback}\n\nSon ve hatasiz cozumu Turkce aciklayarak sun.")
            ]
            final_res = await self.main_brain.chat(final_msg)
            return final_res.content
        
        return proposed_solution

orchestrator = AgentOrchestrator()
