# Reserved final-test source review

These are two new repository-authored CC0 PDF families. They are separate
from the reviewed development/validation corpus and historical chart test.
The owner confirmed all six labels before inference on 2026-11-17. The
[one-shot run](../../reports/reserved-final-evaluation.md) has since completed.

| Family | Review against the source |
| --- | --- |
| [Orchid Reef permit](../fixtures/orchid-reef-permit.pdf) | Check the shoreline-only class on page 1 and the sampling class plus receipt deadline on pages 1–2. Check both pages for the missing application fee. |
| [Meridian kiln card](../fixtures/meridian-kiln-shift-card.pdf) | Check the conveyor threshold and required alarm response on page 1. Check the page for a reset delay. |

The [owner-reviewed snapshot](reserved_final_test.jsonl) preserves the six
confirmed checks for answerability, acceptable answers and source anchors.

## Declaration

- [Document manifest](../manifests/reserved-final-test.json), LF-normalized
  SHA-256 `d652e461a3af8160a8ec0bacf21614fc60dfab1168fdb3a0e08849664396fb82`.
  The manifest records each PDF's exact byte hash.
- [Owner-approved labels](reserved_final_test.jsonl), LF-normalized SHA-256
  `9fa4d394513fbb29411ee6a76b5abfc49131a367075decb746db13d1eb3ccf4a`.
- Freeze the owner-approved labels, source commit and lock, model, prompt,
  BM25 K=5, evidence budget and grounding policy before inference. Use
  canonical evidence-unit Hit@5 and Recall@5 for eligible answerable rows.
  Judge emitted answers against the declared gold and source pages. Report
  citation support per claim–citation link, correct answers and coverage over
  answerable items, and false answers over unanswerable items. Preserve
  failed calls separately with the original per-query records.
- The run occurred once after the [freeze](../../reports/runs/reserved-final-freeze.json).
  Keep these families out of implementation tuning.
