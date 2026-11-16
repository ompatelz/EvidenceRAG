"""Optional natural-language inference over the exact cited context."""

import math
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import BoundedSemaphore
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

MODEL_NAME = "cross-encoder/nli-deberta-v3-small"
MODEL_REVISION = "98f45e15fc3e6c918f51a7e858cda1139cbc9e59"
PREPROCESSING = "cited-premise-first-v1"
MAX_TOKENS = 512

Support = Literal["supported", "contradicted", "insufficient"]
AssessmentStatus = Literal["assessed", "truncated", "unavailable", "timeout", "failed", "busy"]


class SemanticResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    support: Support
    status: AssessmentStatus
    model: str
    revision: str
    preprocessing: str = PREPROCESSING
    margin: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    conflicting: bool = False
    passage_support: tuple[Support, ...] = ()


class NLIScorer(Protocol):
    model: str
    revision: str

    def logits(self, premise: str, claim: str) -> Sequence[float]: ...


class EvidenceTooLongError(ValueError):
    """The complete premise and claim exceed the supported model input."""


class VerifierUnavailableError(RuntimeError):
    """The local model files or optional inference dependencies are unavailable."""


class LocalDeberta:
    """Load only the pinned local ONNX snapshot on first use."""

    model = MODEL_NAME
    revision = MODEL_REVISION

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self._inference: tuple[object, object] | None = None

    def logits(self, premise: str, claim: str) -> Sequence[float]:
        try:
            import numpy as np
            import onnxruntime as ort  # type: ignore[import-untyped]
            from huggingface_hub import snapshot_download
            from tokenizers import Tokenizer
        except ImportError as exc:
            raise VerifierUnavailableError from exc
        if self._inference is None:
            try:
                snapshot = Path(
                    snapshot_download(
                        self.model,
                        revision=self.revision,
                        cache_dir=self.cache_dir,
                        local_files_only=True,
                        allow_patterns=["tokenizer.json", "onnx/model.onnx"],
                    )
                )
                tokenizer = Tokenizer.from_file(str(snapshot / "tokenizer.json"))
                tokenizer.no_truncation()
                tokenizer.no_padding()
                options = ort.SessionOptions()
                options.intra_op_num_threads = 2
                options.inter_op_num_threads = 1
                session = ort.InferenceSession(
                    str(snapshot / "onnx/model.onnx"), options, providers=["CPUExecutionProvider"]
                )
                self._inference = tokenizer, session
            except Exception as exc:
                raise VerifierUnavailableError from exc
        cached_tokenizer, cached_session = self._inference
        assert isinstance(cached_tokenizer, Tokenizer)
        assert isinstance(cached_session, ort.InferenceSession)
        encoded = cached_tokenizer.encode(premise, claim)
        if len(encoded.ids) > MAX_TOKENS:
            raise EvidenceTooLongError
        inputs = {
            "input_ids": np.asarray([encoded.ids], dtype=np.int64),
            "attention_mask": np.asarray([encoded.attention_mask], dtype=np.int64),
            "token_type_ids": np.asarray([encoded.type_ids], dtype=np.int64),
        }
        result = cached_session.run(
            ["logits"], {item.name: inputs[item.name] for item in cached_session.get_inputs()}
        )
        return tuple(float(value) for value in result[0][0])


class SemanticVerifier:
    """Bound a whole draft assessment and keep provider errors out of results and logs."""

    def __init__(self, scorer: NLIScorer, *, timeout_ms: int = 5000) -> None:
        if timeout_ms <= 0:
            raise ValueError("verifier timeout must be positive")
        self.scorer = scorer
        self.timeout_ms = timeout_ms
        self._slot = BoundedSemaphore()

    def _result(
        self,
        status: AssessmentStatus,
        support: Support = "insufficient",
        *,
        margin: float | None = None,
        conflicting: bool = False,
        passage_support: tuple[Support, ...] = (),
    ) -> SemanticResult:
        return SemanticResult(
            support=support,
            status=status,
            model=self.scorer.model,
            revision=self.scorer.revision,
            margin=margin,
            conflicting=conflicting,
            passage_support=passage_support,
        )

    def _assess(self, claim: str, passages: tuple[str, ...], truncated: bool) -> SemanticResult:
        if truncated:
            return self._result("truncated")
        premises = (*passages, "\n\n".join(passages)) if len(passages) > 1 else passages
        margins: dict[Support, float] = {}
        passage_labels: list[Support] = []
        try:
            for premise in premises:
                values = self.scorer.logits(premise, claim)
                if len(values) != 3 or not all(math.isfinite(value) for value in values):
                    return self._result("failed")
                order = sorted(range(3), key=lambda index: values[index], reverse=True)
                margin = values[order[0]] - values[order[1]]
                if not math.isfinite(margin):
                    return self._result("failed")
                labels: tuple[Support, ...] = ("contradicted", "supported", "insufficient")
                label = labels[order[0]] if margin > 0 else "insufficient"
                margins[label] = max(margin, margins.get(label, 0))
                passage_labels.append(label)
        except EvidenceTooLongError:
            return self._result("truncated")
        except VerifierUnavailableError:
            return self._result("unavailable")
        except Exception:
            return self._result("failed")
        for label in ("contradicted", "supported", "insufficient"):
            if label in margins:
                return self._result(
                    "assessed",
                    label,
                    margin=margins[label],
                    conflicting="contradicted" in margins and "supported" in margins,
                    passage_support=tuple(passage_labels[: len(passages)]),
                )
        return self._result("failed")

    def assess(
        self, inputs: Sequence[tuple[str, tuple[str, ...], bool]]
    ) -> tuple[SemanticResult, ...]:
        if not inputs:
            return ()
        if not self._slot.acquire(blocking=False):
            return tuple(self._result("busy") for _ in inputs)
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="semantic-verifier")
        future = pool.submit(lambda: tuple(self._assess(*item) for item in inputs))
        future.add_done_callback(lambda _: self._slot.release())
        try:
            return future.result(timeout=self.timeout_ms / 1000)
        except TimeoutError:
            future.cancel()
            return tuple(self._result("timeout") for _ in inputs)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
