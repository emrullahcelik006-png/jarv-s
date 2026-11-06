import asyncio
import socket
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
import psutil
from core.config import get_settings
from core.logger import setup_logger
from core.paths import WORKSPACE_ROOT
from services.diagnostic_service import DiagnosticService

logger = setup_logger("BackgroundAgent")

# Dongu 30 sn'de bir calisir; agir isler (yedek, rotasyon, gorev suresi dolumu) daha seyrek yapilir.
BACKUP_EVERY_N_CYCLES = 10      # ~5 dk
ROTATE_EVERY_N_CYCLES = 20      # ~10 dk
BACKUP_KEEP = 10
MEM_WARN_KEEP = 5
REPORTS_KEEP = 50
TEST_TASKS_KEEP = 30


class ProactiveBackgroundAgent:
    def __init__(self, interval_seconds: int = 30):
        self.interval = interval_seconds
        self.is_running = False
        self._task: asyncio.Task = None
        self._cycle = 0
        self._last_ram_warn = 0.0
        self._last_backed_up_mtime = 0.0
        self.stats = {
            "backups_taken": 0,
            "warnings_triggered": 0,
            "files_rotated": 0,
            "port_disruptions": 0,
            "tasks_expired": 0,
            "last_heartbeat": None,
        }

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._main_loop())
        logger.info("Proaktif Arka Plan Ajanı başlatıldı (Kalp Atışı: 30s).")

    async def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Proaktif Arka Plan Ajanı durduruldu.")

    async def _main_loop(self):
        while self.is_running:
            try:
                self._cycle += 1
                self.stats["last_heartbeat"] = datetime.now(timezone.utc).isoformat()

                # RUTİN 1: Donanım Sağlığı (her döngü, hafif)
                await self._check_hardware_health()

                # RUTİN 2: Veritabanı yedeği (yalnızca DEĞİŞİKLİK varsa ve seyrek)
                if self._cycle % BACKUP_EVERY_N_CYCLES == 1 or self.interval >= 60:
                    await self._auto_backup_db()

                # RUTİN 3: Depo/log rotasyonu + süresi dolmuş onay görevleri (seyrek)
                if self._cycle % ROTATE_EVERY_N_CYCLES == 1 or self.interval >= 60:
                    await self._rotate_storage_files()
                    await self._expire_stale_tasks()

                # RUTİN 4: Ağ ve port sağlığı
                await self._check_network_port_health()

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Arka plan ajanı döngü hatası: {e}")

            await asyncio.sleep(self.interval)

    async def _check_hardware_health(self):
        settings = get_settings()
        ram_percent = psutil.virtual_memory().percent
        if ram_percent <= settings.RAM_WARN_PERCENT:
            return

        # Eski surum RAM yuksek kaldigi surece HER 30 SANIYEDE yeni bir rapor dosyasi uretiyordu.
        now = time.monotonic()
        if self._last_ram_warn and (now - self._last_ram_warn) < settings.RAM_WARN_COOLDOWN_SECONDS:
            return
        self._last_ram_warn = now

        # cpu_percent(interval=...) olay dongusunu bloklar; thread'de olc.
        cpu_percent = await asyncio.to_thread(psutil.cpu_percent, 0.2)
        self.stats["warnings_triggered"] += 1
        await asyncio.to_thread(
            DiagnosticService.create_report,
            event_type="HIGH_MEMORY_WARNING",
            user_prompt="[PROAKTİF ARKA PLAN DENETİMİ]",
            error_message=f"RAM kullanımı kritik seviyede: %{ram_percent}. CPU: %{cpu_percent}",
            tool_name="background_agent",
            context={"ram": ram_percent, "cpu": cpu_percent},
        )

    def _backup_db_sync(self) -> bool:
        db_file = WORKSPACE_ROOT / "storage" / "db" / "jarvis_memory.db"
        backup_dir = WORKSPACE_ROOT / "storage" / "backups"
        if not db_file.exists():
            return False
        mtime = db_file.stat().st_mtime
        if mtime <= self._last_backed_up_mtime:
            return False  # degisiklik yok -> yedek alma
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"jarvis_memory_autobackup_{stamp}.db"
        # Canli SQLite dosyasini kopyalamak tutarsiz olabilir; resmi backup API'si tutarli kopya verir.
        src = sqlite3.connect(db_file)
        try:
            dst = sqlite3.connect(backup_file)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
        self._last_backed_up_mtime = mtime
        return True

    async def _auto_backup_db(self):
        try:
            if await asyncio.to_thread(self._backup_db_sync):
                self.stats["backups_taken"] += 1
        except Exception as e:
            logger.warning(f"Otomatik yedekleme hatası: {e}")

    def _rotate_sync(self) -> int:
        # YALNIZCA kendi urettigimiz dosya desenleri doner. Eski kural backups/* idi ve
        # autonomous_patch'in .bak yedeklerini de siliyordu.
        rules = [
            # DiagnosticService dosyalari: storage/reports/report_<olay>_<tarih>_<id>.txt
            (WORKSPACE_ROOT / "storage" / "reports", "report_high_memory_warning_*.txt", MEM_WARN_KEEP),
            (WORKSPACE_ROOT / "storage" / "reports", "report_*.txt", REPORTS_KEEP),
            (WORKSPACE_ROOT / "storage" / "backups", "jarvis_memory_autobackup_*.db", BACKUP_KEEP),
            (WORKSPACE_ROOT / "storage" / "test_tasks", "*.json", TEST_TASKS_KEEP),
        ]
        rotated = 0
        for target_dir, pattern, max_keep in rules:
            if not target_dir.exists():
                continue
            try:
                files = sorted(target_dir.glob(pattern), key=lambda p: p.stat().st_mtime)
                for f in files[:-max_keep] if len(files) > max_keep else []:
                    try:
                        if f.is_file():
                            f.unlink()
                            rotated += 1
                    except Exception as ex:
                        logger.warning(f"Rotasyon silme hatası ({f.name}): {ex}")
            except Exception as err:
                logger.warning(f"Rotasyon tarama hatası ({target_dir.name}): {err}")
        return rotated

    async def _rotate_storage_files(self):
        self.stats["files_rotated"] += await asyncio.to_thread(self._rotate_sync)

    async def _expire_stale_tasks(self):
        try:
            from tasks.service import default_task_service
            ttl = float(get_settings().TASK_APPROVAL_TTL_HOURS)
            self.stats["tasks_expired"] += await asyncio.to_thread(default_task_service.expire_stale_tasks, ttl)
        except Exception as e:
            logger.warning(f"Eski görev temizliği hatası: {e}")

    async def _check_network_port_health(self):
        """Ollama (11434) ve Web API (8000) portlarını kontrol eder."""
        critical_ports = {11434: "Ollama LLM", 8000: "Web API"}
        for port_num, service_name in critical_ports.items():
            is_open = await asyncio.to_thread(self._is_port_open, "127.0.0.1", port_num)
            if not is_open and port_num == 11434:
                self.stats["port_disruptions"] += 1
                logger.warning(f"Kritik servis erişilemez durumda: {service_name} (Port {port_num})")

    @staticmethod
    def _is_port_open(host: str, port: int, timeout: float = 0.3) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False


background_agent = ProactiveBackgroundAgent(interval_seconds=30)
