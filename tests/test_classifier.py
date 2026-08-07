from valheim_vn.classifier import baseline_tier, family_for
from valheim_vn.schema import Tier


def test_short_ui_is_basic() -> None:
    tier, _ = baseline_tier("menu_logout", "Log out")
    assert tier == Tier.BASIC


def test_ambiguous_entity_name_requires_inspection() -> None:
    tier, reasons = baseline_tier("item_ancientseed", "Ancient seed")
    assert tier == Tier.INSPECT
    assert any("ambiguous" in reason for reason in reasons)


def test_long_lore_is_high_or_ultra() -> None:
    tier, _ = baseline_tier("tutorial_raven_text", "Long ago, the Allfather cast you here. " * 12)
    assert tier == Tier.ULTRA


def test_family_strips_semantic_suffix() -> None:
    assert family_for("item_sword_iron_description") == "item_sword_iron"

