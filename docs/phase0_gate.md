# Phase 0 acceptance gate

This table distinguishes verified evidence from planned work. Phase 0 is complete only when
the final pull-request head has passed every local and CI item below.

| Requirement | Proof | State |
| --- | --- | --- |
| Clean development installation | `uv sync --all-extras --dev` from an isolated copy | Passed locally |
| Locked dependency graph | `uv lock --check` | Passed locally |
| Lint and formatting | Ruff check and format check | Passed locally |
| Static typing | strict mypy over `src`, `tests`, and `scripts` | Passed locally |
| Automated tests | 30 pytest tests | Passed locally |
| Package import/version | package tests and manual API response | Passed locally |
| API startup | uvicorn factory command | Passed locally |
| `/health` and `/ready` | live local HTTP requests | Passed locally |
| Evaluation data | validator over every committed JSONL and manifest | Passed locally |
| Deterministic fixtures | regeneration byte comparison | Passed locally |
| PDF quality | Poppler render plus visual and extracted-text inspection | Passed locally |
| Compose validity | `docker compose config --quiet` | Passed locally |
| Container build | pinned multi-stage build tagged `evidencerag:pr` | Passed locally |
| Non-root runtime | container reports UID 10001 | Passed locally |
| Container health | Docker health status plus live endpoint requests | Passed locally |
| Runtime exclusions | no datasets, tests, Git directory, `.env`, or model artifacts | Passed locally |
| Secret/generated-file hygiene | ignore rules, explicit Docker copies, credential scan | Pending final scan |
| Linux/Python CI | Python 3.11 and 3.14 jobs | Pending final head |
| Container CI | Compose, build, health, and UID job | Pending final head |
| Deployment boundary | no registry push, credentials, or deployment steps | Verified by workflow review |

## Scope conclusion

Phase 0 establishes contracts and reproducibility only. It does not implement ingestion,
retrieval, vector search, answer generation, model calls, a database, or a frontend. The
fixture rows are not benchmark results.
