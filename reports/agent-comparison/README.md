# Exploratory agent comparison

On 2026-11-22 three isolated agents answered the same four owner-reviewed
synthetic development questions. They received no gold labels or other-arm
responses. A fourth agent inspected the emitted answers against the two source
PDFs with the arm names blinded. Its judgments are **agent source audits, not
human verification**.

| Measure | Direct PDF reading | EvidenceRAG tools | Tools plus skill |
| --- | ---: | ---: | ---: |
| Correct final answers / answerable questions | 3/3 | 3/3 | 2/3 |
| False abstentions / answerable questions | 0/3 | 0/3 | 1/3 |
| False answers / unanswerable questions | 0/1 | 0/1 | 0/1 |
| Supported emitted answers | 3/3 | 3/3 | 2/2 |
| Correctly paged emitted answers | 3/3 | 3/3 | 2/2 |
| Document/search/check operations | 2 | 10 | 11 |

The direct-reading arm extracted the named PDF text with PyMuPDF. The two tool
arms used the same BM25/grounding-v1 configuration and pinned local verifier.
Agents wrote their own drafts. The skill arm's renewal-period synthesis was
withheld despite valid source citations. The tool-only wording passed. This is
a real remaining sensitivity in the support model; the policy was not weakened
to force acceptance. All arms declined to invent an absent sensor mass.

This trial shows usability and limitations. It does not establish an improvement:
there was one trial per arm, only four synthetic questions, incomplete exposure
of model revision/sampling, and source changes underway without loaded-source
hashes. Execution-time scopes differ, so latency is not compared. Token usage and
provider charges were not observed; null is not reported as zero cost. No
separate provider API request was made by the tools.

## Evidence

- questions.json contains only the task packet, without gold labels.
- baseline.json, tools_only.json and tools_and_skill.json preserve responses and
  operation traces. Local absolute workspace paths are redacted where present.
- source-judgments.json records independent agent source judgments. Blind-arm
  mapping: A = tools plus skill; B = direct reading; C = tools only.
- summary.json contains computed counts, exact input hashes and limitations.

Regenerate/check counts from raw outcomes and explicit judgments:

```sh
python scripts/summarize_agent_trial.py --output reports/agent-comparison/summary.json --check
```

The script rejects missing/duplicate arm judgments, inconsistent emitted states,
and query IDs outside the existing development/validation cohort. A stronger
future comparison should follow docs/agent_evaluation.md with frozen code,
exposed model settings, repeated trials and human claim judgments. None of the
historical or reserved final-test cases was selected or rerun here.
