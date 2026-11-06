import re
from pathlib import Path
from typing import Optional
from core.config import get_settings
from core.logger import setup_logger
from core.paths import WORKSPACE_ROOT
from memory.service import MemoryService
from tasks.models import StepStatus, Task, TaskStatus, TaskStep
from tasks.service import TaskService
from tools.code_runner import PythonExecuteTool, PythonSyntaxCheckTool, TestRunnerTool
from tools.desktop_vision import DesktopIconClickTool
from tools.dev_mode import SelfCodeAnalysisTool
from tools.docker_control import DockerControlTool
from tools.filesystem import DirectoryCreateTool, DirectoryScanTool, FileReadTool, FileWriteTool
from tools.filesystem_organizer import SystemOrganizerTool
from tools.git_control import GitControlTool
from tools.gui_automation import KeyPressTool
from tools.mouse_control import MouseControlTool
from tools.notification import NotificationTool
from tools.os_control import AppLauncherTool
from tools.patch_engine import AutonomousPatchTool
from tools.process_manager import ProcessKillTool
from tools.registry import ToolRegistry
from tools.report_tool import ProblemAnalysisReportTool
from tools.screen import ScreenCaptureTool
from tools.camera_sensor import CameraVisionTool
from tools.system import SystemInfoTool, NetworkPortHealthTool
from tools.system_control import SystemHardwareControlTool
from tools.terminal import TerminalExecuteTool
from tools.universal_launcher import UniversalLauncherTool
from tools.vision_click import VisionClickTool
from tools.web import AutonomousResearchTool, BrowserDiscoveryTool, DeepWebReaderTool, WebSearchTool
from tools.window_manager import WindowManagerTool
from tools.advanced_os import PipInstallerTool, PowerManagementTool, WindowsServiceTool, DeepFileSearchTool
from tools.memory_inspector import MemoryInspectorTool
from tools.pc_control import PCControlTool

logger = setup_logger("AgentRunner")

# Yan etkisi olan araclar: dogrulama basarisiz oldu diye AYNI adim tekrar calistirilmaz
# (dosya yazma / terminal komutu iki kez uygulanmasin).
SIDE_EFFECT_TOOLS = {
    "file_write", "terminal_execute", "python_execute", "process_kill", "docker_control",
    "git_control", "pip_installer", "power_management", "autonomous_patch", "system_organizer",
    "directory_create", "mouse_control", "key_press", "vision_click", "desktop_icon_click",
    "app_launcher", "universal_launcher", "window_manager", "system_hardware_control",
}

# "No module named X" icindeki import adi ile pip paket adi her zaman ayni degildir.
IMPORT_TO_DIST = {
    "sklearn": "scikit-learn", "cv2": "opencv-python", "pil": "pillow", "yaml": "pyyaml",
    "bs4": "beautifulsoup4", "dotenv": "python-dotenv", "serial": "pyserial", "dateutil": "python-dateutil",
    "win32api": "pywin32", "win32con": "pywin32", "win32gui": "pywin32", "pythoncom": "pywin32",
    "pywintypes": "pywin32", "googlesearch": "googlesearch-python",
}
_PKG_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}$")


def parse_solution_fix(fix: str) -> dict:
    """'package_name=x' ve eski "pip_installer(package_name='x')" bicimlerini ayristirir."""
    s = str(fix or "").strip()
    m = re.search(r"\((.*)\)\s*$", s)
    inner = m.group(1) if m else s
    out = {}
    for part in re.split(r",\s*(?=\w+\s*=)", inner):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip().strip("'\"")
    return out


