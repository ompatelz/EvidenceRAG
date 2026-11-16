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

## Reviewed benchmark workflow

The benchmark runner is an explicit local workflow. It stays outside CI.
After choosing reviewed development or validation IDs, authorize the selected
excerpts, inject the key from a secret store, and prepare the pinned offline
verifier. Set a total estimated ceiling. For example, an authorization for
a single Atlas query would use:

```powershell
uv run --locked --all-extras python scripts/reviewed_live_answers.py --query-id p2_atlas_rate --send-selected-excerpts-to-openai --max-estimated-usd 0.01 --output reports/generated/live-atlas-reviewed.jsonl
```

Each selected ID reserves the adapter's USD 0.01 estimate. The runner
requires exact committed CC0 fixture bytes and a current owner decision
before sending. It uses one attempt, exact-version BM25 K=5, the adapter's
fixed evidence limits and prompt, temperature zero, and local grounding-v1
checks. It writes request evidence, raw provider output, final answer or
abstention, citations, timing, usage, returned model ID and provenance.
Store the output under the ignored local reports directory.

Compare the raw provider draft and final decision on the same query and
evidence pack. Have the owner judge answer correctness and each claim-link
against the exact rendered page before scoring either arm. Report provider
failures separately from semantic abstention. A locally withheld draft can
be inspected for the counterfactual but did not reach the user. Live
results, usage, and human claim judgments are currently pending.
