# ADR-0002: Evidence identity and anchor precision

- Status: Accepted
- Date: 2026-10-29

## Decision

- Page indexes are zero-based everywhere in code and API contracts.
- A document version retains both the immutable lowercase SHA-256 content hash and an
  explicit version label. Changing document bytes creates a new version.
- Document IDs identify a logical source; evidence IDs identify a stable extracted element
  within one immutable document version. Regenerating an equivalent representation should
  preserve IDs; changes to source bytes or element boundaries must create new IDs.
- Bounding boxes use normalized `[0, 1]` coordinates with a top-left origin and the shape
  `(x0, y0, x1, y1)`, where both lower coordinates are strictly smaller.
- `region` precision requires a real bounding box and coordinate-system label.
- `page` and `unavailable` precision prohibit bounding boxes. Missing coordinates are
  represented honestly as page-level or unavailable evidence, never guessed.
- Client-facing assets use opaque `asset:<id>` references. Filesystem paths are forbidden.
- Models are frozen, reject unknown fields, and serialize using Pydantic's JSON mode.

## Example

For a 1000 by 2000 pixel page, a region from pixel `(100, 400)` to `(900, 1000)` becomes
`(0.10, 0.20, 0.90, 0.50)`. The normalized values remain stable when the page preview is
rendered at another resolution.

## Consequences

The contract can express honest page-only evidence even when a parser lacks coordinates.
It cannot silently promote that evidence to a precise highlight. Zero-based indexes align
with Python and common parser APIs, while user interfaces may display `page_index + 1`.

Changing identity rules, coordinate origin, or page indexing is a versioned contract change
and requires migration guidance plus a new ADR.
