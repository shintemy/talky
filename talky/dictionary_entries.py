from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DictionaryEntry:
    term: str
    kind: str = "term"  # "term" | "person"


_PERSON_LABELS = {"\u4eba\u540d", "\u59d3\u540d", "person", "name"}


def parse_dictionary_entries(lines: list[str]) -> list[DictionaryEntry]:
    entries: list[DictionaryEntry] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        entry = _parse_line(line)
        if entry is not None:
            entries.append(entry)
    return entries


def extract_terms(entries: list[DictionaryEntry]) -> list[str]:
    return [entry.term for entry in entries if entry.term]


def extract_person_terms(entries: list[DictionaryEntry]) -> list[str]:
    return [entry.term for entry in entries if entry.kind == "person" and entry.term]


def _parse_line(line: str) -> DictionaryEntry | None:
    if line.startswith("[") and "]" in line:
        right = line.find("]")
        label = line[1:right].strip().lower()
        term = line[right + 1 :].strip()
        if not term:
            return None
        return DictionaryEntry(term=term, kind="person" if label in _PERSON_LABELS else "term")

    for sep in ("：", ":"):
        if sep not in line:
            continue
        label, term = line.split(sep, 1)
        label = label.strip().lower()
        term = term.strip()
        if not term:
            return None
        return DictionaryEntry(term=term, kind="person" if label in _PERSON_LABELS else "term")

    return DictionaryEntry(term=line, kind="term")
