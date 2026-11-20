"""
Local chat-completion client backed by Ollama.
Replaces the Claude API for summarization/reranking/analysis so these
pipeline steps run without per-token billing.
"""
from ecodev_core import SETTINGS
from ollama import Client

from app.methodo.ollama import OLLAMA_BASE_URL

LOCAL_LLM_MODEL = SETTINGS.ollama.chat_model
# Verdicts must be reproducible: a tag can move to new weights (qwen3.5:latest did, #103).
CHAT_MODEL_DIGEST = SETTINGS.ollama.chat_model_digest
# Stored with each summary: a summary from another model or digest is stale.
CHAT_MODEL_ID = f"{LOCAL_LLM_MODEL}@{CHAT_MODEL_DIGEST}"
# Chat runs on the rented GPU through an SSH tunnel; embedding stays on the Mac (base_url).
CHAT_BASE_URL = getattr(SETTINGS.ollama, "chat_base_url", None) or OLLAMA_BASE_URL
# Verdicts carry ~30 verbatim passages (~12k tokens, #101): 32k leaves room for the answer.
# Chat runs on the rented GPU only; an 8 GB Mac can't hold this context.
CHAT_NUM_CTX = int(getattr(SETTINGS.ollama, "chat_num_ctx", 32768))


class ChatModelMismatchError(Exception):
    """
    The chat host doesn't serve the pinned chat model at the pinned digest.

    Purpose: stops summaries and verdicts being written by other weights than the ones
    recorded in `model_used` (a moved tag, or a host that never pulled the model).
    """

    def __init__(self, host: str, model: str, expected_digest: str, found_digest: str | None) -> None:
        self.host = host
        self.model = model
        self.expected_digest = expected_digest
        self.found_digest = found_digest
        super().__init__(f"{host} serves {model} at {found_digest or 'no digest (not pulled)'}, "
                         f"expected {expected_digest}")


def get_local_llm_client(host: str = CHAT_BASE_URL) -> Client:
    """
    Ollama client for the chat model, checked against the pinned digest.

    Purpose: shared by the summary commands and `topic_analysis_pipeline`.

    Raises:
        ChatModelMismatchError: the host lacks the model, or serves other weights.
    """
    client = Client(host=host)
    found = next((m.digest for m in client.list().models if m.model == LOCAL_LLM_MODEL), None)
    if not (found or "").startswith(CHAT_MODEL_DIGEST):
        raise ChatModelMismatchError(host, LOCAL_LLM_MODEL, CHAT_MODEL_DIGEST, found)
    return client


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
        # documents together, which can leave no budget to generate a response at all.
        options={"num_ctx": CHAT_NUM_CTX},
    )
    return response["message"]["content"]
