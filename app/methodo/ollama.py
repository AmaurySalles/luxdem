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
        if response.status_code == 200:
            models = response.json().get("models", [])
            model_names = [m["name"].split(":")[0] for m in models]
            if OLLAMA_EMBEDDING_MODEL in model_names:
                print(f"✓ Ollama is running with {OLLAMA_EMBEDDING_MODEL} model available")
                return True
            else:
                print(f"✗ {OLLAMA_EMBEDDING_MODEL} not found. Available: {model_names}")
                return False
        else:
            print(f"✗ Ollama API returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError as e:
        print(f"✗ Connection failed to {OLLAMA_BASE_URL}: {e}")
        print("  - Ensure Ollama is started with 'ollama serve'.")
        print("  - Check if port 11434 is correct (run 'lsof -i :11434' on Mac).")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


# def verify_ollama_running() -> bool:
#     """Check if Ollama is running and model is available."""
#     try:
#         response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
#         models = response.json().get("models", [])
#         model_names = [m["name"].split(":")[0] for m in models]
#         if OLLAMA_EMBEDDING_MODEL in model_names:
#             print(f"✓ Ollama is running with {OLLAMA_EMBEDDING_MODEL} model available")
#             return True
#         else:
#             print(f"✗ {OLLAMA_EMBEDDING_MODEL} not found. Available: {model_names}")
#             return False
#     except Exception as e:
#         print(f"✗ Ollama not reachable at {OLLAMA_BASE_URL}: {e}")
#         return False
