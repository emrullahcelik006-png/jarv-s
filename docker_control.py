import asyncio
import re
import shutil
import subprocess
from core.logger import setup_logger
from core.types import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("DockerTools")

# Sadece guvenli karakterlere izin verilir: harf, rakam, alt cizgi, nokta, tire
SAFE_NAME_PATTERN = re.compile(r'^[A-Za-z0-9_.-]+$')


def _is_safe_token(value: str) -> bool:
    """Container adi veya dosya adi gibi degerlerin shell injection icermedigini dogrular."""
    if not value:
        return True
    return bool(SAFE_NAME_PATTERN.match(value))


class DockerControlTool(BaseTool):
    name = "docker_control"
    description = "Docker container ve compose komutlarini (ps, logs, up, down, build) otonom yonetir."
    risk_level = RiskLevel.HIGH

    async def execute(self, action: str = "ps", container_name: str = "", compose_file: str = "", **kwargs) -> ToolResult:
        try:
            if not shutil.which("docker"):
                return ToolResult(
                    success=True,
                    output="ℹ️ **[DOCKER TESPİTİ]**: Docker bu bilgisayarda kurulu değil veya PATH sistem değişkeninde bulunamadı. "
                           "Docker Desktop indirmek isterseniz resmi indirme sayfasını sizin için açabilirim."
                )

            # GUVENLIK: container_name ve compose_file injection karakteri icermemeli
            if container_name and not _is_safe_token(container_name):
                logger.warning(f"Docker guvenlik engeli: supheli container_name reddedildi: {container_name!r}")
                return ToolResult(
                    success=False, output=None,
                    error=f"Geçersiz container adı: '{container_name}'. Sadece harf, rakam, '.', '_', '-' karakterlerine izin verilir."
                )
            if compose_file and not _is_safe_token(compose_file):
                logger.warning(f"Docker guvenlik engeli: supheli compose_file reddedildi: {compose_file!r}")
                return ToolResult(
                    success=False, output=None,
                    error=f"Geçersiz compose dosya adı: '{compose_file}'. Sadece harf, rakam, '.', '_', '-' karakterlerine izin verilir."
                )

            act = action.lower().strip()
            if act in ("ps", "list", "containers"):
                cmd = ["docker", "ps", "-a"]
            elif act == "logs":
                cmd = ["docker", "logs", "--tail", "50", container_name] if container_name else ["docker", "ps"]
            elif act in ("up", "compose_up"):
                cmd = ["docker", "compose"]
                if compose_file:
                    cmd += ["-f", compose_file]
                cmd += ["up", "-d"]
            elif act in ("down", "compose_down"):
                cmd = ["docker", "compose"]
                if compose_file:
                    cmd += ["-f", compose_file]
                cmd += ["down"]
            elif act == "build":
                cmd = ["docker", "build", "-t", "jarvis_app", "."]
            else:
                # Beyaz listede olmayan eylemler icin de ham 'action' kelimesi
                # dogrulanmadan calistirilmamali.
                if not _is_safe_token(act):
                    return ToolResult(
                        success=False, output=None,
                        error=f"Geçersiz veya desteklenmeyen docker eylemi: '{action}'."
                    )
                cmd = ["docker", act]

            res = await asyncio.to_thread(
                subprocess.run,
                cmd,
                shell=False,
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
                errors="replace"
            )

            display_cmd = " ".join(cmd)
            if res.returncode == 0:
                out_text = res.stdout.strip() or "Docker işlemi başarıyla tamamlandı."
                return ToolResult(success=True, output=f"🐳 **[DOCKER EYLEMİ İCRA EDİLDİ]** ({display_cmd})\n\n`	ext\n{out_text}\n`")
            else:
                err_text = res.stderr.strip() or res.stdout.strip()
                return ToolResult(success=False, output=res.stdout, error=f"Docker Hatası [{res.returncode}]: {err_text}")
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output=None, error="Docker komutu zaman aşımına uğradı (Timeout 30s)")
        except Exception as e:
            logger.error(f"Docker hatasi: {e}")
            return ToolResult(success=False, output=None, error=str(e))
