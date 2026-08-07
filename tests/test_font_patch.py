from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parents[1]
    / "font-patch"
    / "VietnameseFontPlugin.cs"
).read_text(encoding="utf-8")


def test_svn_norse_replaces_the_whole_valheim_norse_font() -> None:
    assert 'StartsWith("Valheim-Norse"' in SOURCE
    assert "text.font = replacement;" in SOURCE


def test_svn_norse_is_not_a_fallback_for_normal_fonts() -> None:
    assert "AddGlobalFallback(_customRegular)" not in SOURCE
    assert "AddAssetFallback(asset, customFallback)" not in SOURCE
