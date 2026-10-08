# Contributing

## Reporting bugs / proposing changes

Open an issue first for anything beyond a trivial fix (typo, obvious bug). Describe the problem or the change you want to make before writing code — it saves you from a PR that gets rejected for reasons you couldn't have known about.

## Making a PR

1. Fork the repo, branch off `main`.
2. Keep PRs focused — one change, one PR. Unrelated fixes go in a separate PR.
3. Run the test suite before opening the PR: `make all-tests` (or `docker exec luxdem_backend python3 -m unittest discover tests` if the container is already running).
4. `pre-commit run --all-files` before pushing. CI runs the same checks (tests, pylint, coverage) and will fail the PR otherwise.
5. Describe what changed and why in the PR description. Link the issue it resolves, if any.

## Code style

See `CLAUDE.md` and `.claude/ARCHITECTURE.md` for the project's conventions (folder layout, import ordering, formatting). Pre-commit enforces most of it automatically.

## Local setup

See `README.md` for running the app locally.
