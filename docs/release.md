# Release and deployment boundary

Phase 0 builds and verifies a candidate container but does not publish or deploy it. CI has
read-only repository permission, receives no deployment credentials, and never pushes an
image. This keeps unreviewed pull-request code away from registries and environments.

## Future release model

1. A focused pull request is reviewed.
2. Every required quality, data, and container check passes.
3. The reviewed PR is merged to the protected default branch.
4. CI builds an immutable candidate artifact labeled with the commit SHA.
5. A maintainer explicitly approves a semantic version tag.
6. A protected deployment environment is used if deployment is later introduced.
7. The release health check is observed; rollback selects the previous immutable image.

Publishing, signing, SBOM generation, vulnerability policy, and deployment remain future
decisions. They should be introduced together with an actionable ownership and failure
policy, not as ignored or unactionable CI output.

## Current container boundary

The image contains only the installed runtime package and its dependencies. It runs as UID
and GID 10001, exposes port 8000, and checks `/health` using Python's standard library. It
does not contain tests, PDFs, datasets, local environments, Git history, credentials, model
weights, or generated indexes.

Compose adds a read-only filesystem, a bounded temporary directory, and
`no-new-privileges`. No database or other service is introduced because Phase 0 does not
use one.

## Rollback

Before merge, close the pull request and delete its branch. After merge, revert the Phase 0
PR. No schema migration, registry publication, or deployment resource requires cleanup.
