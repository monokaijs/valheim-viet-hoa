using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using BepInEx;
using TMPro;
using UnityEngine;
using UnityEngine.TextCore.LowLevel;

namespace ValheimVietnameseFont
{
    [BepInPlugin(PluginId, PluginName, PluginVersion)]
    public sealed class VietnameseFontPlugin : BaseUnityPlugin
    {
        public const string PluginId = "dev.valheim-vn.font-fallback";
        public const string PluginName = "Valheim Vietnamese Font Fallback";
        public const string PluginVersion = "0.2.11";

        // Pre-warm the complete Vietnamese alphabet. The dynamic assets can
        // still add other glyphs from their source fonts on demand.
        private const string VietnameseCharacters =
            "ÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨ" +
            "ÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ" +
            "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩ" +
            "òóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ";

        private TMP_FontAsset _customRegular;
        private TMP_FontAsset _customBold;
        private string _averiaSansPath;
        private string _averiaSerifPath;
        private TMP_FontAsset _sansFallback;
        private TMP_FontAsset _serifFallback;
        private readonly HashSet<int> _patchedAveriaAssets = new HashSet<int>();
        private readonly Dictionary<Material, Material> _regularMaterials =
            new Dictionary<Material, Material>();
        private readonly Dictionary<Material, Material> _boldMaterials =
            new Dictionary<Material, Material>();
        private bool _installed;

        private void Awake()
        {
            StartCoroutine(InstallWhenResourcesAreReady());
        }

        private IEnumerator InstallWhenResourcesAreReady()
        {
            for (var attempt = 1; attempt <= 120; attempt++)
            {
                if (TryInstall())
                {
                    yield break;
                }

                yield return null;
            }

            Logger.LogError(
                "Could not find Valheim's embedded Noto fonts after 120 frames."
            );
        }

        private bool TryInstall()
        {
            if (_installed)
            {
                return true;
            }

            var sourceFonts = Resources.FindObjectsOfTypeAll<Font>();
            var sansSource = sourceFonts.FirstOrDefault(font => font.name == "NotoSans-Regular");
            var serifSource = sourceFonts.FirstOrDefault(font => font.name == "NotoSerif-Regular");
            if (sansSource == null || serifSource == null)
            {
                return false;
            }

            var pluginDirectory = Path.GetDirectoryName(typeof(VietnameseFontPlugin).Assembly.Location);
            _averiaSansPath = Path.Combine(pluginDirectory, "ValheimVN-Sans-Regular.ttf");
            _averiaSerifPath = Path.Combine(pluginDirectory, "ValheimVN-Serif-Regular.ttf");
            if (!File.Exists(_averiaSansPath) || !File.Exists(_averiaSerifPath))
            {
                Logger.LogError(
                    "The bundled Vietnamese-complete Averia source files are missing; " +
                    "the original font assets cannot be populated safely."
                );
                return true;
            }

            _sansFallback = CreateFallback(sansSource, "ValheimVN-NotoSans-Fallback");
            _serifFallback = CreateFallback(serifSource, "ValheimVN-NotoSerif-Fallback");
            if (_sansFallback == null || _serifFallback == null)
            {
                Logger.LogError(
                    "TextMeshPro could not create the embedded Noto safety fallback assets."
                );
                return true;
            }

            var regularPath = Path.Combine(pluginDirectory, "SVN-Norse Regular.otf");
            var boldPath = Path.Combine(pluginDirectory, "SVN-Norse Bold.otf");
            if (File.Exists(regularPath) && File.Exists(boldPath))
            {
                _customRegular = CreateFallback(regularPath, "ValheimVN-SVN-Norse-Regular");
                _customBold = CreateFallback(boldPath, "ValheimVN-SVN-Norse-Bold");
                if (_customRegular == null || _customBold == null)
                {
                    Logger.LogWarning(
                        "SVN-Norse was found but TextMeshPro could not load it; using bundled Noto fonts."
                    );
                    _customRegular = null;
                    _customBold = null;
                }
            }
            else
            {
                Logger.LogInfo(
                    "Optional SVN-Norse fonts were not found; using Valheim's bundled Noto fonts."
                );
            }

            EnableFallbackMaterialPresetMatching();
            AddGlobalFallback(_sansFallback);
            if (_customRegular != null)
            {
                AddAssetFallback(_customRegular, _sansFallback);
                AddAssetFallback(_customBold, _sansFallback);
            }
            var patched = PatchLoadedFontAssets();
            var replaced = ReplaceLoadedFonts();
            StartCoroutine(PatchFontsAsTheyLoad());

            var fontDescription =
                $"Norse={(_customRegular == null ? "original" : "SVN-Norse Regular/Bold")}, " +
                "AveriaSans=original asset populated from patched bundled source, " +
                "AveriaSerif=original asset populated from patched bundled source, " +
                "Noto safety fallback";
            Logger.LogInfo(
                $"Vietnamese font fallback ready with {fontDescription}; preloaded " +
                $"{VietnameseCharacters.Length} characters, patched {patched} fallback tables, " +
                $"and replaced {replaced} loaded text components."
            );
            _installed = true;
            return true;
        }

