# Source arithmetic delivery record

Date: 2026-11-23. This feature checks source quantities and arithmetic without
changing narrative support policy, model thresholds or frozen-test results.

The owned library-loans development PDF contains a Resident table cell of
21 days on page 1 and a renewal addition of 14 days on page 2. The calculator
returns exactly 35 days with resolvable source anchors. An expected value of
34 is flagged false while the actual result remains 35. The deterministic
[raw smoke](runs/source-calculation-v1.json) records exact source hashes and both
controls. Its provider call count is zero; no inference is performed by that smoke.

Tests cover exact decimal arithmetic, the four operators, zero division,
unit mismatches, duplicate/ambiguous table rows, missing or foreign-version
evidence, truncated sources, unavailable preview assets, unsupported number
formats and invalid payloads. Negated source context is retained and explicitly
does not receive semantic approval. A public SDK regression verifies that a
successful arithmetic receipt cannot bypass a missing-verifier abstention.

## Skill usability trial

An isolated agent received the updated companion skill and the permitted
development PDF, without tests, labels, reports or expected results. In five
SDK operations it ingested, searched, computed the source-backed sum, and
checked its own draft with the existing local verifier. The calculation returned
35 days. The verifier accepted that particular combined-premise draft, while
each individual passage was labeled insufficient for the full claim. The two
citations jointly supply the inputs; neither passage alone states the whole sum.

[Raw trial, calls, source contexts, model outcomes and code/skill hashes](source-calculation-forward-trial.json)

The trial snapshot precedes an additional rejection guard for clock-style
number formatting. Recorded source hashes preserve that distinction; current
regression tests and the deterministic smoke exercise the release source.
This is one usability trial, not an accuracy comparison or evidence that the
semantic false-abstention issue is resolved. Existing withheld outputs are
preserved; no retry was used to tune wording or model thresholds.

## Support boundary

`arithmetic_verified` checks extraction plus arithmetic. `claim_support` remains
`not_assessed`. The result does not establish eligibility, causal relationships,
which values belong in an answer, or whether contrary evidence exists elsewhere.
Existing `check_draft` behavior is unchanged. Unit conversion and unsupported
numeric formats are rejected rather than guessed. [API and limits](../docs/source_calculations.md)
