from pathlib import Path

from valheim_vn.classifier import segment_id, source_hash
from valheim_vn.memory import TranslationMemory
from valheim_vn.schema import CatalogEntry, Tier


def entry(text: str) -> CatalogEntry:
    return CatalogEntry(
        segment_id=segment_id("menu_test", text), key="menu_test", english=text,
        source_hash=source_hash("menu_test", text), asset="localization", row_index=1,
        family="menu_test", domain="interface", baseline_tier=Tier.BASIC,
    )


def test_source_change_archives_translation(tmp_path: Path) -> None:
    db = tmp_path / "memory.sqlite3"
    with TranslationMemory(db) as memory:
        first = entry("Play")
        memory.sync_catalog([first])
        memory.save_translation(first.segment_id, "Chơi", "approved", "human", "human", "", [])
        second = entry("Start game")
        memory.sync_catalog([second])
        state = memory.get(second.segment_id)
        assert state is not None
        assert state.translation is None
        assert state.status == "pending"
        archived = memory.db.execute("SELECT translation FROM source_history").fetchone()
        assert archived["translation"] == "Chơi"


def test_related_context_honors_configured_limit(tmp_path: Path) -> None:
    db = tmp_path / "memory.sqlite3"
    with TranslationMemory(db) as memory:
        entries = []
        for index in range(20):
            item = entry(f"Phrase {index}")
            item.key = f"menu_test_{index}"
            item.family = "menu_test"
            entries.append(item)
        memory.sync_catalog(entries)

        related = memory.related("menu_test", entries[0].segment_id, limit=16)

    assert len(related) == 16
