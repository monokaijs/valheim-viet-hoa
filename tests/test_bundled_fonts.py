from pathlib import Path

import pytest
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont


ROOT = Path(__file__).resolve().parents[1]
VIETNAMESE_CHARACTERS = (
    "ÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨ"
    "ÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ"
    "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩ"
    "òóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
)

# The Steam-verified Valheim Averia sources contain 308 glyph slots and only
# these 32 Vietnamese characters. Every other required character must be
# appended beyond the original glyph-ID range so TMP's baked glyph lookup
# cannot alias a new character to an existing atlas entry.
ORIGINAL_AVERIA_GLYPH_COUNT = 308
ORIGINAL_AVERIA_VIETNAMESE_CODEPOINTS = {
    0x00C0, 0x00C1, 0x00C2, 0x00C3, 0x00C8, 0x00C9, 0x00CA, 0x00CC,
    0x00CD, 0x00D2, 0x00D3, 0x00D4, 0x00D5, 0x00D9, 0x00DA, 0x00DD,
    0x00E0, 0x00E1, 0x00E2, 0x00E3, 0x00E8, 0x00E9, 0x00EA, 0x00EC,
    0x00ED, 0x00F2, 0x00F3, 0x00F4, 0x00F5, 0x00F9, 0x00FA, 0x00FD,
}


@pytest.mark.parametrize(
    "filename",
    [
        "SVN-Norse Regular.otf",
        "SVN-Norse Bold.otf",
        "ValheimVN-Sans-Regular.ttf",
        "ValheimVN-Serif-Regular.ttf",
    ],
)
def test_bundled_fonts_cover_the_complete_vietnamese_alphabet(filename: str) -> None:
    cmap = TTFont(ROOT / filename).getBestCmap()
    missing = [character for character in VIETNAMESE_CHARACTERS if ord(character) not in cmap]
    assert missing == []


@pytest.mark.parametrize(
    ("filename", "expected_family", "expected_postscript_name"),
    [
        ("ValheimVN-Sans-Regular.ttf", "Valheim VN Sans", "ValheimVNSans"),
        ("ValheimVN-Serif-Regular.ttf", "Valheim VN Serif", "ValheimVNSerif"),
    ],
)
def test_patched_fonts_use_non_reserved_family_names(
    filename: str,
    expected_family: str,
    expected_postscript_name: str,
) -> None:
    font = TTFont(ROOT / filename)
    family_names = {
        record.toUnicode() for record in font["name"].names if record.nameID == 1
    }
    postscript_names = {
        record.toUnicode() for record in font["name"].names if record.nameID == 6
    }
    assert family_names == {expected_family}
    assert postscript_names == {expected_postscript_name}
    assert all("Averia" not in name for name in family_names | postscript_names)


@pytest.mark.parametrize(
    "filename",
    ["ValheimVN-Sans-Regular.ttf", "ValheimVN-Serif-Regular.ttf"],
)
def test_patched_vietnamese_glyphs_have_valid_outlines_and_metrics(filename: str) -> None:
    font = TTFont(ROOT / filename)
    cmap = font.getBestCmap()
    glyph_set = font.getGlyphSet()
    horizontal_metrics = font["hmtx"].metrics

    for character in VIETNAMESE_CHARACTERS:
        glyph_name = cmap[ord(character)]
        advance_width, _ = horizontal_metrics[glyph_name]
        bounds_pen = BoundsPen(glyph_set)
        glyph_set[glyph_name].draw(bounds_pen)
        assert advance_width > 0, f"{filename}: U+{ord(character):04X} has no advance"
        assert bounds_pen.bounds is not None, f"{filename}: U+{ord(character):04X} is empty"


@pytest.mark.parametrize(
    "filename",
    ["ValheimVN-Sans-Regular.ttf", "ValheimVN-Serif-Regular.ttf"],
)
def test_new_vietnamese_glyph_ids_do_not_collide_with_valheims_baked_glyphs(
    filename: str,
) -> None:
    font = TTFont(ROOT / filename)
    cmap = font.getBestCmap()
    new_codepoints = {
        ord(character) for character in VIETNAMESE_CHARACTERS
    } - ORIGINAL_AVERIA_VIETNAMESE_CODEPOINTS
    new_glyph_ids = {font.getGlyphID(cmap[codepoint]) for codepoint in new_codepoints}

    assert len(new_codepoints) == 102
    assert len(new_glyph_ids) == 102
    assert min(new_glyph_ids) >= ORIGINAL_AVERIA_GLYPH_COUNT
