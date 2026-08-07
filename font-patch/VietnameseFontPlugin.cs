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
        public const string PluginVersion = "0.2.7";

        // Pre-warm the complete Vietnamese alphabet. The dynamic assets can
        // still add other Noto glyphs on demand.
        private const string VietnameseCharacters =
            "ÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨ" +
            "ÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ" +
            "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩ" +
            "òóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ";

        private TMP_FontAsset _customRegular;
        private TMP_FontAsset _customBold;
        private TMP_FontAsset _patrickHand;
        private TMP_FontAsset _bitterRegular;
        private TMP_FontAsset _bitterBold;
        private TMP_FontAsset _sansFallback;
        private TMP_FontAsset _serifFallback;
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

            Logger.LogError("Could not find Valheim's embedded Noto fonts after 120 frames.");
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

            _sansFallback = CreateFallback(sansSource, "ValheimVN-NotoSans-Fallback");
            _serifFallback = CreateFallback(serifSource, "ValheimVN-NotoSerif-Fallback");
            if (_sansFallback == null || _serifFallback == null)
            {
                Logger.LogError("TextMeshPro could not create the Vietnamese fallback font assets.");
                return true;
            }

            var pluginDirectory = Path.GetDirectoryName(typeof(VietnameseFontPlugin).Assembly.Location);
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

            var patrickHandPath = Path.Combine(pluginDirectory, "PatrickHand-Regular.ttf");
            if (File.Exists(patrickHandPath))
            {
                _patrickHand = CreateFallback(
                    patrickHandPath,
                    "ValheimVN-PatrickHand-Regular"
                );
                if (_patrickHand == null)
                {
                    Logger.LogWarning(
                        "Patrick Hand was found but TextMeshPro could not load it; " +
                        "keeping Valheim's Averia fonts."
                    );
                }
            }
            else
            {
                Logger.LogWarning(
                    "PatrickHand-Regular.ttf was not found; keeping Valheim's Averia fonts."
                );
            }

            var bitterRegularPath = Path.Combine(pluginDirectory, "Bitter-Regular.ttf");
            var bitterBoldPath = Path.Combine(pluginDirectory, "Bitter-Bold.ttf");
            if (File.Exists(bitterRegularPath) && File.Exists(bitterBoldPath))
            {
                _bitterRegular = CreateFallback(
                    bitterRegularPath,
                    "ValheimVN-Bitter-Regular"
                );
                _bitterBold = CreateFallback(bitterBoldPath, "ValheimVN-Bitter-Bold");
                if (_bitterRegular == null || _bitterBold == null)
                {
                    Logger.LogWarning(
                        "Bitter was found but TextMeshPro could not load it; " +
                        "keeping Valheim's Averia Serif font."
                    );
                    _bitterRegular = null;
                    _bitterBold = null;
                }
            }
            else
            {
                Logger.LogWarning(
                    "Bitter Regular/Bold were not found; keeping Valheim's Averia Serif font."
                );
            }

            EnableFallbackMaterialPresetMatching();
            AddGlobalFallback(_sansFallback);
            if (_customRegular != null)
            {
                AddAssetFallback(_customRegular, _sansFallback);
                AddAssetFallback(_customBold, _sansFallback);
            }
            if (_patrickHand != null)
            {
                AddAssetFallback(_patrickHand, _sansFallback);
            }
            if (_bitterRegular != null)
            {
                AddAssetFallback(_bitterRegular, _serifFallback);
                AddAssetFallback(_bitterBold, _serifFallback);
            }
            var existingAssets = Resources.FindObjectsOfTypeAll<TMP_FontAsset>();
            var patched = 0;
            foreach (var asset in existingAssets)
            {
                if (asset == null || asset == _customRegular || asset == _customBold ||
                    asset == _patrickHand || asset == _bitterRegular || asset == _bitterBold ||
                    asset == _sansFallback || asset == _serifFallback)
                {
                    continue;
                }

                var notoFallback = asset.name.IndexOf("Serif", StringComparison.OrdinalIgnoreCase) >= 0
                    ? _serifFallback
                    : _sansFallback;
                if (asset.fallbackFontAssetTable == null)
                {
                    asset.fallbackFontAssetTable = new List<TMP_FontAsset>();
                }
                if (AddAssetFallback(asset, notoFallback))
                {
                    patched++;
                }
            }

            var replaced = ReplaceLoadedFonts();
            if (_customRegular != null || _patrickHand != null || _bitterRegular != null)
            {
                StartCoroutine(ReplaceFontsAsTheyLoad());
            }

            var fontDescription =
                $"Norse={(_customRegular == null ? "original" : "SVN-Norse Regular/Bold")}, " +
                $"AveriaSans={(_patrickHand == null ? "original" : "Patrick Hand")}, " +
                $"AveriaSerif={(_bitterRegular == null ? "original" : "Bitter Regular/Bold")}, " +
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

        private IEnumerator ReplaceFontsAsTheyLoad()
        {
            var wait = new WaitForSecondsRealtime(1f);
            while (true)
            {
                ReplaceLoadedFonts();
                yield return wait;
            }
        }

        private int ReplaceLoadedFonts()
        {
            if ((_customRegular == null || _customBold == null) && _patrickHand == null &&
                (_bitterRegular == null || _bitterBold == null))
            {
                return 0;
            }

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
                else if (IsValheimAveriaSans(text.font) && _patrickHand != null)
                {
                    replacement = _patrickHand;
                }
                else if (IsValheimAveriaSerif(text.font) && _bitterRegular != null &&
                    _bitterBold != null)
                {
                    replacement = useBold ? _bitterBold : _bitterRegular;
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
            return asset != null && asset != _patrickHand &&
                asset.name.StartsWith(
                    "Valheim-AveriaSansLibre",
                    StringComparison.OrdinalIgnoreCase
                );
        }

        private bool IsValheimAveriaSerif(TMP_FontAsset asset)
        {
            return asset != null && asset != _bitterRegular && asset != _bitterBold &&
                asset.name.StartsWith(
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
