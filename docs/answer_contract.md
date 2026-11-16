# Structured answers, citations, and deterministic support

`POST /api/v1/query` accepts a question and one exact document ID and SHA-256
version. The local single-user API requires that version's ingestion manifest
be `ready`, rebuilds BM25 from its canonical evidence, and searches within the
requested version by default. The inspector also exposes dense, hybrid, and
optional reranked retrieval.

The evidence pack has at most five ranked units, 1,200 characters per unit,
and 4,000 characters total. The generator sees only the question and this
structured pack. Its response must be a bounded structured answer with
material claims and explicit evidence ID, document, version, and page for
each citation, or `insufficient_evidence`. Write one independently checkable
statement per claim. The `answer` field must match the ordered claim texts
joined with spaces, ignoring whitespace differences. The API builds its
displayed answer from those texts. A missing citation or extra prose makes
the entire answer ineligible. There is no external provider call.
`ScriptedGenerator` supplies saved deterministic responses in tests and
owned-fixture demos. An ordinary app without a configured generator returns
`generator_unavailable` rather than inventing an answer. Empty retrieval,
unsupported questions, malformed responses, generator errors, and timeouts
produce explicit insufficient-evidence reasons.

The validator checks every citation against IDs actually supplied in the
pack, the stored canonical unit, the requested document/version, the claimed
page, region geometry where applicable, and the preview file. One invalid
citation withholds the whole draft, including all of its source links.
Citation output uses stored provenance and never substitutes another source.

| Field | Meaning |
| --- | --- |
| `reason: missing_citation` | A claim lacks citations or the answer contains unmatched text. |
| `reason: invalid_citation` | A citation fails scope, pack membership, version, location, or asset checks. |
| `citation_status: valid` | The cited evidence passed those provenance checks. |
| `rule_support: rule_supported` | The cited structured values agree with the stated decimal lookup or calculation. |
| `rule_support: contradicted` | The cited cell value differs, the calculation is wrong, or cited values disagree. |
| `rule_support: insufficient` | An explicit table expression cannot be evaluated from the supplied evidence. |
| `rule_support: not_assessed` | The claim falls outside the table rule, including free-form prose and visual claims. |

Contradicted or insufficient table claims withhold the displayed answer.
The API retains the checked claims and their valid citations as diagnostics.
Free-form claims can still be displayed with `not_assessed` at this stage.
If the optional verifier runs, its estimate is in `semantic_support` on the
claim. Individual cited sources can also carry model estimates. The
[opt-in policy](abstention.md) uses those signals to withhold unsupported drafts.

## Worked table example

The owned retrieval table lists Hybrid Recall as 0.84 and Dense Recall as 0.80.
With the intact parsed table cited, the following claim is `rule_supported`:

```text
table_value("Hybrid", "Recall") - table_value("Dense", "Recall") = 0.04
```

Writing 0.4 yields `contradicted`. Asking for the Latency column yields
`insufficient`. The rule supports a single lookup or addition/subtraction of
two lookups. It matches normalized first-column row labels and named value
columns, requires unambiguous cells with plain decimal values, and computes
with exact rational arithmetic. Truncated cited tables cannot establish a
rule result. The rule checks the extracted cells supplied in context.
It cannot verify parser fidelity, determine whether prose has been decomposed
into atomic claims, or reason about plots, implicit units, or free-form wording.

The generator wait limit is 2 seconds. A timeout returns
`generation_timeout`; it does not forcibly stop an already-running thread.
The local single-user API has no tenant authorization or model-provider
integration. Questions and source text are not logged by this flow. PDF text
is untrusted data, including strings that resemble instructions. Tests use a
generated PDF with an instruction to cite a fabricated ID; the API abstains.

## One owned-fixture trace

For the provisional development question “What is the calibration sampling
rate of the Atlas sensor?”, BM25's saved E0 run ranks
`ev_db963e2e6b7064f643c914bace118433` first in document
`doc_cedee38ab4152274426cf3f8`, version
`sha256:b6a8b1d7f3fda491b08adf9aeb1bc40d1b073804ab63045e3cf090ff1dff4aaa`.
That unit points to zero-based page 0. The pack includes its bounded text
and ID. A deterministic response can state “The Atlas sensor's calibration
sampling rate is 20 hertz” and cite that ID. Validation confirms that the
ID was in the pack, matches the exact document/version and page, and resolves
to an existing page preview. The API returns the claim and source-page asset.
The 20-hertz answer and source label remain provisional pending owner review;
the validator alone does not establish semantic support.

## Live provider

The optional [OpenAI adapter](live_answers.md) consumes the same bounded
exact-version pack and draft schema. It requires per-query external consent
and applies the local support policy before returning a cited answer.
