"""JARVIS depolama temizligi (tek seferlik, GUVENLI: once yedek alir).

Kullanim (proje klasorunde, JARVIS KAPALIYKEN):
    python storage_cleanup.py            # sadece rapor: neyin silinecegini gosterir
    python storage_cleanup.py --apply    # yedek alir ve uygular

Yaptiklari:
  1. storage/ klasorunun tamamini storage_backup_<tarih>/ altina kopyalar.
  2. Vektor hafizadan modelin kendi cevaplarini iceren sohbet kayitlarini siler
     ("User Query: ... | Response: ..." bicimindekiler). Bunlar RAG ile geri beslenip hatali bilgiyi
     "hafiza" gibi sunuyordu.
  3. Takili kalmis bekleyen gorevleri (waiting_for_user / created / ready) iptal eder.
  4. storage/reports icindeki eski RAM-uyari raporlarini (report_high_memory_warning_*.txt) en yeni 5'i haric siler.
"""
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STORAGE = ROOT / "storage"
APPLY = "--apply" in sys.argv
CHAT_LOG_PREFIXES = ("user query:", "kullanici sorusu:", "kullanıcı sorusu:")


def backup():
    if not STORAGE.exists():
        print("storage/ yok, yedeklenecek bir sey yok.")
        return None
    dest = ROOT / f"storage_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copytree(STORAGE, dest)
    print(f"[yedek] {dest}")
    return dest


def clean_vector_memory():
    db = STORAGE / "db" / "jarvis_vector_memory.db"
    if not db.exists():
        print("[hafiza] vektor veritabani yok.")
        return
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute("SELECT id, category, content, metadata_json FROM semantic_memories").fetchall()
        bad = []
        for mem_id, category, content, meta in rows:
            try:
                source = json.loads(meta or "{}").get("source")
            except Exception:
                source = None
            if str(content or "").strip().lower().startswith(CHAT_LOG_PREFIXES) or source == "chat":
                bad.append((mem_id, str(content)[:90].replace("\n", " ")))
        print(f"[hafiza] toplam {len(rows)} kayit, silinecek sohbet kaydi: {len(bad)}")
        for mem_id, preview in bad[:15]:
            print(f"    - #{mem_id}: {preview}")
        if APPLY and bad:
            conn.executemany("DELETE FROM semantic_memories WHERE id = ?", [(i,) for i, _ in bad])
            conn.commit()
            print(f"[hafiza] {len(bad)} kayit silindi.")
    finally:
        conn.close()


def cancel_stale_tasks():
    tdir = STORAGE / "tasks"
    if not tdir.exists():
        print("[gorev] storage/tasks yok.")
        return
    pending = {"waiting_for_user", "created", "ready"}
    n = 0
    for f in tdir.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("status") in pending:
            n += 1
            if APPLY:
                data["status"] = "cancelled"
                data["error_summary"] = "storage_cleanup: eski bekleyen gorev iptal edildi."
                f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[gorev] iptal {'edilen' if APPLY else 'edilecek'} bekleyen gorev: {n}")


def prune_memory_warnings():
    rdir = STORAGE / "reports"
    if not rdir.exists():
        print("[rapor] storage/reports yok.")
        return
    files = sorted(rdir.glob("report_high_memory_warning_*.txt"), key=lambda p: p.stat().st_mtime)
    old = files[:-5] if len(files) > 5 else []
    print(f"[rapor] RAM uyari raporu: {len(files)}, silinecek: {len(old)}")
    if APPLY:
        for f in old:
            f.unlink()


if __name__ == "__main__":
    print("MOD:", "UYGULA" if APPLY else "SADECE RAPOR (uygulamak icin --apply)")
    if APPLY:
        backup()
    clean_vector_memory()
    cancel_stale_tasks()
    prune_memory_warnings()
    print("Bitti.")
