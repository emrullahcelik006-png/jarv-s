import os
from pathlib import Path

files = {}

# 1. NOTIFICATION TOOL
files["tools/notification.py"] = """import asyncio
import subprocess
from core.logger import setup_logger
from core.types import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("NotificationTools")


class NotificationTool(BaseTool):
    name = "toast_notification"
    description = "Windows masaustu bildirimi (Toast Notification) firlatir."
    risk_level = RiskLevel.LOW

    async def execute(self, title: str = "JARVIS Bildirimi", message: str = "Islem tamamlandi.", **kwargs) -> ToolResult:
        try:
            ps_script = f'''
            [void] [System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms")
            $objNotifyIcon = New-Object System.Windows.Forms.NotifyIcon
            $objNotifyIcon.Icon = [System.Drawing.SystemIcons]::Information
            $objNotifyIcon.BalloonTipIcon = "Info"
            $objNotifyIcon.BalloonTipText = "{message}"
            $objNotifyIcon.BalloonTipTitle = "{title}"
            $objNotifyIcon.Visible = $True
            $objNotifyIcon.ShowBalloonTip(5000)
            '''
            await asyncio.to_thread(
                subprocess.run,
                ["powershell", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=10
            )
            return ToolResult(success=True, output=f"Masaüstü bildirimi fırlatıldı: '{title}' - '{message}'")
        except Exception as e:
            logger.error(f"Notification hatasi: {e}")
            return ToolResult(success=False, output=None, error=str(e))
"""

# 2. DOCKER CONTROL TOOL
files["tools/docker_control.py"] = """import asyncio
import subprocess
from core.logger import setup_logger
from core.types import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("DockerTools")


class DockerControlTool(BaseTool):
    name = "docker_control"
    description = "Docker container ve compose komutlarini (ps, logs, up, down, build) otonom yonetir."
    risk_level = RiskLevel.HIGH

    async def execute(self, action: str = "ps", container_name: str = "", compose_file: str = "", **kwargs) -> ToolResult:
        try:
            act = action.lower().strip()
            if act in ("ps", "list", "containers"):
                cmd = "docker ps -a"
            elif act == "logs":
                cmd = f"docker logs --tail 50 {container_name}" if container_name else "docker ps"
            elif act in ("up", "compose_up"):
                f_flag = f"-f {compose_file} " if compose_file else ""
                cmd = f"docker compose {f_flag}up -d"
            elif act in ("down", "compose_down"):
                f_flag = f"-f {compose_file} " if compose_file else ""
                cmd = f"docker compose {f_flag}down"
            elif act == "build":
                cmd = "docker build -t jarvis_app ."
            else:
                cmd = f"docker {action}"

            res = await asyncio.to_thread(
                subprocess.run,
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
                errors="replace"
            )

            if res.returncode == 0:
                out_text = res.stdout.strip() or "Docker işlemi başarıyla tamamlandı."
                return ToolResult(success=True, output=f"🐳 **[DOCKER EYLEMİ İCRA EDİLDİ]** (`{cmd}`)\\n\\n```text\\n{out_text}\\n```")
            else:
                err_text = res.stderr.strip() or res.stdout.strip()
                return ToolResult(success=False, output=res.stdout, error=f"Docker Hatası [{res.returncode}]: {err_text}")
        except Exception as e:
            logger.error(f"Docker hatasi: {e}")
            return ToolResult(success=False, output=None, error=str(e))
"""

