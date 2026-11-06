import os
import re
from pathlib import Path
from typing import Tuple, Dict, Any
from core.logger import setup_logger
from tasks.models import RiskLevel

logger = setup_logger("SecurityPolicy")
from core.paths import WORKSPACE_ROOT
USER_HOME = Path(os.path.expanduser("~")).resolve()

ALLOWED_READ_LAUNCH_ROOTS = [
    WORKSPACE_ROOT,
    USER_HOME,
    Path("C:/"),
    Path("D:/"),
    Path("E:/"),
    Path(r"C:\ProgramData"),
    Path(r"C:\Program Files"),
    Path(r"C:\Program Files (x86)"),
]

FILE_PATH_ALIASES = ("file_path", "filepath", "path", "filename", "file", "target_file", "target")
DIR_PATH_ALIASES = ("dir_path", "dir", "directory", "folder", "folder_path", "target_dir")
ALL_PATH_ALIASES = FILE_PATH_ALIASES + DIR_PATH_ALIASES

TOOL_RISK_MAP = {
    "file_write": RiskLevel.HIGH,
    "file_read": RiskLevel.LOW,
    "directory_create": RiskLevel.LOW,
    "directory_scan": RiskLevel.LOW,
    "python_execute": RiskLevel.HIGH,
    "terminal_execute": RiskLevel.HIGH,
    "process_kill": RiskLevel.HIGH,
    "docker_control": RiskLevel.HIGH,
    "autonomous_patch": RiskLevel.HIGH,
    "pip_installer": RiskLevel.HIGH,
    "power_management": RiskLevel.HIGH,
    "windows_service_manager": RiskLevel.LOW,  # yalnizca durum okur
    "self_code_analysis": RiskLevel.LOW,  # yalnizca proje kodunu okur/analiz eder
    "system_hardware_control": RiskLevel.LOW,
    "window_manager": RiskLevel.MEDIUM,
    "app_launcher": RiskLevel.LOW,
    "universal_launcher": RiskLevel.LOW,
    "web_search": RiskLevel.LOW,
    "deep_web_reader": RiskLevel.LOW,
    "toast_notification": RiskLevel.LOW,
    "screen_capture": RiskLevel.LOW,
    "camera_vision": RiskLevel.LOW,
    "system_info": RiskLevel.LOW,
    "git_control": RiskLevel.MEDIUM,
    "problem_analysis_report": RiskLevel.LOW,
    "reasoning": RiskLevel.LOW,
    "deep_file_search": RiskLevel.MEDIUM,
    "system_organizer": RiskLevel.MEDIUM,
    "memory_inspector": RiskLevel.LOW,
    "network_port_health": RiskLevel.LOW,
    "autonomous_research": RiskLevel.LOW,
    "browser_discovery": RiskLevel.LOW,
    "desktop_icon_click": RiskLevel.MEDIUM,
    "vision_click": RiskLevel.HIGH,
    "key_press": RiskLevel.MEDIUM,
    "mouse_control": RiskLevel.LOW,
    "pc_control": RiskLevel.MEDIUM,
    "syntax_check": RiskLevel.LOW,
    "test_runner": RiskLevel.LOW,
}

ALIAS_MAP = {
    "write_file": "file_write",
    "read_file": "file_read",
    "create_directory": "directory_create",
    "scan_directory": "directory_scan",
    "kill_process": "process_kill",
    "exec_terminal": "terminal_execute",
    "run_python": "python_execute",
    "execute_python": "python_execute",
    "install_package": "pip_installer",
    "shutdown": "power_management",
    "lock_pc": "power_management",
}


# Onaysiz (LOW riskli) araclarla bile okunmasi istenmeyen yollar. Bu yollar HIGH + onay gerektirir
# ve GOD MODE ile GEVSEMEZ.
SENSITIVE_PATH_PATTERNS = (
    r"(^|/)\.env(\..*)?$",
    r"(^|/)\.ssh(/|$)",
    r"(^|/)id_(rsa|dsa|ecdsa|ed25519)(\.pub)?$",
    r"\.(pem|pfx|p12|kdbx|ppk)$",
    r"/(login data|cookies|local state|web data)$",
    r"/\.aws/",
    r"/\.config/gcloud",
    r"/appdata/(local|roaming)/(google/chrome|microsoft/edge|mozilla/firefox|opera software)",
    r"/windows/system32/config/",
)
_SENSITIVE_RE = [re.compile(p) for p in SENSITIVE_PATH_PATTERNS]

