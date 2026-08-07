import unicodedata

from valheim_vn.validation import locked_glossary_errors, validate_translation


def test_preserved_game_tokens_pass() -> None:
    source = "Deal 25% damage to $enemy with <color=yellow>$1</color>."
    target = "Gây 25% sát thương lên $enemy bằng <color=yellow>$1</color>."
    assert validate_translation(source, target).ok


def test_changed_number_fails() -> None:
    result = validate_translation("Adds 10 armor", "Thêm 15 giáp")
    assert not result.ok
    assert any("numeric" in error for error in result.errors)


def test_changed_rich_text_fails() -> None:
    result = validate_translation("<color=yellow>Warning</color>", "<b>Cảnh báo</b>")
    assert not result.ok
    assert any("rich-text" in error for error in result.errors)


def test_non_nfc_fails() -> None:
    decomposed = unicodedata.normalize("NFD", "Tiếng Việt")
    result = validate_translation("Vietnamese", decomposed)
    assert not result.ok
    assert any("NFC" in error for error in result.errors)


def test_literal_ui_arrows_are_not_treated_as_unbalanced_tags() -> None:
    assert validate_translation("<", "<").ok
    assert validate_translation(">", ">").ok


def test_glossary_matches_whole_terms_not_substrings() -> None:
    glossary = [{"source": "Odin", "target": "Odin", "locked": 1}]

    assert locked_glossary_errors("exploding", "đang phát nổ", glossary) == []
    assert locked_glossary_errors("Odin speaks", "Một vị thần lên tiếng", glossary)
