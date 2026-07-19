"""
Local chat-completion client backed by Ollama.
Replaces the Claude API for summarization/reranking/analysis so these
pipeline steps run without per-token billing.
"""
from ecodev_core import SETTINGS
from ollama import Client

from app.methodo.ollama import OLLAMA_BASE_URL

LOCAL_LLM_MODEL = SETTINGS.ollama.chat_model


def get_local_llm_client() -> Client:
    return Client(host=OLLAMA_BASE_URL)


def chat_completion(
    client: Client,
    system_prompt: str,
    user_message: str,
    *,
    json_mode: bool = False,
) -> str:
    response = client.chat(
        model=LOCAL_LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        format="json" if json_mode else None,
    )
    return response["message"]["content"]
