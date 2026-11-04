# Embedding comparison after the chunking fixes (#52)

Scores for [Compare bge-m3, arctic-embed2 and nomic on French and German queries](https://github.com/AmaurySalles/luxdem/issues/52), on post-fix chunks and on pre-fix chunks. The pre-fix run is Pilot B's no-regression baseline ([Decide the pilot pass bar](https://github.com/AmaurySalles/luxdem/issues/72)).

## Setup

- **Sample:** the original 65 docs (5,019 chunks on Oct 12): all 35 ONH PDFs plus 30 dossiers. The dossiers are the 20 most recent housing-titled ones plus 10 picked by `md5(number)`. The list was recovered from the Oct 11 session transcript and is in `../docs.tsv`. Dossier PDFs: `data/_pilot_a/all/<n>.pdf`.
- **Post-fix chunker:** `origin/main` @ 42e58f6 plus PRs #74, #75, #76 and #79, merged locally on `scratch/embed-compare-postfix`. One trivial conflict in `docling_parser.py`: both blocks were kept.
- **Pre-fix chunker:** `origin/main` @ 42e58f6. PR #82 merged later but doesn't touch the chunker.
- **Parse:** `luxdem:latest` image (docling 2.142.1, docling-parse 7.23.0, docling-core 2.104.0), one process per doc (`parse_one.py`, `drive.sh`).
  - Pre-fix shortcut: 47 of the 65 docs have no `~~` mark after the post-fix conversion. For those, the pre-fix run reuses the saved post-fix DoclingDocument and only reruns the pre-fix chunking code. The other 18 were converted again with the pre-fix code.
- **Embedding:** the repo's `OllamaEmbedEmbeddings` (#51), loaded by path. Production prefixes: arctic `query: ` on queries only, nomic `search_document: ` / `search_query: `, bge-m3 none. Batch 32, `truncate=False`, num_ctx = num_batch = 8192 (nomic 2048).
- **Ollama:** native Ollama.app **0.40.13** (Metal), not the pinned `ollama/ollama:0.20.5`. The pinned container is CPU-only here and about 15x slower (bench: 185 vs 2,700 tokens/s).

  | Model | Digest used (0.40.13) | Pin (0.20.5 container) |
  |---|---|---|
  | bge-m3 | `790764642607…` | same |
  | snowflake-arctic-embed2 | `30685f516da4…` | `5de93a84837d…` (**differs**) |
  | nomic-embed-text | `0a109f422b47…` | same |

  Parity on 45 queries + 60 random post-fix chunks (`parity_*.json`), cosine between the two servers:
  - bge-m3: queries 1.0, chunks min 0.99958 / mean 0.99998.
  - arctic: queries 1.0, chunks min 0.98219 / mean 0.99606.
- **Gold set:** `eval/gold_set.json` @ 89f4adb, 56 queries: 40 FR, 5 old DE (q41–q45) and 11 new DE (q46–q56, passage-first, `target` = strike / table / long).

## Rules

- **Search:** per `doc_type`, top 10, as in production (`topic_analysis_pipeline._query_by_type`). A query hits if any of its gold passages is in the top 10 of the search for that passage's doc type.
- **Hit:** a chunk from the gold source that contains the quote, ignoring `~~` and **all** whitespace.
  - `match_rule` in the gold set says "collapse whitespace". Under that rule 23 quotes match no chunk in either run, because the current Docling stack spaces punctuation differently from the Oct 12 parse (`2024 .` vs `2024.`). Removing all whitespace leaves 7.
  - Those 7 differ in real text (page header in the quote, `JUULSER` artefact, `’` vs `'`, a link) and are listed in `results.json`. Each of those queries still has other gold passages that match.
- **MRR:** first gold-or-acceptable chunk, best rank across the query's doc-type searches, no cutoff.
  - Acceptable labels are pre-fix chunk IDs from Oct 12. They are carried across re-chunking by text: a chunk from the same source counts if its word 5-grams cover at least 50% of the acceptable chunk's text, or the reverse (`acceptable_prefix_texts.json`).
  - **q46–q56 have no acceptable labels, so their MRR is gold-only and stricter.** Their hit@10 is comparable with the other slices.
- **Cover infographics:** cover-infographic chunks (under `LE LOGEMENT en chiffres`) are dropped from both indexes. Pre-fix has 6; post-fix has 0.
- **Pre-fix quote check for q46–q56:** every quote matches a pre-fix chunk, so no query is excluded from pre-fix scoring.

## Scores (hit@10; n = 56 queries)

| Run | hit@10 | MRR | FR (40) | DE all (16) | DE q41–45 (5) | DE q46–56 (11) | dossier | ONH |
|---|---|---|---|---|---|---|---|---|
| post-fix bge-m3 | 0.946 | 0.870 | 1.000 | 0.812 | 1.000 | 0.727 | 0.893 | 1.000 |
| post-fix arctic-embed2 | **0.982** | **0.910** | 1.000 | **0.938** | 1.000 | **0.909** | **0.964** | 1.000 |
| post-fix nomic | 0.732 | 0.670 | 0.900 | 0.312 | 0.600 | 0.182 | 0.571 | 0.849 |
| pre-fix bge-m3 | 0.946 | 0.867 | 1.000 | 0.812 | 1.000 | 0.727 | 0.893 | 1.000 |
| pre-fix arctic-embed2 | 0.982 | 0.910 | 1.000 | 0.938 | 1.000 | 0.909 | 0.964 | 1.000 |
| pre-fix nomic | 0.732 | 0.670 | 0.900 | 0.312 | 0.600 | 0.182 | 0.607 | 0.849 |

The doc-type columns count queries with gold of that type: 28 dossier, 33 ONH.

| Run | MRR FR | MRR DE all | MRR DE q41–45 | MRR DE q46–56 (gold only) |
|---|---|---|---|---|
| post-fix bge-m3 | 0.969 | 0.624 | 0.900 | 0.498 |
| post-fix arctic-embed2 | 1.000 | 0.687 | 1.000 | 0.544 |
| post-fix nomic | 0.843 | 0.236 | 0.603 | 0.069 |
| pre-fix bge-m3 | 0.969 | 0.611 | 0.900 | 0.480 |
| pre-fix arctic-embed2 | 1.000 | 0.683 | 1.000 | 0.540 |
| pre-fix nomic | 0.843 | 0.236 | 0.603 | 0.070 |

## Pre-fix → post-fix flips (query hit@10, 56 compared)

| Model | hit→miss | miss→hit | miss in both |
|---|---|---|---|
| bge-m3 | none | none | q46, q47, q49 (gold at rank 12–14, all `strike`) |
| arctic-embed2 | none | none | q54 (gold at rank 99, `table`) |
| nomic | none | none | q04, q05, q14, q29, q43, q45, q46–q50, q52–q54, q56 |

## Pass bar (#72), on this sample

- **arctic-embed2:** passes. 0.982 overall, 0.938 DE, 0 flips.
- **bge-m3:** passes. 0.946 overall, 0.812 DE, 0 flips.
- **nomic:** fails. DE is 0.312.

## Chunk checks

- **Post-fix:** 5,034 chunks, 0 zero-chunk docs, 0 `DoclingPagesDroppedError`.
  - `~~` marks in 18 dossiers and 0 ONH docs.
  - Over-long split-and-pool: 0 chunks for bge-m3 and arctic, 38 for nomic (its context is 2,048 tokens).
- **Pre-fix:** 5,010 chunks.

## Caveats

- The gold set was pooled from these models' own top 10 on Oct 12, so hit@10 for q01–q45 is biased upward for all three models.
- Pre- and post-fix scores are almost the same, because the fixes change few of the passages that the queries hit.

## Files

| File | Contents |
|---|---|
| `results.json` | All metrics, unmatched quotes, per-doc conversion mode, server versions and digests |
| `rankings.json.gz` | Per query, run and search: top-20 IDs, scores and gold/acceptable flags, plus the top-10 passage texts |
| `scores_table.md` | Raw tables |
| `parity_*.json` | Pinned-vs-native vector parity |
| `../embed_compare.py`, `../parse_one.py`, `../drive.sh`, `../parity.py` | Scripts to reproduce |
