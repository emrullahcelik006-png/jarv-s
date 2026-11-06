from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class LLMMessage(BaseModel):
    role: str  # "system", "user", "assistant"
    content: str


class LLMResponse(BaseModel):
    content: str
    model: str
    raw_response: Optional[Dict[str, Any]] = None
    total_tokens: Optional[int] = None


class BaseLLMProvider(ABC):
    @abstractmethod
    async def is_available(self) -> bool:
        """Sağlayıcıya erişilebiliyor mu?"""
        pass

    @abstractmethod
    async def list_models(self) -> List[str]:
        """Kullanılabilir modellerin listesi."""
        pass

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Tekli metin üretimi."""
        pass

    @abstractmethod
    async def chat(
        self,
        messages: List[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Çok turlu konuşma üretimi."""
        pass
