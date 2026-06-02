from __future__ import annotations

import re
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


_CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def _term_appears(term: str, text: str) -> bool:
    if _CJK_RE.search(term):
        return term in text
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.IGNORECASE) is not None


def match_dictionary_tags(
    text: str, entries: list[DictionaryEntry]
) -> tuple[list[str], list[str]]:
    """Return (matched_persons, matched_terms) that appear in text.

    person = entry.kind == "person"; term = otherwise. CJK terms match by
    substring; pure-ASCII terms match on word boundaries (case-insensitive).
    De-duplicated, preserving dictionary order.
    """
    persons: list[str] = []
    terms: list[str] = []
    seen_persons: set[str] = set()
    seen_terms: set[str] = set()
    for entry in entries:
        term = entry.term
        if not term or not _term_appears(term, text):
            continue
        if entry.kind == "person":
            if term not in seen_persons:
                seen_persons.add(term)
                persons.append(term)
        elif term not in seen_terms:
            seen_terms.add(term)
            terms.append(term)
    return persons, terms
