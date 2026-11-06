import pytest
from memory.embeddings import cosine_similarity
from memory.vector_store import VectorMemoryStore
from memory.rag_engine import RAGEngine


def test_cosine_similarity_math():
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]
    assert cosine_similarity(v1, v2) == 1.0
    assert cosine_similarity(v1, v3) == 0.0


@pytest.mark.asyncio
async def test_vector_store_add_and_semantic_search():
    store = VectorMemoryStore(db_path="storage/db/test_vector_memory.db")
    await store.add_memory("project_note", "JARVIS TaskService hatasi pytest ile basariyla duzeltildi.")
    await store.add_memory("user_preference", "Kullanici Python 3.14 ve Windows 11 tercih ediyor.")

    results = await store.search_similar("TaskService hatasi nasil cozuler?", limit=2)
    assert len(results) > 0
    assert any("TaskService" in r["content"] for r in results)


@pytest.mark.asyncio
async def test_rag_engine_prompt_augmentation():
    store = VectorMemoryStore(db_path="storage/db/test_vector_memory.db")
    await store.add_memory("solution", "Ollama provider timeout 60s yapilarak baglanti hatasi giderildi.")

    rag = RAGEngine(vector_store=store)
    augmented = await rag.augment_prompt("Ollama baglanti hatasi", "Base System Prompt")
    assert "Ollama provider timeout 60s" in augmented
