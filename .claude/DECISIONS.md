# Technical Decisions

Living record of architectural and operational choices for this project. Each entry explains what was decided, why, and what the alternatives were. Add new entries at the top.

---

## 2026-10 — Custom Ollama embedding client; new Chroma store per model

**Issues**: [#48](https://github.com/AmaurySalles/luxdem/issues/48) (decision), [#51](https://github.com/AmaurySalles/luxdem/issues/51) (implementation)

**Decision**: `get_ollama_embeddings` returns `OllamaEmbedEmbeddings` (`app/methodo/ollama_embeddings.py`), a LangChain `Embeddings` over `ollama.Client` calling `/api/embed` in batches of 64. It sets `truncate=False`, per-model `num_ctx`/`num_batch` (8192 bge-m3/arctic2, 2048 nomic), `keep_alive` (`ollama.embedding_keep_alive`), a 120 s timeout, retry with backoff on connection errors/5xx, and per-model prefixes (bge-m3 none; arctic2 `query: ` on queries; nomic `search_document: `/`search_query: `). It logs `prompt_eval_count`. Model stays `ollama.embedding_model`; the default is picked by the comparison (#52).

**Why**: the `langchain_community` client sent one request per chunk to the deprecated `/api/embeddings`, added E5 prefixes nomic never saw, and had no timeout/retry. `langchain-ollama` 0.1.3 (the only version fitting the 0.2 pins) can't set `num_ctx`/`num_batch`. `/api/embed` truncates silently by default.

**Over-long chunks**: with `truncate=False` Ollama returns 400 "input length exceeds the context length". The client then embeds the batch one by one, splits the offending chunk in two on a paragraph/line/word boundary (recursively), and stores the token-weighted mean of the parts, re-normalized. One vector per chunk, so chunk IDs don't change, and no text is dropped. Each split is logged.

**Chroma**: the store comes from config `chroma.directory`/`chroma.collection` (default: the old `data/embeddings`/`dossier_docs`). New collections are created with `hnsw:space=cosine`, `hnsw:search_ef=100` (the default 10 missed an exact match among near-duplicate chunks in testing), `hnsw:construction_ef=200`, and the model, Ollama version and digest. A collection without `embedding_model` metadata predates #51 and keeps the old client, so old and new vectors never mix; opening a collection with another model raises. The re-embed (#32) points the config at a new store. `add_documents` is sliced into 256-doc calls, since langchain-chroma 0.1.4 embeds the whole list then does one upsert.

---

## 2026-10 — Table-shredded chunking fix: merge, not reconfigure

**Issues**: [#28](https://github.com/AmaurySalles/luxdem/issues/28) (investigation), [#31](https://github.com/AmaurySalles/luxdem/issues/31) (implementation), PR [#33](https://github.com/AmaurySalles/luxdem/pull/33)

**Decision**: `docling_parser.py` now merges chunks that got split across a table boundary, via `_merge_table_shredded_chunks()`, run right after `HybridChunker.chunk()`.

**Why**: 49% of chunks in a diagnosis sample had a table split across multiple chunks. The cause is Docling's `HybridChunker`: when a table doesn't fit its 512-token budget, it falls through to a plain-text splitter with no table awareness. Docling's table recognition itself (`TableFormerMode.ACCURATE`) was already correct — reconfiguring it would have changed nothing. The fix merges split chunks back together post-chunking instead.

**Result**: verified on the 18-doc diagnosis sample (2,333 shredded flags → 0) and the full 35-doc ONH corpus (0 shredded, max chunk 2,355 words). Correction (#51): that is not "well under the 8192-token limit" for nomic-embed-text, which Ollama clamps to 2048 tokens, so such chunks overflow it; the #51 client splits them instead of letting Ollama cut them.

---

## 2026-10 — Chroma chunk-ID cleanup is a one-off migration, not a pipeline change

**Issue**: [#29](https://github.com/AmaurySalles/luxdem/issues/29)

**Decision**: a one-off migration script deletes and re-embeds only the docs whose chunk count changed after the table-shredding fix (detected by reparsing and comparing to the `chunk_count` already in Chroma's metadata). `onh_pipeline()`/`main_pipeline()` themselves are untouched.

**Why**: chunk IDs are `md5(source_url::chunk_index)`. Changing chunk counts leaves stale chunks behind at indices the new run no longer writes, and the existing "skip if chunk 0's ID exists" check (`onh_pipeline.py:40`, `main_pipeline.py:38`) would otherwise skip every doc without noticing anything changed. Scoping the fix to a one-off script — rather than making every pipeline run always reparse and compare — keeps that cheap skip-check fast for the common case where nothing changed.

**Implementation**: deletes by `vectorstore.get(where={"source_url": ...})` then `vectorstore.delete(ids=...)`, the same pattern already used by `_delete_coalition_chunks()`. Dry-run by default; a `--commit` flag is required to actually touch Chroma.

---

## 2026-06 — `constants.py` path resolution made environment-aware

**Commit**: `1bf7bf1` — "fixed dossier pipeline" (`git show 1bf7bf1`)

**Decision**: `DATA_DIR` and `ASSETS_DIR` in `constants.py` now read from the `base_path` environment variable (falling back to `/app`) rather than being hardcoded to Docker-internal paths.

**Why**: The native `local-embed-dossiers` Makefile target failed with `OSError: [Errno 30] Read-only file system: '/app'` because `DATA_DIR = Path('/app/data')` is a Docker-internal path that doesn't exist on the Mac host. The `LOCAL_ENV` Makefile variable already passed `base_path=$(PROJECT_ROOT)` to native runs — `constants.py` was simply not reading it. In Docker, `base_path` is unset, so it falls back to `/app`, preserving existing container behaviour.

**Implications**: Any new path constant rooted at the project root should derive from `_base` (the `base_path` env var) rather than hardcoding `/app`. This is the established convention for keeping native and Docker paths consistent.

---

## 2026-06 — Idempotent embedding pipelines via Chroma ID check

**Commit**: `d525999` — "claude doc" (`git show d525999`)

**Decision**: Before embedding each document, check whether its first chunk ID already exists in Chroma. Skip if found.

**Why**: Both `dossier_pipeline` and `onh_pipeline` had an `item_cache = set()` guard, but that set is a local variable re-initialised on every process start. Re-running the pipeline would re-embed every document through Ollama — not creating duplicate *rows* (because `langchain_chroma` calls `upsert` internally, so same IDs overwrite), but wasting significant compute time for a batch of hundreds of PDFs.

**How the check works**: `embed_and_store_in_chroma` assigns each chunk a deterministic ID: `md5("{source_url}::{chunk_index}")`. Checking whether `md5("{url}::0")` exists in Chroma is a reliable proxy for "this document was fully processed in a previous run." A single `vectorstore.get(ids=[first_id])` call is cheap.

**Side fix**: the vectorstore was being re-initialised inside the loop on every document in `dossier_pipeline`. Moved to before the loop.

---

## 2026-06 — Native MPS batch processing via local `.venv`

**Commit**: `2cd4605` — "docling local" (`git show 2cd4605`)

**Decision**: Run Docling PDF parsing on native macOS (Apple Silicon MPS) for large one-off batches, rather than inside the Docker container.

**Why**: The `luxdem_backend` Docker image uses CPU-only PyTorch (`--index-url https://download.pytorch.org/whl/cpu`) because Docker on Mac cannot access the GPU. For a batch of hundreds of ONH PDFs, MPS gives a meaningful throughput advantage. Docker keeps using CPU — that behaviour is intentional and unchanged.

**How**: Three `@local` Makefile targets manage the native environment:
- `local-venv` — creates `.venv` with Python 3.13, installs default PyTorch wheels (pip resolves MPS-capable wheels on Apple Silicon automatically), then installs `requirements.txt` and `requirements-dev.txt`.
- `local-verify` — checks `torch.backends.mps.is_available()` and that Docling imports cleanly.
- `local-embed-onh` / `local-embed-dossiers` — run the respective Typer commands from the native venv.

**Config-driven accelerator**: `docling.accelerator` in `config/local.yaml` (`mps`) and `config/prod.yaml` (`cpu`). Read by `_read_docling_config()` in `docling_parser.py` with safe defaults when the section is absent. If MPS is requested but unavailable (e.g. CI, Linux), `_resolve_device()` logs a warning and falls back to CPU automatically.

---

## 2026-06 — ecodev_core / project `.env` conflict workaround

**Commit**: `2cd4605` — "docling local" (same commit as MPS setup; the `/tmp` workaround is in the `LOCAL_ENV` Makefile variable)

**Decision**: All `@local` Makefile targets that import `ecodev_core` run with `cd /tmp` as the working directory, and `PYTHON` is an absolute path.

**Why**: `ecodev_core.DeploymentSetting` is a `pydantic_settings.BaseSettings` model with `model_config = SettingsConfigDict(env_file='.env')`. It only expects two fields: `environment` and `base_path`. The project root `.env` contains Docker Compose infrastructure variables (`app_port`, `fastapi_env`, `postgres_db`, etc.) which pydantic_settings v2 loads and rejects with `extra_forbidden` validation errors.

This `.env` is required by Docker Compose and must not be renamed or modified. The solution: run from `/tmp`, which has no `.env` file. pydantic_settings resolves `env_file='.env'` relative to the CWD, so it finds nothing to load. Both `environment` and `base_path` are passed as explicit env vars via `LOCAL_ENV`, so `ecodev_core` still reads the correct YAML config.

**Why not fix `ecodev_core`**: it is a third-party library (pinned at `0.*`). Monkey-patching or subclassing the module-level `DEPLOYMENT_SETTINGS = DeploymentSetting()` singleton is not feasible.

---

## 2026-06 — Native service connectivity (DB and Ollama)

**Commits**: `luxdem-infra/docker-compose.override.yml` — pending commit in the `luxdem-infra` repo as of 2026-06-20. `secrets/local.yaml` is gitignored and will never appear in history.

**Decision**: Expose Postgres to the host on `5432:5432` via `luxdem-infra/docker-compose.override.yml` and update `secrets/local.yaml` to use `localhost` hostnames.

**Why**: `luxdem_backend` inside Docker resolves service names (`luxdem_db`, `ollama`) via `luxdem-network`. Native Python has no access to that Docker bridge network. Ollama (`11434`) and Chroma (`8000`) were already port-mapped in `luxdem-infra/docker-compose.yml`; only Postgres was missing a mapping.

**Chroma**: despite running a `luxdem_chroma` server container, `chroma.py` uses `langchain_chroma.Chroma(persist_directory=...)` — a **file-based** local client, not HTTP. The Chroma server port is irrelevant to the application. Data lives in `luxdem-app/data/embeddings/`, which is bind-mounted (`./data:/app/data`), so both Docker and native runs share the same store on disk with no configuration change.

**Secrets file** (`secrets/local.yaml`, gitignored): changed `db_host: luxdem_db → localhost` and `ollama.base_url: http://ollama:11434 → http://127.0.0.1:11434`. The `config/local.yaml` already had the right Ollama URL, but `secrets/local.yaml` overrides config via `deep_update`, so the secrets file wins.

---

## 2026-06 — PDF parser strategy

**Commits**: Documents pre-existing design. Parsers introduced across `0efd014` (Feat/pdf reader), `2178fbf` (feat/pdf-embedding), and `2cd4605` (docling local).

Three parsers exist; they serve different purposes:

| Parser | Location | Mode | When to use |
|---|---|---|---|
| **Docling** | `parsing/docling_parser.py` | Local model, MPS/CPU |  Open source parser with good OCRs (to parse images, tables, layout). Used in both `dossier_pipeline` and `onh_pipeline`. |

**Why Docling**: it produces semantically meaningful chunks (respects document structure, headings, tables) which improves retrieval quality downstream. The model download (~1–2 GB) is a one-time cost cached at `~/.cache/docling` (or similar).


---

## 2026-06 — YAML config layering and secrets

**Commits**: Documents pre-existing `ecodev_core` behaviour; no single commit to reference. Observed as a consequence of the native-run setup in `2cd4605`.

`ecodev_core.Settings` merges two YAML files via `deep_update`:
1. `config/{environment}.yaml` — committed, contains structure and non-secret defaults.
2. `secrets/{environment}.yaml` — gitignored, overrides anything from config.

**Implication**: if a key appears in both files, the secrets file wins. `ollama.base_url` must be set correctly in `secrets/local.yaml` (not just `config/local.yaml`) for local native runs, otherwise the committed config's correct value gets silently overridden by the stale Docker hostname in secrets.
