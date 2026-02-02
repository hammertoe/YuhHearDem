"""Embeddings service tests"""

from unittest.mock import Mock, patch
import pytest

from services.embeddings import EmbeddingService


class TestEmbeddingService:
    """Test embeddings service."""

    @patch("services.embeddings.SentenceTransformer")
    def test_generate_embeddings_mocked(self, mock_transformer):
        """Test embedding generation with mocked transformer."""
        mock_model = Mock()
        mock_model.encode.return_value = [[0.1, 0.2, 0.3]]
        mock_transformer.return_value = mock_model

        service = EmbeddingService()
        embeddings = service.generate_embeddings(["test text"])

        assert len(embeddings) == 1
        assert len(embeddings[0]) == 3
        mock_model.encode.assert_called_once()

    def test_initialization_without_client(self):
        """Test initialization without Gemini client."""
        service = EmbeddingService(gemini_client=None)

        assert service.gemini_client is None

    def test_initialization_with_client(self):
        """Test initialization with Gemini client."""
        mock_client = Mock()
        service = EmbeddingService(gemini_client=mock_client)

        assert service.gemini_client == mock_client

    @patch("services.embeddings.SentenceTransformer")
    def test_generate_batch(self, mock_transformer):
        """Test batch embedding generation."""
        mock_model = Mock()
        mock_model.encode.return_value = [[0.1, 0.2], [0.3, 0.4]]
        mock_transformer.return_value = mock_model

        service = EmbeddingService()
        texts = ["text1", "text2", "text3", "text4"]
        embeddings = service.generate_batch(texts, batch_size=2)

        assert len(embeddings) == 4
        mock_model.encode.assert_called_once()
