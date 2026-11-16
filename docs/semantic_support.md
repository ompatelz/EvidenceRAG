# Semantic support assessment

The optional verifier treats the cited text as the premise and the claim as
the hypothesis. A local DeBERTa cross-encoder trained on SNLI and MultiNLI
scores contradiction, entailment, and neutral. It is separate from the answer
generator and uses no judge prompt. The pinned label order, model limits, and
weights are in the
[model configuration](https://huggingface.co/cross-encoder/nli-deberta-v3-small/blob/98f45e15fc3e6c918f51a7e858cda1139cbc9e59/config.json)
and [model card](https://huggingface.co/cross-encoder/nli-deberta-v3-small).

The `cited-premise-first-v1` input uses each distinct cited passage in order.
Multiple citations also get a joint premise separated by blank lines. A
contradiction wins over an entailment. When both occur, the assessment records
the conflict. Exact top-score ties become insufficient. The reported margin is
the leading logit minus its nearest competitor. It is a model score.
The verifier declines truncated context and oversize pairs rather than dropping
lines. Missing weights or dependencies, timeouts, and malformed outputs are
recorded using fixed statuses. No passage, claim, or exception message is logged.
The application allows five seconds for a complete draft assessment, including
the first local model load. A still-running verifier keeps its worker slot
after a timeout, so subsequent requests cannot queue additional work behind it.

This model was trained on sentence pairs. Combining PDF passages can change
how it handles qualifiers, arithmetic, mutually exclusive numbers, units,
or omitted context. The deterministic table rule remains the first check.
The verifier consumes text only.

## Reproduce the pilot

Install the existing optional local dependencies and explicitly populate the
cache. The ONNX weights are a roughly 568 MB one-time download.

```powershell
uv sync --all-extras --dev
uv run hf download cross-encoder/nli-deberta-v3-small --revision 98f45e15fc3e6c918f51a7e858cda1139cbc9e59 --cache-dir tmp/hf-model-cache --include tokenizer.json onnx/model.onnx
uv run python -m evidence_rag.eval.semantic_audit --cache-dir tmp/hf-model-cache --output reports/generated/semantic-audit.json
```

Set `EVIDENCERAG_SEMANTIC_VERIFIER=true` to attach the cached verifier to the
query API. Runtime and CI do not fetch weights. CI uses deterministic scorer
fixtures. The audit uses owned fixture passages and provisional judgments.
Its uncertain unit-conversion wording needs human adjudication. There are
no pixel-dependent cases in this audit because the application has no pixel
interpreter.
