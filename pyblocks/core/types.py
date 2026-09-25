"""Static value contracts: type, optional unit, and explicit uncertainty.

Annotations describe source values; parsing and compatibility never evaluate
Python. A missing unit is unknown, not a request for implicit conversion.
"""

import ast
import re
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache

UNITS = frozenset({"deg", "deg/s", "deg/s²", "mm", "mm/s", "ms", "s", "%", "N", "Hz"})
NUMERIC = frozenset({"int", "float", "number"})


@dataclass(frozen=True)
class ValueType:
    name: str
    unit: str | None = None

    def __str__(self):
        return f"{self.name}[{self.unit}]" if self.unit else self.name


class Compatibility(Enum):
    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


@lru_cache(maxsize=512)
def annotation_types(annotation: str | None) -> tuple[ValueType, ...]:
    if not annotation:
        return ()
    result = []
    for part in annotation.split("|"):
        part = part.strip()
        if part in UNITS:
            value = ValueType("number", part)
        else:
            match = re.fullmatch(
                r"([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)(?:\[([^\[\]]+)\])?", part
            )
            if match is None:
                raise ValueError(f"Invalid type annotation: {annotation!r}")
            name, unit = match.groups()
            if unit is not None:
                if name not in NUMERIC or unit not in UNITS:
                    raise ValueError(
                        f"Unknown numeric unit in annotation: {annotation!r}"
                    )
            value = ValueType(name, unit)
        if value not in result:
            result.append(value)
    return tuple(result)


def canonical(annotation: str | None) -> str | None:
    values = annotation_types(annotation)
    return " | ".join(map(str, values)) if values else None


def known_type(annotation: str | None) -> ValueType | None:
    """Ordinary Python may use richer annotations; unsupported hints are unknown."""
    try:
        values = annotation_types(annotation)
    except ValueError:
        return None
    return values[0] if len(values) == 1 and values[0].name != "Any" else None


def numeric_literal(node):
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        node = node.operand
    return isinstance(node, ast.Constant) and type(node.value) in (int, float)


def compatibility(
    expected: str | None, actual: ValueType | None, *, literal=False
) -> Compatibility:
    choices = annotation_types(expected)
    if not choices or any(t.name == "Any" for t in choices):
        return Compatibility.COMPATIBLE
    if actual is None:
        return Compatibility.UNKNOWN
    uncertain = False
    for choice in choices:
        if choice.unit and actual.unit and choice.unit != actual.unit:
            continue
        if not (
            choice.name == actual.name
            or choice.name == "number"
            and actual.name in NUMERIC
            or choice.name == "float"
            and actual.name == "int"
        ):
            if actual.name == "number" and choice.name in NUMERIC:
                uncertain = True
            continue
        if choice.unit is None or choice.unit == actual.unit:
            return Compatibility.COMPATIBLE
        if actual.unit is None:
            if literal:
                return Compatibility.COMPATIBLE
            uncertain = True
    return Compatibility.UNKNOWN if uncertain else Compatibility.INCOMPATIBLE
