# E1: dense search baseline

## Model and index contract

E1 uses FastEmbed `0.9.1` with ONNX Runtime on CPU, encoding documents with
`TextEmbedding.embed` and questions with `TextEmbedding.query_embed`. The model is
`sentence-transformers/all-MiniLM-L6-v2`, served by FastEmbed from the ONNX repository
`Qdrant/all-MiniLM-L6-v2-onnx` at revision
`d13954661f83248295ba75c1ed411eef3b7b936e`. The license is Apache-2.0 and
the vector dimension is 384. The explicit model download is pinned to that revision;
ordinary CI uses a two-dimensional deterministic test double and makes no model request.
Documents are encoded in batches of 32; the local run used two CPU threads. Both query
and document vectors are checked for finite values and L2-normalized before indexing
or search. Qdrant uses cosine distance in a 384-dimensional collection for the real
run. The saved run records model, library, parser, index, corpus, and dataset versions.

Qdrant payloads retain canonical evidence ID, document/version, page, anchor precision
and box, model revision, and index generation. The query filter restricts exact
document/version and active generation inside Qdrant. Returned payload model and
generation are rechecked before exposure. An incompatible collection dimension,
distance, or model revision fails. A rebuild encodes all units before mutation,
upserts a complete new generation, switches the active generation, then deletes older
points. Search filters out old generations even if cleanup fails. Duplicate upsert
replaces a stable point; exact-version deletion removes stale vectors. A new process
must rebuild before searching because the active generation lives in process memory.
Qdrant errors fail the request; they are never converted into an empty ranking.

## Reproduce the local real-model run

```bash
uv sync --all-extras --dev
uv run python -m evidence_rag.eval.bm25_run
uv run python -m evidence_rag.eval.dense_run --download-model
```

The first E1 run downloads a pinned public model into ignored `tmp/hf-model-cache`.
Later runs can omit `--download-model` and use those cached files. It runs Qdrant's
local-memory implementation; the dedicated CI job tests the index lifecycle against
the pinned Qdrant server image `qdrant/qdrant:v1.20.0-unprivileged`. Local Docker was
unavailable during development, so no local server-container result is claimed.
The real run output is `reports/runs/e1-phase2-pilot.json`.

E1 validates the E0 dataset hash, document versions, query IDs, relevance unit, and
K values before running. Both runs use the same persisted canonical `EvidenceUnit`
records and the same development and validation questions. No frozen-test query is
searched. Both score binary evidence-unit relevance at K=1, 3, and 5. The two
unanswerable questions retain raw rankings but have no relevance denominator. Query
embedding and vector search times are saved separately. Build preparation and
embedding/index time are recorded separately from those query timings. Single-process
cold timing is exploratory, not a portfolio latency measurement.

## Provisional controlled comparison

Both runs have 8 queries, 6 scored answerable nonvisual candidates, and 11 indexed
evidence units. In **both** development and validation, E0 and E1 each have
Hit Rate@1=2/3, Hit Rate@3=3/3, Recall@3=3/3, MRR@3=5/6, and nDCG@3≈0.877.
The relevant unit appears at the same rank for all six scored questions. Neither
method wins on this pilot. Both rank the Atlas flow caption and the best-F1 table
at rank 2. Both return plausible units on the unanswerable queries; neither
implements abstention. These are provisional diagnostics against labels that have
not been human reviewed. The corpus is synthetic and too small to support a
general retrieval-quality conclusion.

Official implementation references consulted on 2026-11-04:

- https://qdrant.tech/documentation/quickstart/
- https://qdrant.tech/documentation/search/filtering/
- https://qdrant.tech/documentation/embeddings/fastembed/
- https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
- https://huggingface.co/Qdrant/all-MiniLM-L6-v2-onnx
