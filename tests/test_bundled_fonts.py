from pathlib import Path

import pytest
from fontTools.ttLib import TTFont


ROOT = Path(__file__).resolve().parents[1]
VIETNAMESE_CHARACTERS = (
    "ÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨ"
    "ÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ"
    "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩ"
    "òóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
)


@pytest.mark.parametrize(
    "filename",
    [
        "SVN-Norse Regular.otf",
        "SVN-Norse Bold.otf",
        "PatrickHand-Regular.ttf",
        "Bitter-Regular.ttf",
        "Bitter-Bold.ttf",
    ],
)
def test_bundled_fonts_cover_the_complete_vietnamese_alphabet(filename: str) -> None:
    cmap = TTFont(ROOT / filename).getBestCmap()
    missing = [character for character in VIETNAMESE_CHARACTERS if ord(character) not in cmap]
    assert missing == []
