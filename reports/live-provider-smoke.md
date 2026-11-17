# Signed-in Codex smoke

Observed on 2026-11-17 using Codex CLI 0.160.0 with ChatGPT sign-in, the
repository-owned Atlas PDF, BM25, and the pinned local DeBERTa verifier.
The [fixture manifest](../datasets/manifests/fixtures.json) records the exact
source bytes. The signed-in CLI selected its default model.

- The first request returned a draft for the Filter process question. The
  local verifier recorded contradictory support and withheld the answer.
  [Raw record](runs/codex-atlas-withheld.log)
- A direct calibration-rate question returned 20 hertz. The final response
  passed grounding, and the citation resolved to a source anchor and PNG.
  [Raw record](runs/codex-atlas-verified.log)

A separate development attempt returned an answer but failed a mistaken PNG
signature assertion. The successful run followed correction of that
assertion. These records cover individual fixture smoke outcomes. There was
no broader answer evaluation in these smoke runs.

A later one-request OpenRouter smoke returned 20 Hz, passed local support,
and resolved a page-one region and PNG. The app response identified
OpenRouter. The exact served model and actual invoice amount were unavailable.
[Redacted OpenRouter raw result](runs/openrouter-atlas-http.json)