class AgentRunner:
    def __init__(self, task_service: Optional[TaskService] = None, memory_service: Optional[MemoryService] = None):
        self.task_service = task_service or TaskService()
        self.memory_service = memory_service or MemoryService()
        self.registry = ToolRegistry()
        self._heal_hint = None
        self._register_default_tools()

    def _register_default_tools(self):
        self.registry.register(DirectoryCreateTool())
        self.registry.register(FileReadTool())
        self.registry.register(FileWriteTool())
        self.registry.register(DirectoryScanTool())
        self.registry.register(SystemInfoTool())
        self.registry.register(NetworkPortHealthTool())
        self.registry.register(SystemOrganizerTool())
        self.registry.register(PythonSyntaxCheckTool())
        self.registry.register(PythonExecuteTool())
        self.registry.register(TestRunnerTool())
        self.registry.register(AppLauncherTool())
        self.registry.register(WebSearchTool())
        self.registry.register(DeepWebReaderTool())
        self.registry.register(AutonomousResearchTool())
        self.registry.register(BrowserDiscoveryTool())
        self.registry.register(SelfCodeAnalysisTool())
        self.registry.register(AutonomousPatchTool())
        self.registry.register(ScreenCaptureTool())
        self.registry.register(CameraVisionTool())
        self.registry.register(KeyPressTool())
        self.registry.register(ProcessKillTool())
        self.registry.register(MouseControlTool())
        self.registry.register(TerminalExecuteTool())
        self.registry.register(GitControlTool())
        self.registry.register(SystemHardwareControlTool())
        self.registry.register(UniversalLauncherTool())
        self.registry.register(DesktopIconClickTool())
        self.registry.register(WindowManagerTool())
        self.registry.register(VisionClickTool())
        self.registry.register(ProblemAnalysisReportTool())
        self.registry.register(NotificationTool())
        self.registry.register(DockerControlTool())
        self.registry.register(PipInstallerTool())
        self.registry.register(PowerManagementTool())
        self.registry.register(WindowsServiceTool())
        self.registry.register(DeepFileSearchTool())
        # NOT: approve_pending_task bilerek KAYDEDILMEZ. Onay, LLM tarafindan secilebilen bir arac olamaz;
        # yalnizca arayuz kartlari (/api/v1/tasks/{id}/approve/{step}) uzerinden verilir.
        self.registry.register(MemoryInspectorTool())
        self.registry.register(PCControlTool())

    async def _verify_step_output(self, step: TaskStep, tool_result) -> bool:
        method = str(step.verification_method or "").lower().strip()
        if method in ("none", "", "null"):
            return True
        if method == "syntax_check":
            file_path = step.parameters.get("file_path") or step.parameters.get("path")
            if not file_path:
                return True
            result = await self.registry.execute("syntax_check", file_path=file_path, bypass_approval=True)
            return result.success
        if method == "test_pass":
            test_target = step.parameters.get("test_target") or "tests"
            result = await self.registry.execute("test_runner", test_target=test_target, bypass_approval=True)
            return result.success
        if method == "output_check":
            return bool(tool_result.output) and not bool(tool_result.error)
        return True

    async def _heal_missing_package(self, import_name: str) -> bool:
        """Eksik paketi kurmayi dener. VARSAYILAN KAPALI (AUTO_PIP_INSTALL=false): hata metninden
        turetilen paket adini onaysiz pip ile kurmak tedarik zinciri (typosquatting) riskidir."""
        settings = get_settings()
        if not getattr(settings, "AUTO_PIP_INSTALL", False):
            logger.warning(f"Eksik paket '{import_name}' icin otomatik kurulum KAPALI (AUTO_PIP_INSTALL=false).")
            return False
        dist = IMPORT_TO_DIST.get(str(import_name).lower(), str(import_name))
        if not _PKG_NAME_RE.match(dist):
            logger.warning(f"Gecersiz paket adi reddedildi: {dist!r}")
            return False
        allow = {p.strip().lower() for p in str(getattr(settings, "AUTO_PIP_ALLOWLIST", "") or "").split(",") if p.strip()}
        if allow and dist.lower() not in allow:
            logger.warning(f"'{dist}' AUTO_PIP_ALLOWLIST disinda; otomatik kurulum yapilmadi.")
            return False
        res = await self.registry.execute("pip_installer", bypass_approval=True, package_name=dist)
        return bool(res.success)

    async def _heal_missing_dir(self, dir_path: str) -> bool:
        """Eksik klasoru YALNIZCA proje klasoru icinde olusturur."""
        try:
            target = Path(str(dir_path))
            if not target.is_absolute():
                target = WORKSPACE_ROOT / target
            target = target.resolve()
            if not target.is_relative_to(WORKSPACE_ROOT):
                logger.warning(f"Proje disi klasor otomatik olusturulmadi: {target}")
                return False
        except Exception:
            return False
        res = await self.registry.execute("directory_create", bypass_approval=True, dir_path=str(target))
        return bool(res.success)

    async def _apply_cached_fix(self, fix_tool: str, fix_desc: str) -> bool:
        """Onbellekteki recete yalnizca iki guvenli arac icin uygulanir (rastgele arac tekrar oynatilmaz)."""
        params = parse_solution_fix(fix_desc)
        if fix_tool == "pip_installer" and params.get("package_name"):
            return await self._heal_missing_package(params["package_name"])
        if fix_tool == "directory_create" and params.get("dir_path"):
            return await self._heal_missing_dir(params["dir_path"])
        logger.warning(f"Onbellek recetesi icin desteklenmeyen arac/parametre: {fix_tool} {params}")
        return False

    async def _attempt_self_learning_heal(self, err_msg: str, step: TaskStep) -> bool:
        """
        Milestone 16: Bilinmeyen hatalari analiz eder, GUVENLI recete uygular ve basarili
        olursa cozumu SQLite solution_cache'e kaydeder.
        """
        clean_err = str(err_msg or "").strip()
        if not clean_err:
            return False

        match_mod = re.search(r"(?:ModuleNotFoundError|ImportError):\s*No module named ['\"]([^'\"]+)['\"]", clean_err, re.IGNORECASE)
        if match_mod:
            missing_pkg = match_mod.group(1).split(".")[0]
            dist = IMPORT_TO_DIST.get(missing_pkg.lower(), missing_pkg)
            if await self._heal_missing_package(missing_pkg):
                self.memory_service.save_solution(
                    error_signature=clean_err,
                    tool_name="pip_installer",
                    solution_fix=f"package_name={dist}"
                )
                return True
            self._heal_hint = f"Eksik Python paketi: '{missing_pkg}'. Kurmak icin: pip install {dist}"

        match_fnf = re.search(r"FileNotFoundError:.*?'([^'\"]+)'", clean_err, re.IGNORECASE)
        if match_fnf:
            parent_dir = Path(match_fnf.group(1)).parent
            if parent_dir and str(parent_dir) not in (".", ""):
                if await self._heal_missing_dir(str(parent_dir)):
                    self.memory_service.save_solution(
                        error_signature=clean_err,
                        tool_name="directory_create",
                        solution_fix=f"dir_path={parent_dir}"
                    )
                    return True

        return False

    async def run_task(self, task_id: str) -> Task:
        task = self.task_service.get_task(task_id)
        if not task or not task.steps: raise ValueError("Invalid or empty task")
        task.status = TaskStatus.RUNNING
        self.task_service.save_task(task)

        for step in task.steps:
            if step.status == StepStatus.COMPLETED: continue
            if step.requires_approval and not step.approved:
                step.status = StepStatus.WAITING_APPROVAL
                task.status = TaskStatus.WAITING_FOR_USER
                self.task_service.save_task(task)
                return task

            step.status = StepStatus.RUNNING
            self.task_service.save_task(task)
            tool_to_use = step.tool_name or "reasoning"

            if tool_to_use in ["reasoning", "none", None]:
                step.result = f"Reasoning completed: {step.description}"
                step.status = StepStatus.COMPLETED
                step.verified = True
                task.step_outputs[f"step_{step.id}"] = step.result
                self.task_service.save_task(task)
                continue

            exec_success = False
            while step.retry_count <= step.max_retries and not exec_success:
                tool_result = await self.registry.execute(tool_to_use, bypass_approval=step.approved, **step.parameters)
                if tool_result.success:
                    verified = await self._verify_step_output(step, tool_result)
                    if verified:
                        exec_success = True
                        step.result = str(tool_result.output)
                        step.status = StepStatus.COMPLETED
                        step.verified = True
                        step.error = None
                        task.step_outputs[f"step_{step.id}"] = tool_result.output
                        self.task_service.save_task(task)
                    else:
                        if tool_to_use in SIDE_EFFECT_TOOLS:
                            # Arac zaten calisti; tekrar calistirmak yan etkiyi (dosya yazma, komut...) cogaltir.
                            step.retry_count = step.max_retries
                        step.retry_count += 1
                        step.error = f"Step verification failed for method: '{step.verification_method}'"
                        if step.retry_count <= step.max_retries:
                            task.status = TaskStatus.RECOVERING
                            self.task_service.save_task(task)
                        else:
                            step.status = StepStatus.FAILED
                            task.status = TaskStatus.FAILED
                            task.error_summary = f"Step {step.id} verification failed."
                            self.task_service.save_task(task)
                            return task
                else:
                    err_msg = str(tool_result.error or "")
                    try:
                        err_code = (tool_result.metadata or {}).get("error_code")
                    except Exception:
                        err_code = None
                    if err_code == "approval_required" or "kullanıcı onayı" in err_msg.lower() or "requires approval" in err_msg.lower():
                        step.requires_approval = True
                        step.status = StepStatus.WAITING_APPROVAL
                        task.status = TaskStatus.WAITING_FOR_USER
                        task.error_summary = f"Step {step.id} waiting for user approval."
                        self.task_service.save_task(task)
                        return task

                    healed = False
                    # Milestone 14: Önceden verilere kaydedilmiş hazır reçete var mı?
                    try:
                        cached_solution = self.memory_service.find_solution(err_msg)
                        if cached_solution and cached_solution.get("tool_name"):
                            fix_tool = cached_solution["tool_name"]
                            fix_desc = cached_solution["solution_fix"]
                            logger.info(f"Self-Healing triggered! Applying cached solution '{fix_tool}' for error: {err_msg[:50]}")

                            healed = await self._apply_cached_fix(fix_tool, fix_desc)
                    except Exception as sh_err:
                        logger.warning(f"Self-Healing check failed: {sh_err}")

                    # Milestone 16: Reçete yoksa dinamik hata analizi yap ve çözümü SQLite'a kaydet (Self-Learning Loop)
                    if not healed:
                        try:
                            healed = await self._attempt_self_learning_heal(err_msg, step)
                        except Exception as sl_err:
                            logger.warning(f"Self-Learning healing attempt failed: {sl_err}")

                    step.retry_count += 1
                    step.error = tool_result.error or "Unknown tool execution error"
                    if self._heal_hint:
                        step.error = f"{step.error}\n{self._heal_hint}"
                        self._heal_hint = None
                    if step.retry_count <= step.max_retries:
                        task.status = TaskStatus.RECOVERING
                        self.task_service.save_task(task)
                    else:
                        step.status = StepStatus.FAILED
                        task.status = TaskStatus.FAILED
                        task.error_summary = f"Step {step.id} failed: {step.error}"
                        self.task_service.save_task(task)
                        return task

        task.status = TaskStatus.COMPLETED
        self.task_service.save_task(task)
        return task

    async def approve_step(self, task_id: str, step_id: int) -> Task:
        task = self.task_service.get_task(task_id)
        if not task: raise ValueError("Task not found")
        if task.status == TaskStatus.CANCELLED:
            raise ValueError("Bu gorev iptal edildi veya onay suresi doldu; yeniden olusturun.")
        for step in task.steps:
            if step.id == step_id:
                step.approved = True
                step.status = StepStatus.PENDING
                break
        self.task_service.save_task(task)
        return await self.run_task(task_id)