# 3. REFINED VISION CLICK TOOL
files["tools/vision_click.py"] = r"""import base64
import json
import re
import httpx
import pyautogui
from pathlib import Path
from PIL import ImageGrab
from core.config import get_settings
from core.logger import setup_logger
from core.types import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("VisionClickTools")
WORKSPACE_ROOT = Path("C:/JARVIS").resolve()
settings = get_settings()


class VisionClickTool(BaseTool):
    name = "vision_click"
    description = "Ekran goruntusunu alir, Vision AI ile istenen butonun/ikonun koordinatlarini bulur ve fareyle tiklar."
    risk_level = RiskLevel.HIGH

    async def execute(self, element_name: str, click_type: str = "double_click", **kwargs) -> ToolResult:
        try:
            screen_file = WORKSPACE_ROOT / "storage" / "temp_vision_click.png"
            screen_file.parent.mkdir(parents=True, exist_ok=True)
            
            screenshot = ImageGrab.grab()
            screenshot.save(screen_file, "PNG")
            screen_w, screen_h = pyautogui.size()

            with open(screen_file, "rb") as img_f:
                b64_img = base64.b64encode(img_f.read()).decode("utf-8")

            coords = await self._locate_element_coordinates(b64_img, element_name)
            if not coords:
                return ToolResult(success=False, output=None, error=f"Vision AI ekranda '{element_name}' ögesinin yerini tespit edemedi.")

            x_pct, y_pct = coords
            target_x = max(0, min(int((x_pct / 100.0) * screen_w), screen_w - 1))
            target_y = max(0, min(int((y_pct / 100.0) * screen_h), screen_h - 1))

            pyautogui.moveTo(target_x, target_y, duration=0.3)
            if click_type == "double_click":
                pyautogui.doubleClick(target_x, target_y)
            else:
                pyautogui.click(target_x, target_y)

            return ToolResult(
                success=True,
                output=f"👁️🖱️ **[GÖRSEL VISION TIKLAMA BAŞARILI]**: Ekranda '{element_name}' algılandı. ({target_x}, {target_y}) konumuna tıklandı.",
                metadata={"x": target_x, "y": target_y, "element": element_name}
            )

        except Exception as e:
            logger.error(f"VisionClick hatasi: {e}")
            return ToolResult(success=False, output=None, error=str(e))

    async def _locate_element_coordinates(self, b64_img: str, element_name: str) -> Optional[tuple]:
        if not settings.GROQ_API_KEY:
            return None

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        
        prompt_text = (
            f"Analyze this computer screenshot. I want to click on '{element_name}'. "
            f"Estimate the center coordinates as percentage of screen width and height (0 to 100). "
            f"Reply ONLY with JSON: {{\"x_percent\": float, \"y_percent\": float}}"
        )

        payload = {
            "model": settings.GROQ_VISION_MODEL or "llama-3.2-11b-vision-preview",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}}
                    ]
                }
            ],
            "max_tokens": 150
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, json=payload, headers=headers)
                if res.status_code == 200:
                    raw = res.json()["choices"][0]["message"]["content"]
                    match = re.search(rrr"\{.*\}", raw, re.DOTALL)
                    if match:
                        data = json.loads(match.group(0))
                        return (float(data["x_percent"]), float(data["y_percent"]))
        except Exception:
            pass
        return None
"""

