#!/usr/bin/env bash
# PostToolUse: lint an edited app/ Python file with flake8 inside the backend container.
# The file is piped via stdin, so it works from any worktree, not just the checkout the container mounts.
set -euo pipefail

file_path=$(jq -r '.tool_input.file_path // ""')

[[ "$file_path" == */app/*.py && -f "$file_path" ]] || exit 0

# Linting is a convenience, not a gate: skip when the container is down.
if ! docker exec luxdem_backend true 2>/dev/null; then
    exit 0
fi

if ! output=$(docker exec -i luxdem_backend python3 -m flake8 --max-line-length=100 \
        --stdin-display-name "$file_path" - <"$file_path" 2>&1); then
    # Non-blocking warning (exit 1) so a missing linter is visible, not silently skipped.
    if grep -q "No module named flake8" <<<"$output"; then
        echo "flake8 hook: flake8 not installed in luxdem_backend; rebuild with 'make dev-build'." >&2
        exit 1
    fi
    echo "$output" >&2
    exit 2
fi
