"""Vector embeddings service"""

from services.gemini import GeminiClient


class EmbeddingService:
    """Service for generating vector embeddings."""

    def __init__(self, gemini_client: GeminiClient | None = None) -> None:
        """Initialize embedding service.

        Args:
            gemini_client: Optional Gemini client (if None, will use sentence-transformers)
        """
        self.gemini_client = gemini_client
        if gemini_client:
            self.model_name = "text-multilingual-embedding"  # v1beta compatible model  # Note: Using v1beta, model names differ
            self.model_version = "gemini"
        else:
            self.model_name = "all-MiniLM-L6-v2"
            self.model_version = "sentence-transformers"

    def generate_embeddings(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """
        Generate embeddings for texts.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (384 dimensions each)
        """
        if self.gemini_client:
            return self.gemini_client.embed_texts(texts)

        try:
            from sentence_transformers import SentenceTransformer

            model_name = "all-MiniLM-L6-v2"
            model = SentenceTransformer(model_name)

            all_embeddings = model.encode(
                texts,
                convert_to_numpy=True,
                show_progress_bar=False,
            )

            return all_embeddings.tolist()

        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            ) from None

    def generate_batch(
        self,
        texts: list[str],
        batch_size: int = 32,
    ) -> list[list[float]]:
        """
        Generate embeddings in batches for large datasets.

        Args:
            texts: List of text strings to embed
            batch_size: Number of texts to process at once

        Returns:
            List of embedding vectors
        """
        result_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_embeddings = self.generate_embeddings(batch)
            result_embeddings.extend(batch_embeddings)

        return result_embeddings
