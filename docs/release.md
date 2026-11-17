# Local release candidates

The CI workflow runs on pull requests and pushes to `main`. Its Python 3.11
and 3.14 checks run the locked quality gate, alongside standalone ingestion
and live Qdrant jobs. The container job requires all of them to pass.
GitHub concurrency cancels obsolete runs. Checkout credentials are removed
after checkout, third-party actions are pinned to full commits, and the
workflow has read-only repository access.

A candidate image is built and smoke-tested in the runner. CI saves the
image ID, platform, OCI revision, hashes of the lock and build inputs,
installed runtime package versions, and the HTTP demo result. The smoke
uploads the owned fixture to the running Compose service, checks the source
region and PNG, and verifies an unsupported question abstains.
The verification record expires after
14 days. It is a build record, with no signature or vulnerability scan attestation.
The project and PyMuPDF licensing review remains open for redistribution.

Candidate verification is the end of the current pipeline. A future maintainer
can adopt reviewed version tags for release publishing after distribution terms
are settled. Deployment would require a real host, protected credentials, health
checks and a tested rollback before any deployment job is added.

## Rebuild and verify from a clean clone

Install uv 0.12.7, Python 3.12, Node.js with the built-in test runner, and
Docker with Compose. The owned fixtures are tracked with their SHA-256s
and CC0 license under [datasets](../datasets/README.md).

```sh
git clone https://github.com/ompatelz/EvidenceRAG.git
cd EvidenceRAG
uv sync --locked --all-extras --dev
uv run --locked python scripts/quality_gate.py
docker compose config --quiet
export IMAGE_TAG=candidate
VCS_REF=$(git rev-parse HEAD) EVIDENCERAG_DEMO_ANSWERS=true docker compose up --build --wait --wait-timeout 45
uv run --locked python scripts/measure_local.py --base-url http://127.0.0.1:8000 --output reports/generated/container-demo.json
docker compose down
```

On PowerShell set `$env:VCS_REF = git rev-parse HEAD`,
`$env:IMAGE_TAG = 'candidate'` and `$env:EVIDENCERAG_DEMO_ANSWERS = 'true'`
before `docker compose up --build --wait --wait-timeout 45`. Clear the demo
setting after the rehearsal to restore the default behavior.
Use [the inspector guide](inspector.md) to run the answer demonstration
from the Python environment. The base image has no optional model weights.
The pinned revisions for optional models are defined in
[`dense.py`](../src/evidence_rag/retrieval/dense.py),
[`rerank.py`](../src/evidence_rag/retrieval/rerank.py) and
[`semantic.py`](../src/evidence_rag/semantic.py).

## Roll back configuration and derived indexes

Retain the previous source commit, image tag and a copy of documented
local settings before changing them. Stop the candidate with
`docker compose down`. Use the previous checkout and restored settings,
set its saved `IMAGE_TAG`, then run `docker compose up --no-build --wait`.
If the image is absent, rebuild from that checkout and its lock. Check
both operational endpoints before ingesting or querying.

Keep the artifact volume across the restart. Before changing parser or
rendering versions, take a backup of the volume with the app stopped.
For rollback, restore the matching backup or re-index the selected exact
PDF version under the restored runtime. Verify that citation page and
preview match after re-index. Avoid deleting the volume when stopping
the app because it also holds the source PDFs.

The serving API recreates its BM25 and optional embedded Qdrant indexes
from versioned evidence per request. For a separately persisted Qdrant
experiment index, keep each model revision and dimensions in a distinct
collection and rebuild the old index from old inputs if necessary.
See [dense index compatibility](dense_baseline.md).

## Distribution decision

The repository has no project-wide license. The original PDF fixtures use
[CC0-1.0](../datasets/LICENSE-FIXTURES.txt). PyMuPDF and MuPDF are offered
under AGPL and commercial terms. [GitHub repository licensing](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository) · [PyMuPDF license terms](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright)

The owner can keep the project local, review an AGPL-compatible distribution
with corresponding source and applicable notices, or obtain a written Artifex
license covering the intended distribution. Replacing PyMuPDF would require
revalidating extraction, table structure and region anchors before reviewing
the replacement’s terms. Each distribution route needs a decision on the app
license and a review of notices and terms for the exact image and any bundled
models. Publishing a release or registry image remains blocked.

## Candidate notes

- Exact-version artifact validation, bounded generator concurrency and
  source-safe request logs improve failure handling in the local prototype.
- The read-only Compose build supports the local inspector with BM25 and
  an optional fixture answer setting. Pinned external model files can be
  added to the Python quickstart separately.
- The [frozen evaluation](../reports/final_evaluation.md) records one
  authorized held-out run. Human-reviewed general quality, distribution
  terms and any deployment remain open.
