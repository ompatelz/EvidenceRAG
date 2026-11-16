# Interview study guide

## 1. Follow one PDF from upload to source region

Read `documents/storage.py`, `documents/parser.py`, `evidence.py`,
`documents/rendering.py`, and `documents/orchestration.py` in that order.
Use `tests/test_lifecycle.py` to see interrupted ingestion and duplicate
handling. Content hashes identify exact bytes. An evidence region is in
normalized source coordinates. The renderer applies page rotation before
computing display pixels. A source-page hit can include several unrelated
passages. An evidence-unit hit needs the correct extracted block or table.
A region judgment also requires the correct box. Page-local tables retain
rows and cells, so arithmetic can cite one auditable table. Complex or
multi-page layouts may break that association.

## 2. Understand the four retrievers

Read `retrieval/bm25.py`, `dense.py`, `hybrid.py`, and `rerank.py` in that
directory. BM25 rewards rare exact tokens and saturates term frequency,
while correcting for passage length. It can win on an exact identifier.
Dense retrieval maps text and questions to vectors whose cosine similarity
can rank paraphrases. An embedding revision or dimension change requires a
matching index. Qdrant excludes stale points by version and generation.
Reciprocal rank fusion adds reciprocal discounted ranks across methods.
If a unit is rank 1 and rank 3 with constant 60, its score is
`1/61 + 1/63`. A cross-encoder sees the question and candidate together
and scores a bounded shortlist. This costs more CPU than comparing vectors.
The provisional pilot provides an example where fusion loses to both inputs.

## 3. Separate citations, support and decisions

Read `answers.py`, `grounding.py`, `semantic.py`, and `policy.py`.
A valid citation establishes identity, pack membership, and source location.
Entailment asks whether the evidence supports the actual claim. An
irrelevant sentence on the right page can pass a page check and fail support.
Exact arithmetic on cited cells can be verified by rules. The optional
prose verifier can be wrong and has an explicit insufficient or conflict
state. Its margin is a decision signal. Measure selective accuracy alongside
coverage and false abstentions when choosing a threshold on validation.
The checked arm withheld the correct result in
[one same-page citation failure](../reports/error_analysis.md).

## 4. Understand what the benchmark can prove

Read `evaluation_protocol.md`, `eval/validate.py` and `eval/metrics.py`,
then the [baseline report](../reports/baselines.md) and
[paired ablation](../reports/ablation_study.md). Fix corpus revisions,
queries, relevance granularity and K when comparing retrievers. Fix
rankings, evidence budget and drafts when comparing the verifier. Separate
document families across splits. Reusing a paraphrase of the same table
or tuning against final outcomes leaks information. Review candidate labels
against the page before treating them as gold. A chart crop shows location.
Pixel-dependent QA requires actual image analysis and its own region
judgments. See [the visual feasibility decision](decisions/ADR-0009-visual-evidence-feasibility.md).

## 5. Trace operational failures

Read `api.py`, `config.py`, the [reliability guide](reliability.md),
and `tests/test_inspector.py`. A failed render prevents ingestion from
publishing ready. Missing models return scoped errors while the BM25 path
remains available. The API uses embedded Qdrant for optional dense queries.
The standalone remote service is exercised in an integration test.
A timed-out generator can outlive its request and retains its one slot.
Trace a withheld answer through its reason and request ID without exposing
the extracted document text in operational logs.

## Five interview questions

1. **Why might BM25 beat a dense model?** Rare identifiers can receive a
   strong exact-match signal. Vector similarity favors a different notion
   of relevance and may rank semantically similar passages higher.
2. **How can a correct page produce a bad citation?** A page can contain
   many claims. A valid anchor can point to a sentence that does not
   entail the answer. Inspect claim support and region precision separately.
3. **How did you isolate the effect of the verifier?** Reuse the same
   rankings, evidence budget, drafts and provenance checks in both arms.
   Change the support checks and policy, and report the coverage lost.
4. **What happens after a partial ingestion or model outage?** Storage
   retains the stage that failed. A retry regenerates from immutable bytes.
   Optional retrieval failures surface as scoped errors or policy abstentions.
5. **Which numbers would you defend publicly?** Describe the reported
   synthetic diagnostic and its denominators. General quality, held-out
   accuracy and steady-state latency still need evidence.
