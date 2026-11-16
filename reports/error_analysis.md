# Claim support error analysis

The following judgments come from inspecting the exact passages and drafts
saved in the two run files. They are provisional. A human reviewer should
read the passage and draft before looking at the model verdict and record
agreement or a correction. The original benchmark labels also await owner
review.

| Case and source | Source check | Observed result |
| --- | --- | --- |
| `atlas_partial`, Atlas p. 1 | The source establishes 20 Hz during calibration and provides no normal-operation rate. | NLI returned insufficient for the claim that adds an operating rate of 100 Hz. |
| `checksum_reverse`, Checksum p. 1 | A mismatch produces a negative acknowledgment. Other possible causes are unspecified. | NLI returned insufficient for the reverse implication, with margin 0.92. |
| `cache_units`, Cache p. 1 | The passage explicitly says 64 MiB. The claim substitutes 64 KiB. | NLI returned contradiction with margin 2.16. |
| `cache_wording`, Cache p. 1 | 64 MiB is about 67.1 decimal MB. “Roughly 64 megabytes” depends on the allowed rounding and unit conventions. | NLI returned supported with margin 4.49. The label remains uncertain and is excluded from agreement. |
| `atlas-unsupported`, Atlas p. 1 | The saved JSON-storage draft cites a passage outside the generator's retrieval pack. | Both arms rejected the citation before semantic assessment. |
| `table-wrong`, Retrieval p. 1 | Dense Recall is 0.80. The saved draft copied Hybrid's 0.84 into the Dense claim. | The baseline emitted the wrong value. The table rule rejected it. The cited page and region still resolved. |
| `checksum-wrong`, Checksum p. 2 | The timeout is 250 ms per attempt. | The baseline emitted 500 ms. NLI returned contradiction and the policy withheld it. |
| `cache-valid-irrelevant`, Cache p. 1 | The draft correctly states 800 hits and 200 misses, and cites the separate cache-capacity region. | The baseline counted a correct answer with invalid semantic support. The page matched, the region differed, and the checked arm abstained. |

The NLI audit matched 11 of 11 determinate provisional labels. It had no
determinate disagreement in this small sample. The ambiguous unit case shows
why even a large margin needs a domain rubric. In the deterministic smoke
run, a deliberately incorrect support score makes the policy emit an
unsupported Atlas claim. That regression fixture records the limit of a
policy that depends on an imperfect verifier.

Raw assessment and comparison records are in
[the semantic audit](runs/grounding-semantic-audit-v1.json) and
[the paired run](runs/grounding-comparison-v1.json). The two review sets are
[semantic_audit.jsonl](../datasets/eval/semantic_audit.jsonl) and
[claim_comparison.jsonl](../datasets/eval/claim_comparison.jsonl).

## Human review to complete

For each audit row, confirm the expected label from the saved passages
and adjudicate `cache_wording` only if there is an agreed unit and tolerance
rubric. For each comparison row, confirm question answerability, draft
correctness, claim support, and the expected page and region against the
corresponding owned fixture. Preserve any unresolved label as uncertain.
Record the reviewer and corrections before interpreting the comparison as
human-verified. The frozen chart family is outside both runs.

## Frozen BM25 observations

The single authorized held-out run used the default generator-disabled
runtime. The two flagged chart questions abstained on modality. For the
unanswerable failure-count query, the retriever still returned five
units and ranked the experiment ID first. The page states how many
requests were processed and gives no failure count. This is an example
of lexical overlap returning context that cannot support an answer.
The generator-unavailable outcome offers no evidence of semantic
abstention accuracy. See [the frozen report](final_evaluation.md).

## Current retrieval snapshot

The Atlas path label is now owner verified. Its caption remains at rank 2
in both BM25 and dense, so the rank-1 miss persists with confirmed evidence.
The added library renewal case needs passages on both pages. A hit on any
one passage gives Hit@K credit, while Recall@K measures the fraction of
the three proposed evidence units retrieved. The garden map question is
owner-verified and excluded from text-ranking scores. Claim
support and false-abstention performance from live answers remain pending.
[Current retrieval comparison](reviewed-answer-benchmark/retrieval-ablation.md)
