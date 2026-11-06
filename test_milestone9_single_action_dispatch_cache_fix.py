import pytest
from unittest.mock import AsyncMock, MagicMock
from skills.base import SingleActionSkill, SkillContext


@pytest.mark.asyncio
async def test_single_action_skill_dispatches_only_once():
    """
    Milestone 9 regresyon testi: SingleActionSkill.can_handle() ve execute()
    SIRAYLA cagrildiginda (SkillRegistry.execute_best_skill()'in gercek davranisi),
    action_dispatcher.dispatch() SADECE BIR KEZ cagrilmali.

    FIX ONCESI: Bu sayi 2 olurdu (can_handle + execute ayri ayri dispatch ederdi)
    FIX SONRASI: can_handle() sonucu context._dispatch_cache'e yazilir,
                 execute() bu cache'den okur, tekrar dispatch etmez.
    """
    mock_dispatcher = MagicMock()
    mock_dispatcher.dispatch = AsyncMock(return_value={
        "matched": True,
        "tool_name": "system_info",
        "arguments": {},
        "requires_approval": False,
    })

    mock_tool_result = MagicMock(success=True, output={"os": "Windows"}, error=None)
    mock_registry = MagicMock()
    mock_registry.execute = AsyncMock(return_value=mock_tool_result)

    mock_agent_runner = MagicMock(registry=mock_registry)

    mock_request = MagicMock()
    mock_request.message = "sistem bilgisini goster"
    mock_request.session_id = "test_session_milestone9"
    mock_request.provider = "ollama"

    context = SkillContext(
        request=mock_request,
        history_context="",
        chat_service=None,
        task_service=None,
        agent_runner=mock_agent_runner,
        memory_service=None,
        action_dispatcher=mock_dispatcher,
        intent_router=None,
        orchestrator=None,
    )

    skill = SingleActionSkill()

    # SkillRegistry.execute_best_skill()'in GERCEK davranisini simule et:
    # once can_handle(), sonra (ayni context ile) execute()
    score = await skill.can_handle(context)
    assert score == 0.8

    response = await skill.execute(context)

    # KRITIK KANIT: dispatch sadece 1 kez cagrilmis olmali, 2 degil
    assert mock_dispatcher.dispatch.call_count == 1, \
        f"dispatch() {mock_dispatcher.dispatch.call_count} kez cagrildi, 1 olmali (cift cagri bug'i geri gelmis olabilir)"

    assert response is not None
    assert response.matched_tool == "system_info"


@pytest.mark.asyncio
async def test_single_action_skill_execute_without_can_handle_still_works():
    """
    Savunmaci programlama testi: execute() can_handle() cagrilmadan
    (cache bos iken) dogrudan cagrilirsa, hala calismali (fallback dispatch).
    """
    mock_dispatcher = MagicMock()
    mock_dispatcher.dispatch = AsyncMock(return_value={
        "matched": True,
        "tool_name": "system_info",
        "arguments": {},
        "requires_approval": False,
    })

    mock_tool_result = MagicMock(success=True, output={"os": "Windows"}, error=None)
    mock_registry = MagicMock()
    mock_registry.execute = AsyncMock(return_value=mock_tool_result)
    mock_agent_runner = MagicMock(registry=mock_registry)

    mock_request = MagicMock()
    mock_request.message = "sistem bilgisini goster"
    mock_request.session_id = "test_session_milestone9b"
    mock_request.provider = "ollama"

    context = SkillContext(
        request=mock_request,
        history_context="",
        chat_service=None,
        task_service=None,
        agent_runner=mock_agent_runner,
        memory_service=None,
        action_dispatcher=mock_dispatcher,
        intent_router=None,
        orchestrator=None,
    )

    skill = SingleActionSkill()
    # can_handle() ATLANIYOR - cache bos kalacak
    response = await skill.execute(context)

    # Fallback devreye girmis olmali, hala 1 kez dispatch cagrilmis olmali
    assert mock_dispatcher.dispatch.call_count == 1
    assert response is not None


def test_skill_context_removes_investor_demo_string_leftover():
    """
    Milestone 9 regresyon testi (B2): SkillContext artik unutulmus
    yatirimci demo string'ini temizlemeye calismiyor (dead code kaldirildi).
    Bu test, normal bir mesajin bu replace islemine takilmadan
    oldugu gibi gectigini dogrular.
    """
    mock_request = MagicMock()
    mock_request.message = "Bu normal bir kullanici mesaji 💬 emoji icerebilir"
    mock_request.session_id = "test"
    mock_request.provider = "ollama"

    context = SkillContext(
        request=mock_request,
        history_context="",
        chat_service=None,
        task_service=None,
        agent_runner=None,
        memory_service=None,
        action_dispatcher=None,
        intent_router=None,
        orchestrator=None,
    )

    assert context.user_text == "Bu normal bir kullanici mesaji 💬 emoji icerebilir"
