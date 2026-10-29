# ADR-0005: Versioned page previews and evidence-anchor transforms

- Status: Accepted
- Date: 2026-10-29

## Context

Phase 1.3 must make extracted evidence visually inspectable without inventing regions or
exposing private files. The parser stores unrotated, top-left PyMuPDF coordinates relative
to the visible crop box. A preview renderer respects page rotation and the crop box, so the
source coordinate space cannot be treated as rendered pixels directly.

The current official PyMuPDF documentation was checked on 2026-10-29. It states that page
methods return unrotated coordinates except for `Page.rect`, that `Page.rotation_matrix`
maps into rotated coordinates, and that `Page.get_pixmap()` respects page rotation and the
crop box. The rendering recipe supports explicit DPI and PNG output.

References:

- <https://pymupdf.readthedocs.io/en/latest/page.html>
- <https://pymupdf.readthedocs.io/en/latest/recipes-images.html>
- <https://pymupdf.readthedocs.io/en/latest/pixmap.html>

## Measured coordinate behavior

A bounded owned experiment used a 300 by 200 point media box with crop box
`(50, 25, 250, 125)` and rotations 0, 90, 180, and 270 degrees.

- Extracted text coordinates were relative to the visible 200 by 100 point crop-box origin.
- The crop-box offset remained `(50, 25)` and the media box remained 300 by 200 points.
- At 72 DPI, rendered dimensions were 200 by 100 pixels for 0/180 degrees and 100 by 200
  pixels for 90/270 degrees.
- Rotation matrices and rendered dimensions agreed with the documented behavior.

This confirms that the evidence source box, crop/media metadata, and rotated preview size
must be retained as distinct values.

## Decision

### Rendering profile

- Render explicitly after parsing; upload and parse remain separate operations.
- Pin the profile as `png-rgb-no-annotations-v1` using PyMuPDF `1.28.2`.
- Render the visible crop box as RGB PNG at a configurable default of 144 DPI.
- Suppress PDF annotations so comments, links, or mutable annotation appearances do not
  obscure the immutable source-content preview used for evidence comparison.
- Enforce the existing page limit plus configurable pre-render per-page and total pixel
  limits.
- Record renderer name/version/profile, DPI, PNG hash, source dimensions, pixel dimensions,
  rotation, crop box, and media box.

### Coordinate transforms

Evidence boxes remain normalized in the unrotated visible source space. Before mapping to
pixels, rotate the normalized rectangle clockwise with these formulas:

```text
0:   (x0, y0, x1, y1)
90:  (1-y1, x0, 1-y0, x1)
180: (1-x1, 1-y1, 1-x0, 1-y0)
270: (y0, 1-x1, y1, 1-x0)
```

Convert the displayed normalized box to a containing pixel box by flooring lower bounds,
ceiling upper bounds, and clamping to the actual pixmap dimensions. The transform never
shrinks the source region through rounding.

- Region evidence returns source-normalized, display-normalized, and pixel boxes.
- Page evidence resolves the correct preview but returns no box.
- Unavailable evidence returns neither a preview nor a box.
- A page-size or rotation mismatch between evidence and preview is a conflict, not a guessed
  transform.

### Storage and security

- Write every page into a private same-filesystem staging directory.
- Write the page manifest into that directory, then publish the complete page set with one
  directory rename. A partial page set has no published manifest.
- Scope all lookups by allowlisted document ID, exact document hash/version, and validated
  zero-based page index.
- Return opaque `asset:page:...` identifiers and PNG bytes; never return an absolute path.
- Hash each PNG and return an immutable private-cache ETag.
- Resolve an evidence ID only inside the evidence artifact belonging to the requested exact
  document version, preventing cross-document and stale-version access.

The ingestion lifecycle remains `parsed` or `partial` after rendering. Phase 1.3 does not
claim `ready`; the atomic end-to-end transition belongs to Phase 1.4.

## API boundary

- `POST .../render` creates or idempotently returns the fixed-profile page set.
- `GET .../pages` returns client-safe page metadata.
- `GET .../pages/{page_index}/preview` returns a manifest-backed `image/png`.
- `GET .../evidence/{evidence_id}/anchor` resolves honest page/region geometry.

## Verification evidence

- Geometry tests cover all four rotations and inverse round trips.
- Tests cover multiple DPI scales, full-page boundaries, crop/media offsets, resource
  limits, missing files, invalid IDs/versions/pages, cross-document requests, stale versions,
  rendering failure, page-only precision, and unavailable precision.
- A pixel-based regression checks the owned table fixture's expected grid border at the
  resolved coordinates.
- Manual inspection at 144 DPI showed the generated red box enclosing the complete table
  border and cells while excluding the separately extracted caption.

## Consequences and limitations

- Fixed-profile previews are reproducible and cacheable but do not offer arbitrary client
  DPI negotiation.
- PNG output costs more storage than a tiled or on-demand system; acceptable for the bounded
  local MVP.
- Annotation suppression is deliberate; an annotation-inspection mode would need a separate
  profile and asset identity.
- Crop/media metadata is retained, but unusual malformed PDF boxes remain parser-dependent.
- Concurrent render publication, retry, stale-artifact replacement, timing, and lifecycle
  transition to `ready` are deferred to Phase 1.4.
- No polished viewer is implemented. The API and deterministic overlay proof establish the
  geometry contract for a later inspector.

## Rejected alternatives

- **Return private PNG paths:** rejected because paths disclose local layout and create path
  traversal authority.
- **Draw boxes into the canonical preview:** rejected because it would mix source pixels with
  one evidence selection and prevent reuse. Overlays belong in the client or debug tooling.
- **Show a guessed page box for page-only evidence:** rejected because it overstates
  precision.
- **Ignore page rotation:** rejected because region anchors would land on the wrong pixels.
- **Render the full media box unconditionally:** rejected because normal PDF viewers display
  the crop box and parser evidence is relative to that visible space.

## Rollback

Before merge, discard the Phase 1.3 commit. After merge, revert it and remove only generated
local `pages/` directories. Accepted PDFs, intake manifests, and parsed `evidence.json`
artifacts remain valid.
