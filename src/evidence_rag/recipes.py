"""Bounded exact calculation recipes with source leaves and auditable steps."""

from collections.abc import Mapping
from fractions import Fraction
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from evidence_rag.calculations import (
    NUMBER,
    CalculationError,
    ResolvedOperand,
    TableOperand,
    TextOperand,
    resolve_operand,
)
from evidence_rag.evidence import EvidenceUnit

# Explicit linear units only. No currencies, temperatures, inferred or compound units.
UNITS: dict[str, tuple[str, Fraction]] = {
    "count": ("count", Fraction(1)),
    "hits": ("count", Fraction(1)),
    "misses": ("count", Fraction(1)),
    "requests": ("count", Fraction(1)),
    "ms": ("time", Fraction(1, 1000)),
    "s": ("time", Fraction(1)),
    "seconds": ("time", Fraction(1)),
    "minutes": ("time", Fraction(60)),
    "hours": ("time", Fraction(3600)),
    "days": ("time", Fraction(86400)),
    "mm": ("length", Fraction(1, 1000)),
    "cm": ("length", Fraction(1, 100)),
    "m": ("length", Fraction(1)),
    "km": ("length", Fraction(1000)),
    "g": ("mass", Fraction(1)),
    "kg": ("mass", Fraction(1000)),
    "B": ("bytes", Fraction(1)),
    "KiB": ("bytes", Fraction(1024)),
    "MiB": ("bytes", Fraction(1024**2)),
    "KB": ("bytes", Fraction(1000)),
    "MB": ("bytes", Fraction(1000**2)),
}


class StepReference(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: Literal["step"]
    index: int = Field(ge=0, le=7)


RecipeInput = Annotated[TextOperand | TableOperand | StepReference, Field(discriminator="kind")]


class CalculationStep(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    operation: Literal[
        "add", "subtract", "multiply", "divide", "percentage", "percent_change", "convert"
    ]
    inputs: tuple[RecipeInput, ...] = Field(min_length=1, max_length=2)
    target_unit: str | None = Field(default=None, max_length=32)


class CalculationRecipe(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    steps: tuple[CalculationStep, ...] = Field(min_length=1, max_length=8)
    expected_value: str | None = Field(default=None, pattern=rf"^{NUMBER}$")


class StepReceipt(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    operation: str
    result: str
    unit: str
    conversion_factor: str | None = None


class RecipeResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    version: Literal["source-recipe-v1"] = "source-recipe-v1"
    status: Literal["arithmetic_verified"] = "arithmetic_verified"
    steps: tuple[StepReceipt, ...]
    sources: tuple[ResolvedOperand, ...]
    result: str
    unit: str
    matches_expected: bool | None
    claim_support: Literal["not_assessed"] = "not_assessed"


def calculate_recipe(recipe: CalculationRecipe, units: Mapping[str, EvidenceUnit]) -> RecipeResult:
    receipts: list[StepReceipt] = []
    sources: list[ResolvedOperand] = []
    scope: set[tuple[str, str]] = set()
    for step in recipe.steps:
        operands: list[tuple[Fraction, str]] = []
        for operand in step.inputs:
            if isinstance(operand, StepReference):
                if operand.index >= len(receipts):
                    raise CalculationError("recipe_forward_reference")
                previous = receipts[operand.index]
                operands.append((Fraction(previous.result), previous.unit))
            else:
                unit = units.get(operand.evidence_id)
                if unit is None or unit.evidence_id != operand.evidence_id or len(unit.text) > 1200:
                    raise CalculationError("recipe_source_missing_or_truncated")
                resolved = resolve_operand(operand, unit)
                sources.append(resolved)
                scope.add((resolved.document_id, resolved.document_version))
                if len(scope) > 1:
                    raise CalculationError("calculation_version_mismatch")
                operands.append((Fraction(resolved.value), resolved.unit))
        first, name = operands[0]
        factor = None
        if step.operation == "convert":
            target = step.target_unit
            if len(operands) != 1 or name not in UNITS or target not in UNITS:
                raise CalculationError("recipe_conversion_unsupported")
            if UNITS[name][0] != UNITS[target][0]:
                raise CalculationError("calculation_unit_mismatch")
            if UNITS[name][0] == "count" and target != "count":
                raise CalculationError("recipe_count_relabel_forbidden")
            factor = str(UNITS[name][1] / UNITS[target][1])
            value, name = first * Fraction(factor), target
        else:
            if len(operands) != 2 or step.target_unit is not None:
                raise CalculationError("recipe_operation_shape")
            second, other = operands[1]
            if (
                step.operation in ("add", "subtract", "percentage", "percent_change")
                and name != other
            ):
                raise CalculationError("calculation_unit_mismatch")
            if step.operation == "add":
                value = first + second
            elif step.operation == "subtract":
                value = first - second
            elif step.operation == "multiply":
                value = first * second
                name = f"{name}*{other}" if name and other else name or other
            else:
                denominator = first if step.operation == "percent_change" else second
                if not denominator:
                    raise CalculationError("calculation_division_by_zero")
                value = (
                    (second - first) / first * 100
                    if step.operation == "percent_change"
                    else first / second * (100 if step.operation == "percentage" else 1)
                )
                name = (
                    "%"
                    if step.operation != "divide"
                    else (
                        name if not other else "" if name == other else f"({name or '1'})/({other})"
                    )
                )
        if value.numerator.bit_length() > 4096 or value.denominator.bit_length() > 4096:
            raise CalculationError("recipe_numeric_limit")
        receipts.append(
            StepReceipt(
                operation=step.operation, result=str(value), unit=name, conversion_factor=factor
            )
        )
    final = receipts[-1]
    return RecipeResult(
        steps=tuple(receipts),
        sources=tuple(sources),
        result=final.result,
        unit=final.unit,
        matches_expected=(Fraction(final.result) == Fraction(recipe.expected_value))
        if recipe.expected_value is not None
        else None,
    )
