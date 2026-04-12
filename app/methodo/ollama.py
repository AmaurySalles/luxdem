# === Step 5: Ollama Embeddings Setup ===

from contextlib import suppress
from ipaddress import ip_address
from urllib.parse import urlparse
from urllib.parse import urlunparse

import requests
from ecodev_core import SETTINGS
from langchain_community.embeddings import OllamaEmbeddings

DEFAULT_OLLAMA_PORT = 11434
_LOCAL_OLLAMA_HOSTNAMES = frozenset({'localhost', '127.0.0.1', '::1'})


def _netloc_host_port(hostname: str | None, port: int) -> str:
    h = hostname or '127.0.0.1'
    with suppress(ValueError):
        if ip_address(h).version == 6:
            return f'[{h}]:{port}'
    return f'{h}:{port}'


def _resolved_ollama_base_url() -> str:
    o = SETTINGS.ollama
    raw = str(getattr(o, 'base_url', f'http://127.0.0.1:{DEFAULT_OLLAMA_PORT}')).strip()
    yaml_port = getattr(o, 'port', None)
    parsed = urlparse(raw.rstrip('/'))
    if not parsed.scheme:
        parsed = urlparse(f'http://{raw}')
    host = (parsed.hostname or '').lower()
    is_local = host in _LOCAL_OLLAMA_HOSTNAMES

    if yaml_port is not None and is_local:
        netloc = _netloc_host_port(parsed.hostname, int(yaml_port))
        return urlunparse((parsed.scheme or 'http', netloc, '', '', '', '')).rstrip('/')

    if is_local and parsed.port is None and yaml_port is None:
        netloc = _netloc_host_port(parsed.hostname, DEFAULT_OLLAMA_PORT)
        return urlunparse((parsed.scheme or 'http', netloc, '', '', '', '')).rstrip('/')

    return raw.rstrip('/')


OLLAMA_BASE_URL = _resolved_ollama_base_url()
OLLAMA_EMBEDDING_MODEL = SETTINGS.ollama.embedding_model
OLLAMA_PORT = str(urlparse(OLLAMA_BASE_URL).port or DEFAULT_OLLAMA_PORT)


def get_ollama_embeddings(model: str = OLLAMA_EMBEDDING_MODEL):
    """Initialize Ollama embeddings"""
    embeddings = OllamaEmbeddings(
        base_url=OLLAMA_BASE_URL,
        model=model,
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
                print(f"✗ {OLLAMA_EMBEDDING_MODEL} not found. Available: {model_names or '(none)'}")
                print(f"  - Host Ollama: ollama pull {OLLAMA_EMBEDDING_MODEL}")
                print(
                    f"  - Compose: docker compose exec ollama ollama pull {OLLAMA_EMBEDDING_MODEL}"
                )
                return False
        else:
            print(f"✗ Ollama API returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError as e:
        print(f"✗ Connection to Ollama {OLLAMA_EMBEDDING_MODEL} failed to {OLLAMA_BASE_URL}: {e}")
        print(f"  - Host: start Ollama (Docker service or `ollama serve`); only one listener on {OLLAMA_PORT}.")
        print('  - In Docker, set config ollama.base_url to the service (e.g. http://ollama:11434).')
        print(f"  - On Mac: `lsof -i :{OLLAMA_PORT}` — ollama_port in .env is only for Compose host mapping, not this URL.")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False
