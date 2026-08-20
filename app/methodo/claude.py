import anthropic
from ecodev_core import SETTINGS

CLAUDE_MODEL = "claude-sonnet-4-6"


def get_claude_client() -> anthropic.Anthropic:
    api_key = SETTINGS.api_keys.claude
    if not api_key:
        raise ValueError("api_keys.claude is not set in config/local.yaml")
    return anthropic.Anthropic(api_key=api_key)
