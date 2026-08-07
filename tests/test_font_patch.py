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


def test_averia_sans_uses_the_bundled_complete_source_in_place() -> None:
    assert '"ValheimVN-Sans-Regular.ttf"' in SOURCE
    assert "PopulateAveriaAsset(asset, _averiaSansPath, _sansFallback)" in SOURCE


def test_averia_serif_uses_the_bundled_complete_source_in_place() -> None:
    assert '"ValheimVN-Serif-Regular.ttf"' in SOURCE
    assert "PopulateAveriaAsset(asset, _averiaSerifPath, _serifFallback)" in SOURCE


def test_obsolete_third_party_averia_replacements_are_gone() -> None:
    assert "PatrickHand" not in SOURCE
    assert "Bitter" not in SOURCE


def test_averia_assets_are_switched_to_dynamic_population_in_place() -> None:
    method = SOURCE.split("private bool PopulateAveriaAsset", 1)[1]
    method = method.split("private int ReplaceLoadedFonts", 1)[0]
    assert '"m_SourceFontFile"' in method
    assert '"m_SourceFontFilePath"' in method
    assert "sourceField.SetValue(asset, null);" in method
    assert "sourcePathField.SetValue(asset, sourcePath);" in method
    assert "asset.atlasPopulationMode = AtlasPopulationMode.Dynamic;" in method
    assert "asset.isMultiAtlasTexturesEnabled = true;" in method
    assert "asset.TryAddCharacters(charactersToAdd" in method


def test_averia_fonts_are_not_replaced_or_given_a_fallback_when_population_succeeds() -> None:
    replacement_method = SOURCE.split("private int ReplaceLoadedFonts", 1)[1]
    replacement_method = replacement_method.split("private bool IsValheimNorse", 1)[0]
    assert "IsValheimAveria" not in replacement_method

    population_method = SOURCE.split("private bool PopulateAveriaAsset", 1)[1]
    population_method = population_method.split("private int ReplaceLoadedFonts", 1)[0]
    success_branch = population_method.split("if (unresolved.Length > 0)", 1)[1]
    success_branch = success_branch.split("foreach (var text", 1)[0]
    assert success_branch.count("AddAssetFallback(asset, safetyFallback);") == 1


def test_font_assets_loaded_later_are_also_patched() -> None:
    coroutine = SOURCE.split("private IEnumerator PatchFontsAsTheyLoad", 1)[1]
    coroutine = coroutine.split("private int PatchLoadedFontAssets", 1)[0]
    assert "PatchLoadedFontAssets();" in coroutine


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
