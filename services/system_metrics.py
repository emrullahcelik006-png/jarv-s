import time
import platform
import psutil
from typing import Dict, Any, Optional
from core.logger import setup_logger

logger = setup_logger("SystemMetrics")


class SystemMetricsService:
    @staticmethod
    def get_realtime_metrics() -> Dict[str, Any]:
        """Bilgisayarin canlı donanim, bellek, disk ve pil metriklerini okur."""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=None)
            cpu_count_logical = psutil.cpu_count(logical=True)
            cpu_count_physical = psutil.cpu_count(logical=False) or cpu_count_logical

            # RAM
            vm = psutil.virtual_memory()
            ram_total_gb = round(vm.total / (1024 ** 3), 2)
            ram_used_gb = round(vm.used / (1024 ** 3), 2)
            ram_percent = vm.percent

            # DISK (C:)
            disk_c = psutil.disk_usage("C:\\")
            disk_total_gb = round(disk_c.total / (1024 ** 3), 2)
            disk_used_gb = round(disk_c.used / (1024 ** 3), 2)
            disk_free_gb = round(disk_c.free / (1024 ** 3), 2)
            disk_percent = disk_c.percent

            # PIL (BATTERY)
            battery_info = None
            try:
                bat = psutil.sensors_battery()
                if bat:
                    battery_info = {
                        "percent": bat.percent,
                        "power_plugged": bat.power_plugged,
                        "secs_left": bat.secsleft if bat.secsleft != psutil.POWER_TIME_UNLIMITED else -1
                    }
            except Exception:
                pass

            # GPU (İsteğe bağlı GPUtil kontrolü)
            gpu_info = None
            try:
                import GPUtil
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]
                    gpu_info = {
                        "name": gpu.name,
                        "load_percent": round(gpu.load * 100, 1),
                        "memory_used_mb": gpu.memoryUsed,
                        "memory_total_mb": gpu.memoryTotal,
                        "temperature": gpu.temperature
                    }
            except Exception:
                pass

            # UPTIME
            uptime_seconds = int(time.time() - psutil.boot_time())

            return {
                "timestamp": int(time.time()),
                "os": f"{platform.system()} {platform.release()}",
                "cpu": {
                    "percent": cpu_percent,
                    "cores_logical": cpu_count_logical,
                    "cores_physical": cpu_count_physical
                },
                "ram": {
                    "percent": ram_percent,
                    "used_gb": ram_used_gb,
                    "total_gb": ram_total_gb
                },
                "disk": {
                    "percent": disk_percent,
                    "used_gb": disk_used_gb,
                    "free_gb": disk_free_gb,
                    "total_gb": disk_total_gb
                },
                "battery": battery_info,
                "gpu": gpu_info,
                "uptime_seconds": uptime_seconds
            }
        except Exception as e:
            logger.error(f"Sistem metrikleri okuma hatasi: {e}")
            return {
                "error": str(e),
                "cpu": {"percent": 0.0},
                "ram": {"percent": 0.0, "used_gb": 0.0, "total_gb": 0.0},
                "disk": {"percent": 0.0, "used_gb": 0.0, "total_gb": 0.0},
                "uptime_seconds": 0
            }
