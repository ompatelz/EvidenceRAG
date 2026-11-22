# Changelog

## 0.2.0 - 2026-11-22

### Added

- Embedded Python SDK, JSON CLI, eight local MCP tools and an exportable agent skill.
- Paginated stored-document discovery, lifecycle status and bounded source-page context.
- Truncation metadata for evidence packs and explicit abstention with an empty pack.
- Wheel/source/skill distributions, deterministic skill packaging, provenance and SHA-256 sums.
- Fresh-environment installation tests and release publication after successful main CI.
- Raw exploratory three-arm agent outputs, independent agent source judgments and a checked summary.

### Fixed

- CLI artifact-root selection now respects environment settings unless explicitly overridden.
- Failed or partial CLI ingestion exits nonzero while retaining its lifecycle JSON.
- Draft JSON reads are bounded to 64 KiB.
- PyMuPDF recommendations cannot corrupt CLI JSON or MCP stdio output.
- Conflicting explicit SDK configuration is rejected instead of silently ignored.
- Injected verifier configuration is reported correctly by MCP capabilities.

### Evaluation and scope

The independent agent audit found every emitted answer in the four-question
trial supported, but the skill arm withheld one answerable arithmetic synthesis.
No quality improvement is claimed. Verifier policy and thresholds were preserved;
historical and reserved held-out outputs were not rerun or used for tuning.
Human verification of newly generated claims and broader natural-document
validation remain separate research work. The release is an alpha local toolkit,
with the scope and unsupported modalities stated in docs/PROJECT_STATUS.md.
