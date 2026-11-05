"""Run one protected Phase 2 retriever and save its raw evaluation artifact."""

import argparse
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from evidence_rag.eval.bm25_run import run as run_e0
from evidence_rag.eval.dense_run import run as run_e1
from evidence_rag.eval.hybrid_run import run as run_e2
from evidence_rag.eval.runner import CUTOFFS
from evidence_rag.retrieval.hybrid import HybridConfig


class BenchmarkConfig(BaseModel):
    """Closed benchmark contract: development and validation, never frozen test."""

    model_config = ConfigDict(extra="forbid")

    retriever: Literal["E0", "E1", "E2"]
    manifest: Path = Path("datasets/manifests/fixtures.json")
    seed: Path = Path("datasets/eval/phase2_seed.jsonl")
    output: Path
    e0_baseline: Path = Path("reports/runs/e0-phase2-pilot.json")
    e1_baseline: Path = Path("reports/runs/e1-phase2-pilot.json")
    model_cache: Path = Path("tmp/hf-model-cache")
    download_model: bool = False
    splits: tuple[Literal["development", "validation"], ...] = (
        "development",
        "validation",
    )
    cutoffs: tuple[int, ...] = Field(default=CUTOFFS)
    hybrid_configs: tuple[HybridConfig, ...] = ()

    @model_validator(mode="after")
    def validate_contract(self) -> "BenchmarkConfig":
        if self.splits != ("development", "validation"):
            raise ValueError("benchmark requires development and validation only")
        if self.cutoffs != CUTOFFS:
            raise ValueError("benchmark cutoffs must be 1, 3, 5")
        if self.retriever == "E1" and self.output.resolve() == self.e0_baseline.resolve():
            raise ValueError("E1 output would overwrite the E0 comparison artifact")
        if self.retriever == "E2" and (
            not self.hybrid_configs
            or self.output.resolve() in {self.e0_baseline.resolve(), self.e1_baseline.resolve()}
        ):
            raise ValueError("E2 requires configurations and a distinct output")
        return self


def run(config: BenchmarkConfig) -> dict[str, Any]:
    """Dispatch through the same contract and preserve per-query failures."""
    if config.retriever == "E0":
        return run_e0(config.manifest, config.seed, config.output)
    if config.retriever == "E1":
        return run_e1(
            config.manifest,
            config.seed,
            config.e0_baseline,
            config.output,
            cache_dir=config.model_cache,
            download_model=config.download_model,
        )
    return run_e2(
        config.manifest,
        config.seed,
        config.e0_baseline,
        config.e1_baseline,
        config.output,
        cache_dir=config.model_cache,
        configurations=config.hybrid_configs,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    raw = json.loads(args.config.read_text(encoding="utf-8"))
    config = BenchmarkConfig.model_validate(raw)
    result = run(config)
    print(f"saved {config.retriever}: {result['counts']} to {config.output}")
    return 2 if result.get("failures") else 0


if __name__ == "__main__":
    raise SystemExit(main())
