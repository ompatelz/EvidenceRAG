# Agent interface verification

Date: 2026-11-22. Runtime baseline: published main at
`c1cc0652463cfe166df6790905ec3a15a1b2fd1a`. This change packages existing
retrieval and grounding as Python, CLI, MCP and companion-skill interfaces.
It does not change the semantic scorer, preprocessing, grounding-v1 threshold,
benchmark labels or frozen test outputs.

## Local verifier audit

Command from the isolated source checkout, with its src directory on PYTHONPATH:

```sh
python -m evidence_rag.eval.semantic_audit --cache-dir ../tmp/hf-model-cache --output reports/generated/agent-semantic-audit.json
```

The existing audit includes six development and six validation cases. The
pinned local model assessed all 12 without unavailable/timeout outcomes. Its
support labels matched all 11 definite expected labels. The remaining
`cache_wording` validation row is expected uncertain; the model returned
supported. That is a pending source-review question, not a scored success.
All audit judgments remain marked needs_human_review. Do not describe this
as 100% verified accuracy or evidence of improved agent behavior.

[Raw audit, dataset hash, model revision and runtime](runs/agent-interface-semantic-audit.json)

These results support preserving the existing policy while adding interfaces.
They do not establish that the verifier has no false abstentions. No cases were
constructed from the held-out failures, and no held-out inference was repeated.

## Companion skill forward trial

An independent agent received the bundled skill, local CLI location and a task
asking for the Atlas calibration rate and retail price. It received no expected
answer or assessment diagnosis. It ingested the permitted owned Atlas PDF,
searched the combined question, made one targeted retail/price search and
fetched the calibration evidence anchor.

The rate was quoted from page 1 at evidence
`ev_db963e2e6b7064f643c914bace118433`, document version
`sha256:b6a8b1d7f3fda491b08adf9aeb1bc40d1b073804ab63045e3cf090ff1dff4aaa`.
The price search returned no_relevant_evidence. Draft checking returned a valid
citation and verifier_unavailable, because that trial did not enable a semantic
verifier. The final response disclosed the withheld support approval, quoted
the rate, and declined to establish a retail price. No provider was called.

This tests instruction usability and handling of unavailable verification on
one development fixture. It is not a comparative accuracy experiment.

## Integration and distribution

The SDK/CLI tests exercise a real owned PDF, duplicate ingestion, bounded packs,
canonical source anchors, visual-modality abstention, wrong-version citations,
foreign and duplicate IDs, unavailable verification, and an explicitly injected
test scorer. They also cover MCP ingestion scope and non-overwriting skill export.
The test scorer is a deterministic double and is not included in quality metrics.

The MCP tests discover registered schemas and exercise the real optional SDK's
client/server protocol in memory. Local registration/function checks can run in
this environment. Windows asyncio transport initialization blocks in the
sandbox's loopback socketpair creation before application code runs. The same
restriction blocks existing HTTP TestClient suites here. Hosted Linux CI is the
verification surface for the full protocol and unchanged HTTP regression suites.

The distribution check builds a wheel and source archive, verifies packaged
skill/UI/license resources and entry-point metadata, then exercises the extracted
wheel's module entry point and skill export outside the source checkout. It does
not publish to PyPI or install a personal ChatGPT skill.

## Remaining evidence

A matched baseline/tools-only/tools-plus-skill live agent comparison with
source-reviewed claims has not been completed. Follow the
[predeclared protocol](../docs/agent_evaluation.md). The new interfaces and this
trial do not justify a claim of improved correctness, fewer hallucinations or
better population accuracy. Verifier behavior changes require independent
reviewed development cases and a separate controlled comparison.
