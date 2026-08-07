from __future__ import annotations

import hashlib
import re

from .schema import TIER_ORDER, Tier

LORE_PATTERNS = re.compile(
    r"(tutorial|lore|dream|rune|hugin|munin|npc|quest|dialog|speech|saga|story|"
    r"forsaken|boss|location|random_event)",
    re.IGNORECASE,
)
MECHANIC_PATTERNS = re.compile(
    r"(description|tooltip|effect|status|skill|damage|armor|stamina|health|food|"
    r"recipe|craft|build|item|weapon|attack|piece|material)",
    re.IGNORECASE,
)
UI_PATTERNS = re.compile(
    r"^(menu|settings|button|key|msg|hud|inventory|server|input|language)_",
    re.IGNORECASE,
)
SUFFIXES = (
    "_description", "_desc", "_tooltip", "_text", "_topic", "_label",
    "_name", "_title", "_message", "_msg",
)


def source_hash(key: str, english: str) -> str:
    return hashlib.sha256(f"{key}\0{english}".encode()).hexdigest()


def segment_id(key: str, english: str) -> str:
    return source_hash(key, english)[:20]


def family_for(key: str) -> str:
    lowered = key.lower()
    for suffix in SUFFIXES:
        if lowered.endswith(suffix):
            return key[: -len(suffix)]
    parts = key.split("_")
    return "_".join(parts[: min(3, len(parts))])


def domain_for(key: str, english: str) -> str:
    probe = f"{key} {english[:80]}"
    if LORE_PATTERNS.search(probe):
        return "lore_dialogue"
    if MECHANIC_PATTERNS.search(key):
        return "gameplay_mechanics"
    if UI_PATTERNS.search(key):
        return "interface"
    if key.startswith(("item_", "piece_", "enemy_", "creature_")):
        return "world_entity"
    return "general"


def baseline_tier(key: str, english: str) -> tuple[Tier, list[str]]:
    reasons: list[str] = []
    stripped = english.strip()
    if not stripped or key.upper().startswith("NOT USED") or key.startswith("//"):
        return Tier.SKIP, ["empty or unused source row"]

    tier = Tier.BASIC
    if len(stripped) > 55 or "\n" in stripped:
        tier = Tier.INSPECT
        reasons.append("long or multiline text")
    if re.search(r"\$\d+|\$[A-Za-z_][\w]*|<[^>]+>|%\w|\{\d+", stripped):
        tier = max_tier(tier, Tier.INSPECT)
        reasons.append("runtime token, format placeholder, or rich-text markup")
    if MECHANIC_PATTERNS.search(key) and re.search(r"\d", stripped):
        tier = max_tier(tier, Tier.HIGH)
        reasons.append("gameplay definition contains numeric values")
    if LORE_PATTERNS.search(key) or len(stripped) > 140:
        tier = max_tier(tier, Tier.HIGH)
        reasons.append("lore/dialogue or nuanced prose")
    if len(stripped) > 320 or stripped.count("\n") >= 3:
        tier = Tier.ULTRA
        reasons.append("extended narrative requires continuity review")
    if len(stripped.split()) <= 3 and not UI_PATTERNS.search(key):
        tier = max_tier(tier, Tier.INSPECT)
        reasons.append("short phrase may be ambiguous without game context")
    return tier, reasons


def max_tier(left: Tier, right: Tier) -> Tier:
    return left if TIER_ORDER[left] >= TIER_ORDER[right] else right

