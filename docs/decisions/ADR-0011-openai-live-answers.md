# OpenAI Responses for opt-in grounded answers

## Context and decision

The answer service accepts a bounded evidence pack and independently checks
citations and support. Use OpenAI Responses REST v1 with `gpt-6-luna` and
strict JSON Schema. The model is OpenAI's documented replacement for the
retiring GPT-4.1 mini snapshot and supports reasoning effort `none`. OpenAI
lists the Luna model ID without a dated snapshot. The run record stores the
requested ID and model ID returned by the API. Reproducibility across alias
updates depends on the provider exposing a dated version. The adapter uses
Python 3.11+ standard-library HTTPS and has no provider SDK version or new
runtime package to pin. The
transport is a single TLS POST to `api.openai.com` with no redirect, retry,
tools, or conversation state.

The operator enables OpenAI and supplies its API key. The caller must also
approve the question, selected extracted text and scoped citation IDs for
that exact query. PDF files, previews and images stay local. The adapter
sends text as data in a separate message from instructions. A malicious
excerpt can still influence the generator. The service checks every citation
against the exact-version pack and local anchor before applying the existing
table rules and pinned local semantic support policy. A semantic model can
make mistakes and support scores remain provisional. Missing local support
assessment causes abstention for claims that the table rules cannot verify.

## Data handling

Requests set `store: false`. OpenAI documents that API data is excluded from
training and default abuse-monitoring retention can be up to 30 days. Project
data controls can vary. Send excerpts only when authorized for the material.
Locally the structured event contains allowlisted metadata and numeric usage,
never source text, questions, response bodies, exception strings, or keys.

## Limits and trade-offs

The pack holds up to five excerpts, 1,200 characters each and 4,000 total.
Serialized requests have a 16,000-byte limit; the cost estimate uses one
token per serialized byte plus 1,024 tokens for framing. Generation allows
768 output tokens and a 32 KiB response envelope. Standard prices per
million tokens are USD 0.10 input, USD 0.125 cache writes and USD 0.50 output.
Charging every input token at the cache-write rate gives a maximum
estimated cost of USD 0.002512.
The adapter enforces an estimated ceiling of USD 0.01 and checks returned
token usage. The estimate depends on the pricing
assumption and the provider's actual accounting. An account-wide spend
limit is outside the application.

One live generation can run at a time per application process, with a
10-second response deadline and zero automatic retries. A timed-out or
disconnected request discards its answer. The worker retains the slot until
it exits. Disconnects cannot retract data already transmitted or guarantee
that OpenAI stops generation or billing. The separate local support
assessment has its existing five-second budget.

The base Compose candidate continues to run with local dependencies and
the opt-in Atlas fixture demo. Run the live provider from the host Python
environment with the optional local verifier dependencies and cached model.
Roll back by turning off the live provider setting.

Reviewed 2026-11-16 against the [model and price list](https://developers.openai.com/api/docs/models/gpt-6-luna),
[retirement schedule](https://developers.openai.com/api/docs/deprecations),
[Responses request reference](https://developers.openai.com/api/reference/resources/responses/methods/create),
[Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
and [API data controls](https://developers.openai.com/api/docs/guides/your-data).
