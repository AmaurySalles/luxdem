# GPU provider for the remote Ollama embed run

Issue: #45. Researched 2026-10-09. Prices are live snapshots; recheck in the console before renting.

## Recommendation

**Vast.ai, single RTX 3090 (or any 8 GB+ RTX card), Ollama template, SSH `-L` tunnel.**

- Has a ready Ollama template [V2] and documents SSH local port forwarding [V3], which is exactly our setup.
- Cheapest: verified on-demand RTX 3090 from $0.16/h (median $0.27/h) [V4].
- Billed per second [V1].
- Downside: it's a marketplace, so host quality varies. Pick a "verified" host with good reliability. For a ~1 h job this barely matters.

Fallback: **RunPod**, RTX A5000 or 3090 on Community Cloud ($0.16–0.22/h), PyTorch template plus the Ollama install script [R2]. It's billed per second and has fixed prices.

**Cost estimate (estimate):** 10k–50k chunks need 0.5–1.5 h wall time including setup, so **$0.10–$0.40 of GPU time**. Budget about $2 to cover retries and idle time.

## Comparison

| | Vast.ai | RunPod | Lambda |
|---|---|---|---|
| Ollama | Official "Open Webui (Ollama)" template, Ollama API on 11434 [V2] | No Ollama template. Official tutorial: PyTorch template, then `curl ollama.com/install.sh \| sh` [R2] | Nothing Ollama-specific; install the same way on an Ubuntu VM |
| SSH / port forward | Key-only SSH, documents `ssh -L` port forwarding [V3] | Proxied "basic SSH" has no SCP/SFTP. Full SSH needs a public-IP pod; official templates have sshd preconfigured [R3]. Whether `-L` works over the proxy isn't documented, so use full SSH | Full VM with root SSH |
| Cheapest suitable GPU | RTX 3090 $0.156/h, RTX A5000 $0.189/h, RTX 3060 $0.052/h (verified, on-demand, live API query) [V4] | RTX A5000 $0.16/h community / $0.27/h secure. RTX 3090 $0.22 / $0.50 [R1] | Quadro RTX 6000 $0.69/h, A10 $1.29/h, A6000 $1.09/h [L1] |
| Billing | Per second. Storage and bandwidth billed separately [V1] | Per second for compute and storage. No ingress/egress fees. Needs ≥1 h of credit to deploy [R4] | Per minute [L2] |

Lambda costs 3–8x more and is overkill for this job. Skip it.

## Throughput (estimate: no primary-source benchmark found)

- nomic-embed-text is 137M params, fp16, 274 MB, with a **2K context window in Ollama** [O1]. It fits on any GPU.
- Compute: about 2 × 137M × 512 tokens ≈ 0.14 TFLOP per full chunk. At a realistic 5–15 TFLOPS effective on a 3090 under llama.cpp, that's **about 35–100 chunks/s when batched**. Short chunks go faster.
- Non-primary data point: about 10 ms per single embed on an RX 7800 XT (forge.lthn.ai/core/go-rag benchmark). That's consistent with the range above.
- So 50k chunks take about 8–25 min of GPU time if batched. Setup (rent, install, `ollama pull`) adds about 10–15 min.

## Latency and batching: this matters

- The current code uses `langchain_community.embeddings.OllamaEmbeddings` (installed 0.2.19, deprecated). `embed_documents` loops **one sequential `POST /api/embeddings` per text**, with no batching and no concurrency (`_embed` → `[self._process_emb_response(p) for p in iter_]`, local site-packages `langchain_community/embeddings/ollama.py` L147–202).
- Over the tunnel, each chunk then costs RTT + GPU time. From Luxembourg to an EU host (about 20–40 ms RTT), 50k chunks spend about 20–35 min on latency alone. To a US host (about 100–150 ms), about 1.5–2 h, which would dominate. **These latency numbers are estimates.**
- Ollama's `POST /api/embed` accepts `input` as a list [O2]. `langchain_ollama.OllamaEmbeddings.embed_documents` sends all texts in one `client.embed(model, texts)` call. That's true in 0.1.3, which still targets `langchain-core ^0.2.36`, so it fits our pins [LO1]. `langchain_chroma` `add_documents` passes the whole document's chunks to `embed_documents` at once, so that's one round trip per document.
- `OLLAMA_NUM_PARALLEL` defaults to 1 [O3], so client-side concurrency alone wouldn't help much. Batching is the fix.

Do one of these:
1. Switch to `langchain-ollama` (0.1.x) before the run. This is the best fix.
2. Or rent a host in an EU region to keep RTT low.

Either way, run Docling parsing before renting, or make sure parsing isn't interleaved with embedding. Otherwise the GPU is billed while the laptop parses.

## Side findings (affect the re-embed, not the provider choice)

- **Truncation:** Ollama's nomic-embed-text has a 2K context [O1], and `/api/embed` truncates by default (`truncate: true`) [O2]. Merged table chunks of up to about 2,400 words (about 3k+ tokens) will be silently cut. Raise `num_ctx` (the model supports 8192 [N1]) or split those chunks.
- **Prefix mismatch:** `langchain_community` prepends `"passage: "` / `"query: "` (E5-style defaults). nomic expects `search_document: ` / `search_query: ` [N1]. `langchain_ollama` adds no prefix. Decide the prefixes before the bulk run, because changing them later means re-embedding everything.

## Sources

- [V1] Vast pricing: https://docs.vast.ai/documentation/instances/pricing
- [V2] Vast Ollama template: https://docs.vast.ai/ollama-webui
- [V3] Vast SSH / port forwarding: https://docs.vast.ai/documentation/instances/connect/ssh
- [V4] Vast offers API, queried 2026-10-09: `https://console.vast.ai/api/v0/bundles/` (verified, rentable, on-demand, 1 GPU)
- [R1] RunPod pricing: https://www.runpod.io/pricing
- [R2] RunPod Ollama tutorial: https://docs.runpod.io/tutorials/pods/run-ollama
- [R3] RunPod SSH: https://docs.runpod.io/pods/configuration/use-ssh
- [R4] RunPod pod billing: https://docs.runpod.io/pods/pricing
- [L1] Lambda pricing: https://lambda.ai/pricing
- [L2] Lambda billing: https://docs.lambda.ai/public-cloud/billing/
- [O1] Ollama model page: https://ollama.com/library/nomic-embed-text
- [O2] Ollama API, `/api/embed`: https://github.com/ollama/ollama/blob/main/docs/api.md
- [O3] Ollama FAQ, `OLLAMA_NUM_PARALLEL`: https://github.com/ollama/ollama/blob/main/docs/faq.mdx
- [LO1] langchain-ollama 0.1.3 embeddings.py and pyproject: https://github.com/langchain-ai/langchain/tree/langchain-ollama%3D%3D0.1.3/libs/partners/ollama
- [N1] nomic-embed-text-v1.5 model card: https://huggingface.co/nomic-ai/nomic-embed-text-v1.5
