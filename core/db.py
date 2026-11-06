"""SQLite baglantisi: with blogu cikisinda COMMIT + KAPATMA yapar.

sqlite3.connect(...) bir `with` icinde kullanildiginda yalnizca commit/rollback yapar, baglantiyi
KAPATMAZ; Windows'ta dosya kilidi ve kaynak sizintisina yol acar.
"""
import sqlite3
from contextlib import contextmanager


@contextmanager
def connect_db(path, timeout: float = 10.0):
    conn = sqlite3.connect(str(path), timeout=timeout)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
