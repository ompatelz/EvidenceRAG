# Structured answers and citation checks — checkpoint 3

`POST /api/v1/query` accepts a question and one exact document ID and SHA-256
version. The local single-user API requires that version's ingestion manifest
be `ready`, rebuilds BM25 from its canonical evidence, and searches within the
requested version. This is the smallest query path for the answer contract;
retriever selection remains for the evidence-inspector checkpoint.

The evidence pack has at most five ranked units, 1,200 characters per unit,
and 4,000 characters total. The generator sees only the question and this
structured pack. Its response must be a bounded structured answer with
material claims and explicit evidence ID, document, version, and page for
each citation, or `insufficient_evidence`. There is no external provider call.
`ScriptedGenerator` supplies saved deterministic responses in tests and
owned-fixture demos. An ordinary app without a configured generator returns
`generator_unavailable` rather than inventing an answer. Empty retrieval,
unsupported questions, malformed responses, generator errors, and timeouts
produce explicit insufficient-evidence reasons.

The validator checks every citation against IDs actually supplied in the
pack, the stored canonical unit, the requested document/version, the claimed
page, the page-preview manifest, and the preview file. An unavailable anchor
is not emitted as a usable citation. It rejects the whole draft if one
citation is invalid. Citation output is constructed from stored provenance,
not generator-provided paths or coordinates. This **does not prove that the
claim is semantically supported** by the cited text; claim support requires a
separate human or measured semantic check. Retrieval relevance, citation
validity, and claim support remain distinct outcomes.

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
