# ADR-0004: PyMuPDF for provenance-preserving PDF extraction

- Status: Accepted
- Date: 2026-10-29

## Context

Phase 1.2 needs deterministic extraction of page text, tables, captions, and reliable
regions from the owned PDF fixtures. The parser must expose enough source geometry to keep
the evidence contract honest, work on the supported Python versions, and remain feasible
inside the existing local API and container. OCR, visual understanding, retrieval, and
answer generation are outside this decision.

The following official documentation was reviewed on 2026-10-29:

- Docling's document model supports typed text, tables, pictures, hierarchy, and provenance.
- Docling installation includes a PyTorch-backed pipeline and model downloads.
- PyMuPDF exposes text dictionaries with block/span bounding boxes and page-local table
  detection with table, header, row, and column geometry.
- PyMuPDF method coordinates are unrotated except for page rectangles; rotation matrices
  are required when a future viewer maps them onto rotated display space.

References:

- <https://docling-project.github.io/docling/concepts/docling_document/>
- <https://docling-project.github.io/docling/getting_started/installation/>
- <https://pymupdf.readthedocs.io/en/latest/textpage.html>
- <https://pymupdf.readthedocs.io/en/latest/page.html#Page.find_tables>
- <https://pymupdf.readthedocs.io/en/latest/page.html>
- <https://pymupdf.readthedocs.io/en/latest/about.html#license>

## Feasibility gate

Both candidates were installed in an ignored temporary environment and exercised against
the two repository-owned, single-page fixtures with OCR disabled.

- Docling `2.129.0` resolved 106 packages occupying approximately 1177.8 MiB and downloaded
  approximately 494.4 MiB of model data. Its first tiny fixture did not complete within the
  bounded local feasibility window after model loading, so the run was stopped.
- PyMuPDF `1.28.2` opened and extracted the narrative fixture in 0.018 seconds: one page,
  six text blocks, and source bounding boxes.
- PyMuPDF extracted the table fixture in 0.011 seconds: one page, eight text blocks, and one
  four-by-four table with the expected header and cell values.

These are feasibility observations on synthetic fixtures, not general performance claims.

## Decision

- Pin PyMuPDF exactly at `1.28.2` for Phase 1.2. Keep it behind the narrow `PdfParser`
  protocol so a later measured experiment can replace it.
- Parsing is explicit and synchronous through a version-specific endpoint. Upload remains
  a durable `received` operation; automatic background orchestration is Phase 1.4 work.
- Persist a versioned `EvidenceArtifact` rather than PyMuPDF's raw dictionaries. Raw image
  bytes and unstable parser internals are excluded; meaningful text, table structure,
  source geometry, parser version, representation version, and bounded issues are retained.
- Use zero-based page indexes. Reading order is zero-based within each page after a stable
  top-to-bottom, left-to-right sort with parser element ID as the final tie-breaker.
- Retain parser-native boxes in PDF points with a top-left, unrotated coordinate system,
  page dimensions, and page rotation. Also store normalized top-left boxes in `[0, 1]` for
  downstream display independence.
- Assign `region` precision only when a non-empty source box is inside the recorded page.
  Missing or invalid boxes downgrade to `page`; coordinates are never guessed.
- Preserve page-local table headers, rows, dimensions, captions, and whether the detected
  header was external. Do not infer multi-page table continuity.
- Associate a caption only when its type matches, it horizontally overlaps the element,
  it is within 72 PDF points, and the nearest match is not tied. Embedded images become
  figure evidence only with such a reliable caption. Vector diagrams are not claimed.
- Record `parsed`, `partial`, or `failed` truthfully. Empty pages and recoverable page/table/
  figure failures produce bounded issues; no parser exception exposes source text or paths.
- Enforce configurable page and evidence-unit limits before persisting results.

## Consequences

### Positive

- Evidence can be inspected at both parser-native and normalized coordinates.
- Parser and representation versions make regenerated artifacts auditable.
- The selected parser adds a much smaller runtime footprint than the measured Docling
  candidate and requires no model download for the implemented extraction path.
- Table data remains structured instead of being flattened into unsupported prose claims.

### Costs and limitations

- There is no OCR, scanned-page recovery, equation semantics, vector-figure understanding,
  multi-page table linking, or reading-order model for complex magazine layouts.
- Heading classification is a conservative font-size/bold heuristic, not semantic analysis.
- Crop-box offsets and mapping onto a rotated rendered preview require further viewer tests.
- Synchronous parsing is suitable only for the bounded local MVP.
- PyMuPDF is offered under AGPL and commercial licensing. This repository has not selected
  a license and does not publish a container. Licensing and redistribution must be resolved
  before distributing a build; this ADR is an engineering record, not legal advice.

## Rejected or deferred alternatives

- **Docling now:** deferred because its richer semantic model did not pass this phase's
  bounded dependency/startup feasibility gate. Reconsider for layout-heavy or scanned
  corpora only with a representative benchmark and an explicit model-cache strategy.
- **Flatten all page text:** rejected because tables and source regions would be lost.
- **Store raw parser objects:** rejected because they may contain image bytes, unnecessary
  implementation detail, and fields that are not a stable application contract.
- **Guess figure/table relationships:** rejected because plausible but unsupported links
  weaken evidence provenance.

## Conditions for revisiting

Re-run the parser comparison when representative legal documents exist, OCR or complex
layout becomes a measured requirement, the PyMuPDF license is incompatible with the chosen
distribution model, or extraction quality data justifies the heavier Docling pipeline.

## Rollback

Before merge, discard the Phase 1.2 commit. After merge, revert that commit and remove only
generated local `evidence.json` artifacts. Accepted source PDFs and Phase 1.1 manifests stay
valid because upload and parsing are separate lifecycle steps.
