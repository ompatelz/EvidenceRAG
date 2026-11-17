# Reserved final-test source review

These are two new repository-authored CC0 PDF families. They are separate
from the reviewed development/validation corpus and historical chart test.
The six candidate labels were prepared from the source pages and parser
anchors. No retrieval or answer predictions have been generated for them.

| Family | Review against the source |
| --- | --- |
| [Orchid Reef permit](../fixtures/orchid-reef-permit.pdf) | Check the shoreline-only class on page 1 and the sampling class plus receipt deadline on pages 1–2. Check both pages for the missing application fee. |
| [Meridian kiln card](../fixtures/meridian-kiln-shift-card.pdf) | Check the conveyor threshold and required alarm response on page 1. Check the page for a reset delay. |

For each query ID in [the candidate labels](reserved_final_test.jsonl),
confirm or correct answerability, acceptable answers and the completeness of
the source regions. Return the query ID and corrected wording or evidence for
any change. All six rows are pending owner confirmation.

## Declaration

- [Document manifest](../manifests/reserved-final-test.json), LF-normalized
  SHA-256 `d652e461a3af8160a8ec0bacf21614fc60dfab1168fdb3a0e08849664396fb82`.
  The manifest records each PDF's exact byte hash.
- [Candidate labels](reserved_final_test.jsonl), LF-normalized SHA-256
  `19830ad3ffd4de635bfb80a3b0aa50ad494d1582c86026a4b50b4f8613f4bab6`.
- Freeze the owner-approved labels, source commit and lock, model, prompt,
  BM25 K=5, evidence budget and grounding policy before inference. Use
  canonical evidence-unit Hit@5 and Recall@5 for eligible answerable rows.
  Judge emitted answers against the declared gold and source pages. Report
  citation support per claim–citation link, correct answers and coverage over
  answerable items, and false answers over unanswerable items. Preserve
  failed calls separately with the original per-query records.
- Run once after the freeze and keep these families out of implementation
  tuning. The initial candidate hashes support review and input validation.
  The owner-confirmed hashes will define the actual evaluation freeze.
