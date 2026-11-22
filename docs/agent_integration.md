# Use EvidenceRAG from an agent or application

EvidenceRAG has four interfaces over the same ingestion, retrieval and grounding
code: a Python SDK, JSON CLI, optional stdio MCP server, and bundled agent skill.
The web inspector remains available. The SDK and tools never invoke an answer
provider: the calling agent supplies its own draft.

## Install the package

From the repository root, with Python 3.12:

```sh
python -m pip install .
evidence-rag --version
```

For dense retrieval, hybrid fusion, reranking or the semantic verifier:

```sh
python -m pip install '.[dense]'
```

Build distributable wheel and source archives with `uv build`. Install a wheel
with `python -m pip install dist/evidence_rag-0.1.0-py3-none-any.whl`. The skill
resources, inspector assets and license notices are included. This is a source
and wheel installation workflow; no PyPI release has been published by this change.

Keep model downloads explicit. Follow [dense setup](dense_baseline.md),
[reranking](reranking.md), and [verifier setup](semantic_support.md) to prepare
pinned caches. Ordinary search and check calls only look in the local cache.

## Python SDK

```python
from evidence_rag.sdk import DocumentRef, EvidenceRAG, SearchRequest

rag = EvidenceRAG(artifact_root="artifacts")
ingested = rag.ingest("datasets/fixtures/atlas-narrative.pdf")
document = DocumentRef(
    document_id=ingested.document_id,
    document_sha256=ingested.document_sha256,
)
result = rag.search(SearchRequest(
    **document.model_dump(),
    question="What is the calibration sampling rate?",
    mode="bm25",
))
for item in result.pack.items:
    print(item.text, item.evidence_id, item.page_index + 1)
source = rag.evidence(document, result.pack.items[0].evidence_id)
print(source.anchor.precision)
```

Create a `DraftAnswer` using your own model, citing only selected evidence IDs.
Call `rag.check_draft(document, question, evidence_ids, draft)`. All material
claims need citations and the answer must exactly join their texts. The checker
uses the existing `GroundedAnswerService`, table rules and grounding-v1 policy.
It reconstructs up to five pack items, 1200 characters each, 4000 total.

Without a configured semantic verifier, a natural-language draft is withheld
with `verifier_unavailable` even if its citations resolve. Set
`EVIDENCERAG_SEMANTIC_VERIFIER=true` and `EVIDENCERAG_MODEL_CACHE_DIR` before
constructing the SDK, or inject a `SemanticVerifier`. Table-rule claims can be
assessed without that model. Do not interpret a valid source location as a
support judgment. Fetch is bounded to 4000 text characters and reports truncation.

Explicit settings can be supplied with `EvidenceRAG(settings=AppSettings(...))`.
Live-provider and demo-generator settings do not cause this SDK to generate
answers. Use one SDK instance per trusted local application process.

## JSON CLI

```sh
evidence-rag --artifact-root artifacts ingest datasets/fixtures/atlas-narrative.pdf
evidence-rag --artifact-root artifacts search --document-id ID --sha256 SHA --question "calibration sampling"
evidence-rag --artifact-root artifacts evidence --document-id ID --sha256 SHA --evidence-id EV
evidence-rag --artifact-root artifacts check --document-id ID --sha256 SHA --question "calibration sampling" --evidence-id EV --draft draft.json
```

Replace ID, SHA and EV with values from actual results. Repeat `--evidence-id`
in pack order for multiple units. `python -m evidence_rag` is equivalent to the
installed console command. Successful commands emit JSON to stdout; request
errors emit redacted JSON to stderr and exit nonzero. An ingestion response
contains a lifecycle state: continue only when it is ready. Use `retry` with
the same document arguments for an explicitly selected failed/interrupted intake.

## Optional MCP server

Install the transport requirements separately from the core lock:

```sh
python -m pip install . -r integrations/mcp/requirements.txt
evidence-rag --artifact-root /absolute/path/to/artifacts mcp --documents-root /absolute/path/to/permitted-pdfs
```

The adapter pins official MCP SDK 1.30.0. Its v1 FastMCP interface is supported
separately from the incompatible v2 SDK. The optional requirement pins the SDK,
not every transitive transport dependency. Core `uv.lock` is unchanged; ordinary
core installs do not add MCP. MCP protocol tests run in a separate CI job.

Use a stdio-capable MCP client's server configuration:

```json
{
  "mcpServers": {
    "evidencerag": {
      "command": "/absolute/path/to/venv/bin/evidence-rag",
      "args": [
        "--artifact-root", "/absolute/path/to/artifacts",
        "mcp", "--documents-root", "/absolute/path/to/permitted-pdfs"
      ]
    }
  }
}
```

On Windows use the absolute `venv/Scripts/evidence-rag.exe` path with JSON
backslashes escaped or forward slashes. Match your client's configuration schema;
the example uses the common mcpServers shape. No network MCP listener is started.

| Tool | Behavior |
| --- | --- |
| capabilities | Return available modes, evidence budgets and ingestion/verifier configuration |
| ingest_pdf | Ingest a selected PDF relative to the configured documents root |
| search_evidence | Retrieve a version-scoped evidence pack and method-specific rankings |
| fetch_evidence | Return a canonical unit, truncation information and source anchor |
| check_draft | Validate an agent-written structured answer; return an answer or abstention |

Omitting documents-root disables ingestion. Absolute paths, parent traversal,
and symlinks resolving outside that root are rejected. Tools do not scan the
filesystem, retrieve URLs, change provider settings or execute document instructions.
No user document is ingested automatically. Treat document content as untrusted.
Giving excerpts to a remote agent can still transmit them through that agent's
client even though the MCP server itself is local.

## Companion skill

The canonical distributable skill lives inside the package at
`src/evidence_rag/evidence-rag-agent/`. Export it to a new folder:

```sh
evidence-rag export-skill ./evidence-rag-agent
```

This writes SKILL.md, agents/openai.yaml and references/tools.md. It refuses to
overwrite an existing directory. Import/copy that complete folder using your
agent client's skill installation flow. Export alone does not install a personal
ChatGPT skill or configure an MCP connection. The instructions can use the MCP,
CLI or SDK interface and require an installed engine and authorized documents.

The skill instructs agents to preserve exact versions, ignore PDF prompt
injections, inspect qualifying context, use bounded additional searches, check
drafts and disclose withheld answers. It does not grant new source permissions
or promise improved accuracy. [Tool payload reference](../src/evidence_rag/evidence-rag-agent/references/tools.md)

## Verification and evaluation

Run the existing shared quality gate after a locked development setup. To test
the real optional MCP client/server protocol in memory:

```sh
uv pip install -r integrations/mcp/requirements.txt
uv run --no-sync pytest tests/test_mcp_server.py -q
```

Core tests can run without MCP and explicitly skip that module. Additional tests
cover SDK/CLI ingestion, version isolation, draft checking with and without a
verifier, bounded output, skill export and filesystem scope. Required tests make
no live provider calls. The protocol smoke is an integration check, not evidence
of better agent answer quality.

The [agent evaluation protocol](agent_evaluation.md) defines matched baseline,
tools-only and tools-plus-skill runs. Keep frozen test families closed to tuning.
