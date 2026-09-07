import os
import time
import json
import sqlite3
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

import numpy as np
from storage.vector_store import SQLiteVectorStore

logger = logging.getLogger("ProfileEpisodicMemory")


@dataclass
class EpisodeRecord:
    episode_id: str
    timestamp: float
    domain: str
    topic: str
    content: str
    sentiment: float
    similarity: float = 0.0


class ProfileEpisodicMemory:
    """
    Per-Profile Long-Term Episodic Memory Manager.
    Stores historical interactions, visited domains, search narratives, and opinion stances
    to prevent AI persona amnesia and maintain consistent clickstream coherence ('Roter Faden').
    """

    def __init__(self, profile_id: str, db_dir: Optional[str] = None):
        self.profile_id = profile_id
        if not db_dir:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_dir = os.path.join(base_dir, "profiles", profile_id)

        os.makedirs(db_dir, exist_ok=True)
        self.db_path = os.path.join(db_dir, "episodic_memory.sqlite")
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodic_memory (
                    id TEXT PRIMARY KEY,
                    timestamp REAL NOT NULL,
                    domain TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sentiment REAL DEFAULT 0.0,
                    embedding BLOB NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ep_domain ON episodic_memory(domain)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ep_time ON episodic_memory(timestamp)")
            conn.commit()

    def record_episode(
        self,
        domain: str,
        topic: str,
        content: str,
        sentiment: float = 0.0,
        episode_id: Optional[str] = None
    ) -> bool:
        """Records an episodic browsing or persona experience."""
        import uuid
        ep_id = episode_id or str(uuid.uuid4())
        text_to_embed = f"{domain} {topic} {content}"
        emb = SQLiteVectorStore.generate_embedding(text_to_embed)
        emb_blob = emb.tobytes()

        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO episodic_memory (id, timestamp, domain, topic, content, sentiment, embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (ep_id, time.time(), domain, topic, content, sentiment, emb_blob))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"[ProfileEpisodicMemory] Failed to record episode for profile '{self.profile_id}': {e}")
            return False

    def recall_episodes(
        self,
        query: str,
        limit: int = 3,
        min_similarity: float = 0.18
    ) -> List[EpisodeRecord]:
        """Recalls the most relevant past memories matching the given context or topic."""
        if not query:
            return []

        q_vec = SQLiteVectorStore.generate_embedding(query)

        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM episodic_memory").fetchall()

        if not rows:
            return []

        ep_ids = []
        timestamps = []
        domains = []
        topics = []
        contents = []
        sentiments = []
        embeddings = []

        for r in rows:
            ep_ids.append(r["id"])
            timestamps.append(r["timestamp"])
            domains.append(r["domain"])
            topics.append(r["topic"])
            contents.append(r["content"])
            sentiments.append(r["sentiment"])
            embeddings.append(np.frombuffer(r["embedding"], dtype=np.float32))

        matrix = np.vstack(embeddings)
        sims = np.dot(matrix, q_vec)

        sorted_indices = np.argsort(-sims)
        results: List[EpisodeRecord] = []

        for idx in sorted_indices:
            score = float(sims[idx])
            if score < min_similarity:
                break
            results.append(EpisodeRecord(
                episode_id=ep_ids[idx],
                timestamp=timestamps[idx],
                domain=domains[idx],
                topic=topics[idx],
                content=contents[idx],
                sentiment=sentiments[idx],
                similarity=score
            ))
            if len(results) >= limit:
                break

        return results

    def format_memory_context_prompt(self, current_topic: str) -> str:
        """Formats recalled past episodes into prompt context to maintain persona continuity."""
        memories = self.recall_episodes(current_topic, limit=3)
        if not memories:
            return ""

        lines = ["[EPISODIC PERSONA MEMORY - MAINTAIN THEMATIC COHERENCE]"]
        for m in memories:
            lines.append(f"- [{m.domain}] {m.topic}: {m.content}")
        lines.append("[END PERSONA MEMORY]")
        return "\n".join(lines)
