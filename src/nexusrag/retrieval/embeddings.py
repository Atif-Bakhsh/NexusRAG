from functools import cached_property

from nexusrag.config import Settings

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class Embedder:
    def __init__(self, settings: Settings):
        self.settings = settings

    @cached_property
    def model(self):
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(
            self.settings.embedding_model, revision=self.settings.embedding_revision, device="cpu"
        )

    def count(self, text: str) -> int:
        return len(self.model.tokenizer.encode(text, add_special_tokens=True, verbose=False))

    def passages(self, texts: list[str]) -> list[list[float]]:
        if any(self.count(t) > 320 for t in texts):
            raise ValueError("Chunk exceeds embedding token limit")
        return self.model.encode(
            texts, normalize_embeddings=True, batch_size=16, show_progress_bar=False
        ).tolist()

    def query(self, question: str) -> list[float]:
        text = QUERY_PREFIX + question
        if self.count(text) > 512:
            raise ValueError("Question exceeds embedding model token limit")
        return self.model.encode([text], normalize_embeddings=True, show_progress_bar=False)[
            0
        ].tolist()