        private TMP_FontAsset CreateFallback(string fontPath, string assetName)
        {
            var asset = TMP_FontAsset.CreateFontAsset(
                fontPath,
                0,
                64,
                8,
                GlyphRenderMode.SDFAA,
                2048,
                2048
            );
            return PrepareFallback(asset, assetName);
        }

        private TMP_FontAsset CreateFallback(Font source, string assetName)
        {
            var asset = TMP_FontAsset.CreateFontAsset(
                source,
                64,
                8,
                GlyphRenderMode.SDFAA,
                2048,
                2048,
                AtlasPopulationMode.Dynamic,
                true
            );
            return PrepareFallback(asset, assetName);
        }

        private TMP_FontAsset PrepareFallback(TMP_FontAsset asset, string assetName)
        {
            if (asset == null)
            {
                return null;
            }

            asset.name = assetName;
            asset.hideFlags = HideFlags.HideAndDontSave;
            if (!asset.TryAddCharacters(VietnameseCharacters, out var missing, true))
            {
                Logger.LogWarning($"{assetName} could not preload: {missing}");
            }
            return asset;
        }

        private void EnableFallbackMaterialPresetMatching()
        {
            if (TMP_Settings.matchMaterialPreset)
            {
                return;
            }

            var field = typeof(TMP_Settings).GetField(
                "m_matchMaterialPreset",
                BindingFlags.Instance | BindingFlags.NonPublic
            );
            if (field == null || TMP_Settings.instance == null)
            {
                Logger.LogWarning(
                    "Could not enable TextMeshPro fallback material matching; " +
                    "fallback glyph outlines may differ."
                );
                return;
            }

            try
            {
                field.SetValue(TMP_Settings.instance, true);
            }
            catch (Exception exception)
            {
                Logger.LogWarning(
                    $"Could not enable TextMeshPro fallback material matching: {exception.Message}"
                );
                return;
            }

            foreach (var text in Resources.FindObjectsOfTypeAll<TMP_Text>())
            {
                if (text != null)
                {
                    text.SetAllDirty();
                }
            }
            Logger.LogInfo("TextMeshPro fallback material preset matching enabled.");
        }

        private IEnumerator PatchFontsAsTheyLoad()
        {
            var wait = new WaitForSecondsRealtime(1f);
            while (true)
            {
                PatchLoadedFontAssets();
                ReplaceLoadedFonts();
                yield return wait;
            }
        }

        private int PatchLoadedFontAssets()
        {
            var patched = 0;
            foreach (var asset in Resources.FindObjectsOfTypeAll<TMP_FontAsset>())
            {
                if (asset == null || asset == _customRegular || asset == _customBold ||
                    asset == _sansFallback || asset == _serifFallback)
                {
                    continue;
                }

                if (IsValheimAveriaSans(asset))
                {
                    if (PopulateAveriaAsset(asset, _averiaSansPath, _sansFallback))
                    {
                        patched++;
                    }
                    continue;
                }
                if (IsValheimAveriaSerif(asset))
                {
                    if (PopulateAveriaAsset(asset, _averiaSerifPath, _serifFallback))
                    {
                        patched++;
                    }
                    continue;
                }

                var preferredFallback =
                    asset.name.IndexOf("Serif", StringComparison.OrdinalIgnoreCase) >= 0
                        ? _serifFallback
                        : _sansFallback;
                if (AddAssetFallback(asset, preferredFallback))
                {
                    patched++;
                }
            }
            return patched;
        }

