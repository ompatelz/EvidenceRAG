# Demo in under three minutes

Run the [inspector quickstart](inspector.md) and enable the fixed Atlas fixture
answer. For the optional live comparison, cache the pinned dense model first
using the [dense setup](dense_baseline.md). Keep the same document version and
question when changing the mode.

| Time | Action and narration |
| --- | --- |
| 0:00–0:25 | Ingest the owned Atlas narrative PDF. Point to the ready state and the immutable version. |
| 0:25–1:10 | Select the Atlas example and run BM25. Open the 20 hertz answer citation. Show the page-one highlight over the calibration sentence. Explain that the adapter answers one known fixture question and requires its canonical evidence ID. |
| 1:10–1:35 | Ask “What is the calibration sampling rate on Neptune?” Show the insufficient-evidence outcome. |
| 1:35–2:05 | Restore the Atlas question and change BM25 to Hybrid. Compare top evidence IDs and stages on the same input. If weights have not been cached, use the saved validation comparison rather than downloading during the demo. |
| 2:05–2:40 | Show the paired support experiment. The checked arm emitted six of 13 fixed drafts and had zero false answers on four unanswerable cases. The baseline emitted 12 of 13 and had three false answers on those four cases. Point out the fall from seven to six correct answers and the provisional labels. |

The saved E2 comparison scores canonical evidence-unit ranks on one shared
validation split: BM25 0.797, dense 0.814, and hybrid 0.781 nDCG@5. This is a
case where fusion underperforms both individual runs on that metric.
[Raw E2 output](../reports/runs/e2-hybrid-validation.json).
The paired support comparison fixes both retrieval and drafts.
[Raw paired output](../reports/runs/grounding-comparison-v1.json).

Rehearse the upload, answer, unsupported query and citation routes using
`uv run --locked python scripts/measure_local.py --output reports/generated/demo-smoke.json`
after creating `reports/generated`. The [saved smoke](../reports/runs/local-release-smoke.json)
contains the inspected citation ID, query outputs, and preview size.
