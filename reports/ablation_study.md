# Claim support and abstention ablation

The paired run uses 13 provisional development and validation cases from
four owned PDFs. Both arms load the same artifacts and build the same BM25
index with top K=5. Both use a single fixed saved draft per question, the
same context budget, and the same citation validity checks. A saved draft
has no prompt, sampling parameters, or generation latency from an LLM.
The treatment turns on table rules, the pinned local ONNX NLI verifier,
and the locked `grounding-v1` policy. The runner asserts identical rankings
for each pair. It excludes the frozen chart family and changes no threshold
based on this comparison.

| Metric | Support checks off | Support checks on |
| --- | ---: | ---: |
| Answer coverage | 12/13 (92.3%) | 6/13 (46.2%) |
| Correct answers, all queries | 7/13 | 6/13 |
| Selective accuracy | 7/12 (58.3%) | 6/6 (100%) |
| False answers on unanswerable questions | 3/4 | 0/4 |
| False abstentions on answerable questions | 0/9 | 3/9 |
| Supported citations among emitted answers | 6/12 | 6/6 |
| Correct page among emitted citations with gold pages | 9/9 | 6/6 |
| Exact gold region among emitted citations with gold regions | 8/9 | 6/6 |
| Query pipeline p50 | 11.8 ms | 61.9 ms |
| Query pipeline p95 | 14.1 ms | 3,591.9 ms |

Support was assessed against each saved citation's actual content. Page
grounding uses the authored gold page. Exact region grounding requires
the gold canonical evidence ID and a region anchor. These denominators
condition on emission. The treatment did not increase the absolute count
of supporting citations. Its six withheld baseline answers include three
unanswerable questions, two answerable questions with incorrect drafts, and
one correct draft with an irrelevant same-page citation. See
[the individual cases](error_analysis.md).

Latency includes artifact reads, index build, retrieval, saved generation,
and checks. It excludes HTTP transport, ingestion, and real answer model
inference. This single Windows run times each arm once per case, baseline
first. The checked arm includes the cold ONNX model load on the first
query. With 13 observations, nearest-rank p95 is the maximum. The latency
figures describe this run and do not establish a steady-state capacity.

The [paired run](runs/grounding-comparison-v1.json) includes a shared manifest,
input and code hashes, paired rankings and outputs, per-query latency, and
category summaries. The [semantic audit](runs/grounding-semantic-audit-v1.json)
records 11/11 agreement with determinate provisional labels and one uncertain
label. Its audit and comparison labels await human review. The small owned
corpus and fixed drafts support a controlled diagnostic, with general
accuracy and real-world threshold calibration still unverified.

## Reproduce

Populate the local cache per [the semantic verifier guide](../docs/semantic_support.md).

```powershell
uv run python -m evidence_rag.eval.claim_comparison --cache-dir tmp/hf-model-cache --output reports/generated/grounding-comparison-v1.json
uv run python -m evidence_rag.eval.semantic_audit --cache-dir tmp/hf-model-cache --output reports/generated/grounding-semantic-audit-v1.json
uv run python -m evidence_rag.eval.policy_validation --output reports/generated/grounding-policy-validation-v1.json
uv run python -m evidence_rag.eval.claim_comparison --smoke --output reports/generated/claim-comparison-ci.json
```

The final command uses three deterministic fixtures and requires no network
or large model. Its scripted verifier deliberately includes a false positive.
