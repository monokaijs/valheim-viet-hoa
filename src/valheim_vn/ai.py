from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
from typing import Iterable

from openai import OpenAI

from .assets import read_catalog
from .classifier import max_tier
from .memory import TranslationMemory
from .schema import (
    CatalogEntry, ClassificationBatch, ReviewBatch, SegmentState, Tier,
    TranslationBatch,
)
from .validation import contains_glossary_term, locked_glossary_errors, validate_translation


SYSTEM_PROMPT = """You are the senior Vietnamese localization editor for Valheim.
Translate player-visible English into natural Vietnamese while preserving exact game behavior.

Non-negotiable rules:
- Never translate or modify the localization key, segment_id, $tokens, $1-style slots,
  printf/.NET format placeholders, rich-text tags, numbers, percentages, or units.
- Do not add, omit, soften, or strengthen gameplay facts. English is authoritative.
- Use the supplied official-language renderings only to disambiguate context.
- Obey the locked glossary exactly and keep proper nouns consistent across the whole game.
- Interface text is concise and immediately readable.
- Lore, dreams, runestones, and raven speech use polished Vietnamese saga prose: grave,
  vivid, and Viking in atmosphere, but never purple, comic, or needlessly archaic.
- Preserve speaker identity, intent, register, line breaks when practical, and all markup.
- If context is insufficient, be conservative and record the ambiguity in notes.
Return only the requested structured object."""

CLASSIFIER_PROMPT = """Classify localization segments by the inspection needed before release.
basic: obvious short UI text with one safe meaning.
need_more_inspection: short ambiguity, entity/item names, placeholders, tags, or ordinary descriptions.
high_inspection: mechanics, tutorial/dialogue, nuanced prose, or lore requiring related-key context.
ultra_inspection: extended narrative, conflicting source context, crucial terminology, or text where
a subtle error can change mechanics/character voice. Never lower the provided baseline tier.
Also identify domain, likely speaker, concise context notes, and concrete ambiguities."""

REVIEW_PROMPT = """Act as an independent Valheim localization reviewer. Compare every Vietnamese
candidate against English, related segments, style rules, glossary, and invariants. Reject invented
facts or changed mechanics. Use revise only when you can provide a complete corrected translation.
The revised translation must preserve every protected token, tag, number, and placeholder exactly."""


@dataclass(frozen=True)
class Route:
    model: str
    effort: str
    review_model: str | None
    review_effort: str | None
    batch_size: int


LOW_MODEL = os.environ.get("VALHEIM_VN_LOW_MODEL", "gpt-5.6-luna")
HIGH_MODEL = os.environ.get("VALHEIM_VN_HIGH_MODEL", "gpt-5.6-sol")
CLASSIFIER_MODEL = os.environ.get("VALHEIM_VN_CLASSIFIER_MODEL", LOW_MODEL)
ECONOMY_MODEL = os.environ.get("VALHEIM_VN_ECONOMY_MODEL", "gpt-5.6-luna")

DEFAULT_ROUTES = {
    Tier.BASIC: Route(LOW_MODEL, "low", None, None, 24),
    Tier.INSPECT: Route(LOW_MODEL, "high", HIGH_MODEL, "low", 16),
    Tier.HIGH: Route(HIGH_MODEL, "high", HIGH_MODEL, "xhigh", 5),
    # Ultra requests can contain long narrative context and two max-effort
    # passes. Keep them deliberately small so one slow/failed request never
    # strands much work (or budget).
    Tier.ULTRA: Route(HIGH_MODEL, "max", HIGH_MODEL, "max", 2),
}


def _client() -> OpenAI:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set. No API request was made.")
    # Do not automatically duplicate a costly translation request after a
    # timeout or a project-spend 429. Ultra reasoning can legitimately take
    # several minutes, so allow one long attempt and checkpoint each finished
    # batch before beginning another.
    return OpenAI(max_retries=0, timeout=600.0)


def _chunks(items: list[SegmentState], size: int) -> Iterable[list[SegmentState]]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _catalog_map(workspace: Path) -> dict[str, CatalogEntry]:
    return {entry.segment_id: entry for entry in read_catalog(workspace)}


