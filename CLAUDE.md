# LuxDem app

Luxembourg housing-policy analysis. Scrapes chd.lu dossiers and ONH publications, embeds them in Chroma, and has a local LLM compare laws against coalition-agreement commitments.

The pipeline is open-source only (Docling, `nomic-embed-text`, `qwen3.5` via Ollama). No Anthropic API calls: `app/methodo/claude.py`, the `anthropic` requirement and `api_keys.claude` are dead leftovers. A hook blocks new `anthropic` imports.

## Pipeline

scrape (`methodo/scraper.py`, `onh_scraper.py`) → parse + chunk (`methodo/parsing/`) → embed (`methodo/chroma.py`, one collection `dossier_docs`, split by `doc_type`) → summarize → rerank → analyze (via `methodo/local_llm.py`). `topic_analysis_pipeline.py` runs the last three.

## Commands

Everything runs in Docker (`docker compose up -d`). See `Makefile` and `python3 -m app.typer_app --help`.

- Single test: `docker exec luxdem_backend python3 -m unittest tests.unitary.<module>.<Class>.<method>`
- A hook runs flake8 on edited `app/` files; pre-commit does the rest.

## Gotchas

- Real secrets go in `secrets/local.yaml` (gitignored), layered over `config/`.
- Locally the chat model runs on native Ollama.app (`127.0.0.1:11434`), not the `luxdem_ollama` container.

## Read when relevant

- `.claude/ARCHITECTURE.md`: before adding modules or Dash pages
- `.claude/TESTING.md`: before writing tests
- `.claude/STYLE_GUIDE.md`: before writing new functions
- `.claude/DECISIONS.md`: before changing parsing, embedding, config or paths
