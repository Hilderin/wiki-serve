from functools import lru_cache


_EMBEDDING_DIM = 384


class Embedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: str = "cpu"):
        self._model_name = model_name
        self._device = device
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer
        print(f"[wiki-serve] Loading embedding model '{self._model_name}' (this may download on first run)...", flush=True)
        self._model = SentenceTransformer(self._model_name, device=self._device)
        print(f"[wiki-serve] Embedding model loaded.", flush=True)

    def load(self) -> None:
        self._load_model()

    def embed(self, text: str) -> list[float]:
        self._load_model()
        vec = self._model.encode(text, normalize_embeddings=True)
        return vec.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._load_model()
        vecs = self._model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vecs]

    @property
    def dimension(self) -> int:
        return _EMBEDDING_DIM
