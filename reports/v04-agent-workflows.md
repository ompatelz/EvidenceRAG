# v0.4.0 delivery and usability record

Date: 2026-11-23. This release expands source workflows without changing
grounding-v1 thresholds, rewriting historical frozen outcomes, or claiming an
answer-quality improvement.

The package/CLI/MCP interfaces expose connected context, per-claim explanations,
explicit collection scopes and separate draft checks, a setup doctor, exact
recipes and visual page handoff. Local OCR is opt-in and requires language data.
The companion workflow shares one bounded recovery budget across claims and
sources. [Complete behavior and limits](../docs/agent_improvements.md)

An isolated agent received the revised workflow and two authorized owned
development PDFs, without tests, gold labels, historical reports or other trial
artifacts. It searched the collection, found both source counts and the retry
timeout, used explicit count normalization and returned an 80% arithmetic receipt.
Both narrative drafts remained withheld because the local verifier files were
absent. The agent ran doctor and reported that limit; it did not download models,
call a provider or repeatedly paraphrase for acceptance. The source timeout was
250 ms per attempt. [Raw result and fingerprints](v04-agent-workflow-trial.json)

An earlier development trial exposed that literal `hits` and `misses` could not
be added. The final interface permits explicit normalization to `count`, preserves
the original source labels, and rejects conversion between category labels.
This is arithmetic normalization, not proof that populations or intervals match.
Regression tests cover the conversion and forbidden relabeling. The final fresh
agent received only the task and source/workflow artifacts, without that diagnosis.

The trial is a single usability observation, not a comparison against another
agent or a human review. Snapshot raw hashes are retained, including Windows line
endings. The release CI tests the final code and packages its exact commit.

Local validation passed 77 Python tests, strict mypy on 95 source files, Ruff,
registered MCP functions, three inspector tests and wheel/source-content checks.
Real OCR, HTTP/MCP protocol, container and external natural-PDF evaluation are
verified in hosted CI; use the release commit's Actions results for final status.

The natural-PDF probes use the official NIST AI RMF 1.0 publication and preserve
its downloaded fingerprint. Page relevance judgments were audited by an agent
and await human review. The separate matched-three-arm evaluation record format
supports repeated comparisons and explicit human judgments; no such new
human-reviewed answer comparison has been completed in this delivery.
