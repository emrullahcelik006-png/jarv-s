import shlex
import subprocess
from pathlib import Path
from core.logger import setup_logger
from tasks.models import RiskLevel
from tools.base import BaseTool, ToolResult

logger = setup_logger("GitTools")
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

# Izinli git alt komutlari; baska hicbir sey calistirilmaz.
ALLOWED_GIT_SUBCOMMANDS = {"status", "log", "diff", "show", "branch", "checkout", "add", "commit", "init"}
# Keyfi komut calistirmaya yol acabilen secenekler
FORBIDDEN_GIT_ARGS = ("-c", "--exec", "--upload-pack", "--receive-pack", "--config", "--git-dir", "--work-tree")


class GitControlTool(BaseTool):
    name = "git_control"
    description = "Git versiyon kontrol komutlarini (status, log, add, commit, checkout) otonom calistirir."
    risk_level = RiskLevel.MEDIUM

    async def execute(self, action: str = "status", message: str = "JARVIS auto commit", repo_path: str = ".", **kwargs) -> ToolResult:
        try:
            target_repo = (WORKSPACE_ROOT / repo_path).resolve()
            try:
                target_repo.relative_to(WORKSPACE_ROOT)
            except ValueError:
                return ToolResult(success=False, output=None, error=f"Erisim engellendi: repo_path proje disinda: {target_repo}")
            act = action.lower().strip()

            if act == "history":
                argv = ["git", "log", "-n", "5", "--oneline"]
            elif act == "log":
                argv = ["git", "log", "-n", "5", "--oneline"]
            elif act in ("add_all", "add"):
                argv = ["git", "add", "."]
            elif act == "commit":
                argv = None  # iki adim: add + commit (asagida)
            else:
                try:
                    parts = shlex.split(action.strip())
                except ValueError as ve:
                    return ToolResult(success=False, output=None, error=f"Gecersiz git komutu: {ve}")
                if not parts or parts[0].lower() not in ALLOWED_GIT_SUBCOMMANDS:
                    return ToolResult(success=False, output=None, error=f"Erisim engellendi: izinli git eylemleri: {sorted(ALLOWED_GIT_SUBCOMMANDS)}")
                if any(a.lower().startswith(FORBIDDEN_GIT_ARGS) for a in parts[1:]):
                    return ToolResult(success=False, output=None, error="Erisim engellendi: yasakli git secenegi.")
                argv = ["git"] + parts

            run_kwargs = dict(cwd=str(target_repo), capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
            if argv is None:
                add_res = subprocess.run(["git", "add", "."], **run_kwargs)
                if add_res.returncode != 0:
                    return ToolResult(success=False, output=add_res.stdout.strip(), error=f"Git Hatası [{add_res.returncode}]: {add_res.stderr.strip()}")
                argv = ["git", "commit", "-m", str(message)]
            cmd = " ".join(argv)
            res = subprocess.run(argv, **run_kwargs)

            if res.returncode == 0:
                return ToolResult(
                    success=True,
                    output=f"🐙 **[GIT EYLEMİ İCRA EDİLDİ]** (`{cmd}`)\n\n```text\n{res.stdout.strip() or 'Git işlemi tamamlandı.'}\n```",
                    metadata={"action": act, "repo": str(target_repo)}
                )
            else:
                return ToolResult(
                    success=False,
                    output=res.stdout.strip(),
                    error=f"Git Hatası [{res.returncode}]: {res.stderr.strip() or res.stdout.strip()}"
                )

        except Exception as e:
            logger.error(f"Git hatasi: {e}")
            return ToolResult(success=False, output=None, error=str(e))
