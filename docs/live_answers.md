# Live cited answers

The application defaults to local retrieval. To enable OpenAI on a trusted
local instance, install the optional inference dependencies and prepare the
pinned offline verifier cache using [the verifier procedure](semantic_support.md).
Set `EVIDENCERAG_LIVE_ANSWER_PROVIDER=openai` and inject
`EVIDENCERAG_OPENAI_API_KEY` into the process environment from your secret
store. Start the host server as shown in the README. The configured server
continues to accept local queries and the existing opt-in Atlas demo.

In the inspector, check the OpenAI box on each question you want to send.
Programmatic clients add `"external_answer_consent": "openai"` to the
exact-version query body after the caller approves sending the question,
selected PDF text excerpts and citation identifiers to OpenAI. Omit the field
for local queries. A live query with a missing key, invalid draft, failed
independent check or unavailable service can abstain while providing the
retrieved evidence. Generated answers are labeled separately from the fixed
Atlas demo.

Live generation logs one redacted JSON event under `evidence_rag.openai`
at INFO level. Configure that logger in the host process to collect those
events. Its fields include requested and reported model IDs, prompt revision, latency,
attempt count, outcome, observed token usage and estimated cost when usage
is returned. The query result records the final local policy decision.
Read [the decision record](decisions/ADR-0011-openai-live-answers.md) for
pricing, data retention and failure behavior.

## Owned-fixture smoke

After authorizing the fixture and configuring the key and local verifier,
run the following from the repository root.

```powershell
uv run --locked --all-extras python scripts/live_answer_smoke.py --send-atlas-excerpts-to-openai --output reports/generated/live-atlas.jsonl
```

The command checks the offline verifier, announces the USD 0.01 estimated
ceiling and attempts one OpenAI request. It ingests the repository-owned
Atlas PDF locally and uses a question outside the evaluation dataset. The
output contains redacted generation and final policy records. Use a new
path for each deliberate run. CI exercises the same path with a fake transport.

## Evaluation status

The live smoke and live accuracy remain unverified. A smoke requires an
OpenAI API key, local verifier cache and express approval to transmit the
owned Atlas excerpts. Accuracy evaluation also requires owner-reviewed
development or validation labels and per-claim source review. The historical
frozen run stays closed.

Use the [source review guide](../datasets/eval/SOURCE_REVIEW_GUIDE.md) to
return decisions. Once reviewed labels are available, rerun the existing
BM25, dense, hybrid, reranking, claim and abstention runners on eligible
development and validation examples. Save the raw outcomes by category and
record the exact command/config, reviewed dataset and corpus hashes, Git SHA,
model and prompt revisions, and cost. For a live comparison, fix retrieval,
evidence budgets, prompt, model, and generation parameters and review each
generated claim and citation manually. Record the provider's returned model
ID and disclose if it identifies only a rolling alias.
