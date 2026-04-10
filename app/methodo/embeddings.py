import os

from langchain_core.embeddings import Embeddings

try:
    import voyageai
except ImportError:  # pragma: no cover - handled at runtime when deps are missing
    voyageai = None


DEFAULT_EMBEDDING_PROVIDER = "voyage"
DEFAULT_EMBEDDING_MODEL = "voyage-3-large"
VOYAGE_ALLOWED_INPUT_TYPES = {"document", "query"}


def get_embedding_provider() -> str:
    return os.getenv("EMBEDDING_PROVIDER", DEFAULT_EMBEDDING_PROVIDER).strip().lower()


def get_embedding_model() -> str:
    return os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL).strip()


def get_voyage_api_key() -> str:
    return os.getenv("VOYAGE_API_KEY", "").strip()


class VoyageEmbeddingsAdapter(Embeddings):
    """LangChain-compatible Voyage embedding adapter."""

    def __init__(self, model_name: str, api_key: str) -> None:
        if voyageai is None:
            raise ImportError(
                "The 'voyageai' package is not installed. Add it to requirements "
                "and rebuild the environment before using Voyage embeddings."
            )
        if not api_key:
            raise ValueError("VOYAGE_API_KEY is required when EMBEDDING_PROVIDER=voyage.")

        self.model_name = model_name
        self._client = voyageai.Client(api_key=api_key)

    def _embed_texts(self, texts: list[str], input_type: str) -> list[list[float]]:
        if not texts:
            return []
        if input_type not in VOYAGE_ALLOWED_INPUT_TYPES:
            raise ValueError(
                f"Unsupported Voyage input_type={input_type!r}. "
                "Supported values: document, query."
            )

        response = self._client.embed(texts, model=self.model_name, input_type=input_type)
        embeddings = getattr(response, "embeddings", None)
        if embeddings is None and isinstance(response, dict):
            embeddings = response.get("embeddings")
        if embeddings is None:
            raise ValueError("Voyage API returned an unexpected embedding payload.")
        return embeddings

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed_texts(texts, input_type="document")

    def embed_query(self, text: str) -> list[float]:
        embeddings = self._embed_texts([text], input_type="query")
        return embeddings[0]


def get_embedding_function() -> Embeddings:
    """Return the configured embedding provider."""
    embedding_provider = get_embedding_provider()
    embedding_model = get_embedding_model()

    if embedding_provider == "voyage":
        return VoyageEmbeddingsAdapter(
            model_name=embedding_model,
            api_key=get_voyage_api_key(),
        )

    raise ValueError(
        f"Unsupported EMBEDDING_PROVIDER={embedding_provider!r}. "
        "Supported providers: voyage."
    )


def embed_texts(texts: list[str], input_type: str = "document") -> list[list[float]]:
    """Embed text through the configured provider."""
    embedding_provider = get_embedding_provider()
    if embedding_provider != "voyage":
        raise ValueError(
            f"Unsupported EMBEDDING_PROVIDER={embedding_provider!r}. "
            "Supported providers: voyage."
        )

    embeddings = get_embedding_function()
    if not isinstance(embeddings, VoyageEmbeddingsAdapter):
        raise TypeError("Configured embeddings do not support direct batch embedding.")

    return embeddings._embed_texts(texts, input_type=input_type)


def verify_embedding_provider() -> bool:
    """Run a lightweight connectivity check against the configured provider."""
    try:
        embeddings = get_embedding_function()
        vector = embeddings.embed_query("healthcheck")
    except Exception as exc:
        print(f"✗ Embedding provider check failed: {exc}")
        return False

    print(
        f"✓ Embedding provider '{get_embedding_provider()}' is reachable "
        f"with model '{get_embedding_model()}' ({len(vector)} dims)"
    )
    return True


if __name__ == "__main__":
    raise SystemExit(0 if verify_embedding_provider() else 1)