def classify_segments(workspace: Path, use_ai: bool, limit: int | None = None) -> dict[str, int]:
    catalog = _catalog_map(workspace)
    with TranslationMemory(workspace / "memory.sqlite3") as memory:
        pending = memory.select(("pending", "classified"), limit=limit)
        if not use_ai:
            for state in pending:
                entry = catalog[state.segment_id]
                memory.update_classification(state.segment_id, entry.baseline_tier, entry.domain, {
                    "risk_reasons": entry.risk_reasons,
                    "classifier": "deterministic",
                })
            return memory.stats()

        client = _client()
        for batch in _chunks(pending, 30):
            payload = []
            for state in batch:
                entry = catalog[state.segment_id]
                payload.append({
                    "segment_id": state.segment_id,
                    "key": state.key,
                    "english": state.english,
                    "family": state.family,
                    "baseline_tier": entry.baseline_tier.value,
                    "deterministic_risks": entry.risk_reasons,
                    "official_references": entry.reference_translations,
                })
            response = client.responses.parse(
                model=CLASSIFIER_MODEL,
                reasoning={"effort": "low"},
                instructions=CLASSIFIER_PROMPT,
                input=json.dumps(payload, ensure_ascii=False),
                text_format=ClassificationBatch,
                store=False,
            )
            parsed = response.output_parsed
            if parsed is None:
                raise RuntimeError("Classification response did not contain parsed output")
            by_id = {item.segment_id: item for item in parsed.items}
            expected = {item.segment_id for item in batch}
            if set(by_id) != expected:
                raise RuntimeError("Classifier returned missing or unexpected segment IDs; batch was not saved")
            for state in batch:
                entry = catalog[state.segment_id]
                item = by_id[state.segment_id]
                tier = max_tier(entry.baseline_tier, item.tier)
                memory.update_classification(state.segment_id, tier, item.domain, {
                    "speaker": item.speaker,
                    "context_notes": item.context_notes,
                    "ambiguity_notes": item.ambiguity_notes,
                    "risk_reasons": entry.risk_reasons,
                    "classifier": CLASSIFIER_MODEL,
                })
        return memory.stats()


def _glossary_context(memory: TranslationMemory, states: list[SegmentState]) -> list[dict[str, object]]:
    joined = "\n".join(s.english for s in states)
    return [
        term for term in memory.glossary()
        if contains_glossary_term(joined, str(term["source"]))
    ]


def _translation_payload(memory: TranslationMemory, catalog: dict[str, CatalogEntry],
                         states: list[SegmentState], context_limit: int = 8) -> dict[str, object]:
    return {
        "style": "Vietnamese Viking fiction for prose; compact modern Vietnamese for UI",
        "glossary": _glossary_context(memory, states),
        "segments": [{
            "segment_id": state.segment_id,
            "key": state.key,
            "english": state.english,
            "tier": state.tier.value,
            "domain": state.domain,
            "known_context": state.context,
            "official_references": catalog[state.segment_id].reference_translations,
            "related_segments": memory.related(
                state.family, state.segment_id, limit=context_limit
            ),
        } for state in states],
    }


def _review(client: OpenAI, route: Route, memory: TranslationMemory,
            catalog: dict[str, CatalogEntry], states: list[SegmentState],
            candidates: dict[str, str], context_limit: int) -> ReviewBatch:
    payload = _translation_payload(memory, catalog, states, context_limit)
    payload["candidates"] = candidates
    response = client.responses.parse(
        model=route.review_model,
        reasoning={"effort": route.review_effort},
        instructions=SYSTEM_PROMPT + "\n\n" + REVIEW_PROMPT,
        input=json.dumps(payload, ensure_ascii=False),
        text_format=ReviewBatch,
        store=False,
    )
    if response.output_parsed is None:
        raise RuntimeError("Review response did not contain parsed output")
    return response.output_parsed


def _run_route(tier: Tier, economy: bool) -> Route:
    if economy:
        # Preserve the translate-then-review safety loop while replacing both
        # expensive Sol/max calls with non-reasoning, individually checkpointed
        # Luna calls. Deterministic invariant checks remain unchanged.
        return Route(ECONOMY_MODEL, "none", ECONOMY_MODEL, "none", 1)
    return DEFAULT_ROUTES[tier]


def _progress(enabled: bool, message: str) -> None:
    if enabled:
        print(message, file=sys.stderr, flush=True)


