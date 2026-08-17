"""Embedding generator using FastEmbed for fast local vector representations."""

from typing import List, Optional
from fastembed import TextEmbedding


class EmbeddingService:
    """Service to produce dense vector embeddings locally or via model APIs."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.model_name = model_name
        self._model: Optional[TextEmbedding] = None

    def _get_model(self) -> TextEmbedding:
        if self._model is None:
            self._model = TextEmbedding(model_name=self.model_name)
        return self._model

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of documents or chunks."""
        if not texts:
            return []
        model = self._get_model()
        # fastembed returns generator of numpy arrays
        embeddings_iter = model.embed(texts)
        return [list(emb) for emb in embeddings_iter]

    def embed_query(self, query: str) -> List[float]:
        """Generate embedding for a single search query."""
        model = self._get_model()
        embeddings = list(model.query_embed(query))
        if embeddings:
            return list(embeddings[0])
        return []
