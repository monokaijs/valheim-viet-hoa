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
