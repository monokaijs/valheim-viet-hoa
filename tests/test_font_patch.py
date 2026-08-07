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


def test_patrick_hand_replaces_whole_averia_sans_font_asset() -> None:
    assert 'StartsWith(\n                    "Valheim-AveriaSansLibre"' in SOURCE
    assert "replacement = _patrickHand;" in SOURCE


def test_bitter_replaces_whole_averia_serif_font_asset() -> None:
    assert 'StartsWith(\n                    "Valheim-AveriaSerifLibre"' in SOURCE
    assert "replacement = useBold ? _bitterBold : _bitterRegular;" in SOURCE


def test_new_font_assets_get_a_fallback_table_before_it_is_used() -> None:
    method = SOURCE.split("private static bool AddAssetFallback", 1)[1]
    null_check = method.index("asset.fallbackFontAssetTable == null")
    contains_check = method.index("asset.fallbackFontAssetTable.Contains")
    assert null_check < contains_check


def test_fallback_glyphs_match_the_primary_material_preset() -> None:
    method = SOURCE.split("private void EnableFallbackMaterialPresetMatching", 1)[1]
    assert 'GetField(\n                "m_matchMaterialPreset"' in method
    assert "field.SetValue(TMP_Settings.instance, true);" in method
    assert "text.SetAllDirty();" in method


def test_replacement_material_uses_tmpro_preset_copy() -> None:
    method = SOURCE.split("private Material GetReplacementMaterial", 1)[1]
    method = method.split("private static bool AddAssetFallback", 1)[0]
    assert "TMP_MaterialManager.CopyMaterialPresetProperties(source, material);" in method
    assert "material.CopyPropertiesFromMaterial(source);" not in method
