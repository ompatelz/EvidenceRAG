# Abstention policy

Enable `EVIDENCERAG_ABSTENTION_POLICY=grounding-v1` to apply the policy to
cited answers. Enable `EVIDENCERAG_SEMANTIC_VERIFIER=true` with the
[pinned local verifier](semantic_support.md) to assess free-form claims.
A verified table rule can support an answer without the model. If the verifier
is unavailable, the policy withholds claims that need it. The policy is
opt-in while real-world calibration remains unverified.

The query API returns an explicit reason for empty retrieval, insufficient
support, contradictions, mixed support and contradiction, parsing failure,
index or artifact failure, and unavailable verification. An explicit
`requires_visual_evidence` request field produces `unsupported_modality`.
The runtime cannot infer visual dependence reliably from the question alone.
Unknown documents and ingestion that has yet to finish use the existing
HTTP errors. The result includes the active policy version.

Positive retrieval supplies candidate evidence. Its raw score has varying
meaning across retrieval methods, so the policy uses pack availability and
leaves raw scores out of the support decision. Each free-form claim needs a
supported assessment from the expected model, revision, and preprocessing
with a logit margin of at least 1.0. A detected contradiction or conflict
withholds the answer regardless of its margin. A margin measures score
separation, with no probability interpretation.

## Validation

The 16 validation cases are scripted signals for policy behavior. They do
not measure the NLI model's score distribution on PDFs. The sweep checks
four margins. Among those margins it minimizes emitted wrong answers,
then maximizes correct answers, then chooses the lower margin.

| Setting | Answered / 16 | False answers / 5 unanswerable | False abstentions / 11 answerable | Selective accuracy |
| --- | ---: | ---: | ---: | ---: |
| Always answer | 16 | 5 | 0 | 5/16 |
| Always abstain | 0 | 0 | 11 | Undefined |
| 0 or 0.5 | 6 | 1 | 6 | 5/6 |
| **1.0** | **4** | **0** | **7** | **4/4** |
| 2.0 | 2 | 0 | 9 | 2/2 |

At 1.0 the policy drops a wrong draft and a weak correct draft compared
with 0.5. Raising the margin to 2.0 then drops two correct drafts. The
selected setting covers 25% of these cases, with zero observed false
answers on five unanswerable examples. This is fixture-level calibration.
The denominator includes synthetic availability failures and a visual case.
The visual case was authored independently of the frozen test. The frozen
test was not scored or used to select a threshold.

Run `uv run python -m evidence_rag.eval.policy_validation --output
reports/generated/grounding-policy-validation-v1.json`. The saved
[validation run](../reports/runs/grounding-policy-validation-v1.json)
records the inputs, per-query decisions, category counts, and every setting.
