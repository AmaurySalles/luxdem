# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

LuxDem is a Luxembourg housing policy analysis tool. It scrapes legislative dossiers from chd.lu and ONH (Observatoire National de l'Habitat) publications, embeds them into a Chroma vector store, and uses Claude to generate structured policy analyses cross-referencing laws against coalition agreement commitments and ONH research.

## Commands

All commands run inside Docker containers. The container must be running first (`docker compose up -d`).

```bash
# Setup and build
make setup           # Install pre-commit hooks (run once on a new clone)
make dev-build       # Build the development Docker image (no cache)
make prod-build      # Build the production image

# Run tests
make all-tests       # Run the full test suite inside the container

# Data pipelines (run inside the backend container)
make scrape-dossiers              # Scrape chd.lu for legislative dossier metadata
make insert-dossier-embedings     # Parse + embed dossiers into Chroma

# Typer CLI (exec into backend for more pipeline commands)
docker exec luxdem_backend python3 -m app.typer_app --help
docker exec luxdem_backend python3 -m app.typer_app scrape-onh-command
docker exec luxdem_backend python3 -m app.typer_app embed-onh-command
docker exec luxdem_backend python3 -m app.typer_app ingest-coalition-agreement-command <pdf_path>
docker exec luxdem_backend python3 -m app.typer_app summarize-laws-command
docker exec luxdem_backend python3 -m app.typer_app analyze-topic-command "logement abordable"

# Run a single test
docker exec luxdem_backend python3 -m unittest tests.unitary.<module>.<TestClass>.<test_method>

# Logs
docker logs luxdem_backend --tail=100 -f
```

## Architecture

The app runs as two Docker services sharing the same image:
- **`luxdem_backend`** — FastAPI, port 8000. Entry point: `app/app.py`. Houses the analysis API and all data pipelines.
- **`luxdem-frontend`** — Plotly Dash (on Flask), port 8050. Entry point: `app/dash_app.py`.

In dev (`docker-compose.override.yml`), both use `uvicorn` with `--reload`. In prod, gunicorn with multiple workers.

### Data flow

The full pipeline to get from raw web sources to a topic analysis runs in order:

1. **Scrape** (`app/methodo/scraper.py`, `onh_scraper.py`) — fetch dossier/ONH metadata and store in Postgres via SQLModel.
2. **Parse** (`app/methodo/parsing/`) — download PDFs and parse with Docling (`docling_parser.py`); fallbacks via `pdfplumber.py`. Produces text chunks with metadata dicts.
3. **Embed** (`app/methodo/chroma.py`) — chunks are embedded with Ollama (`nomic-embed-text` by default) and stored in Chroma at `data/embeddings/`. All documents are in a single collection `dossier_docs`, distinguished by `doc_type` metadata (`"dossier"`, `"onh"`, `"coalition"`).
4. **Summarize** (`app/methodo/summarizer.py`) — Claude generates per-document summaries that are cached in `DossierSummary` / `OnhSummary` DB tables. Run `summarize-laws-command` to pre-warm the cache.
5. **Rerank** (`app/methodo/reranker.py`) — Claude scores each candidate document for relevance to the query topic.
6. **Analyze** (`app/methodo/analyzer.py`) — Claude generates a structured `TopicAnalysisResult` (Pydantic model) containing commitments, matched laws, ONH reports, gaps, and a conclusion.

`topic_analysis_pipeline.py` orchestrates steps 4–6 end-to-end and is called both from the Typer CLI and from `POST /api/analysis/topic`.

### Configuration

Settings are loaded by `ecodev_core.SETTINGS` from layered YAML files under `config/` and `secrets/`. `config/local.yaml` contains structure with nulled secrets; real values go in `secrets/local.yaml` (gitignored). Key settings: `ollama.embedding_model`, `api_keys.claude`.

### Database

SQLModel + PostgreSQL. Tables are defined under `app/db_model/tables/`: `Dossier`, `Resource`, `DossierSummary`, `OnhPublication`, `OnhSummary`. Tables inherited from `ecodev_core`: `AppUser`, `AppRight`, `AppActivity`. All tables are auto-created on Dash startup via `create_db_and_tables()`. DB operations follow the pattern: retrievers in `app/db_model/retrievers/`, inserters in `app/db_model/inserters/`.

### Frontend

Dash pages are registered centrally: define a `Page` object, add it to `app/pages/modules.py` via a `Module`, and it auto-registers in `dash_app.py`. The `app/pages/registry.py` module-level singleton prevents circular imports between pages that reference `MODULES` or `PAGES`.

## Code style

Pre-commit enforces: `autopep8` (max line length 100), `flake8`, `mypy` (`--ignore-missing-imports`), `reorder-python-imports`, `autoflake`, trailing whitespace, LF line endings, and double-quote string fixer (single quotes → double quotes). Run `pre-commit run --all-files` to check before committing.

The pre-commit `check_dependencies` hook runs inside the container and requires it to be up.

## Reference docs

@.claude/ARCHITECTURE.md
@.claude/TESTING.md
