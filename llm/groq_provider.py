import asyncio
from typing import Any, Dict, List, Optional
import httpx
from core.config import get_settings
from core.logger import setup_logger
from llm.base import BaseLLMProvider, LLMMessage, LLMResponse

logger = setup_logger("GroqProvider")
settings = get_settings()


class GroqProvider(BaseLLMProvider):
    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.base_url = "https://api.groq.com/openai/v1"
        self.default_model = default_model or settings.GROQ_MODEL
        self.timeout = timeout

    async def is_available(self) -> bool:
        if not self.api_key:
            return False
        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = f"{self.base_url}/models"
        
        try:
            async with httpx.AsyncClient(timeout=10.0, trust_env=True) as client:
                res = await client.get(url, headers=headers)
                return res.status_code == 200
        except Exception as e:
            logger.warning(f"Groq async check warning ({e}), retrying via thread-isolated sync client...")
            try:
                def _sync_check():
                    with httpx.Client(timeout=10.0, trust_env=True) as sync_client:
                        return sync_client.get(url, headers=headers).status_code == 200
                return await asyncio.to_thread(_sync_check)
            except Exception as ex:
                logger.error(f"Groq is_available sync fallback error: {ex}")
                return False

    async def list_models(self) -> List[str]:
        if not self.api_key:
            return []
        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = f"{self.base_url}/models"

        try:
            async with httpx.AsyncClient(timeout=10.0, trust_env=True) as client:
                res = await client.get(url, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    return [m.get("id", "") for m in data.get("data", [])]
        except Exception as e:
            logger.warning(f"Groq list_models async warning ({e}), retrying via sync fallback...")

        # Sync Thread Fallback
        try:
            def _sync_list():
                with httpx.Client(timeout=10.0, trust_env=True) as sync_client:
                    r = sync_client.get(url, headers=headers)
                    if r.status_code == 200:
                        return [m.get("id", "") for m in r.json().get("data", [])]
                    return []
            return await asyncio.to_thread(_sync_list)
        except Exception as ex:
            logger.error(f"Groq list_models sync fallback error: {ex}")
            return []

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        messages = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        messages.append(LLMMessage(role="user", content=prompt))
        return await self.chat(messages=messages, model=model, temperature=temperature)

    async def chat(
        self,
        messages: List[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        if not self.api_key:
            raise ValueError("Groq API anahtari ayarlanmamis!")

        target_model = model or self.default_model
        payload = {
            "model": target_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"

        # 1) Ag istegi. YALNIZCA ag/baglanti hatalarinda sync yedek denenir; HTTP hata kodlari
        #    (429/500 vb.) ag hatasi degildir ve ikinci istek gondermek kotayi iki katina cikarirdi.
        res = None
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=True) as client:
                res = await client.post(url, json=payload, headers=headers)
        except (httpx.TransportError, OSError) as e:
            logger.warning(f"Groq chat async network error ({e}), retrying via thread-isolated sync client...")
            def _sync_post():
                with httpx.Client(timeout=self.timeout, trust_env=True) as sync_client:
                    return sync_client.post(url, json=payload, headers=headers)
            res = await asyncio.to_thread(_sync_post)

        # 2) Model adi gecersizse (400/404) mevcut bir sohbet modeline duserek BIR kez daha dene (async).
        if res.status_code in (404, 400):
            fallback_model = await self._pick_fallback_model(headers, exclude=payload["model"])
            if fallback_model:
                logger.warning(f"Groq model '{payload['model']}' reddedildi ({res.status_code}); '{fallback_model}' deneniyor.")
                payload["model"] = fallback_model
                target_model = fallback_model
                async with httpx.AsyncClient(timeout=self.timeout, trust_env=True) as client:
                    res = await client.post(url, json=payload, headers=headers)

        if res.status_code != 200:
            raise RuntimeError(f"Groq API hatasi [{res.status_code}]: {res.text[:500]}")

        data = res.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return LLMResponse(
            content=content,
            model=target_model,
            raw_response=data,
            total_tokens=data.get("usage", {}).get("total_tokens"),
        )

    async def _pick_fallback_model(self, headers: Dict[str, str], exclude: str) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=10.0, trust_env=True) as client:
                m_res = await client.get(f"{self.base_url}/models", headers=headers)
            if m_res.status_code != 200:
                return None
            available = [m.get("id", "") for m in m_res.json().get("data", [])]
        except Exception as e:
            logger.warning(f"Groq model listesi alinamadi: {e}")
            return None
        chat_models = [
            m for m in available
            if m and m != exclude and not any(x in m.lower() for x in ["guard", "whisper", "embed", "safeguard", "vision", "tts"])
        ]
        if not chat_models:
            return None
        preferred = [m for m in chat_models if "llama-3.3" in m or "llama-3.1" in m or "llama3" in m]
        return preferred[0] if preferred else chat_models[0]
