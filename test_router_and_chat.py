import pytest
from unittest.mock import patch, AsyncMock
from core.types import IntentType
from llm.router import IntentRouter
from llm.base import LLMResponse
from llm.ollama_provider import OllamaProvider
from llm.groq_provider import GroqProvider
from services.chat_service import ChatService


@pytest.mark.asyncio
async def test_intent_router_chat_detection():
    router = IntentRouter()
    result = await router.classify("Merhaba JARVIS, bugun gunun nasil geciyor?")
    assert result.intent == IntentType.CHAT
    assert result.confidence >= 0.5


@pytest.mark.asyncio
async def test_intent_router_task_detection():
    router = IntentRouter()
    result = await router.classify("Python projesindeki requirements.txt dosyasini incele ve eksik paketleri bul")
    assert result.intent == IntentType.TASK
    assert result.extracted_goal is not None or result.confidence >= 0.5


@pytest.mark.asyncio
async def test_intent_router_system_detection():
    router = IntentRouter()
    result = await router.classify("Bilgisayardaki CPU ve RAM kullanim oranlari nedir?")
    assert result.intent in [IntentType.SYSTEM_QUERY, IntentType.TASK]


@pytest.mark.asyncio
async def test_chat_service_reply_ollama_executes_real_pipeline_with_mocked_network():
    """
    Milestone 10 fix: Onceki versiyon ChatService.reply()'in KENDISINI mock'luyordu,
    bu yuzden gercek kod (history yonetimi, provider secimi, RAG, windowed history)
    hic calismiyordu ve test hicbir kosulda kirmiziya dusemiyordu (kendi yalanini
    dogruluyordu - mock sabit "Sonuc: 4" donduruyor, test de icinde "4" ariyordu).

    Bu versiyon SADECE network sinirini (OllamaProvider.chat -> gercek HTTP istegi)
    mock'lar. ChatService.generate_response() icindeki TUM gercek mantik
    (history olusturma, RAG augmentation, windowed history, provider secimi,
    session state guncelleme) gercekten calisir ve kanitlanir.
    """
    service = ChatService()
    mock_response = LLMResponse(content="4", model="test-model")

    with patch.object(OllamaProvider, "chat", new_callable=AsyncMock, return_value=mock_response) as mock_chat:
        reply = await service.reply(
            user_message="2 + 2 kac eder? Sadece sayiyi yaz.",
            session_id="test_session_ollama_real",
            provider_name="ollama",
        )

    # Gercek kod calisti mi kaniti: provider.chat() tam olarak 1 kez cagrilmali
    assert mock_chat.call_count == 1, "Provider.chat() tam olarak 1 kez cagrilmali"
    assert reply == "4"

    # Session history GERCEKTEN guncellenmis mi (gercek state mutation kaniti -
    # eski testte bu imkansizdi cunku reply() mock'tu, hicbir state degismiyordu)
    history = service.get_session_history("test_session_ollama_real")
    roles = [m.role for m in history]
    assert "user" in roles
    assert "assistant" in roles
    assert history[-1].content == "4"


@pytest.mark.asyncio
async def test_chat_service_reply_groq_executes_real_pipeline_with_mocked_network():
    """
    Milestone 10 fix (Groq variant): Ayni mantik, Groq provider icin.
    Ek olarak: provider_name='groq' secildiginde GERCEKTEN GroqProvider.chat()
    cagrildigini, OllamaProvider.chat()'in HIC cagrilmadigini dogrular
    (provider routing mantiginin gercekten calistiginin kaniti).
    """
    service = ChatService()
    mock_response = LLMResponse(content="OK", model="llama-3.3-70b")

    with patch.object(GroqProvider, "chat", new_callable=AsyncMock, return_value=mock_response) as mock_groq_chat, \
         patch.object(OllamaProvider, "chat", new_callable=AsyncMock) as mock_ollama_chat:
        reply = await service.reply(
            user_message="Respond ONLY with the word OK",
            session_id="test_session_groq_real",
            provider_name="groq",
        )

    assert mock_groq_chat.call_count == 1, "GroqProvider.chat() cagrilmali"
    assert mock_ollama_chat.call_count == 0, "provider_name='groq' iken OllamaProvider.chat() cagrilmamali (routing hatasi)"
    assert reply == "OK"


@pytest.mark.asyncio
async def test_chat_service_falls_back_to_ollama_when_primary_provider_fails():
    """
    Milestone 10 bonus test: generate_response()'daki try/except fallback
    zincirini GERCEKTEN tetikleyip dogrular. Onceki test suite'inde bu
    fallback mekanizmasi hic test edilmiyordu. Birincil provider (groq)
    hata verdiginde, sistem gercekten yerel Ollama'ya fallback yapmali.
    """
    service = ChatService()
    mock_fallback_response = LLMResponse(content="Fallback yaniti", model="local-model")

    with patch.object(GroqProvider, "chat", new_callable=AsyncMock, side_effect=RuntimeError("Groq 429 Rate Limit")), \
         patch.object(OllamaProvider, "chat", new_callable=AsyncMock, return_value=mock_fallback_response) as mock_ollama_chat:
        reply = await service.reply(
            user_message="Test fallback mekanizmasi",
            session_id="test_session_fallback",
            provider_name="groq",
        )

    assert mock_ollama_chat.call_count == 1, "Groq hata verince Ollama fallback cagrilmali"
    assert reply == "Fallback yaniti"
