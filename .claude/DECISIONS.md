# Technical Decisions

Living record of architectural and operational choices for this project. Each entry explains what was decided, why, and what the alternatives were. Add new entries at the top.

---

## 2026-11 — Government members and author parties from gouvernement.lu, with sources

**Issue**: [#119](https://github.com/AmaurySalles/luxdem/issues/119)

**Decision**: `import-government-command` scrapes every government mandate since 1999 with its dates from gouvernement.lu's "Anciens membres du gouvernement" page (current members included), and the party current members' biographies state ("Membre du DP depuis 1994"). An author's party at the date of an act comes from that biography quote, else from the political group of their latest CHD commission role (dataset 104), else stays unknown; every party shown carries its source. Open mandates of people no longer in government (a source error: Mutsch "depuis le 18.12.2015") are left out and logged. A minister's laws in one policy area are those the matching commission examined (Meisch's housing laws: Commission du Logement), a fact from chd.lu rather than a model's classification.

**Why**: who supported what must be sourced. gouvernement.lu does not list parties, and several biographies do not state one (Backes, Roth); guessing from the coalition would be wrong for independents and party changes (Polidori: Piraten, then LSAP).

---

## 2026-11 — Proxy seats resolved from vote bulletins, all-or-nothing per ballot

**Issue**: [#119](https://github.com/AmaurySalles/luxdem/issues/119)

**Decision**: `scrape-dossier-pages-command` stores each dossier page's commissions, rapporteurs and "Bulletin de Vote (Vote Public)" PDF links; `resolve-proxies-command` reads each bulletin ('Arendt Nancy Oui (Adehm Diane)': Adehm cast Arendt's vote) and sets `seat_vote.on_behalf_of_id` for every seat of its ballot. A bulletin is matched to the ballot held at the same second; its label, often cut short, only separates ballots held at the same second. Any disagreement with open data (unknown name, missing seat, choice, owner set by an earlier run) leaves the whole ballot unresolved and is reported. Rows are rebuilt from text positions: since Oct 2026 the PDF text runs column-wise.

Left unresolved: 2022 bulletins that are OCR'd scans ('Ficher Fmile'), ballots where open data and bulletin count different seats, bulletins newer than the last open data refresh, and motions (their bulletins are not on dossier pages).

**Why**: bulletins are the only public source naming whose vote a proxy seat was. Scans and mismatches would mean guessing.

---

## 2026-11 — Votes and commissions from CHD open data, proxies kept unresolved

**Issue**: [#119](https://github.com/AmaurySalles/luxdem/issues/119)

**Decision**: `import-chd-opendata` mirrors CHD datasets 109 (per-seat plenary votes, 07/2021 on) and 104 (commission memberships) from data.public.lu into `ballot`, `ballot_dossier`, `seat_vote`, `commission_membership`, replacing the previous import and logging it in `open_data_import` (CC licence: shown with the data). `deputy` rows are kept across imports so ids stay stable. Contact details in dataset 105 are never imported.

Dataset 109 lists the deputy who cast each seat's vote, not whose vote it is: a proxy holder appears twice, the absent deputy not at all. `seat_vote.on_behalf_of_id` is set only when certain (deputy listed once) and left empty for both seats of a proxy holder until the session minutes resolve them. Ballots the export repeated whole (180 rows, each row 3 times) are collapsed; labels merging distinct ballots (a deputy listed 3+ times, 4 debates in 2021-2023) are `is_ambiguous` and left out of individual records.

The backend container sets `REQUESTS_CA_BUNDLE` to the system bundle: certifi fails the HARICA chain of data.public.lu and chd.lu, the system bundle verifies it. Verification stays on.

**Why**: who supported what must never be guessed. Pairing proxies by party would misattribute cross-party proxies; the minutes name them.

---

## 2026-11 — Chat model: mistral-small3.2:24b, pinned by digest

**Issues**: [#103](https://github.com/AmaurySalles/luxdem/issues/103) (comparison), [#98](https://github.com/AmaurySalles/luxdem/issues/98) (summaries)

**Decision**: summaries, rerank and verdicts use `mistral-small3.2:24b` at digest `5a408ab55df5` (`ollama.chat_model`, `ollama.chat_model_digest`). `get_local_llm_client` checks the chat host's digest and raises `ChatModelMismatchError` otherwise. Chat goes to `ollama.chat_base_url` (the rented GPU through an SSH tunnel, set in secrets), embedding stays on `base_url` (the Mac). Summaries store `model_used` as `<model>@<digest>`; a summary from any other model or digest is stale and regenerated in place by `summarize-laws-command` / `summarize-onh-command`.

Summaries are written in French, like verdicts (#98): the site and its testers are French-speaking, and the language must be set before the 776 summaries are regenerated.

**Why**: in round 2 (French prompt, at most 3 ids per sentence) mistral gave 0 unknown citations and 1 uncited claim over 3 verdicts; qwen3:14b invented ids and left 10 claims uncited; gemma3:12b looped on one topic in two runs. `qwen3.5:latest` had moved to new weights since the old summaries were written, so a tag alone doesn't make verdicts reproducible.

---

## 2026-11 — Verdicts cite verbatim passages

**Issues**: [#101](https://github.com/AmaurySalles/luxdem/issues/101) (decided in the grilling on map [#109](https://github.com/AmaurySalles/luxdem/issues/109))

**Decision**: the verdict (`analyzer.generate_analysis`) gets, besides each law's and ONH report's summary, its top 4 verbatim passages, plus the coalition excerpts, each prefixed with an id (`dossier/8589#42`, `onh/note-38.pdf#3`, `coalition#120`, from `evidence.py`). The prompt requires every commitment, gap and analysis paragraph to cite ids, and to drop claims no passage supports. After generation, `TopicAnalysisResult` stores the passages seen, `unknown_citations` (ids not given) and `uncited_items`. Search is grouped by document: 100 chunks per doc type, keeping the top N distinct docs. With 10 chunks, one long law (8082) took every slot. Summaries stay cached per document but read its 30 chunks most relevant to the housing scope (`SUMMARY_FOCUS_QUERY`) in reading order, not its first 30. `ollama.chat_num_ctx` defaults to 32k (verdict prompts are ~12k tokens), which only fits on the rented GPU.

**Update (#103)**: verdicts are written in French (the sources and the Luxembourg testers are French-speaking), whatever the source language. Each claim sentence cites at most 3 ids, of passages that state the claim; `overcited_sentences` flags more (`find_overcited_sentences`), after round 1 showed mistral-small3.2 ending paragraphs with 10–15 ids. An empty verdict is retried once.

**Why**: a verdict built on summaries passes their errors on unchecked, and reviewers (Darius, Amaury) need to check each claim against its source quickly. Verdicts must be reproducible, so the passages are stored with them.

---

## 2026-11 — Parse-only worker for the rented parse box

**Issues**: [#71](https://github.com/AmaurySalles/luxdem/issues/71), [#77](https://github.com/AmaurySalles/luxdem/issues/77) (decisions), [#80](https://github.com/AmaurySalles/luxdem/issues/80) (implementation)

**Decision**: the full-corpus Docling parse runs on a rented GPU box with no Postgres or Chroma. `export-parse-manifest-command` (laptop) writes `parse_manifest.jsonl`: one `ManifestRow` per ONH doc, dossier and the coalition agreement, holding the file path relative to `data/`, the DB metadata, the parse args and `page_count`. It fails if any PDF is missing. On the box, `python -m app.methodo.parse_worker supervise` fills the parse cache. A supervisor feeds restarting worker subprocesses in two lanes: normal (`--workers`, exit over 10 GB RSS or after 20 docs) and long (1 worker for docs over 250 pages, restarted after every doc). Replies go over a dedicated pipe, not stdout. A SIGKILLed normal-lane doc is retried once in the long lane. Other failures go straight to `failed.jsonl` in the cache dir, which the dry run reports and never reparses. The laptop dry run then hits the cache for every doc. `ParseJob` (`parse_cache.py`) is shared by the migration, the manifest and the worker, so all three compute the same fingerprint.

**Fingerprint**: it now hashes all of `app/methodo/parsing/*.py`, docling-parse and the torch base version (`2.14.1`, pinned). The torch build/device (`+cpu`, `+cu128`) is stored per entry as `parse_env` but not hashed, otherwise the laptop could never hit box-made entries. The dry run prints the entry count per `parse_env`, so a mix is visible.

**Coalition**: `coalition_agreement_pipeline` reads from the cache (key `coalition:accord_coalition_2023_2028`, not put in chunk metadata, so Chroma ids are unchanged). `ingest-coalition-agreement-command` takes the PDF path, defaulting to `data/downloads/accord_coalition_2023_2028.pdf` (it pointed at a nonexistent file).

**Why**: an OOM kill breaks `ProcessPoolExecutor` and hangs `multiprocessing.Pool`, so the supervisor owns the subprocesses. Each worker loads the models once.

---

## 2026-10 — ONH sources stored as paths relative to `data/downloads`

**Issues**: [#49](https://github.com/AmaurySalles/luxdem/issues/49) (decision), [#55](https://github.com/AmaurySalles/luxdem/issues/55) (implementation)

**Decision**: `OnhPublication.url` and the chunks' `source_url` hold e.g. `onh/Note-30.pdf`. `resolve_onh_source()` (`app/methodo/onh_paths.py`) resolves it against `DATA_DIR / "downloads"` at parse time; legacy `file://` values are still accepted. `ingest-onh-from-dir-command` refuses dirs outside `data/downloads`. `--onh-dir` is a fallback only. Existing rows are rewritten once with `relativize-onh-urls-command` (dry-run by default).

**Why**: same value works in Docker and natively, chunk IDs carry nothing machine-specific, and it survives moving files to shared storage. Rejected: `/app/...` (Docker-only), keeping `/Users/shmiggit/...` (`--onh-dir` forever), ONH website URLs (site blocks downloads).

---

## 2026-10 — Parse cache: split Docling parsing from embedding

**Issue**: [#46](https://github.com/AmaurySalles/luxdem/issues/46)

**Decision**: `cleanup-stale-chunks-command` dry run parses every ONH + dossier doc (including never-embedded ones) into `data/parse_cache/<md5(source_url)>.json`; `--commit` embeds from that cache only and never parses. Each entry holds a fingerprint (sha256 of `docling_parser.py` source, docling + docling-core versions, parse args, doc metadata); a mismatch means stale, so the dry run reparses and commit skips + reports it.

**Why**: parsing is slow but free on the laptop; embedding needs a rented GPU. Parsing inside the embed loop (as `dossier_pipeline` does) leaves the GPU idle. Hashing the parser source is coarse (a comment change invalidates everything) but can't miss a real change.

---

## 2026-10 — Mark struck-through text as `~~…~~` via a Docling backend hook

**Issues**: [#60](https://github.com/AmaurySalles/luxdem/issues/60) (finding), [#61](https://github.com/AmaurySalles/luxdem/issues/61) (prototype), [#62](https://github.com/AmaurySalles/luxdem/issues/62) (recall check), [#65](https://github.com/AmaurySalles/luxdem/issues/65) (implementation)

**Decision**: `app/methodo/parsing/strike_through.py` patches `ThreadedDoclingParsePageBackend.get_segmented_page` (installed by `_create_converter()`). Struck words become `~~…~~` in text-line and word cells, so chunks read `31 décembre ~~2032~~ 2036`. The summarizer and analyzer prompts say marked text is deleted wording.

**Rule**: a strike line is a horizontal subpath of the page's vector shapes, at most 1.5pt thick by both height and stroke width (yellow highlights are zero-height lines with a 12pt stroke), any colour. A word is struck when such a line sits in the 0.4–0.8 band of its height (underlines sit at ~1.1) and covers ≥60% of its width. A line only counts if the words in its band cover ≥70% of its length: without that, chart gridlines struck axis labels in 21 of 39 ONH docs.

**Why mark, not drop**: keeps what a bill changes. Dropping also let Docling's OCR text fill the gap with garbage, so struck cells are rewritten, never removed.

**Upgrade guard**: the hook uses private docling-parse internals, so `docling`, `docling-parse` and `docling-core` are pinned exactly, and `tests.unitary.test_strike_through` parses a 2-page fixture and fails if the marks go missing. A hook exception drops the page, which `DoclingPagesDroppedError` (#63) turns into a failed parse.

**Result**: on 8589/8449, marked words match an independent pdfplumber detector word for word, apart from tokenization (`1er`, dashes). 0 marked words across the 39 ONH PDFs and the coalition agreement.

---

## 2026-10 — Custom Ollama embedding client; new Chroma store per model

**Issues**: [#48](https://github.com/AmaurySalles/luxdem/issues/48) (decision), [#51](https://github.com/AmaurySalles/luxdem/issues/51) (implementation)

**Decision**: `get_ollama_embeddings` returns `OllamaEmbedEmbeddings` (`app/methodo/ollama_embeddings.py`), a LangChain `Embeddings` over `ollama.Client` calling `/api/embed` in batches of 64. It sets `truncate=False`, per-model `num_ctx`/`num_batch` (8192 bge-m3/arctic2, 2048 nomic), `keep_alive` (`ollama.embedding_keep_alive`), a 600 s timeout (dense table batches took ~170 s on the Mac, #32), retry with backoff on connection errors/5xx, and per-model prefixes (bge-m3 none; arctic2 `query: ` on queries; nomic `search_document: `/`search_query: `). It logs `prompt_eval_count`. Model stays `ollama.embedding_model`: `snowflake-arctic-embed2` since the comparison (#52).

**Why**: the `langchain_community` client sent one request per chunk to the deprecated `/api/embeddings`, added E5 prefixes nomic never saw, and had no timeout/retry. `langchain-ollama` 0.1.3 (the only version fitting the 0.2 pins) can't set `num_ctx`/`num_batch`. `/api/embed` truncates silently by default.

**Over-long chunks**: with `truncate=False` Ollama returns 400 "input length exceeds the context length". The client then embeds the batch one by one, splits the offending chunk in two on a paragraph/line/word boundary (recursively), and stores the token-weighted mean of the parts, re-normalized. One vector per chunk, so chunk IDs don't change, and no text is dropped. Each split is logged.

**Chroma**: the store comes from config `chroma.directory`/`chroma.collection` (default and all configs: `data/embeddings_v2`/`docs`, the arctic re-embed from #32; the pre-fix nomic store was deleted after the switch). New collections are created with `hnsw:space=cosine`, `hnsw:search_ef=100` (the default 10 missed an exact match among near-duplicate chunks in testing), `hnsw:construction_ef=200`, and the model, Ollama version and digest. A collection without `embedding_model` metadata predates #51 and keeps the old client, so old and new vectors never mix; opening a collection with another model raises. `add_documents` is sliced into 256-doc calls, since langchain-chroma 0.1.4 embeds the whole list then does one upsert.

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