def _quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def translate_segments(workspace: Path, tiers: tuple[Tier, ...] | None = None,
                       limit: int | None = None, max_requests: int | None = None,
                       economy: bool = False, context_limit: int = 8,
                       progress: bool = True) -> dict[str, int]:
    if context_limit < 0:
        raise ValueError("context_limit must be zero or greater")
    client = _client()
    catalog = _catalog_map(workspace)
    request_count = 0
    with TranslationMemory(workspace / "memory.sqlite3") as memory:
        states = memory.select(("classified", "failed", "needs_review"), tiers=tiers, limit=limit)
        grouped: dict[Tier, list[SegmentState]] = {}
        for state in states:
            if state.tier not in (Tier.SKIP,):
                grouped.setdefault(state.tier, []).append(state)
        total = sum(len(items) for items in grouped.values())
        _progress(
            progress,
            f"RUN phrases={total} mode={'economy' if economy else 'quality'} "
            f"context_limit={context_limit} max_requests={max_requests or 'unlimited'}",
        )
        completed = 0
        for tier in (Tier.BASIC, Tier.INSPECT, Tier.HIGH, Tier.ULTRA):
            route = _run_route(tier, economy)
            # Keep related keys together; sorting done by TranslationMemory.
            for batch in _chunks(grouped.get(tier, []), route.batch_size):
                calls_needed = 1 + int(route.review_model is not None)
                if max_requests is not None and request_count + calls_needed > max_requests:
                    _progress(
                        progress,
                        f"STOP local request ceiling reached: requests={request_count}, "
                        f"completed={completed}/{total}",
                    )
                    return memory.stats()
                for offset, state in enumerate(batch):
                    _progress(
                        progress,
                        f"[{completed + offset + 1}/{total}] START key={state.key} "
                        f"tier={state.tier.value} model={route.model} effort={route.effort}",
                    )
                    _progress(progress, f"  EN: {_quoted(state.english)}")
                payload = _translation_payload(memory, catalog, batch, context_limit)
                response = client.responses.parse(
                    model=route.model,
                    reasoning={"effort": route.effort},
                    instructions=SYSTEM_PROMPT,
                    input=json.dumps(payload, ensure_ascii=False),
                    text_format=TranslationBatch,
                    store=False,
                )
                request_count += 1
                parsed = response.output_parsed
                if parsed is None:
                    raise RuntimeError("Translation response did not contain parsed output")
                candidates = {item.segment_id: item for item in parsed.items}
                expected = {state.segment_id for state in batch}
                if set(candidates) != expected:
                    raise RuntimeError("Translator returned missing or unexpected segment IDs; batch was not saved")
                for state in batch:
                    item = candidates[state.segment_id]
                    _progress(
                        progress,
                        f"  CANDIDATE confidence={item.confidence:.2f}: {_quoted(item.translation)}",
                    )

                review_by_id = {}
                if route.review_model:
                    _progress(
                        progress,
                        f"  REVIEW model={route.review_model} effort={route.review_effort}",
                    )
                    review = _review(
                        client, route, memory, catalog, batch,
                        {sid: item.translation for sid, item in candidates.items()},
                        context_limit,
                    )
                    request_count += 1
                    review_by_id = {item.segment_id: item for item in review.items}
                    if set(review_by_id) != expected:
                        raise RuntimeError("Reviewer returned missing or unexpected segment IDs; batch was not saved")

                glossary = _glossary_context(memory, batch)
                for state in batch:
                    candidate = candidates[state.segment_id]
                    translation = candidate.translation.strip()
                    review_notes: list[str] = []
                    rejected = False
                    if route.review_model:
                        reviewed = review_by_id[state.segment_id]
                        _progress(
                            progress,
                            f"  REVIEW_RESULT verdict={reviewed.verdict} "
                            f"issues={_quoted('; '.join(reviewed.issues))}",
                        )
                        review_notes.extend(reviewed.issues)
                        if reviewed.verdict == "revise" and reviewed.revised_translation:
                            translation = reviewed.revised_translation.strip()
                        elif reviewed.verdict == "reject":
                            rejected = True
                    validation = validate_translation(state.english, translation)
                    errors = list(validation.errors)
                    errors.extend(locked_glossary_errors(state.english, translation, glossary))
                    notes = "; ".join(filter(None, [candidate.notes, *review_notes, *validation.warnings]))
                    status = "failed" if errors or rejected else "approved"
                    if rejected:
                        errors.append("semantic reviewer rejected the candidate")
                    memory.save_translation(
                        state.segment_id, translation, status, route.model, route.effort, notes, errors
                    )
                    _progress(progress, f"  RESULT status={status} VI={_quoted(translation)}")
                    if errors:
                        _progress(progress, f"  ERRORS: {_quoted('; '.join(errors))}")
                completed += len(batch)
                _progress(
                    progress,
                    f"PROGRESS completed={completed}/{total} requests={request_count}",
                )
        return memory.stats()
