# ADR-0009 · Visual evidence feasibility

Status · No-go for feature implementation on the current evaluation seed, 2026-11-16.

## Reviewed snapshot update, 2026-11-17

The [owner-reviewed snapshot](../data_card.md) adds one visual-dependent
Juniper Garden development item. Validation still has zero visual-dependent
items. The two chart questions belong to the already opened historical test.
The no-go remains in force. One validation item can inform future fixture
design. Visual method comparison requires a broader independent cohort and development controls.

## Evidence available at the original decision

Grounded QA is on `main` at merge commit `c09683214190f34a8a66ce10c27e22ca8f51e34b`.
The manifest has five owned PDFs totaling 17,349 bytes. The seed has 13 development
and 13 validation questions, with zero visual-dependent questions in either split.
The two visual-dependent rows belong to the five-question frozen test. The label
inventory checked their modality and split. The study did not run or tune on those
questions, render the held-out family for feasibility, or change the seed. All 31
labels remain pending owner review.

The existing parser and retrievers index PDF text, including captions where available.
The API's default generator is absent, and the opt-in Atlas demo only handles one
fixed question. Existing saved runs measure retrieval on provisional nonvisual
labels. They cannot supply a general answer-quality baseline.

## Bounded preflight

Run `uv run pytest tests/test_visual_feasibility.py -q`. The test constructs two
owned 160 × 120 RGB previews in memory with identical caption and label text.
The bars swap heights. Both previews expose identical extracted text, and the
answer to which bar is taller flips from A to B. Known test-only pixel columns
contain 55 and 30 black pixels, then 30 and 55. This is a geometry sanity check
with fixture-specific coordinates. It measures neither model accuracy nor
localization. Each decoded RGB buffer is 57,600 bytes before library overhead.
No inference weights or GPU were needed for this probe.

The Windows host has an Intel Core i7-13700H (20 logical CPUs), 16,890,519,552
bytes physical RAM (15.73 GiB), and an RTX 4060 Laptop GPU reporting 397 MiB used
of 8,188 MiB (7,791 MiB free) at inspection time. These are host observations.
No candidate model was downloaded or timed, so model runtime, peak RAM/VRAM,
and changes in answer quality are unknown.

| Candidate | Inputs, resource evidence, and output granularity | Assessment |
| --- | --- | --- |
| Crop with caption and OCR | Tesseract 5.x accepts images. The Apache-2.0 `tessdata_fast` English pack at tag `4.1.0` is 3.92 MB, excluding the engine. Runtime memory was unmeasured. The parser's crop or OCR boxes can anchor recognized text. [Engine documentation](https://tesseract-ocr.github.io/tessdoc/) · [Pinned English weights](https://github.com/tesseract-ocr/tessdata_fast/blob/4.1.0/eng.traineddata) | Sensible CPU baseline for rasterized labels and table cells. The counterexample isolates a bar-height relation that cannot be recovered from its caption or recognized labels. |
| Targeted interpretation of retrieved crops or pages | Apache-2.0 SmolVLM-256M-Instruct at `d039ab0d4b9311b617e8ffec1d06c8464364aeb3` accepts images and text and emits text. The main weight file is 513 MB. The authors report under 1 GB GPU RAM for one-image inference. A result can cite its input page or a trusted parser crop. [Model card](https://huggingface.co/HuggingFaceTB/SmolVLM-256M-Instruct) · [Pinned files](https://huggingface.co/HuggingFaceTB/SmolVLM-256M-Instruct/tree/d039ab0d4b9311b617e8ffec1d06c8464364aeb3) | First candidate for a future pilot. The published one-image footprint fits the observed hardware on paper. Chart accuracy, diagram interpretation, and local runtime require measurement. |
| ColPali visual page retrieval | `vidore/colpali-v1.3-hf`, reference snapshot `e7af6dcfb05e7da70a052c5b14b8b80c9577013f`, uses page images and text queries under the Gemma license. Two weight shards total about 5.85 GB before activations, processor files, and multi-vector index storage. It returns ranked pages. [Pinned model and files](https://huggingface.co/vidore/colpali-v1.3-hf/tree/e7af6dcfb05e7da70a052c5b14b8b80c9577013f) | Defer. Page retrieval could help when text search misses the source. A high page rank supplies neither the chart answer nor a precise support box, and the unquantized weights leave limited GPU headroom. |

## Decision and experiment protocol

Stop the feature milestone at feasibility. The existing validation set cannot
estimate visual-answer gains at any resource cost. The synthetic test validates
the premise for an independent cohort. It is too narrow to serve as that cohort.

To reopen, add permissioned development and validation families with human-reviewed
visual-only chart, diagram, and raster-table items, caption-conflict controls,
unanswerables, and page/region judgments. Keep the frozen chart family sealed.
Before running the comparison, lock one reproducible local answer model and prompt,
generation settings, scope, context budget, corpus, rubric, and latency/memory
budget. Run text, caption/OCR, and targeted pixel-observation arms. Feed each arm's
bounded evidence to the same answer generator and audit citations blind to the arm.
Use a separate oracle-page diagnostic to identify reader failures after correct
retrieval. Record exact revisions, hashes, per-query ranks and outputs, stage
latencies, peak memory, storage and cost.

The proposed go criterion is a positive net count of additional correct and
supporting visual answers against **both** baselines, with zero observed new
unsupported answers or full-validation supported-answer regressions, and measured
resource costs inside the budget agreed before the run. Report denominators,
individual wins and losses, and uncertainty. An empty visual denominator is an
automatic no-go. Report page Hit Rate, Recall, MRR and nDCG independently of
region localization and answer support. A page hit earns page credit only.
