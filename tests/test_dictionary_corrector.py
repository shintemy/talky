import pytest

from talky.dictionary_corrector import apply_phonetic_dictionary, normalize_person_pronouns
from talky.dictionary_entries import extract_person_terms, parse_dictionary_entries

pytest.importorskip("pypinyin")


def test_apply_phonetic_dictionary_replaces_homophone_name() -> None:
    text = "\u521a\u521a\u7ed9\u5706\u5706\u6d17\u4e86\u4e2a\u6fa1\uff0c\u5b83\u6293\u6211\u7684\u624b\u5f88\u75db\u3002"
    dictionary = ["\u6c85\u6c85"]

    corrected = apply_phonetic_dictionary(text, dictionary)

    assert "\u6c85\u6c85" in corrected
    assert "\u5706\u5706" not in corrected


def test_apply_phonetic_dictionary_keeps_unrelated_text() -> None:
    text = "\u4eca\u5929\u51c6\u5907\u6574\u7406\u5f55\u97f3\u8f6f\u4ef6\u7684\u5f00\u6e90\u6587\u6863\u3002"
    dictionary = ["\u6c85\u6c85", "TensorRT"]

    corrected = apply_phonetic_dictionary(text, dictionary)

    assert corrected == text


def test_normalize_person_pronouns_for_person_entries() -> None:
    entries = parse_dictionary_entries(["person:\u6c85\u6c85", "TensorRT"])
    people = extract_person_terms(entries)
    text = (
        "\u521a\u521a\u7ed9\u6c85\u6c85\u6d17\u4e86\u4e2a\u6fa1\uff0c"
        "\u5b83\u6293\u6211\u7684\u624b\u5f88\u75db\u3002"
        "\u4eca\u5929\u5347\u7ea7\u4e86 TensorRT\uff0c\u5b83\u66f4\u5feb\u4e86\u3002"
    )

    corrected = normalize_person_pronouns(text, people)

    assert "\u6c85\u6c85\u6d17\u4e86\u4e2a\u6fa1\uff0c\u4ed6\u6293\u6211\u7684\u624b\u5f88\u75db" in corrected
    assert "TensorRT\uff0c\u5b83\u66f4\u5feb\u4e86" in corrected
