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
        # Thinking models (e.g. qwen3.5) emit a reasoning preamble by default,
        # which slows generation and can leak into the JSON we parse below.
        think=False,
        # Ollama's default num_ctx (2048-4096) truncates prompts stuffing several
        # document summaries together (e.g. reranking 7 laws at once), which can
        # leave no budget left to generate a response at all.
        options={"num_ctx": 16384},
    )
    return response["message"]["content"]