        private bool PopulateAveriaAsset(
            TMP_FontAsset asset,
            string sourcePath,
            TMP_FontAsset safetyFallback
        )
        {
            if (!_patchedAveriaAssets.Add(asset.GetInstanceID()))
            {
                return false;
            }

            var sourceField = typeof(TMP_FontAsset).GetField(
                "m_SourceFontFile",
                BindingFlags.Instance | BindingFlags.NonPublic
            );
            var sourcePathField = typeof(TMP_FontAsset).GetField(
                "m_SourceFontFilePath",
                BindingFlags.Instance | BindingFlags.NonPublic
            );
            if (sourceField == null || sourcePathField == null)
            {
                Logger.LogError(
                    $"Could not attach the bundled source font to {asset.name}."
                );
                AddAssetFallback(asset, safetyFallback);
                return true;
            }

            try
            {
                sourceField.SetValue(asset, null);
                sourcePathField.SetValue(asset, sourcePath);
            }
            catch (Exception exception)
            {
                Logger.LogError(
                    $"Could not attach the source font to {asset.name}: {exception.Message}"
                );
                AddAssetFallback(asset, safetyFallback);
                return true;
            }
            asset.atlasPopulationMode = AtlasPopulationMode.Dynamic;
            asset.isMultiAtlasTexturesEnabled = true;

            var charactersToAdd = new string(
                VietnameseCharacters.Where(character => !asset.HasCharacter(character)).ToArray()
            );
            if (charactersToAdd.Length > 0)
            {
                asset.TryAddCharacters(charactersToAdd, out var _, true);
            }

            var unresolved = new string(
                VietnameseCharacters.Where(character => !asset.HasCharacter(character)).ToArray()
            );
            if (unresolved.Length > 0)
            {
                Logger.LogWarning(
                    $"{asset.name} could not add Vietnamese glyphs in place: {unresolved}"
                );
                AddAssetFallback(asset, safetyFallback);
            }
            else
            {
                Logger.LogInfo(
                    $"Populated {asset.name} in place with its original material and " +
                    $"{asset.atlasTextureCount} atlas texture(s)."
                );
            }

            foreach (var text in Resources.FindObjectsOfTypeAll<TMP_Text>())
            {
                if (text != null && text.font == asset)
                {
                    text.SetAllDirty();
                }
            }
            return true;
        }

        private int ReplaceLoadedFonts()
        {
            var replaced = 0;
            foreach (var text in Resources.FindObjectsOfTypeAll<TMP_Text>())
            {
                if (text == null || text.font == null)
                {
                    continue;
                }

                var useBold = text.font.name.IndexOf("bold", StringComparison.OrdinalIgnoreCase) >= 0 ||
                    (text.fontStyle & FontStyles.Bold) != 0 ||
                    (int)text.fontWeight >= (int)FontWeight.Bold;
                TMP_FontAsset replacement = null;
                if (IsValheimNorse(text.font) && _customRegular != null && _customBold != null)
                {
                    replacement = useBold ? _customBold : _customRegular;
                }
                if (replacement == null)
                {
                    continue;
                }

                var sourceMaterial = text.fontSharedMaterial;

                text.font = replacement;
                text.fontSharedMaterial = GetReplacementMaterial(sourceMaterial, replacement, useBold);
                replaced++;
            }
            return replaced;
        }

        private bool IsValheimNorse(TMP_FontAsset asset)
        {
            return asset != null && asset != _customRegular && asset != _customBold &&
                asset.name.StartsWith("Valheim-Norse", StringComparison.OrdinalIgnoreCase);
        }

        private bool IsValheimAveriaSans(TMP_FontAsset asset)
        {
            return asset != null && asset.name.StartsWith(
                    "Valheim-AveriaSansLibre",
                    StringComparison.OrdinalIgnoreCase
                );
        }

        private bool IsValheimAveriaSerif(TMP_FontAsset asset)
        {
            return asset != null && asset.name.StartsWith(
                    "Valheim-AveriaSerifLibre",
                    StringComparison.OrdinalIgnoreCase
                );
        }

        private Material GetReplacementMaterial(
            Material source,
            TMP_FontAsset replacement,
            bool bold
        )
        {
            if (source == null)
            {
                return replacement.material;
            }

            var cache = bold ? _boldMaterials : _regularMaterials;
            if (cache.TryGetValue(source, out var cached) && cached != null)
            {
                return cached;
            }

            // Start with the replacement material so TextMeshPro gets the correct atlas.
            // TMP's preset copier applies Valheim's shader and visual properties while
            // preserving the replacement font's atlas, gradient scale, and weights.
            var material = new Material(replacement.material);
            TMP_MaterialManager.CopyMaterialPresetProperties(source, material);
            material.name = source.name + " (" + replacement.name + ")";
            material.hideFlags = HideFlags.HideAndDontSave;
            cache[source] = material;
            return material;
        }

        private static bool AddAssetFallback(TMP_FontAsset asset, TMP_FontAsset fallback)
        {
            if (asset == null || fallback == null)
            {
                return false;
            }
            if (asset.fallbackFontAssetTable == null)
            {
                asset.fallbackFontAssetTable = new List<TMP_FontAsset>();
            }
            if (asset.fallbackFontAssetTable.Contains(fallback))
            {
                return false;
            }
            asset.fallbackFontAssetTable.Insert(0, fallback);
            return true;
        }

        private static void AddGlobalFallback(TMP_FontAsset fallback)
        {
            if (TMP_Settings.fallbackFontAssets == null)
            {
                TMP_Settings.fallbackFontAssets = new List<TMP_FontAsset>();
            }
            if (!TMP_Settings.fallbackFontAssets.Contains(fallback))
            {
                TMP_Settings.fallbackFontAssets.Insert(0, fallback);
            }
        }
    }
}
