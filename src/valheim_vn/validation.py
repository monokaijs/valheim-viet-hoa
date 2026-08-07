from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
import unicodedata


RUNTIME_TOKEN = re.compile(r"\$(?:\d+|[A-Za-z_][A-Za-z0-9_]*)")
# Deliberately exclude printf's optional space flag: natural prose such as
# "25% damage" otherwise looks like a "% d" placeholder.
PRINTF_TOKEN = re.compile(r"%(?:\d+\$)?[-+#0]*(?:\d+|\*)?(?:\.\d+)?[a-zA-Z%]")
FORMAT_TOKEN = re.compile(r"\{\d+(?::[^}]*)?\}")
RICH_TAG = re.compile(r"</?\w+(?:=[^>]+)?>")
NUMBER = re.compile(r"(?<![\w])[-+]?\d+(?:[.,]\d+)?%?(?![\w])")


@dataclass(frozen=True)
class ValidationResult:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_translation(source: str, translation: str | None) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    if translation is None or not translation.strip():
        return ValidationResult(("translation is empty",), ())
    if unicodedata.normalize("NFC", translation) != translation:
        errors.append("translation is not Unicode NFC-normalized")
    for label, pattern in (
        ("runtime tokens", RUNTIME_TOKEN),
        ("printf placeholders", PRINTF_TOKEN),
        ("format placeholders", FORMAT_TOKEN),
        ("rich-text tags", RICH_TAG),
    ):
        before, after = Counter(pattern.findall(source)), Counter(pattern.findall(translation))
        if before != after:
            errors.append(f"{label} changed: expected {dict(before)}, got {dict(after)}")
    source_numbers = Counter(NUMBER.findall(RICH_TAG.sub("", source)))
    translated_numbers = Counter(NUMBER.findall(RICH_TAG.sub("", translation)))
    if source_numbers != translated_numbers:
        errors.append(
            f"numeric game values changed: expected {dict(source_numbers)}, "
            f"got {dict(translated_numbers)}"
        )
    # A literal UI arrow may itself be "<" or ">". Only reject an imbalance
    # introduced by the translation when the source was balanced.
    if source.count("<") == source.count(">") and translation.count("<") != translation.count(">"):
        errors.append("unbalanced rich-text angle brackets")
    if source.count("\n") != translation.count("\n"):
        warnings.append("line-break count differs from source")
    if source.strip().casefold() == translation.strip().casefold() and len(source.split()) > 2:
        warnings.append("translation is identical to a multiword English source")
    if "[" in translation and "]" in translation and re.search(r"\[[a-z0-9_]+\]", translation):
        warnings.append("translation may contain Valheim's missing-key marker")
    return ValidationResult(tuple(errors), tuple(warnings))


def contains_glossary_term(text: str, term: str) -> bool:
    """Match glossary terms as terms, not substrings such as Odin/exploding."""
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.IGNORECASE) is not None


def locked_glossary_errors(source: str, translation: str,
                           glossary: list[dict[str, object]]) -> list[str]:
    errors = []
    for term in glossary:
        if not term["locked"]:
            continue
        source_term, target = str(term["source"]), str(term["target"])
        if contains_glossary_term(source, source_term) and not contains_glossary_term(translation, target):
            errors.append(f"locked glossary term '{source_term}' must render as '{target}'")
    return errors
