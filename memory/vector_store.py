import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from core.db import connect_db
from core.logger import setup_logger
from core.paths import WORKSPACE_ROOT
from memory.embeddings import OllamaEmbeddingProvider, cosine_similarity

logger = setup_logger("VectorStore")


def _safe_json(raw):
    try:
        return json.loads(raw or "{}")
    except Exception:
        return {}


class VectorMemoryStore:
    def __init__(self, db_path: str = "storage/db/jarvis_vector_memory.db"):
        _p = Path(db_path)
        self.db_file = _p if _p.is_absolute() else (WORKSPACE_ROOT / _p)
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        self.embedder = OllamaEmbeddingProvider()
        self._init_db()

    def _init_db(self):
        with connect_db(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS semantic_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT,
                    content TEXT,
                    embedding_json TEXT,
                    metadata_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    async def add_memory(self, category: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> int:
        embedding = await self.embedder.get_embedding(content)
        emb_json = json.dumps(embedding)
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)

        with connect_db(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO semantic_memories (category, content, embedding_json, metadata_json) VALUES (?, ?, ?, ?)",
                (category, content, emb_json, meta_json)
            )
            conn.commit()
            mem_id = cursor.lastrowid
            logger.info(f"Semantik hafiza kaydoldu [ID: {mem_id}] Kategori: {category}")
            return mem_id

    async def add_document(self, content: str, category: str = "general", metadata: Optional[Dict[str, Any]] = None) -> int:
        """Alias method for API compatibility."""
        return await self.add_memory(category=category, content=content, metadata=metadata)

    async def add_text(self, text: str, category: str = "general", metadata: Optional[Dict[str, Any]] = None) -> int:
        """Alias method for API compatibility."""
        return await self.add_memory(category=category, content=text, metadata=metadata)

    async def search_similar(self, query: str, limit: int = 2, threshold: float = 0.40) -> List[Dict[str, Any]]:
        query_emb = await self.embedder.get_embedding(query)
        if not query_emb:
            return []

        results = []
        with connect_db(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, category, content, embedding_json, metadata_json, created_at FROM semantic_memories")
            rows = cursor.fetchall()

            for row in rows:
                mem_id, category, content, emb_json, meta_json, created_at = row
                try:
                    mem_emb = json.loads(emb_json)
                    score = cosine_similarity(query_emb, mem_emb)
                except Exception:
                    continue  # bozuk tek kayit tum aramayi dusurmesin

                if score >= threshold:
                    results.append({
                        "id": mem_id,
                        "category": category,
                        "content": content,
                        "score": round(score, 4),
                        "metadata": _safe_json(meta_json),
                        "created_at": created_at
                    })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]
