from pathlib import Path
import runpy


PACKAGE_SCRIPT = runpy.run_path(
    Path(__file__).resolve().parents[1] / "scripts" / "package_thunderstore.py"
)


def test_payload_uses_the_thunderstore_plugins_route() -> None:
    assert PACKAGE_SCRIPT["PLUGIN_DLL_ARCHIVE_PATH"] == (
        "plugins/ValheimVietHoa/ValheimVietnameseFont.dll"
    )
    assert PACKAGE_SCRIPT["TRANSLATION_ARCHIVE_PATH"] == (
        "plugins/ValheimVietHoa/Translations/Vietnamese/ValheimVietHoa.json"
    )


def test_bundled_fonts_exist_with_plugin_expected_names() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "SVN-Norse Regular.otf").is_file()
    assert (root / "SVN-Norse Bold.otf").is_file()
    assert (root / "ValheimVN-Sans-Regular.ttf").is_file()
    assert (root / "ValheimVN-Serif-Regular.ttf").is_file()
    assert (root / "licenses" / "OFL-Averia.txt").is_file()
    assert (root / "licenses" / "OFL-Noto.txt").is_file()


def test_package_does_not_bundle_replacement_fonts_for_averia() -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "package_thunderstore.py"
    source = script.read_text(encoding="utf-8")
    assert "PatrickHand" not in source
    assert "Bitter-Regular" not in source
    assert "Bitter-Bold" not in source


def test_package_bundles_patched_averia_sources_for_in_place_population() -> None:
    assert PACKAGE_SCRIPT["AVERIA_SANS_ARCHIVE_PATH"] == (
        "plugins/ValheimVietHoa/ValheimVN-Sans-Regular.ttf"
    )
    assert PACKAGE_SCRIPT["AVERIA_SERIF_ARCHIVE_PATH"] == (
        "plugins/ValheimVietHoa/ValheimVN-Serif-Regular.ttf"
    )