# LLM / kullanici metninden gelen arguman sozlugunde ASLA bulunmamasi gereken kontrol-duzlemi anahtarlari.
CONTROL_ARG_KEYS = ("bypass_approval", "_approved", "bypass")


def strip_control_args(args: Any) -> Dict[str, Any]:
    """LLM'den gelen arguman sozlugunden kontrol anahtarlarini (bypass_approval vb.) temizler."""
    if not isinstance(args, dict):
        return {}
    return {k: v for k, v in args.items() if str(k).lower() not in CONTROL_ARG_KEYS}


def is_sensitive_path(path_value: Any) -> bool:
    """Gizli bilgi icerebilecek yol mu? (.env, .ssh, tarayici profilleri, anahtar dosyalari...)"""
    raw = str(path_value or "").strip().strip("\"'")
    if not raw:
        return False
    candidates = {raw.replace("\\", "/").lower()}
    try:
        candidates.add(str(Path(raw).expanduser().resolve()).replace("\\", "/").lower())
    except Exception:
        pass
    return any(rx.search(c) for rx in _SENSITIVE_RE for c in candidates)


class SecurityPolicyEngine:
    @staticmethod
    def normalize_tool_name(tool_name: str) -> str:
        clean_name = str(tool_name).lower().strip()
        return ALIAS_MAP.get(clean_name, clean_name)

    @staticmethod
    def evaluate_risk(tool_name: str, arguments: Dict[str, Any]) -> Tuple[RiskLevel, bool]:
        canonical_name = SecurityPolicyEngine.normalize_tool_name(tool_name)
        risk = TOOL_RISK_MAP.get(canonical_name, RiskLevel.HIGH)

        # Milestone 15: GOD MODE aktifse workspace path kisiti gevsetilir
        # (HIGH risk onay gereksinimi KORUNUR — sadece path engeli kaldirilir).
        god_mode = False
        try:
            from core.runtime_state import is_god_mode_active
            god_mode = is_god_mode_active()
        except Exception:
            god_mode = False

        path_args = [arguments.get(alias) for alias in ALL_PATH_ALIASES if arguments.get(alias)]

        # Hassas yollar: GOD MODE dahil her durumda onay iste.
        for val in path_args:
            if is_sensitive_path(val):
                logger.warning(f"Sensitive path access escalated to approval: {val}")
                return RiskLevel.HIGH, True

        if path_args and not god_mode:
            for file_path_arg in path_args:
                try:
                    target_path = Path(str(file_path_arg)).expanduser().resolve()
                    if risk == RiskLevel.HIGH:
                        if not target_path.is_relative_to(WORKSPACE_ROOT):
                            logger.warning(f"Workspace path restriction enforced: {target_path}")
                            return RiskLevel.HIGH, True
                    else:
                        is_allowed = any(
                            target_path == root or target_path.is_relative_to(root)
                            for root in ALLOWED_READ_LAUNCH_ROOTS
                            if root.exists()
                        )
                        if not is_allowed:
                            logger.warning(f"Unallowed directory read attempt: {target_path}")
                            return RiskLevel.HIGH, True
                except Exception as e:
                    logger.error(f"Path evaluation error: {e}")
                    return RiskLevel.HIGH, True

        if canonical_name == "pip_installer":
            raw_pkg = str(arguments.get("package_name") or arguments.get("package") or "").strip()
            clean_pkg = raw_pkg.split()[0].lower() if raw_pkg else ""
            clean_pkg = re.sub(r"[^a-z0-9_\-.]", "", clean_pkg)
            arguments["package_name"] = clean_pkg
            arguments["package"] = clean_pkg

        requires_approval = (risk == RiskLevel.HIGH)
        return risk, requires_approval
