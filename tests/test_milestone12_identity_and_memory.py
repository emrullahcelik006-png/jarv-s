import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from llm.base import LLMResponse
from llm.ollama_provider import OllamaProvider
from services.chat_service import ChatService
from memory.service import MemoryService


@pytest.mark.asyncio
async def test_milestone12_chat_service_injects_sqlite_facts_into_system_prompt(tmp_path):
    """
    IZOLASYON FIX: ChatService artik Dependency Injection ile izole bir
    MemoryService alir. Boylece bu test PRODUCTION veritabanini
    (storage/db/jarvis_memory.db) kirletmez. Daha onceki versiyon bu testi
    production DB'ye yaziyordu ve bu, gercek JARVIS kullaniminda
    "favorite_editor: VS Code Insider" / "user_name: Patron-Test-123"
    seklinde veri sizintisina yol acmisti (benchmark'ta dogrulandi).
    """
    db_path = tmp_path / "test_memory_m12.db"
    db = MemoryService(db_path=str(db_path))
    db.set_fact("favorite_editor", "VS Code Insider")
    db.set_fact("user_name", "Patron-Test-123")

    service = ChatService(memory_service=db)

    mock_response = LLMResponse(content="Anlasildi.", model="test")

    with patch.object(OllamaProvider, "chat", new_callable=AsyncMock, return_value=mock_response) as mock_chat:
        await service.reply(
            user_message="Test",
            session_id="test_session_m12",
            provider_name="ollama"
        )

        args, kwargs = mock_chat.call_args
        sent_messages = kwargs.get("messages") or args[0]
        system_msg = sent_messages[0]

        assert system_msg.role == "system"
        assert "favorite_editor: VS Code Insider" in system_msg.content
        assert "user_name: Patron-Test-123" in system_msg.content
        assert "J.A.R.V.I.S KALICI BELLEK VERİLERİ" in system_msg.content


@pytest.mark.asyncio
async def test_milestone12_sensitive_facts_never_injected(tmp_path):
    """
    Milestone 3 Guvenlik Testi: Hassas anahtarli factlar (password, api_key,
    token vb.) sistem promptuna ASLA enjekte edilmemelidir, normal factlar
    (user_name vb.) ise enjekte edilmeye devam etmelidir.
    """
    db_path = tmp_path / "test_memory_m12_secure.db"
    db = MemoryService(db_path=str(db_path))
    db.set_fact("user_name", "Patron-Test-123")
    db.set_fact("api_key", "sk-super-secret-value-12345")
    db.set_fact("password", "hunter2")

    service = ChatService(memory_service=db)
    mock_response = LLMResponse(content="Anlasildi.", model="test")

    with patch.object(OllamaProvider, "chat", new_callable=AsyncMock, return_value=mock_response) as mock_chat:
        await service.reply(
            user_message="Test",
            session_id="test_session_m12_secure",
            provider_name="ollama"
        )

        args, kwargs = mock_chat.call_args
        sent_messages = kwargs.get("messages") or args[0]
        system_msg = sent_messages[0]

        assert "user_name: Patron-Test-123" in system_msg.content
        assert "sk-super-secret-value-12345" not in system_msg.content
        assert "hunter2" not in system_msg.content


def test_milestone12_identity_prompt_contains_strict_rules():
    from services.chat_service import SYSTEM_IDENTITY_PROMPT
    assert "NEVER claim to be developed by OpenAI" in SYSTEM_IDENTITY_PROMPT
    assert "NEVER claim you have no memory" in SYSTEM_IDENTITY_PROMPT
    assert "NEVER claim you cannot access local files" in SYSTEM_IDENTITY_PROMPT
    assert "independent personal AI agent named JARVIS" in SYSTEM_IDENTITY_PROMPT
