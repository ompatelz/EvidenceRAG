# Owner-reviewed held-out evaluation

The owner confirmed all six source labels before inference. One sequential
run on 2026-11-17 evaluated the two new owned CC0 document families at
`cf3aa9c3032b22eb2b7dec5a732d12ba329efcf3`. The runner requested
`gpt-6.1-sol` through the signed-in Codex CLI, with BM25 and the pinned
local DeBERTa verifier under grounding-v1.

[Freeze record](runs/reserved-final-freeze.json) ·
[Raw outcomes and rankings](runs/reserved-final-run.json) ·
[Owner-reviewed labels and source PDFs](../datasets/eval/RESERVED_FINAL_TEST.md)

| Measure | Result |
| --- | ---: |
| BM25 evidence-unit Hit@5, answerable questions | 4/4 |
| BM25 evidence-unit Recall@5 | 1.000 macro; 5/5 gold units found |
| Correct final answers over answerable questions | 2/4 |
| Answerable coverage | 2/4 |
| False answers over unanswerable questions | 0/2 |
| Supporting emitted claim–citation links | 2/2 |
| Exact region matches among emitted links | 2/2 |
| HTTP or run failures | 0/6 |

## Source check

| Query | Final outcome | Audit |
| --- | --- | --- |
| `holdout_reef_class` | Answered | Class R7 and its shoreline-only rule match the cited permit region on page 1. |
| `holdout_reef_deadline` | Withheld for conflicting evidence | The draft gave 72 hours. The permit links water sampling to Class D4 on page 1 and gives D4 holders the deadline on page 2. The verifier marked the deadline region contradictory. |
| `holdout_reef_fee` | Withheld for insufficient support | Neither permit page specifies a fee. |
| `holdout_kiln_warmup` | Withheld for insufficient support | The draft matched the 180 °C threshold. The card says the conveyor stays stopped until that point. The verifier rejected the draft's positive phrasing. |
| `holdout_kiln_alarm` | Answered | The cited shift-card region says to isolate the feed and call the shift technician when the alarm sounds. |
| `holdout_kiln_reset` | Withheld for insufficient support | The shift card supplies no reset delay. |

I checked the emitted claims and the withheld case diagnoses against the PDF
source text and canonical evidence IDs. These are agent source checks. The
owner's review applies to the benchmark labels. Sample size and the synthetic
documents limit generalization. There were no visual-dependent questions.

The frozen record retained a legacy `models_prompts_thresholds` description
from the historical retrieval-only runner. The explicit `support_model`,
`support_revision` and `policy` fields and raw per-claim assessments capture
the actual live settings. The original freeze and raw results are preserved
as written. This result remains closed to tuning.
