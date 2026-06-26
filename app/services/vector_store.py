from typing import Any

import chromadb
from chromadb.config import Settings

from app.config import CHROMA_DIR
from app.services.ollama_client import ollama_client

COLLECTION_NAME = "job_descriptions"


class VectorStore:
    def __init__(self) -> None:
        self.client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def index_jd(self, jd_id: int, title: str, role: str, content: str, skills: list[str]) -> None:
        self.delete_jd(jd_id)
        chunks = self._chunk_jd(title, role, content, skills)
        if not chunks:
            return

        ids = [f"jd_{jd_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {"jd_id": jd_id, "title": title, "role": role, "chunk_index": i}
            for i in range(len(chunks))
        ]
        embeddings = ollama_client.embed_batch(chunks)
        self.collection.add(
            ids=ids,
            documents=chunks,
            metadatas=metadatas,
            embeddings=embeddings,
        )

    def delete_jd(self, jd_id: int) -> None:
        existing = self.collection.get(where={"jd_id": jd_id})
        if existing and existing.get("ids"):
            self.collection.delete(ids=existing["ids"])

    def search_jds(self, resume_text: str, top_k: int = 3) -> list[dict[str, Any]]:
        if self.collection.count() == 0:
            return []

        query_embedding = ollama_client.embed(resume_text[:8000])
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k * 3, max(self.collection.count(), 1)),
        )

        seen_jds: set[int] = set()
        matches: list[dict[str, Any]] = []
        for doc, meta, distance in zip(
            results.get("documents", [[]])[0],
            results.get("metadatas", [[]])[0],
            results.get("distances", [[]])[0],
        ):
            jd_id = int(meta["jd_id"])
            if jd_id in seen_jds:
                continue
            seen_jds.add(jd_id)
            similarity = max(0.0, 1.0 - float(distance))
            matches.append(
                {
                    "jd_id": jd_id,
                    "title": meta.get("title", ""),
                    "role": meta.get("role", ""),
                    "similarity": similarity,
                    "snippet": doc[:500],
                }
            )
            if len(matches) >= top_k:
                break
        return matches

    def _chunk_jd(self, title: str, role: str, content: str, skills: list[str]) -> list[str]:
        header = f"Title: {title}\nRole: {role}\nSkills: {', '.join(skills)}\n\n"
        full_text = header + content
        chunk_size = 1500
        overlap = 200
        if len(full_text) <= chunk_size:
            return [full_text]

        chunks: list[str] = []
        start = 0
        while start < len(full_text):
            end = start + chunk_size
            chunks.append(full_text[start:end])
            start = end - overlap
        return chunks


vector_store = VectorStore()
