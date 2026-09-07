import pytest
import os
import tempfile
from storage.vector_store import SQLiteVectorStore
from engine.ai_knowledge_rag import AIKnowledgeRAG


def test_sqlite_vector_store_basic():
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        db_path = tmp.name

    try:
        store = SQLiteVectorStore(db_path=db_path)
        assert store.count() == 0

        # Insert documents
        ok1 = store.insert_document(
            doc_id="doc1",
            title="WebGL OS Tensor Harmony",
            content="Linux profiles must never present Direct3D, D3D11, or Apple GPUs.",
            category="hardware"
        )
        ok2 = store.insert_document(
            doc_id="doc2",
            title="WebRTC ICE Protection",
            content="Prevent STUN/TURN queries from leaking real IP addresses over UDP.",
            category="network"
        )
        assert ok1 is True
        assert ok2 is True
        assert store.count() == 2

        # Semantic query
        results = store.query_semantic("How to prevent WebRTC leaks over UDP?", top_k=1)
        assert len(results) == 1
        assert results[0]["id"] == "doc2"
        assert results[0]["similarity"] > 0.30

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_ai_knowledge_rag_integration():
    rag = AIKnowledgeRAG.get_instance()
    # Query for TLS / JA4
    matches = rag.query("Tell me about JA3 and JA4 TLS fingerprints in Camoufox", top_k=2)
    assert len(matches) > 0
    assert any("tls" in str(m.get("title", "")).lower() or "ja3" in str(m.get("title", "")).lower() for m in matches)

    # Dynamic knowledge insertion
    ok = rag.add_knowledge_snippet(
        doc_id="test_turnstile_2026",
        title="Turnstile Evasion 2026",
        content="Turnstile measures 5th-order polynomial cursor curves.",
        category="captcha"
    )
    assert ok is True

    new_matches = rag.query("What does Turnstile measure?", top_k=1)
    assert len(new_matches) > 0
    assert "Turnstile" in new_matches[0]["title"]
