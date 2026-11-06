import pytest
from unittest.mock import AsyncMock, MagicMock

from agent.dispatcher import _ACTION_WORDS_RE, _SEARCH_INTENT_RE, tr_lower
from agent.runner import AgentRunner, IMPORT_TO_DIST, parse_solution_fix
from core import runtime_state
from core.config import get_settings
from core.policy import SecurityPolicyEngine, is_sensitive_path, strip_control_args
from tasks.models import Task, TaskStatus
from tasks.service import TaskService
from tools.registry import ToolRegistry
from tools.os_control import normalize_turkish_text, strip_turkish_app_suffixes


def test_control_args_are_stripped():
    cleaned = strip_control_args({"target": "x", "bypass_approval": True, "_approved": 1})
    assert cleaned == {"target": "x"}


def test_approve_pending_task_not_registered_for_llm():
    runner = AgentRunner(task_service=TaskService(storage_dir="storage/test_tasks"))
    assert runner.registry.get("approve_pending_task") is None


@pytest.mark.asyncio
async def test_execute_untrusted_cannot_bypass_approval():
    from tools.base import BaseTool, ToolResult

    class Boom(BaseTool):
        name = "terminal_execute"
        description = "x"

        async def execute(self, **kw):
            return ToolResult(success=True, output="RAN")

    reg = ToolRegistry()
    reg.register(Boom())
    res = await reg.execute_untrusted("terminal_execute", {"command": "echo hi", "bypass_approval": True})
    assert res.success is False
    assert res.metadata.get("error_code") == "approval_required"


@pytest.mark.parametrize("p", [".env", "C:/JARVIS/.env", "~/.ssh/id_rsa", "x/server.pem", "C:/Users/a/.aws/credentials"])
def test_sensitive_paths_detected(p):
    assert is_sensitive_path(p)


def test_normal_paths_not_sensitive():
    assert not is_sensitive_path("notes/todo.txt")


def test_sensitive_read_requires_approval_even_in_god_mode():
    runtime_state.activate_god_mode()
    try:
        _, needs = SecurityPolicyEngine.evaluate_risk("file_read", {"file_path": "C:/JARVIS/.env"})
        assert needs is True
    finally:
        runtime_state.deactivate_god_mode()


def test_god_mode_expires(monkeypatch):
    import time
    monkeypatch.setattr(get_settings(), "GOD_MODE_TTL_MINUTES", 0)
    runtime_state.activate_god_mode()
    try:
        # Saat cozunurlugunden bagimsiz: baslangici 1 sn geriye al
        runtime_state._state["_god_mode_started_monotonic"] = time.monotonic() - 1.0
        assert runtime_state.is_god_mode_active() is False
    finally:
        runtime_state.deactivate_god_mode()


def test_god_mode_requires_exact_phrase():
    from skills.god_mode import GodModeSkill
    skill = GodModeSkill()
    code = get_settings().GOD_MODE_CODE
    assert skill._extract_code_intent(code) == "activate"
    assert skill._extract_code_intent(f"{code} off") == "deactivate"
    assert skill._extract_code_intent(f"{code} numarali model hakkinda bilgi ver, dev mode degil") is None


def test_turkish_lower_and_word_boundaries():
    assert tr_lower("İNTERNETTE ARA") == "internette ara"
    assert not _SEARCH_INTENT_RE.search(tr_lower("arabam bozuldu"))
    assert not _ACTION_WORDS_RE.search(tr_lower("aramizda kalsin"))
    assert _SEARCH_INTENT_RE.search(tr_lower("python internette ara"))


def test_app_name_not_mangled():
    assert strip_turkish_app_suffixes(normalize_turkish_text("Chrome'u aç")) == "chrome"
    assert strip_turkish_app_suffixes(normalize_turkish_text("Opera GX başlat")) == "opera gx"


def test_parse_solution_fix_formats():
    assert parse_solution_fix("package_name=requests") == {"package_name": "requests"}
    assert parse_solution_fix("pip_installer(package_name='requests')") == {"package_name": "requests"}
    assert IMPORT_TO_DIST["sklearn"] == "scikit-learn"


@pytest.mark.asyncio
async def test_auto_pip_disabled_by_default(monkeypatch):
    monkeypatch.setattr(get_settings(), "AUTO_PIP_INSTALL", False)
    runner = AgentRunner(task_service=TaskService(storage_dir="storage/test_tasks"))
    runner.registry.execute = AsyncMock()
    assert await runner._heal_missing_package("requests") is False
    runner.registry.execute.assert_not_called()


@pytest.mark.asyncio
async def test_auto_pip_allowlist_and_name_validation(monkeypatch):
    monkeypatch.setattr(get_settings(), "AUTO_PIP_INSTALL", True)
    monkeypatch.setattr(get_settings(), "AUTO_PIP_ALLOWLIST", "requests")
    runner = AgentRunner(task_service=TaskService(storage_dir="storage/test_tasks"))
    runner.registry.execute = AsyncMock(return_value=MagicMock(success=True))
    assert await runner._heal_missing_package("evilpkg") is False
    assert await runner._heal_missing_package("--index-url=http://x") is False
    assert await runner._heal_missing_package("requests") is True


@pytest.mark.asyncio
async def test_missing_dir_only_inside_workspace():
    runner = AgentRunner(task_service=TaskService(storage_dir="storage/test_tasks"))
    runner.registry.execute = AsyncMock(return_value=MagicMock(success=True))
    assert await runner._heal_missing_dir("C:/Windows/System32/evil") is False
    runner.registry.execute.assert_not_called()


def test_task_id_path_traversal_rejected(tmp_path):
    svc = TaskService(storage_dir=str(tmp_path))
    assert svc.get_task("../../etc/passwd") is None


def test_expire_stale_tasks(tmp_path):
    from datetime import datetime, timedelta, timezone
    svc = TaskService(storage_dir=str(tmp_path))
    old = Task(goal="eski", status=TaskStatus.WAITING_FOR_USER)
    old.created_at = datetime.now(timezone.utc) - timedelta(hours=48)
    fresh = Task(goal="yeni", status=TaskStatus.WAITING_FOR_USER)
    svc.save_task(old)
    svc.save_task(fresh)
    assert svc.expire_stale_tasks(24) == 1
    assert svc.get_task(old.id).status == TaskStatus.CANCELLED
    assert svc.get_task(fresh.id).status == TaskStatus.WAITING_FOR_USER


def test_rag_filters_chat_log_prefixes():
    from memory.rag_engine import CHAT_LOG_PREFIXES
    assert "user query: 'x' | response: 'y'".startswith(CHAT_LOG_PREFIXES)
