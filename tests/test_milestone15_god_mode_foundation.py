import pytest
from unittest.mock import MagicMock
from core.config import IS_COMPILED, get_settings
from core.runtime_state import (
    activate_god_mode,
    deactivate_god_mode,
    is_god_mode_active,
)
from core.policy import SecurityPolicyEngine
from tasks.models import RiskLevel
from skills.god_mode import GodModeSkill
from skills.base import SkillContext
from skills.registry import SkillRegistry


def test_milestone15_is_compiled_flag_exists():
    assert isinstance(IS_COMPILED, bool)
    settings = get_settings()
    assert hasattr(settings, "GOD_MODE_CODE")
    assert hasattr(settings, "ALLOW_SELF_MODIFICATION")
    assert settings.GOD_MODE_CODE == "1001"


def test_milestone15_god_mode_runtime_toggle():
    deactivate_god_mode()
    assert is_god_mode_active() is False
    activate_god_mode()
    assert is_god_mode_active() is True
    deactivate_god_mode()
    assert is_god_mode_active() is False


def test_milestone15_policy_path_relaxed_in_god_mode():
    deactivate_god_mode()
    # GOD MODE kapali: workspace disi HIGH path -> approval
    risk1, req1 = SecurityPolicyEngine.evaluate_risk(
        "file_write",
        {"file_path": "C:/Windows/Temp/jarvis_god_test.txt"},
    )
    assert risk1 == RiskLevel.HIGH
    assert req1 is True

    activate_god_mode()
    try:
        # GOD MODE acik: path kisiti atlanir; HIGH onay bayragi risk seviyesinden gelir
        risk2, req2 = SecurityPolicyEngine.evaluate_risk(
            "file_write",
            {"file_path": "C:/Windows/Temp/jarvis_god_test.txt"},
        )
        assert risk2 == RiskLevel.HIGH
        assert req2 is True  # onay hâlâ var; sadece path engeli kalkti
    finally:
        deactivate_god_mode()


@pytest.mark.asyncio
async def test_milestone15_god_mode_skill_activates_on_1001():
    deactivate_god_mode()
    skill = GodModeSkill()

    mock_request = MagicMock()
    mock_request.message = "1001 code"
    mock_request.session_id = "god_test"
    mock_request.provider = "ollama"

    mock_memory = MagicMock()
    mock_memory.get_all_user_facts.return_value = {
        "user_name": "Patron",
        "user_role": "Architect",
    }

    ctx = SkillContext(
        request=mock_request,
        history_context="",
        chat_service=None,
        task_service=None,
        agent_runner=None,
        memory_service=mock_memory,
        action_dispatcher=None,
        intent_router=None,
        orchestrator=None,
    )

    score = await skill.can_handle(ctx)
    assert score == 1.0

    resp = await skill.execute(ctx)
    assert is_god_mode_active() is True
    assert "GOD MODE AKTİF" in resp.response
    assert "Patron" in resp.response
    assert "IS_COMPILED" in resp.response

    # kapat
    mock_request.message = "1001 off"
    ctx2 = SkillContext(
        request=mock_request,
        history_context="",
        chat_service=None,
        task_service=None,
        agent_runner=None,
        memory_service=mock_memory,
        action_dispatcher=None,
        intent_router=None,
        orchestrator=None,
    )
    resp2 = await skill.execute(ctx2)
    assert is_god_mode_active() is False
    assert "KAPATILDI" in resp2.response


@pytest.mark.asyncio
async def test_milestone15_god_mode_skill_registered_first():
    reg = SkillRegistry()
    assert reg.skills[0].name == "god_mode"
