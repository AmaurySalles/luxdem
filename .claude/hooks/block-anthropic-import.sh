#!/usr/bin/env bash
# PreToolUse: the pipeline must stay on open-source models, so refuse edits that add an anthropic import.
set -euo pipefail

input=$(cat)
file_path=$(jq -r '.tool_input.file_path // ""' <<<"$input")
new_text=$(jq -r '[.tool_input.content, .tool_input.new_string, (.tool_input.edits // [] | .[].new_string)] | map(select(. != null)) | join("\n")' <<<"$input")

[[ "$file_path" == *.py ]] || exit 0

if grep -qE '^\s*(import anthropic|from anthropic)' <<<"$new_text"; then
    echo "Blocked: LuxDem's pipeline uses Ollama only, no Anthropic API. Use app/methodo/local_llm.py instead." >&2
    exit 2
fi
