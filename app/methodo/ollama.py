# === Step 5: Ollama Embeddings Setup ===


from langchain_community.embeddings import OllamaEmbeddings
import requests

# === Configuration ===
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_EMBEDDING_MODEL = "mistral"

def get_ollama_embeddings():
    """Initialize Ollama embeddings (Mistral model)."""
    embeddings = OllamaEmbeddings(
        base_url=OLLAMA_BASE_URL,
        model=OLLAMA_EMBEDDING_MODEL,
    )
    return embeddings

def verify_ollama_running() -> bool:
    """Check if Ollama is running and model is available."""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        models = response.json().get("models", [])
        model_names = [m["name"].split(":")[0] for m in models]
        if OLLAMA_EMBEDDING_MODEL in model_names:
            print(f"✓ Ollama is running with {OLLAMA_EMBEDDING_MODEL} model available")
            return True
        else:
            print(f"✗ {OLLAMA_EMBEDDING_MODEL} not found. Available: {model_names}")
            return False
    except Exception as e:
        print(f"✗ Ollama not reachable at {OLLAMA_BASE_URL}: {e}")
        return False
