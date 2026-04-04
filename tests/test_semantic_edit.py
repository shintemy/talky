from talky.semantic_edit import looks_like_edit_instruction


def test_looks_like_edit_instruction_for_cjk_replacement() -> None:
    assert looks_like_edit_instruction("周四改成周五")


def test_looks_like_edit_instruction_for_english_pattern() -> None:
    assert looks_like_edit_instruction("change Thursday to Friday")


def test_looks_like_edit_instruction_rejects_regular_sentence() -> None:
    assert not looks_like_edit_instruction("我周四去找你")