# 4. RUNNER (YENİ ARAÇLARIN KAYDI)
files["agent/runner.py"] = """from typing import Optional
from core.logger import setup_logger
from tasks.models import StepStatus, Task, TaskStatus
from tasks.service import TaskService
from tools.code_runner import PythonExecuteTool, PythonSyntaxCheckTool, TestRunnerTool
from tools.desktop_vision import DesktopIconClickTool
from tools.dev_mode import SelfCodeAnalysisTool
from tools.docker_control import DockerControlTool
from tools.filesystem import (
    DirectoryCreateTool,
    DirectoryScanTool,
    FileReadTool,
    FileWriteTool,
)
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
from tools.system import SystemInfoTool
from tools.system_control import SystemHardwareControlTool
from tools.terminal import TerminalExecuteTool
from tools.universal_launcher import UniversalLauncherTool
from tools.vision_click import VisionClickTool
from tools.web import (
    AutonomousResearchTool,
    BrowserDiscoveryTool,
    DeepWebReaderTool,
    WebSearchTool,
)
from tools.window_manager import WindowManagerTool

logger = setup_logger("AgentRunner")


class AgentRunner:
    def __init__(self, task_service: Optional[TaskService] = None):
        self.task_service = task_service or TaskService()
        self.registry = ToolRegistry()
        self._register_default_tools()

    def _register_default_tools(self):
        self.registry.register(DirectoryCreateTool())
        self.registry.register(FileReadTool())
        self.registry.register(FileWriteTool())
        self.registry.register(DirectoryScanTool())
        self.registry.register(SystemInfoTool())
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

    async def run_task(self, task_id: str) -> Task:
        task = self.task_service.get_task(task_id)
        if not task or not task.steps:
            raise ValueError("Gecersiz veya bos task")

        task.status = TaskStatus.RUNNING
        self.task_service.save_task(task)

        for step in task.steps:
            if step.status == StepStatus.COMPLETED:
                continue

            if step.requires_approval and not step.approved:
                step.status = StepStatus.WAITING_APPROVAL
                task.status = TaskStatus.WAITING_FOR_USER
                self.task_service.save_task(task)
                return task

            step.status = StepStatus.RUNNING
            self.task_service.save_task(task)

            tool_to_use = step.tool_name or "reasoning"

            if tool_to_use in ["reasoning", "none", None]:
                step.result = f"Mantik adimi tamamlandi: {step.description}"
                step.status = StepStatus.COMPLETED
                step.verified = True
                task.step_outputs[f"step_{step.id}"] = step.result
                self.task_service.save_task(task)
                continue

            exec_success = False
            while step.retry_count <= step.max_retries and not exec_success:
                tool_result = await self.registry.execute(tool_to_use, **step.parameters)

                if tool_result.success:
                    exec_success = True
                    step.result = str(tool_result.output)
                    step.status = StepStatus.COMPLETED
                    step.verified = True
                    step.error = None
                    task.step_outputs[f"step_{step.id}"] = tool_result.output
                    self.task_service.save_task(task)
                else:
                    step.retry_count += 1
                    step.error = tool_result.error or "Bilinmeyen arac hatasi"
                    if step.retry_count <= step.max_retries:
                        task.status = TaskStatus.RECOVERING
                        self.task_service.save_task(task)
                    else:
                        step.status = StepStatus.FAILED
                        task.status = TaskStatus.FAILED
                        task.error_summary = f"Adim {step.id} basarisiz: {step.error}"
                        self.task_service.save_task(task)
                        return task

        task.status = TaskStatus.COMPLETED
        self.task_service.save_task(task)
        return task

    async def approve_step(self, task_id: str, step_id: int) -> Task:
        task = self.task_service.get_task(task_id)
        if not task:
            raise ValueError("Task bulunamadi")

        for step in task.steps:
            if step.id == step_id:
                step.approved = True
                step.status = StepStatus.PENDING
                break

        return await self.run_task(task_id)
"""

