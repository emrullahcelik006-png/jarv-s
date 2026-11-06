"""In-memory runtime flags (oturum bazli, diske yazilmaz)."""
import time
from datetime import datetime, timezone
from typing import Any, Dict

_state: Dict[str, Any] = {
    "god_mode_active": False,
    "god_mode_activated_at": None,
    "_god_mode_started_monotonic": None,
}


def _ttl_seconds() -> float:
    try:
        from core.config import get_settings
        return float(get_settings().GOD_MODE_TTL_MINUTES) * 60.0
    except Exception:
        return 3600.0


def is_god_mode_active() -> bool:
    """GOD MODE suresiz acik kalamaz: TTL dolunca kendiliginden kapanir."""
    if not _state.get("god_mode_active"):
        return False
    started = _state.get("_god_mode_started_monotonic")
    if started is not None and (time.monotonic() - started) > _ttl_seconds():
        deactivate_god_mode()
        return False
    return True


def activate_god_mode() -> None:
    _state["god_mode_active"] = True
    _state["god_mode_activated_at"] = datetime.now(timezone.utc).isoformat()
    _state["_god_mode_started_monotonic"] = time.monotonic()


def deactivate_god_mode() -> None:
    _state["god_mode_active"] = False
    _state["god_mode_activated_at"] = None
    _state["_god_mode_started_monotonic"] = None


def get_runtime_snapshot() -> Dict[str, Any]:
    snap = dict(_state)
    snap.pop("_god_mode_started_monotonic", None)
    return snap
