# Local evidence inspector

The inspector at `/inspector` joins the existing synchronous PDF ingestion,
version-scoped evidence, retrieval, answer, anchor, and page-preview APIs. It is a
small static HTML/CSS/JavaScript client served by the same FastAPI process. It
requires no browser build or external JavaScript service.

## Run the owned-fixture demonstration

```powershell
$env:EVIDENCERAG_DEMO_ANSWERS = 'true'
uv run uvicorn evidence_rag.api:create_app --factory
```

Open `http://127.0.0.1:8000/inspector`. Choose
`datasets/fixtures/atlas-narrative.pdf`, confirm permission, and ingest it.
Select **Use an Atlas example question** or enter:

> What is the calibration sampling rate of the Atlas sensor?

BM25 works without model weights. The opt-in fixture generator emits the one
documented 20 hertz answer only when the exact Atlas evidence unit is in the
retrieved pack. Click its source citation: the UI requests the scoped anchor,
loads the preview PNG, shows page 1, and draws a region only when the anchor
has verified region precision and display coordinates. Retrieval candidates
can also be opened. Ask an unrelated or diagram-content question to see an
explicit insufficient-evidence result.

The fixture generator is disabled by default. With the normal API settings,
retrieval still works but the answer status is `generator_unavailable`.
`/api/v1/capabilities` advertises whether the fixture demonstration is enabled.
The inspector hides its example-question button when it is disabled.

## Search modes and interpretation

- **BM25** searches the selected ready document version and is available in
  the base runtime image.
- **Dense** uses the pinned FastEmbed embedding model and an in-memory Qdrant
  index. **Hybrid** combines BM25 and dense ranks with the selected RRF
  configuration. **Hybrid + reranker** applies the pinned CPU cross-encoder to
  the bounded hybrid candidates. These modes require optional dependencies
  and cached model weights. The API uses local cache lookup only and returns
  `model_unavailable` when a required model is absent; the page does not
  initiate a download.
- Scores are displayed with their method names and ranks. BM25, cosine, RRF,
  and cross-encoder scores have different scales and must not be compared as
  if they shared one unit. Timings are per-request stages, including model
  loading and index construction where applicable; they are diagnostics, not
  warmed throughput or production latency measurements.

The UI keeps exact document ID and SHA-256 version scope for every query,
anchor, and preview. It uses text-only DOM insertion for document and answer
content. It shows a clear missing-page error, and a page-level label when no
region box is supported. A caption or figure row explicitly says that its
image content has not been interpreted.

## Verification and limits

`tests/test_inspector.py` covers static routes, owned-fixture ingestion and
answer navigation, all four search modes with deterministic model doubles,
missing models, stale/wrong document scope, page-only anchors, and a visual
question abstention. The local manual flow also used real cached models for
all modes:

| Mode | Answer | Retrieved | Request total |
| --- | --- | ---: | ---: |
| BM25 | cited fixture answer | 4 | 1.43 ms |
| Dense | cited fixture answer | 5 | 1338.50 ms |
| Hybrid RRF | cited fixture answer | 5 | 202.20 ms |
| Hybrid + reranker | cited fixture answer | 5 | 429.97 ms |

These are one cold-process, one-PDF manual observations with model/index setup
included, not a benchmark or a comparison to the saved validation runs. The
citation resolved to the owned Atlas evidence unit on page 1 and its real PNG
preview (46,423 bytes). An unrelated question produced
`unsupported_question`. The default container
contains no model files, so its inspector supports BM25 and explicit answer
abstention. No general generator, claim-support verifier, OCR, or visual
interpretation is included.