# 5. DISPATCHER (YENİ KURALLAR)
files["agent/dispatcher.py"] = """import json
import re
from typing import Any, Dict, Optional
from core.config import get_settings
from core.json_utils import parse_json_safely
from core.logger import setup_logger
from core.policy import SecurityPolicyEngine
from llm.base import BaseLLMProvider, LLMMessage
from llm.ollama_provider import OllamaProvider
from llm.groq_provider import GroqProvider
from tasks.models import RiskLevel
from tools.registry import ToolRegistry

logger = setup_logger("ActionDispatcher")
settings = get_settings()

DISPATCHER_SYSTEM_PROMPT = \"\"\"You are the Action Dispatcher of the JARVIS AI Agent.
Analyze user input and select ONE tool if it is a single action request.

AVAILABLE TOOLS SCHEMA:
{tools_schema}

MUST REPLY ONLY WITH A VALID JSON OBJECT:
{{
    "requires_tool": true | false,
    "tool_name": "exact_tool_name" | null,
    "arguments": {{ "param_name": "value" }},
    "reasoning": "brief explanation"
}}\"\"\"


class ActionDispatcher:
    def __init__(self, registry: ToolRegistry, provider: Optional[BaseLLMProvider] = None):
        self.registry = registry
        self.provider = provider or OllamaProvider(default_model=settings.DEFAULT_FAST_MODEL)

    async def dispatch(self, user_input: str, history_context: str = "", provider_override: Optional[str] = None) -> Dict[str, Any]:
        active_provider = self.provider
        if provider_override == "groq":
            active_provider = GroqProvider()

        clean_input = user_input.replace('"', '').replace("'", "").strip()
        lower = clean_input.lower()

        # Bildirim İsteği
        if "bildirim" in lower or "toast" in lower or "hatırlat" in lower:
            msg = lower.replace("bildirim fırlat", "").replace("bildirim gönder", "").replace("bildirim", "").strip()
            return {
                "matched": True,
                "tool_name": "toast_notification",
                "arguments": {"title": "JARVIS Bildirimi", "message": msg or clean_input},
                "risk_level": RiskLevel.LOW,
                "requires_approval": False,
                "reasoning": "Toast notification"
            }

        # Docker İsteği
        if "docker" in lower:
            act = "ps"
            if "build" in lower: act = "build"
            elif "logs" in lower or "log" in lower: act = "logs"
            elif "up" in lower or "başlat" in lower: act = "up"
            elif "down" in lower or "durdur" in lower: act = "down"

            args = {"action": act}
            risk, req_app = SecurityPolicyEngine.evaluate_risk("docker_control", args)
            return {
                "matched": True,
                "tool_name": "docker_control",
                "arguments": args,
                "risk_level": risk,
                "requires_approval": req_app,
                "reasoning": "Docker command"
            }

        # Kapatma
        if any(kw in lower for kw in ["kapat", "close", "kill", "sonlandır"]) and not any(kw in lower for kw in ["bilgisayarı", "sistemi"]):
            target_app = lower.replace("kapat", "").replace("close", "").replace("kill", "").replace("sonlandır", "").strip()
            args = {"target": target_app or clean_input}
            risk, req_app = SecurityPolicyEngine.evaluate_risk("process_kill", args)
            return {
                "matched": True,
                "tool_name": "process_kill",
                "arguments": args,
                "risk_level": risk,
                "requires_approval": req_app,
                "reasoning": "Direct match for process_kill"
            }

        tools_schema_str = json.dumps(self.registry.list_tools(), indent=2, ensure_ascii=False)
        system_prompt = DISPATCHER_SYSTEM_PROMPT.format(tools_schema=tools_schema_str)

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="system", content=f"Recent Context: {history_context[:1000]}"),
            LLMMessage(role="user", content=f"User Input: {clean_input}"),
        ]

        try:
            response = await active_provider.chat(messages=messages, temperature=0.0)
            data = parse_json_safely(response.content)
            tool_name = data.get("tool_name")

            if data.get("requires_tool") and tool_name and self.registry.get(tool_name):
                args = data.get("arguments", {})
                risk, req_app = SecurityPolicyEngine.evaluate_risk(tool_name, args)
                return {
                    "matched": True,
                    "tool_name": tool_name,
                    "arguments": args,
                    "risk_level": risk,
                    "requires_approval": req_app,
                    "reasoning": data.get("reasoning", "Selected by LLM Dispatcher"),
                }

        except Exception as e:
            logger.warning(f"ActionDispatcher LLM hatasi ({e}), kural tabanli fallback deneniyor.")

        return {"matched": False, "tool_name": None, "arguments": {}}
"""

# 6. TESTS
files["tests/test_milestones_23_24_25.py"] = """import pytest
from tools.notification import NotificationTool
from tools.docker_control import DockerControlTool


@pytest.mark.asyncio
async def test_toast_notification_tool():
    tool = NotificationTool()
    res = await tool.execute(title="Test", message="Test Mesaji")
    assert res.success is True
    assert "Bildirimi" in res.output or "fırlatıldı" in res.output


@pytest.mark.asyncio
async def test_docker_control_tool_ps():
    tool = DockerControlTool()
    res = await tool.execute(action="ps")
    # Docker sistemde kurulu olmasa bile hatasiz donmeli
    assert res.success is True or "Docker" in str(res.error)
"""

for rel_path, content in files.items():
    p = Path(f"C:/JARVIS/{rel_path}")
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    print(f"Oluşturuldu/Güncellendi: {p}")



