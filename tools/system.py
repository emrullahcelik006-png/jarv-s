import os
import platform
import socket
import asyncio
from typing import Optional, Dict, Any
from tasks.models import RiskLevel
from tools.base import BaseTool, ToolResult


class SystemInfoTool(BaseTool):
    name = "system_info"
    description = "CPU, RAM, Disk ve Isletim Sistemi durumunu okur."
    risk_level = RiskLevel.LOW

    async def execute(self, **kwargs) -> ToolResult:
        try:
            cpu_count = os.cpu_count()
            os_name = platform.system()
            os_version = platform.version()

            data = {
                "os": f"{os_name} {os_version}",
                "cpu_cores": cpu_count,
                "platform": platform.platform(),
            }

            try:
                import psutil
                data["cpu_percent"] = psutil.cpu_percent(interval=0.1)
                data["ram_total_gb"] = round(psutil.virtual_memory().total / (1024**3), 2)
                data["ram_used_percent"] = psutil.virtual_memory().percent
                data["disk_used_percent"] = psutil.disk_usage("C:\\").percent
            except ImportError:
                data["metrics_note"] = "psutil paketi yuklu degil, temel sistem bilgileri verildi."

            return ToolResult(success=True, output=data)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class NetworkPortHealthTool(BaseTool):
    name = "network_port_health"
    description = "Checks the health status of local network ports and services (Ollama, Web API, Docker, PostgreSQL, etc.)."
    risk_level = RiskLevel.LOW

    DEFAULT_PORTS = {
        11434: "Ollama Local LLM Service",
        8000: "JARVIS Mission Control Web API",
        5432: "PostgreSQL Database",
        6379: "Redis Cache Service",
        27017: "MongoDB Database",
        8080: "Alternative Web Service / Proxy"
    }

    async def execute(self, port: Optional[int] = None, **kwargs) -> ToolResult:
        try:
            ports_to_check = {}
            if port:
                try:
                    p_num = int(port)
                    ports_to_check[p_num] = f"Custom Port {p_num}"
                except (ValueError, TypeError):
                    ports_to_check = self.DEFAULT_PORTS
            else:
                ports_to_check = self.DEFAULT_PORTS

            results = {}
            active_count = 0

            for p, service_name in ports_to_check.items():
                is_open = await asyncio.to_thread(self._check_port_open, "127.0.0.1", p)
                status_str = "ONLINE (Open)" if is_open else "OFFLINE (Closed)"
                results[f"Port {p} ({service_name})"] = status_str
                if is_open:
                    active_count += 1

            summary_lines = [f"• **Port {p}** ({srv}): {'🟢 ONLINE' if 'ONLINE' in stat else '🔴 OFFLINE'}" for (p, srv), stat in zip(ports_to_check.items(), results.values())]

            return ToolResult(
                success=True,
                output=f"🌐 **[AĞ VE PORT SAĞLIK SENSÖRÜ]** ({active_count}/{len(ports_to_check)} Servis Aktif):\n\n" + "\n".join(summary_lines),
                metadata={"active_services": active_count, "details": results}
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))

    @staticmethod
    def _check_port_open(host: str, port: int, timeout: float = 0.4) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False
