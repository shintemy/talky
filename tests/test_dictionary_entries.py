from talky.dictionary_entries import extract_person_terms, extract_terms, parse_dictionary_entries


def test_parse_dictionary_entries_supports_person_label() -> None:
    entries = parse_dictionary_entries(["person:Tom", "TensorRT", "[person]Alice"])

    assert extract_terms(entries) == ["Tom", "TensorRT", "Alice"]
    assert extract_person_terms(entries) == ["Tom", "Alice"]
