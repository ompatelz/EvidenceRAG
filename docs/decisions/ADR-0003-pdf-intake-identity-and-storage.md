# ADR-0003: PDF intake identity, idempotency, and atomic local storage

- Status: Accepted
- Date: 2026-10-29

## Context

Phase 1.1 must accept untrusted PDF uploads without prematurely implementing page parsing,
OCR, rendering, retrieval, or a database. It must keep repeated uploads idempotent, retain
changed byte versions, prevent filename traversal, and never expose private paths.

The following official documentation was checked on 2026-10-29:

- FastAPI request-file documentation: `UploadFile` uses a spooled temporary file and
  provides a file-like interface, avoiding a mandatory whole-file memory copy.
- Starlette request-body-limit documentation: the limit counts raw request bytes, including
  multipart overhead, and handles missing or understated `Content-Length`.
- PyMuPDF opening documentation: the library recognizes multiple formats by content and
  supports PDF parsing/rendering, but opening from an in-memory byte string can consume the
  complete input in memory. Parser selection and bounded feasibility belong to Phase 1.2.

References:

- <https://fastapi.tiangolo.com/tutorial/request-files/>
- <https://www.starlette.io/middleware/#requestbodylimitmiddleware>
- <https://pymupdf.readthedocs.io/en/latest/how-to-open-a-file.html>

## Decision

### Upload and validation

- Accept one `multipart/form-data` `UploadFile` through `POST /api/v1/documents`.
- Apply a raw-body limit of the configured PDF limit plus bounded multipart overhead, then
  enforce the exact PDF-byte limit while reading fixed-size chunks.
- Reject empty files, invalid `%PDF-x.y` signatures, and files without `%%EOF` in the final
  1024 bytes. These checks detect wrong-type and plainly truncated inputs; they are not a
  claim of full PDF conformance or safety.
- Do not integrate a PDF parser or count pages in this slice. Phase 1.2 will research and
  pin the parser, validate structure under bounded resources, and define parser failures.

### Logical identity and immutable versions

- A document ID represents a local logical document, not exact bytes. It is derived from
  the SHA-256 of the sanitized, case-folded filename and never contains the filename.
- A document version represents exact bytes and is `sha256:<64 lowercase hex digits>`.
- Uploading changed bytes under the same canonical filename creates a new immutable version
  beneath the same logical document ID.
- Different filenames may sanitize to the same canonical name and therefore the same
  logical document. The API does not yet offer an explicit user-supplied logical key.

### Duplicate policy

- Exact bytes are deduplicated across the local store by SHA-256.
- Repeating an upload returns HTTP 200 and the existing document/version with
  `duplicate=true`; it does not create another event or manifest.
- Identical bytes under another filename return the first existing document/version. The
  later alias is not retained. This makes content idempotency stronger than filename
  identity for the local single-user MVP.

### Storage and atomicity

- The configured artifact root is resolved once. All paths are assembled from generated,
  allowlisted document IDs and hashes and are checked to remain below that root.
- Uploaded chunks are written to a staging file on the same filesystem while SHA-256 is
  updated. The complete staging file is flushed and synchronized before publication.
- The source file is atomically moved into a newly allocated version directory.
- The versioned JSON manifest is written to a temporary sibling file, flushed and
  synchronized, then atomically replaced as `manifest.json`.
- A successful manifest is the commit marker. If source or manifest publication fails, the
  partial version directory and staging file are removed. Failed intake has no successful
  manifest and is never reported as received.

### Lifecycle and client boundary

- `received` is the only persisted successful state in Phase 1.1. It means validated bytes
  and the intake manifest exist; it does not mean parsed, indexed, rendered, or ready.
- Client responses expose opaque `asset:pdf:...` identifiers, document IDs, versions,
  hashes, safe metadata, and status. They never expose artifact-root or source paths.

## Consequences

### Positive

- Hashing and storage use bounded memory independent of the configured file limit.
- Exact duplicate uploads are cheap after hashing and do not multiply artifacts.
- Changed content cannot silently reuse an immutable version.
- A manifest cannot appear successful before its source artifact is durable.
- Untrusted filenames have no filesystem authority.

### Costs and limitations

- SHA-256 deduplication scans manifests linearly; acceptable for the local MVP, not a large
  corpus index.
- Filename-derived logical identity can collide after sanitization or fail to group renamed
  revisions. A future explicit logical key or metadata store may replace this policy.
- Header/trailer checks do not detect every malformed, encrypted, decompression-bomb, or
  adversarial PDF. Parser sandbox/resource decisions remain open for Phase 1.2.
- Atomic replacement protects each file, not a multi-file transaction. The manifest is the
  authoritative commit marker and cleanup handles failures before it appears.
- No authentication or tenant boundary exists; global deduplication is local-user only.

## Rejected alternatives

- **Use the uploaded filename as a path:** rejected because traversal and platform-specific
  names would control storage layout.
- **Load the whole PDF into memory:** rejected because peak memory would scale with upload
  size and make limits less robust.
- **Document ID equals the content hash:** rejected because changed revisions could not stay
  grouped as one logical document.
- **Create an upload event for every duplicate:** rejected because Phase 1.1 has no event
  history requirement and idempotency is more useful.
- **Introduce SQLite now:** rejected because atomic version manifests satisfy this slice and
  no query workload yet justifies a second persistence system.
- **Add PyMuPDF/Docling now:** rejected until the Phase 1.2 research and fixture feasibility
  gate compares provenance, coordinates, dependency weight, and deterministic behavior.

## Conditions for revisiting

Create a superseding ADR if explicit logical document keys, concurrent writers, large-corpus
lookup performance, tenant isolation, durable event history, remote/object storage, or
parser security requirements invalidate these local policies.

## Rollback

Before merge, discard the Phase 1 branch. After merge, revert the Phase 1.1 commit and
remove only the local `artifacts/` directory if the owner no longer needs its untracked
uploads. No database migration, remote object, or deployed resource exists.
