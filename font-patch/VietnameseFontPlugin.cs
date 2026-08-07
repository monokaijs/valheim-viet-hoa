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
        public const string PluginVersion = "0.2.2";

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
                AddGlobalFallback(_customRegular);
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
                var changed = AddAssetFallback(asset, notoFallback);
                if (_customRegular != null)
                {
                    var customFallback = asset.name.IndexOf("Bold", StringComparison.OrdinalIgnoreCase) >= 0
                        ? _customBold
                        : _customRegular;
                    changed |= AddAssetFallback(asset, customFallback);
                }
                if (changed)
                {
                    patched++;
                }
            }

            var fontDescription = _customRegular == null
                ? "Valheim bundled Noto Sans/Serif"
                : "SVN-Norse Regular/Bold with Noto safety fallback";
            Logger.LogInfo(
                $"Vietnamese font fallback ready with {fontDescription}; preloaded " +
                $"{VietnameseCharacters.Length} characters and patched {patched} loaded " +
                "TextMeshPro font assets."
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
