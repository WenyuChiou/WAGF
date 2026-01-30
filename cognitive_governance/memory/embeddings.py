# cognitive_governance/memory/embeddings.py

from typing import Protocol, List, Optional, Dict, Any
from abc import ABC, abstractmethod
import numpy as np

# Lazy loading for optional dependency
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print("WARNING: sentence-transformers not installed. SentenceTransformerProvider will not be functional.")

class EmbeddingProvider(Protocol):
    """
    Protocol for embedding providers.
    Defines the interface for converting text to embeddings.
    """
    @abstractmethod
    def embed(self, texts: List[str]) -> List[np.ndarray]:
        """
        Generates embeddings for a list of texts.

        Args:
            texts: A list of strings to embed.

        Returns:
            A list of numpy arrays, where each array is an embedding for the corresponding text.
        """
        ...

class SentenceTransformerProvider:
    """
    Embedding provider using SentenceTransformers library.
    Loads the model lazily upon first use.
    """
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        self.model_name = model_name
        self._model: Optional[SentenceTransformer] = None

    @property
    def model(self) -> SentenceTransformer:
        """Lazy load the SentenceTransformer model."""
        if self._model is None:
            if not SENTENCE_TRANSFORMERS_AVAILABLE:
                raise RuntimeError("sentence-transformers library is required but not installed.")
            print(f"Loading SentenceTransformer model: {self.model_name}...")
            self._model = SentenceTransformer(self.model_name)
            print("Model loaded.")
        return self._model

    def embed(self, texts: List[str]) -> List[np.ndarray]:
        """
        Generates embeddings for a list of texts using the SentenceTransformer model.
        """
        if not texts:
            return []
        # Ensure model is loaded before encoding
        # The SentenceTransformer.encode method returns numpy arrays.
        # Convert to list of lists as per expected return type List[np.ndarray].
        return self.model.encode(texts, convert_to_numpy=True).tolist() 

class MockEmbeddingProvider:
    """
    A mock embedding provider for testing purposes.
    Returns deterministic, mock embeddings.
    """
    def __init__(self, dimensions: int = 16):
        self.dimensions = dimensions

    def embed(self, texts: List[str]) -> List[np.ndarray]:
        """
        Returns mock embeddings of a fixed dimension for each text.
        """
        return [np.random.rand(self.dimensions).tolist() for _ in texts]

# Example Usage (optional, for demonstration)
if __name__ == '__main__':
    if SENTENCE_TRANSFORMERS_AVAILABLE:
        try:
            st_provider = SentenceTransformerProvider()
            mock_embeddings = st_provider.embed(["Hello world", "This is a test."])
            print("SentenceTransformer embeddings (first 5 dims):", [e[:5] for e in mock_embeddings])
        except RuntimeError as e:
            print(f"Could not run SentenceTransformer example: {e}")

    mock_provider = MockEmbeddingProvider(dimensions=8)
    mock_embeddings = mock_provider.embed(["This is mock.", "Another mock sentence."])
    print("Mock embeddings (first 5 dims):", [e[:5] for e in mock_embeddings])