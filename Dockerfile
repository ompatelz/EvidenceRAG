FROM ghcr.io/astral-sh/uv:0.12.7@sha256:95f2aa1fe59274951cfe9b0cbc7972e879ff1004bc8945d130a32eb0dbd85945 AS uv

FROM python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337 AS builder

COPY --from=uv /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337 AS runtime

ARG VCS_REF=unknown
LABEL org.opencontainers.image.title="EvidenceRAG" \
      org.opencontainers.image.description="Evidence-first retrieval API foundation" \
      org.opencontainers.image.revision="${VCS_REF}"

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN groupadd --system --gid 10001 evidencerag \
    && useradd --uid 10001 --gid evidencerag --no-create-home \
        --home-dir /nonexistent --shell /usr/sbin/nologin evidencerag

WORKDIR /app
COPY --from=builder --chown=evidencerag:evidencerag /app/.venv /app/.venv

USER evidencerag:evidencerag
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).read()"]

CMD ["uvicorn", "evidence_rag.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
