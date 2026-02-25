"""Embedding-based search for Phase 2 fallback retrieval."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.repositories import ParagraphRepository


class EmbeddingSearch:
    """Fallback semantic search using sentence-transformers + FAISS.

    If embedding dependencies are unavailable, this class transparently falls back
    to text search through ParagraphRepository.
    """

    DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    def __init__(self, session: AsyncSession, model_name: str = DEFAULT_MODEL):
        self.session = session
        self.model_name = model_name
        self.embedding_dir = Path("./data/embeddings")
        self.index_path = self.embedding_dir / "paragraphs.faiss"
        self.id_map_path = self.embedding_dir / "paragraph_ids.json"

        self._enabled = False
        self._model: Any | None = None
        self._faiss: Any | None = None
        self._np: Any | None = None
        self._index: Any | None = None
        self._id_map: list[str] = []

        self._initialize()

    def _initialize(self) -> None:
        """Try loading embedding dependencies and persisted FAISS index."""
        try:
            import faiss  # type: ignore[import-not-found]
            import numpy as np  # type: ignore[import-not-found]
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
        except Exception:
            # Optional Phase 2 dependencies may not be installed in all environments.
            self._enabled = False
            return

        self._faiss = faiss
        self._np = np
        self._model = SentenceTransformer(self.model_name)
        self._enabled = True
        self._load_persisted_index()

    def _load_persisted_index(self) -> None:
        """Load FAISS index and para-id map from disk if available."""
        if not self._enabled:
            return

        if self.index_path.exists() and self.id_map_path.exists():
            with self.id_map_path.open("r", encoding="utf-8") as f:
                self._id_map = json.load(f)
            self._index = self._faiss.read_index(str(self.index_path))

    def _persist_index(self) -> None:
        """Persist FAISS index and para-id map."""
        if not self._enabled or self._index is None:
            return

        self.embedding_dir.mkdir(parents=True, exist_ok=True)
        self._faiss.write_index(self._index, str(self.index_path))
        with self.id_map_path.open("w", encoding="utf-8") as f:
            json.dump(self._id_map, f, ensure_ascii=True)

    def _ensure_index(self, dim: int) -> None:
        """Initialize the FAISS index if not loaded yet."""
        if self._index is None and self._enabled:
            # Cosine similarity is approximated by normalized vectors + inner product.
            self._index = self._faiss.IndexFlatIP(dim)

    async def index_paragraphs(self, paragraphs: list[dict[str, Any]]) -> int:
        """Generate and store embeddings for paragraph batch.

        Returns number of embeddings written to the FAISS index.
        """
        if not self._enabled or not paragraphs:
            return 0

        para_ids: list[str] = []
        texts: list[str] = []
        for para in paragraphs:
            text = str(para.get("text", "")).strip()
            para_id = str(para.get("para_id", "")).strip()
            if text and para_id:
                texts.append(text)
                para_ids.append(para_id)

        if not texts:
            return 0

        embeddings = self._model.encode(texts, normalize_embeddings=True)
        vectors = self._np.asarray(embeddings, dtype="float32")

        self._ensure_index(vectors.shape[1])
        assert self._index is not None
        self._index.add(vectors)
        self._id_map.extend(para_ids)
        self._persist_index()
        return len(para_ids)

    async def search(
        self,
        query: str,
        doc_ids: list[str] | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Search relevant paragraphs by semantic similarity."""
        if self._enabled and self._index is not None and self._id_map:
            query_embedding = self._model.encode([query], normalize_embeddings=True)
            qvec = self._np.asarray(query_embedding, dtype="float32")

            # Overfetch so doc_id filtering still returns up to top_k candidates.
            k = min(max(top_k * 3, top_k), len(self._id_map))
            scores, indices = self._index.search(qvec, k)

            candidates: list[tuple[str, float]] = []
            for idx, score in zip(indices[0].tolist(), scores[0].tolist()):
                if idx < 0:
                    continue
                candidates.append((self._id_map[idx], float(score)))

            para_repo = ParagraphRepository(self.session)
            paragraphs = await para_repo.get_by_ids([para_id for para_id, _ in candidates])
            by_id = {p.para_id: p for p in paragraphs}

            results: list[dict[str, Any]] = []
            for para_id, score in candidates:
                para = by_id.get(para_id)
                if para is None:
                    continue
                if doc_ids and para.doc_id not in doc_ids:
                    continue
                results.append(
                    {
                        "para_id": para.para_id,
                        "text": para.text,
                        "score": score,
                        "doc_id": para.doc_id,
                        "section_path": para.section_path,
                    }
                )
                if len(results) >= top_k:
                    break

            if results:
                return results

        # Dependency-free fallback path.
        para_repo = ParagraphRepository(self.session)
        text_results = await para_repo.search_text(query, doc_ids=doc_ids, regex=False, limit=top_k)
        return [
            {
                "para_id": item["para_id"],
                "text": item["text"],
                "score": 0.0,
                "doc_id": item["doc_id"],
                "section_path": item.get("section_path"),
            }
            for item in text_results
        ]
