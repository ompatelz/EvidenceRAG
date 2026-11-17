# Live cited answers

External generation is off by default. Use the app on loopback with one
trusted user. For any live provider install the optional inference dependencies
and prepare the pinned offline verifier cache using
[the verifier procedure](semantic_support.md).

## Use your ChatGPT plan through Codex

Install the official Codex CLI and run `codex login` with ChatGPT.
Confirm `codex login status` reports ChatGPT sign-in. EvidenceRAG invokes
the official CLI non-interactively with a temporary directory, read-only
permissions, no interactive approvals, and command, web and connector tools
disabled. The CLI manages its own sign-in. Usage follows your ChatGPT plan.
This route runs on the host under your local account.
[Codex plan and sign-in](https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan)

```powershell
$env:EVIDENCERAG_LIVE_ANSWER_PROVIDER = 'codex'
uv run --locked uvicorn evidence_rag.api:create_app --factory --no-access-log
```

On Windows, if PATH exposes only an npm `codex.cmd` launcher, set
`EVIDENCERAG_CODEX_EXECUTABLE` to the full path of the official native
`codex.exe` before starting EvidenceRAG. To locate it for an npm install,
run the following in PowerShell and use the appropriate result for your CPU.

```powershell
Get-ChildItem (Join-Path (Split-Path (Get-Command codex.cmd).Source) 'node_modules/@openai') -Filter codex.exe -Recurse | Select-Object -ExpandProperty FullName
```

Use Codex CLI 0.160.0 or a version
that supports the same flags. Open `http://127.0.0.1:8000/inspector`,
upload a permitted PDF, and explicitly consent to sending selected excerpts
for the question. [Verified Atlas smoke](../reports/live-provider-smoke.md)

## Use OpenRouter with your own key

Create a key with a spend limit in your OpenRouter account. Supply it to the
host process as `EVIDENCERAG_OPENROUTER_API_KEY` through your secret store.
Select a model with strict JSON-schema output and a compatible provider route.

```powershell
$env:EVIDENCERAG_LIVE_ANSWER_PROVIDER = 'openrouter'
$env:EVIDENCERAG_OPENROUTER_MODEL = 'google/gemini-2.5-flash-lite'
uv run --locked uvicorn evidence_rag.api:create_app --factory --no-access-log
```

The app uses a fixed OpenRouter endpoint, disables route fallback, and asks
for providers that support the requested parameters and do not collect the
data for training. Requests cap prompt and completion rates at USD 0.25 and
2 per million tokens respectively, with bounded payload and completion.
OpenRouter routing, availability, retention, and account charges follow
its and the selected model provider’s terms.
[Routing controls](https://openrouter.ai/docs/guides/routing/provider-selection) ·
[Structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs) ·
[Example model](https://openrouter.ai/google/gemini-2.5-flash-lite)

Each local server selects one live provider. The inspector names that
provider in its consent checkbox, resets consent after each submission,
and identifies the source of a published answer. API clients set
`external_answer_consent` to `codex`, `openrouter`, or `openai` to
match the configured provider. Omitting consent keeps the query local.

To rehearse with a single repository-owned fixture after configuring the
selected provider and the cached verifier, use one of these commands.

```powershell
uv run --locked --all-extras python scripts/live_answer_smoke.py --send-atlas-excerpts-via-codex --output reports/generated/codex-atlas.jsonl
uv run --locked --all-extras python scripts/live_answer_smoke.py --send-atlas-excerpts-to-openrouter --output reports/generated/openrouter-atlas.jsonl
```

## Use the OpenAI API
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

The Codex smoke passed on the owned Atlas PDF. The OpenRouter and separately
billed OpenAI API smokes still need provider keys and authorized spend.
Accuracy evaluation also requires per-claim source review on the
owner-reviewed development or validation cohort. The historical
frozen run stays closed.

The owner decisions and rerun of BM25, dense, hybrid and reranking are
recorded in the [reviewed run record](../reports/reviewed-answer-benchmark/README.md).
The next human review concerns generated claims and their cited source pages. Save the raw outcomes by category and
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
be inspected for the counterfactual but did not reach the user. Benchmark live results, usage, and human claim judgments are currently pending.
