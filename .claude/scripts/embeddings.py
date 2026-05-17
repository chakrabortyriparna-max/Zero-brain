from typing import List
import numpy as np


class Embedder:
    """Lazy-loading FastEmbed wrapper for sentence-transformers/all-MiniLM-L6-v2."""

    _model = None
    _model_name = "sentence-transformers/all-MiniLM-L6-v2"
    _dim = 384

    def __init__(self):
        if Embedder._model is None:
            from fastembed import TextEmbedding

            Embedder._model = TextEmbedding(model_name=Embedder._model_name)

    def embed_texts(self, texts: List[str]) -> List[np.ndarray]:
        """Embed a batch of documents. Returns list of 1-D float32 arrays."""
        if not texts:
            return []
        # fastembed returns a generator of np.ndarray
        return list(Embedder._model.embed(texts))

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query string. Returns 1-D float32 array."""
        results = self.embed_texts([query])
        return results[0]
