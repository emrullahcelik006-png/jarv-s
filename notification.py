import os
import asyncio
import subprocess
from core.logger import setup_logger
from core.types import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("NotificationTools")


class NotificationTool(BaseTool):
    name = "toast_notification"
    description = "Fires a native Windows desktop Toast Notification."
    risk_level = RiskLevel.LOW

    async def execute(self, title: str = "JARVIS Notification", message: str = "Operation completed.", **kwargs) -> ToolResult:
        try:
            safe_title = str(title).strip() or "JARVIS Notification"
            safe_message = str(message).strip() or "Operation completed."

            proc_env = os.environ.copy()
            proc_env["JARVIS_TOAST_TITLE"] = safe_title
            proc_env["JARVIS_TOAST_MSG"] = safe_message

            ps_script = r'''
            [void] [System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms")
            $objNotifyIcon = New-Object System.Windows.Forms.NotifyIcon
            $objNotifyIcon.Icon = [System.Drawing.SystemIcons]::Information
            $objNotifyIcon.BalloonTipIcon = "Info"
            $objNotifyIcon.BalloonTipText = $env:JARVIS_TOAST_MSG
            $objNotifyIcon.BalloonTipTitle = $env:JARVIS_TOAST_TITLE
            $objNotifyIcon.Visible = $True
            $objNotifyIcon.ShowBalloonTip(5000)
            '''

            await asyncio.to_thread(
                subprocess.run,
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=10,
                env=proc_env
            )
            return ToolResult(
                success=True,
                output=f"Masaüstü bildirimi fırlatıldı: '{safe_title}' - '{safe_message}'"
            )
        except Exception as e:
            logger.error(f"Notification error: {e}")
            return ToolResult(success=False, output=None, error=str(e))
