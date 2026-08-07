using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
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
        public const string PluginVersion = "0.2.3";

        // Pre-warm the complete Vietnamese alphabet. The dynamic assets can
        // still add other Noto glyphs on demand.
        private const string VietnameseCharacters =
            "ÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨ" +
            "ÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ" +
            "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩ" +
            "òóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ";

        private TMP_FontAsset _customRegular;
        private TMP_FontAsset _customBold;
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

            AddGlobalFallback(_sansFallback);
            if (_customRegular != null)
            {
                AddAssetFallback(_customRegular, _sansFallback);
                AddAssetFallback(_customBold, _sansFallback);
            }
            var existingAssets = Resources.FindObjectsOfTypeAll<TMP_FontAsset>();
            var patched = 0;
            foreach (var asset in existingAssets)
            {
                if (asset == null || asset == _customRegular || asset == _customBold ||
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

            var replaced = ReplaceLoadedNorseFonts();
            if (_customRegular != null)
            {
                StartCoroutine(ReplaceNorseFontsAsTheyLoad());
            }

            var fontDescription = _customRegular == null
                ? "Valheim bundled Noto Sans/Serif"
                : "SVN-Norse Regular/Bold replacing Valheim-Norse, with Noto safety fallback";
            Logger.LogInfo(
                $"Vietnamese font fallback ready with {fontDescription}; preloaded " +
                $"{VietnameseCharacters.Length} characters, patched {patched} fallback tables, " +
                $"and replaced {replaced} loaded Norse text components."
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

        private IEnumerator ReplaceNorseFontsAsTheyLoad()
        {
            var wait = new WaitForSecondsRealtime(1f);
            while (true)
            {
                ReplaceLoadedNorseFonts();
                yield return wait;
            }
        }

        private int ReplaceLoadedNorseFonts()
        {
            if (_customRegular == null || _customBold == null)
            {
                return 0;
            }

            var replaced = 0;
            foreach (var text in Resources.FindObjectsOfTypeAll<TMP_Text>())
            {
                if (text == null || !IsValheimNorse(text.font))
                {
                    continue;
                }

                var useBold = text.font.name.IndexOf("bold", StringComparison.OrdinalIgnoreCase) >= 0 ||
                    (text.fontStyle & FontStyles.Bold) != 0;
                var replacement = useBold ? _customBold : _customRegular;
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

            // Start with the SVN-Norse material so TextMeshPro gets the correct atlas,
            // then retain Valheim's outline/underlay styling from the original preset.
            var material = new Material(replacement.material);
            material.CopyPropertiesFromMaterial(source);
            CopyAtlasProperty(replacement.material, material, "_MainTex");
            CopyFloatProperty(replacement.material, material, "_TextureWidth");
            CopyFloatProperty(replacement.material, material, "_TextureHeight");
            CopyFloatProperty(replacement.material, material, "_GradientScale");
            material.name = source.name + " (SVN-Norse)";
            material.hideFlags = HideFlags.HideAndDontSave;
            cache[source] = material;
            return material;
        }

        private static void CopyAtlasProperty(Material source, Material destination, string property)
        {
            if (source.HasProperty(property) && destination.HasProperty(property))
            {
                destination.SetTexture(property, source.GetTexture(property));
            }
        }

        private static void CopyFloatProperty(Material source, Material destination, string property)
        {
            if (source.HasProperty(property) && destination.HasProperty(property))
            {
                destination.SetFloat(property, source.GetFloat(property));
            }
        }

        private static bool AddAssetFallback(TMP_FontAsset asset, TMP_FontAsset fallback)
        {
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
