import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from services.chat_service import ChatService, MAX_HISTORY_MESSAGES
from llm.base import LLMMessage


def test_windowed_history_keeps_system_message_and_limits_size():
    """
    Milestone 6 regresyon testi: _build_windowed_history, system mesajini
    korumali ve non-system mesaj sayisini MAX_HISTORY_MESSAGES ile
    sinirlamali.
    """
    service = ChatService()

    history = [LLMMessage(role="system", content="SYS")]
    for i in range(50):
        history.append(LLMMessage(role="user", content=f"msg-{i}"))

    windowed = service._build_windowed_history(history)

    assert windowed[0].role == "system"
    assert windowed[0].content == "SYS"
    assert len(windowed) == 1 + MAX_HISTORY_MESSAGES
    # En son mesajlar korunmus olmali (eski mesajlar atilmali)
    assert windowed[-1].content == "msg-49"


def test_windowed_history_short_history_unaffected():
    """Gecmis zaten kisa ise (MAX_HISTORY_MESSAGES altinda), hicbir sey kirpilmamali."""
    service = ChatService()

    history = [LLMMessage(role="system", content="SYS")]
    for i in range(5):
        history.append(LLMMessage(role="user", content=f"msg-{i}"))

    windowed = service._build_windowed_history(history)
    assert len(windowed) == 6


@pytest.mark.asyncio
async def test_generate_response_sends_windowed_history_to_provider():
    """
    Uzun bir oturumda, provider.chat()'e gonderilen mesaj sayisinin
    MAX_HISTORY_MESSAGES + 1 (system) ile sinirli oldugunu dogrular.
    """
    service = ChatService()
    session_id = "test_long_session"

    # Onceden 30 mesajlik yapay bir gecmis olustur
    history = service.get_session_history(session_id)
    for i in range(30):
        history.append(LLMMessage(role="user", content=f"old-msg-{i}"))

    fake_response = MagicMock()
    fake_response.content = "Test cevabi"

    with patch("services.chat_service.OllamaProvider") as MockProvider:
        instance = MockProvider.return_value
        instance.chat = AsyncMock(return_value=fake_response)

        await service.generate_response(message="yeni soru", session_id=session_id)

        call_kwargs = instance.chat.call_args.kwargs
        sent_messages = call_kwargs["messages"]

        # system + son MAX_HISTORY_MESSAGES mesaj = toplam sinirli olmali
        assert len(sent_messages) <= MAX_HISTORY_MESSAGES + 1
