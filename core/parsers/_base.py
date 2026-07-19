from __future__ import annotations
from dataclasses import dataclass
from typing import Any

ParseResult = dict[str, "ParsedField"]


@dataclass
class ParsedField:
    value: Any
    confidence: str  # "high" | "medium" | "low" | "missing"
    source_hint: str


def high(value: Any, hint: str) -> ParsedField:
    return ParsedField(value=value, confidence="high", source_hint=hint)


def medium(value: Any, hint: str) -> ParsedField:
    return ParsedField(value=value, confidence="medium", source_hint=hint)


def low(value: Any, hint: str) -> ParsedField:
    return ParsedField(value=value, confidence="low", source_hint=hint)


def missing(field_name: str) -> ParsedField:
    return ParsedField(value=None, confidence="missing", source_hint=f"{field_name} not found")
