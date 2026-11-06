from typing import Any, Dict, List, Optional
import httpx
from core.config import get_settings
from core.logger import setup_logger
from llm.base import BaseLLMProvider, LLMMessage, LLMResponse

logger = setup_logger("OllamaProvider")
settings = get_settings()


class OllamaProvider(BaseLLMProvider):
    def __init__(
        self,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.default_model = default_model or settings.DEFAULT_CHAT_MODEL
        self.timeout = timeout or settings.OLLAMA_TIMEOUT_SECONDS

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/api/version")
                return res.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama baglanti hatasi: {e}")
            return False

    async def list_models(self) -> List[str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    return [m.get("name", "") for m in data.get("models", [])]
                return []
        except Exception as e:
            logger.error(f"Modeller listelenemedi: {e}")
            return []

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        target_model = model or self.default_model
        payload: Dict[str, Any] = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system_prompt:
            payload["system"] = system_prompt

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.post(f"{self.base_url}/api/generate", json=payload)
            if res.status_code != 200:
                raise RuntimeError(f"Ollama generate failed [{res.status_code}]: {res.text}")
            data = res.json()
            return LLMResponse(
                content=data.get("response", ""),
                model=target_model,
                raw_response=data,
            )

    async def chat(
        self,
        messages: List[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        target_model = model or self.default_model
        payload = {
            "model": target_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {"temperature": temperature},
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.post(f"{self.base_url}/api/chat", json=payload)
            if res.status_code != 200:
                raise RuntimeError(f"Ollama chat failed [{res.status_code}]: {res.text}")
            data = res.json()
            return LLMResponse(
                content=data.get("message", {}).get("content", ""),
                model=target_model,
                raw_response=data,
            )
