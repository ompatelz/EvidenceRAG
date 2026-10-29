# Phase 0 fixture data card

## Purpose

Two tiny synthetic PDFs exercise provenance, tables, regions, visual dependence, and
unanswerable-item validation before retrieval exists.

## Composition

- `atlas-narrative.pdf`: two narrative statements and an original three-node diagram.
- `retrieval-table.pdf`: an original table of explicitly synthetic metrics.

Both contain one page, no personal data, no external source material, and no benchmark
claims. They are deterministic and human-inspectable.

## Provenance and licensing

The repository owns the fixtures and dedicates them under CC0-1.0. The manifest records a
SHA-256 content version, acquisition date, source URI, and redistribution policy.

## Limitations

These fixtures are intentionally simple and cannot demonstrate parser robustness, OCR,
scientific-document diversity, retrieval quality, or real visual reasoning. They exist only
to validate the data and provenance contracts. A later corpus must document permissions,
document-family splits, annotation procedures, uncertainty, and known bias.

## Maintenance

Changing fixture bytes creates a new SHA-256 document version and requires updating every
manifest and evaluation reference. CI regenerates the fixtures and validates their bytes.
