from talky.dictionary_entries import extract_person_terms, extract_terms, match_dictionary_tags, parse_dictionary_entries


def test_parse_dictionary_entries_supports_person_label() -> None:
    entries = parse_dictionary_entries(["person:Tom", "TensorRT", "[person]Alice"])

    assert extract_terms(entries) == ["Tom", "TensorRT", "Alice"]
    assert extract_person_terms(entries) == ["Tom", "Alice"]


def test_match_dictionary_tags_splits_person_and_term() -> None:
    entries = parse_dictionary_entries(["[person]张三", "Kubernetes", "person:李四"])
    persons, terms = match_dictionary_tags("今天张三和我讨论了 Kubernetes 部署", entries)

    assert persons == ["张三"]
    assert terms == ["Kubernetes"]


def test_match_dictionary_tags_ascii_uses_word_boundary() -> None:
    entries = parse_dictionary_entries(["go"])
    # "go" must NOT match inside "google"
    _persons, terms = match_dictionary_tags("I love google", entries)
    assert terms == []

    _persons2, terms2 = match_dictionary_tags("let's go now", entries)
    assert terms2 == ["go"]


def test_match_dictionary_tags_dedupes_and_keeps_dictionary_order() -> None:
    entries = parse_dictionary_entries(["Redis", "[person]张三", "Redis"])
    persons, terms = match_dictionary_tags("张三 用 Redis 又 Redis", entries)
    assert persons == ["张三"]
    assert terms == ["Redis"]


def test_match_dictionary_tags_ascii_special_char_terms() -> None:
    entries = parse_dictionary_entries(["C++", "C#"])
    _persons, terms = match_dictionary_tags("I write C++ and C# code", entries)
    assert terms == ["C++", "C#"]
