import datetime
import hmac
import json
import os

import psutil
from fastapi import FastAPI, Header, HTTPException

ROOT = os.environ.get("JARVIS_HOME") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT_PATH = os.path.join(ROOT, "logs", "operator_audit.jsonl")
TOKEN = os.environ.get("JARVIS_BRIDGE_TOKEN", "")

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


def audit(tool: str, status: str, summary: str) -> None:
    os.makedirs(os.path.dirname(AUDIT_PATH), exist_ok=True)
    record = {
        "ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "tool": tool,
        "level": 0,
        "status": status,
        "summary": summary,
    }
    with open(AUDIT_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def require_token(authorization: str | None) -> None:
    if not TOKEN:
        raise HTTPException(status_code=500, detail="JARVIS_BRIDGE_TOKEN tanımlı değil")
    expected = f"Bearer {TOKEN}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        audit("auth", "denied", "geçersiz token")
        raise HTTPException(status_code=401, detail="yetkisiz")


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/system_status")
def system_status(authorization: str | None = Header(default=None)) -> dict:
    require_token(authorization)
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")
    result = {
        "cpu_percent": cpu,
        "ram_percent": mem.percent,
        "ram_free_gb": round(mem.available / 1024**3, 2),
        "c_drive_free_percent": round(100 - disk.percent, 1),
    }
    audit("system_status", "ok", f"cpu={cpu} ram={mem.percent}")
    return result
