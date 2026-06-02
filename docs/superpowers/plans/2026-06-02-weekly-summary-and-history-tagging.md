# Weekly Auto-Summary + History Dictionary Tagging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add (A) dictionary-based person/term tagging to history entries, and (B) a background weekly auto-summary that turns the previous ISO week's outputs into a named Markdown report via the local Ollama model.

**Architecture:** Part A adds a pure matcher + history metadata fields + a structured reader. Part B adds a self-contained, dependency-injected `talky/weekly_summary.py` orchestrator driven by the controller's existing idle tick, running on a daemon worker thread. No changes to `ui.py` or `talky-server/`.

**Tech Stack:** Python 3.12, PyQt6 (controller signals only), Ollama via existing `OllamaTextCleaner`, pytest. Run tests with `.venv/bin/python -m pytest`.

**Spec:** `docs/superpowers/specs/2026-06-02-weekly-summary-and-history-tagging-design.md`

**Branch:** `claude/blissful-pascal-acf93a` (already checked out).

---

## File Structure

**Create:**
- `talky/weekly_summary.py` — pure helpers (week math, naming, dedup, collection, prompt builders, markdown render, locale→language) + `run_weekly_summary(...)` orchestrator (all deps injected).
- `tests/test_weekly_summary.py`

**Modify:**
- `talky/dictionary_entries.py` — add `match_dictionary_tags(...)`.
- `talky/history_store.py` — add metadata fields, `append` params, metadata rendering, `StructuredHistoryEntry`, `read_structured_entries(...)`.
- `talky/llm_service.py` — add `OllamaTextCleaner.summarize(...)`.
- `talky/controller.py` — compute tags at the `history_store.append` call; add idle-tick weekly-summary hook + worker + state fields + `_summaries_dir`.
- `tests/test_dictionary_entries.py`, `tests/test_history_store.py` — add cases.

**Do NOT touch:** `talky/ui.py`, `talky-server/`, existing `HistoryStore.read_entries` behavior.

---

## Implementation order

Part A first (Task 1→4) because Part B's collection depends on `read_structured_entries`. Then Part B (Task 5→9).

---

## Task 1: `match_dictionary_tags` in dictionary_entries

**Files:**
- Modify: `talky/dictionary_entries.py`
- Test: `tests/test_dictionary_entries.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_dictionary_entries.py`:

```python
from talky.dictionary_entries import match_dictionary_tags, parse_dictionary_entries


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dictionary_entries.py -v`
Expected: FAIL — `ImportError: cannot import name 'match_dictionary_tags'`.

- [ ] **Step 3: Write minimal implementation**

Add to the top imports of `talky/dictionary_entries.py` (after `from dataclasses import dataclass`):

```python
import re
```

Append to `talky/dictionary_entries.py`:

```python
_CJK_RE = re.compile(r"[぀-ヿ㐀-䶿一-鿿豈-﫿]")


def _term_appears(term: str, text: str) -> bool:
    if _CJK_RE.search(term):
        return term in text
    return re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE) is not None


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_dictionary_entries.py -v`
Expected: PASS (all 4 tests).

- [ ] **Step 5: Commit**

```bash
git add talky/dictionary_entries.py tests/test_dictionary_entries.py
git commit -m "feat: add match_dictionary_tags for history tagging"
```

---

## Task 2: History metadata tag fields + rendering

**Files:**
- Modify: `talky/history_store.py` (`HistoryEntryMetadata`, `append`, `_format_metadata_block`)
- Test: `tests/test_history_store.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_history_store.py`:

```python
def test_history_store_renders_dictionary_tags(tmp_path: Path) -> None:
    store = HistoryStore(history_dir=tmp_path / "history")
    day = datetime(2026, 5, 25, 9, 0, 0)

    store.append(
        "张三 部署了 Kubernetes",
        now=day,
        usage_mode="vibecoding",
        asr_language="zh",
        matched_persons=["张三"],
        matched_terms=["Kubernetes"],
    )

    content = (tmp_path / "history" / "2026-05-25.md").read_text(encoding="utf-8")
    assert "人物: 张三" in content
    assert "术语: Kubernetes" in content


def test_history_store_omits_empty_tag_lines(tmp_path: Path) -> None:
    store = HistoryStore(history_dir=tmp_path / "history")
    store.append("没有标签", now=datetime(2026, 5, 25, 9, 0, 0))
    content = (tmp_path / "history" / "2026-05-25.md").read_text(encoding="utf-8")
    assert "人物:" not in content
    assert "术语:" not in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_history_store.py -k dictionary_tags -v`
Expected: FAIL — `TypeError: append() got an unexpected keyword argument 'matched_persons'`.

- [ ] **Step 3: Write minimal implementation**

In `talky/history_store.py`, extend the dataclass (replace the existing `HistoryEntryMetadata`):

```python
@dataclass(frozen=True)
class HistoryEntryMetadata:
    usage_mode: str = ""
    asr_language: str = ""
    translation_output_language: str = ""
    debug_audio_path: str = ""
    matched_persons: tuple[str, ...] = ()
    matched_terms: tuple[str, ...] = ()
```

Update `append(...)` signature — add two keyword params before `debug_audio_path` stays last is fine; add them after it:

```python
    def append(
        self,
        text: str,
        now: datetime | None = None,
        raw_text: str = "",
        *,
        usage_mode: str = "",
        asr_language: str = "",
        translation_output_language: str = "",
        debug_audio_path: str | Path | None = None,
        matched_persons: list[str] | tuple[str, ...] = (),
        matched_terms: list[str] | tuple[str, ...] = (),
    ) -> Path:
```

And inside `append`, update the metadata construction:

```python
        metadata = HistoryEntryMetadata(
            usage_mode=(usage_mode or "").strip(),
            asr_language=(asr_language or "").strip(),
            translation_output_language=(translation_output_language or "").strip(),
            debug_audio_path=self._normalize_debug_audio_path(debug_audio_path),
            matched_persons=tuple(matched_persons),
            matched_terms=tuple(matched_terms),
        )
```

Update `_format_metadata_block` — insert tag lines after the target-language line and before the debug-audio line:

```python
    def _format_metadata_block(self, metadata: HistoryEntryMetadata) -> str:
        lines: list[str] = []
        if metadata.usage_mode:
            lines.append(f"模式: {self._format_usage_mode_label(metadata.usage_mode)}")
        if metadata.asr_language:
            lines.append(f"ASR 语言: {metadata.asr_language}")
        if metadata.usage_mode == "translation" and metadata.translation_output_language:
            lines.append(f"目标语言: {metadata.translation_output_language}")
        if metadata.matched_persons:
            lines.append(f"人物: {', '.join(metadata.matched_persons)}")
        if metadata.matched_terms:
            lines.append(f"术语: {', '.join(metadata.matched_terms)}")
        if metadata.debug_audio_path:
            lines.append(f"调试音频: {metadata.debug_audio_path}")
        if not lines:
            return ""
        return "\n".join(lines) + "\n\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_history_store.py -v`
Expected: PASS (existing + 2 new tests).

- [ ] **Step 5: Commit**

```bash
git add talky/history_store.py tests/test_history_store.py
git commit -m "feat: render dictionary person/term tags in history metadata"
```

---

## Task 3: `read_structured_entries` + `StructuredHistoryEntry`

**Files:**
- Modify: `talky/history_store.py`
- Test: `tests/test_history_store.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_history_store.py`:

```python
from talky.history_store import StructuredHistoryEntry


def test_read_structured_entries_extracts_final_text_and_tags(tmp_path: Path) -> None:
    store = HistoryStore(history_dir=tmp_path / "history")
    day = datetime(2026, 5, 25, 9, 0, 0)
    store.append(
        "整理后的最终文本",
        raw_text="原始识别文本",
        now=day,
        usage_mode="vibecoding",
        asr_language="zh",
        matched_persons=["张三"],
        matched_terms=["Kubernetes"],
    )

    entries = store.read_structured_entries("2026-05-25")
    assert entries == [
        StructuredHistoryEntry(
            time_str="09:00:00",
            usage_mode="vibecoding",
            final_text="整理后的最终文本",
            matched_persons=("张三",),
            matched_terms=("Kubernetes",),
        )
    ]


def test_read_structured_entries_handles_plain_daily_entry(tmp_path: Path) -> None:
    store = HistoryStore(history_dir=tmp_path / "history")
    store.append("纯文本无元数据", now=datetime(2026, 5, 25, 8, 0, 0))

    entries = store.read_structured_entries("2026-05-25")
    assert len(entries) == 1
    assert entries[0].final_text == "纯文本无元数据"
    assert entries[0].usage_mode == ""
    assert entries[0].matched_persons == ()


def test_read_structured_entries_empty_for_missing_date(tmp_path: Path) -> None:
    store = HistoryStore(history_dir=tmp_path / "history")
    assert store.read_structured_entries("2026-01-01") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_history_store.py -k structured -v`
Expected: FAIL — `ImportError: cannot import name 'StructuredHistoryEntry'`.

- [ ] **Step 3: Write minimal implementation**

In `talky/history_store.py`, add the dataclass after `HistoryEntryMetadata`:

```python
@dataclass(frozen=True)
class StructuredHistoryEntry:
    time_str: str
    usage_mode: str
    final_text: str
    matched_persons: tuple[str, ...]
    matched_terms: tuple[str, ...]


_USAGE_MODE_REVERSE = {
    "Daily": "daily",
    "Vibecoding": "vibecoding",
    "Translation": "translation",
}
_KNOWN_META_PREFIXES = (
    "模式: ",
    "ASR 语言: ",
    "目标语言: ",
    "人物: ",
    "术语: ",
    "调试音频: ",
)
```

Add these methods to the `HistoryStore` class (e.g. after `read_entries`):

```python
    def read_structured_entries(self, date_str: str) -> list[StructuredHistoryEntry]:
        """Parse a date's entries into structured records (final text + tags)."""
        result: list[StructuredHistoryEntry] = []
        for time_str, segment in self.read_entries(date_str):
            usage_mode, persons, terms, body = self._parse_segment(segment)
            result.append(
                StructuredHistoryEntry(
                    time_str=time_str,
                    usage_mode=usage_mode,
                    final_text=self._extract_final_output(body),
                    matched_persons=persons,
                    matched_terms=terms,
                )
            )
        return result

    @staticmethod
    def _parse_segment(
        segment: str,
    ) -> tuple[str, tuple[str, ...], tuple[str, ...], str]:
        lines = segment.split("\n")
        usage_mode = ""
        persons: tuple[str, ...] = ()
        terms: tuple[str, ...] = ()
        i = 0
        consumed = False
        while i < len(lines):
            line = lines[i]
            matched_prefix = next(
                (p for p in _KNOWN_META_PREFIXES if line.startswith(p)), None
            )
            if matched_prefix is None:
                break
            value = line[len(matched_prefix):].strip()
            if matched_prefix == "模式: ":
                usage_mode = _USAGE_MODE_REVERSE.get(value, value.lower())
            elif matched_prefix == "人物: ":
                persons = tuple(x.strip() for x in value.split(",") if x.strip())
            elif matched_prefix == "术语: ":
                terms = tuple(x.strip() for x in value.split(",") if x.strip())
            consumed = True
            i += 1
        if consumed:
            while i < len(lines) and lines[i].strip() == "":
                i += 1
        body = "\n".join(lines[i:]).strip()
        return usage_mode, persons, terms, body

    @staticmethod
    def _extract_final_output(body: str) -> str:
        marker = "最终输出"
        if body.startswith(marker):
            inner = body[len(marker):].lstrip("\n")
            idx = inner.find("\n\n原文")
            if idx >= 0:
                inner = inner[:idx]
            return inner.strip()
        return body.strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_history_store.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add talky/history_store.py tests/test_history_store.py
git commit -m "feat: add read_structured_entries for weekly summary input"
```

---

## Task 4: Controller computes tags at append site

**Files:**
- Modify: `talky/controller.py` (imports + new helper + the `history_store.append` call ~line 1024)
- Test: `tests/test_controller_hotkey_threading.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_controller_hotkey_threading.py`:

```python
def test_compute_history_tags_matches_dictionary(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = _build_controller()
    controller.settings.custom_dictionary = ["[person]张三", "Kubernetes"]

    persons, terms = controller._compute_history_tags("张三 部署 Kubernetes")

    assert persons == ["张三"]
    assert terms == ["Kubernetes"]


def test_compute_history_tags_empty_dictionary() -> None:
    controller = _build_controller()
    controller.settings.custom_dictionary = []
    assert controller._compute_history_tags("anything") == ([], [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_controller_hotkey_threading.py -k compute_history_tags -v`
Expected: FAIL — `AttributeError: 'AppController' object has no attribute '_compute_history_tags'`.

- [ ] **Step 3: Write minimal implementation**

In `talky/controller.py`, extend the dictionary import (around line 20-25) to include `match_dictionary_tags`:

```python
from talky.dictionary_corrector import apply_phonetic_dictionary, normalize_person_pronouns
from talky.dictionary_entries import (
    extract_person_terms,
    extract_terms,
    match_dictionary_tags,
    parse_dictionary_entries,
)
```

Add this method to `AppController` (e.g. just above `_process_pipeline`):

```python
    def _compute_history_tags(self, final_text: str) -> tuple[list[str], list[str]]:
        entries = parse_dictionary_entries(self.settings.custom_dictionary)
        return match_dictionary_tags(final_text, entries)
```

In `_process_pipeline`, update the `history_store.append(...)` call (currently ~line 1024) to compute and pass tags:

```python
            matched_persons, matched_terms = self._compute_history_tags(final_text)
            history_path = self.history_store.append(
                final_text,
                raw_text=raw_text,
                usage_mode=self.settings.usage_mode,
                asr_language=self.settings.language,
                translation_output_language=self.settings.translation_output_language,
                debug_audio_path=debug_audio_path,
                matched_persons=matched_persons,
                matched_terms=matched_terms,
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_controller_hotkey_threading.py -k compute_history_tags -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add talky/controller.py tests/test_controller_hotkey_threading.py
git commit -m "feat: tag history entries with dictionary persons/terms"
```

---

## Task 5: weekly_summary pure helpers (week math, naming, dedup, locale)

**Files:**
- Create: `talky/weekly_summary.py`
- Test: `tests/test_weekly_summary.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_weekly_summary.py`:

```python
from __future__ import annotations

from datetime import date
from pathlib import Path

from talky.weekly_summary import (
    is_week_summarized,
    previous_iso_week_range,
    summary_filename,
    summary_language_for_locale,
    summary_path,
)


def test_previous_iso_week_range_midweek() -> None:
    # 2026-06-02 is a Tuesday; previous week is Mon 2026-05-25 .. Sun 2026-05-31
    start, end = previous_iso_week_range(date(2026, 6, 2))
    assert start == date(2026, 5, 25)
    assert end == date(2026, 5, 31)


def test_previous_iso_week_range_on_monday() -> None:
    start, end = previous_iso_week_range(date(2026, 6, 1))  # Monday
    assert start == date(2026, 5, 25)
    assert end == date(2026, 5, 31)


def test_previous_iso_week_range_crosses_year() -> None:
    start, end = previous_iso_week_range(date(2026, 1, 1))  # Thursday
    assert start == date(2025, 12, 22)
    assert end == date(2025, 12, 28)


def test_summary_filename_and_path() -> None:
    start, end = date(2026, 5, 25), date(2026, 5, 31)
    assert summary_filename(start, end) == "summary-2026-05-25_2026-05-31.md"
    assert summary_path(Path("/tmp/s"), start, end) == Path(
        "/tmp/s/summary-2026-05-25_2026-05-31.md"
    )


def test_is_week_summarized(tmp_path: Path) -> None:
    start, end = date(2026, 5, 25), date(2026, 5, 31)
    assert is_week_summarized(tmp_path, start, end) is False
    summary_path(tmp_path, start, end).write_text("x", encoding="utf-8")
    assert is_week_summarized(tmp_path, start, end) is True


def test_is_week_summarized_empty_file_is_not_done(tmp_path: Path) -> None:
    start, end = date(2026, 5, 25), date(2026, 5, 31)
    summary_path(tmp_path, start, end).write_text("", encoding="utf-8")
    assert is_week_summarized(tmp_path, start, end) is False


def test_summary_language_for_locale() -> None:
    assert summary_language_for_locale("mixed") == "zh"
    assert summary_language_for_locale("en") == "en"
    assert summary_language_for_locale("something-future") == "en"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_weekly_summary.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'talky.weekly_summary'`.

- [ ] **Step 3: Write minimal implementation**

Create `talky/weekly_summary.py`:

```python
from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path


def previous_iso_week_range(today: date) -> tuple[date, date]:
    """Return (Monday, Sunday) of the ISO week before today's week."""
    this_monday = today - timedelta(days=today.weekday())
    prev_monday = this_monday - timedelta(days=7)
    return prev_monday, prev_monday + timedelta(days=6)


def summary_filename(start: date, end: date) -> str:
    return f"summary-{start:%Y-%m-%d}_{end:%Y-%m-%d}.md"


def summary_path(summaries_dir: Path, start: date, end: date) -> Path:
    return summaries_dir / summary_filename(start, end)


def is_week_summarized(summaries_dir: Path, start: date, end: date) -> bool:
    path = summary_path(summaries_dir, start, end)
    try:
        return path.exists() and path.stat().st_size > 0
    except OSError:
        return False


def summary_language_for_locale(ui_locale: str) -> str:
    """Map UI locale to summary language code. Extend here for new locales."""
    return "zh" if ui_locale == "mixed" else "en"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_weekly_summary.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add talky/weekly_summary.py tests/test_weekly_summary.py
git commit -m "feat: weekly_summary week-range/naming/dedup/locale helpers"
```

---

## Task 6: `OllamaTextCleaner.summarize`

**Files:**
- Modify: `talky/llm_service.py`
- Test: `tests/test_llm_service.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_llm_service.py`:

```python
from talky.llm_service import OllamaTextCleaner


def test_summarize_accumulates_and_sanitizes(monkeypatch) -> None:
    cleaner = OllamaTextCleaner(model_name="test-model")

    captured: dict = {}

    def fake_chat(*, messages, think, stream, options):
        captured["messages"] = messages
        captured["options"] = options
        return [
            {"message": {"content": "本周"}},
            {"message": {"content": "概览<channel|>真正概览"}},
        ]

    monkeypatch.setattr(cleaner, "_chat_with_fallback", fake_chat)

    out = cleaner.summarize("一些内容", system_prompt="你是助理")

    assert out == "真正概览"  # text after <channel|> only
    assert captured["messages"][0] == {"role": "system", "content": "你是助理"}
    assert captured["messages"][1] == {"role": "user", "content": "一些内容"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_llm_service.py -k summarize -v`
Expected: FAIL — `AttributeError: 'OllamaTextCleaner' object has no attribute 'summarize'`.

- [ ] **Step 3: Write minimal implementation**

Add this method to `OllamaTextCleaner` in `talky/llm_service.py` (e.g. after `rewrite_selected_text`):

```python
    def summarize(
        self, content: str, *, system_prompt: str, num_predict: int = 600
    ) -> str:
        stream = self._chat_with_fallback(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            think=False,
            stream=True,
            options={"temperature": 0.3, "num_predict": num_predict, "top_p": 0.9},
        )
        parts: list[str] = []
        for chunk in stream:
            piece = chunk.get("message", {}).get("content", "") or ""
            if piece:
                parts.append(piece)
        return _sanitize_llm_surface_text("".join(parts).strip())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_llm_service.py -k summarize -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add talky/llm_service.py tests/test_llm_service.py
git commit -m "feat: add OllamaTextCleaner.summarize for weekly reports"
```

---

## Task 7: weekly_summary collection, prompts, markdown render

**Files:**
- Modify: `talky/weekly_summary.py`
- Test: `tests/test_weekly_summary.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_weekly_summary.py`:

```python
from datetime import date as _date

from talky.history_store import StructuredHistoryEntry
from talky.weekly_summary import (
    DayOutputs,
    collect_week_outputs,
    render_summary_markdown,
)


def _entry(t: str, mode: str, text: str) -> StructuredHistoryEntry:
    return StructuredHistoryEntry(
        time_str=t, usage_mode=mode, final_text=text, matched_persons=(), matched_terms=()
    )


def test_collect_week_outputs_skips_empty_days_and_sorts(tmp_path) -> None:
    data = {
        "2026-05-25": [_entry("11:00:00", "daily", "b"), _entry("09:00:00", "daily", "a")],
        "2026-05-27": [],
        "2026-05-28": [_entry("10:00:00", "vibecoding", "c")],
    }

    def fake_read(date_str: str):
        return list(data.get(date_str, []))

    days = collect_week_outputs(fake_read, _date(2026, 5, 25), _date(2026, 5, 31))

    assert [d.day for d in days] == [_date(2026, 5, 25), _date(2026, 5, 28)]
    # sorted ascending by time_str within a day
    assert [e.final_text for e in days[0].entries] == ["a", "b"]


def test_render_summary_markdown_zh() -> None:
    days = [
        ("2026-05-25", _date(2026, 5, 25), "周一小结"),
        ("2026-05-28", _date(2026, 5, 28), "周四小结"),
    ]
    md = render_summary_markdown(
        start=_date(2026, 5, 25),
        end=_date(2026, 5, 31),
        overview="本周概览内容",
        day_summaries=[(d[1], d[2]) for d in days],
        total_entries=5,
        lang="zh",
        now_text="2026-06-01 09:00",
        model_name="qwen3.5:9b",
    )
    assert md.startswith("# 周报 2026-05-25 ~ 2026-05-31")
    assert "## 概览" in md
    assert "本周概览内容" in md
    assert "## 按天" in md
    assert "### 05-25 周一" in md
    assert "周一小结" in md
    assert "### 05-28 周四" in md
    assert "共 5 条输出 / 覆盖 2 天" in md


def test_render_summary_markdown_en() -> None:
    md = render_summary_markdown(
        start=_date(2026, 5, 25),
        end=_date(2026, 5, 31),
        overview="overview body",
        day_summaries=[(_date(2026, 5, 25), "monday digest")],
        total_entries=1,
        lang="en",
        now_text="2026-06-01 09:00",
        model_name="qwen3.5:9b",
    )
    assert md.startswith("# Weekly Report 2026-05-25 ~ 2026-05-31")
    assert "## Overview" in md
    assert "## By Day" in md
    assert "### 05-25 Mon" in md
    assert "1 outputs / 1 days" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_weekly_summary.py -k "collect or render" -v`
Expected: FAIL — `ImportError: cannot import name 'DayOutputs'`.

- [ ] **Step 3: Write minimal implementation**

Add to `talky/weekly_summary.py` — imports at top:

```python
from collections.abc import Callable
from dataclasses import dataclass

from talky.history_store import StructuredHistoryEntry
```

Then append:

```python
_WEEKDAYS = {
    "zh": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
}
_LABELS = {
    "zh": {"title": "周报", "overview": "概览", "byday": "按天"},
    "en": {"title": "Weekly Report", "overview": "Overview", "byday": "By Day"},
}


@dataclass(frozen=True)
class DayOutputs:
    day: date
    entries: list[StructuredHistoryEntry]


def collect_week_outputs(
    read_structured: Callable[[str], list[StructuredHistoryEntry]],
    start: date,
    end: date,
) -> list[DayOutputs]:
    days: list[DayOutputs] = []
    current = start
    while current <= end:
        entries = [
            e
            for e in read_structured(current.strftime("%Y-%m-%d"))
            if e.final_text.strip()
        ]
        if entries:
            entries.sort(key=lambda e: e.time_str)
            days.append(DayOutputs(day=current, entries=entries))
        current += timedelta(days=1)
    return days


def _weekday_label(day: date, lang: str) -> str:
    return _WEEKDAYS.get(lang, _WEEKDAYS["en"])[day.weekday()]


def build_day_system_prompt(lang: str) -> str:
    if lang == "zh":
        return (
            "你是简洁的中文助理。下面是用户某一天的语音转写最终输出（按时间排列）。"
            "请整理成 3-6 条要点小结，只基于给定内容，不要新增建议或评论，不要编造。"
            "直接输出中文要点，每条一行。"
        )
    return (
        "You are a concise assistant. Below are the user's final dictation outputs "
        "for a single day (in time order). Summarize them into 3-6 bullet points. "
        "Use only the given content; do not add advice or fabricate. Output English "
        "bullets, one per line."
    )


def build_day_user_content(day: DayOutputs, lang: str) -> str:
    header = f"{day.day:%Y-%m-%d} {_weekday_label(day.day, lang)}"
    lines = [header]
    for entry in day.entries:
        mode = f" [{entry.usage_mode}]" if entry.usage_mode else ""
        lines.append(f"- {entry.time_str}{mode} {entry.final_text}")
    return "\n".join(lines)


def build_reduce_system_prompt(lang: str) -> str:
    if lang == "zh":
        return (
            "你是简洁的中文助理。下面是用户上一周每天的内容小结。"
            "请综合成一段本周概览（3-6 句），概括主要主题、进展与重点。"
            "只基于给定内容，不要编造。直接输出中文。"
        )
    return (
        "You are a concise assistant. Below are per-day digests of the user's last "
        "week. Write a single weekly overview (3-6 sentences) covering the main "
        "themes, progress, and highlights. Use only the given content; do not "
        "fabricate. Output English."
    )


def build_reduce_user_content(
    day_summaries: list[tuple[date, str]], start: date, end: date, lang: str
) -> str:
    blocks = [f"{start:%Y-%m-%d} ~ {end:%Y-%m-%d}"]
    for day, summary in day_summaries:
        blocks.append(f"{day:%Y-%m-%d} {_weekday_label(day, lang)}:\n{summary}")
    return "\n\n".join(blocks)


def render_summary_markdown(
    *,
    start: date,
    end: date,
    overview: str,
    day_summaries: list[tuple[date, str]],
    total_entries: int,
    lang: str,
    now_text: str,
    model_name: str,
) -> str:
    labels = _LABELS.get(lang, _LABELS["en"])
    days_count = len(day_summaries)
    if lang == "zh":
        meta = (
            f"> 生成于 {now_text} · 模型 {model_name} · "
            f"共 {total_entries} 条输出 / 覆盖 {days_count} 天"
        )
    else:
        meta = (
            f"> Generated {now_text} · model {model_name} · "
            f"{total_entries} outputs / {days_count} days"
        )
    parts = [
        f"# {labels['title']} {start:%Y-%m-%d} ~ {end:%Y-%m-%d}",
        "",
        meta,
        "",
        f"## {labels['overview']}",
        "",
        overview.strip(),
        "",
        f"## {labels['byday']}",
    ]
    for day, summary in day_summaries:
        parts.append("")
        parts.append(f"### {day:%m-%d} {_weekday_label(day, lang)}")
        parts.append("")
        parts.append(summary.strip())
    return "\n".join(parts) + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_weekly_summary.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add talky/weekly_summary.py tests/test_weekly_summary.py
git commit -m "feat: weekly_summary collection, prompts, and markdown render"
```

---

## Task 8: `run_weekly_summary` orchestrator

**Files:**
- Modify: `talky/weekly_summary.py`
- Test: `tests/test_weekly_summary.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_weekly_summary.py`:

```python
from talky.weekly_summary import run_weekly_summary


def _ok_run(**overrides):
    """Build default args for run_weekly_summary; override as needed."""
    data = {
        "2026-05-25": [_entry("09:00:00", "daily", "a")],
        "2026-05-26": [_entry("09:00:00", "vibecoding", "b")],
    }
    args = dict(
        today=_date(2026, 6, 2),
        summaries_dir=overrides.pop("summaries_dir"),
        read_structured=lambda d: list(data.get(d, [])),
        summarize=lambda content, system_prompt: f"SUM[{content[:6]}]",
        is_ready=lambda: True,
        should_abort=lambda: False,
        ui_locale="mixed",
        model_name="qwen3.5:9b",
        now_text="2026-06-01 09:00",
    )
    args.update(overrides)
    return args


def test_run_weekly_summary_writes_file(tmp_path) -> None:
    path = run_weekly_summary(**_ok_run(summaries_dir=tmp_path))
    assert path is not None
    assert path == tmp_path / "summary-2026-05-25_2026-05-31.md"
    content = path.read_text(encoding="utf-8")
    assert "# 周报 2026-05-25 ~ 2026-05-31" in content
    assert "共 2 条输出 / 覆盖 2 天" in content
    # no leftover temp file
    assert list(tmp_path.glob("*.tmp")) == []


def test_run_weekly_summary_skips_when_already_done(tmp_path) -> None:
    (tmp_path / "summary-2026-05-25_2026-05-31.md").write_text("x", encoding="utf-8")
    called = {"n": 0}

    def counting_summarize(content, system_prompt):
        called["n"] += 1
        return "x"

    path = run_weekly_summary(
        **_ok_run(summaries_dir=tmp_path, summarize=counting_summarize)
    )
    assert path is None
    assert called["n"] == 0


def test_run_weekly_summary_skips_when_not_ready(tmp_path) -> None:
    path = run_weekly_summary(**_ok_run(summaries_dir=tmp_path, is_ready=lambda: False))
    assert path is None
    assert list(tmp_path.glob("*.md")) == []


def test_run_weekly_summary_skips_empty_week(tmp_path) -> None:
    path = run_weekly_summary(
        **_ok_run(summaries_dir=tmp_path, read_structured=lambda d: [])
    )
    assert path is None
    assert list(tmp_path.glob("*.md")) == []


def test_run_weekly_summary_aborts_without_writing(tmp_path) -> None:
    path = run_weekly_summary(
        **_ok_run(summaries_dir=tmp_path, should_abort=lambda: True)
    )
    assert path is None
    assert list(tmp_path.glob("*.md")) == []


def test_run_weekly_summary_does_not_write_on_summarize_error(tmp_path) -> None:
    def boom(content, system_prompt):
        raise RuntimeError("llm down")

    try:
        run_weekly_summary(**_ok_run(summaries_dir=tmp_path, summarize=boom))
    except RuntimeError:
        pass
    assert list(tmp_path.glob("*.md")) == []
    assert list(tmp_path.glob("*.tmp")) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_weekly_summary.py -k run_weekly -v`
Expected: FAIL — `ImportError: cannot import name 'run_weekly_summary'`.

- [ ] **Step 3: Write minimal implementation**

Add to `talky/weekly_summary.py` — extend the top imports:

```python
from talky.task_timeout import run_with_timeout
```

Then append:

```python
def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def run_weekly_summary(
    *,
    today: date,
    summaries_dir: Path,
    read_structured: Callable[[str], list[StructuredHistoryEntry]],
    summarize: Callable[[str, str], str],
    is_ready: Callable[[], bool],
    should_abort: Callable[[], bool],
    ui_locale: str,
    model_name: str,
    now_text: str,
    log: Callable[[str], None] = lambda _msg: None,
    day_timeout_s: float = 60.0,
    reduce_timeout_s: float = 90.0,
) -> Path | None:
    """Generate last week's summary markdown. Return path, or None when skipped."""
    start, end = previous_iso_week_range(today)
    target = summary_path(summaries_dir, start, end)

    if is_week_summarized(summaries_dir, start, end):
        return None
    if not is_ready():
        log("weekly summary skipped: LLM not ready")
        return None

    days = collect_week_outputs(read_structured, start, end)
    if not days:
        log("weekly summary skipped: no entries last week")
        return None

    lang = summary_language_for_locale(ui_locale)
    day_system = build_day_system_prompt(lang)
    day_summaries: list[tuple[date, str]] = []
    for day in days:
        if should_abort():
            log("weekly summary aborted before day map")
            return None
        content = build_day_user_content(day, lang)
        summary = run_with_timeout(
            lambda c=content: summarize(c, day_system),
            day_timeout_s,
            label="weekly day summary",
        )
        day_summaries.append((day.day, summary.strip()))

    if should_abort():
        log("weekly summary aborted before reduce")
        return None

    reduce_system = build_reduce_system_prompt(lang)
    reduce_content = build_reduce_user_content(day_summaries, start, end, lang)
    overview = run_with_timeout(
        lambda: summarize(reduce_content, reduce_system),
        reduce_timeout_s,
        label="weekly reduce",
    )

    total_entries = sum(len(d.entries) for d in days)
    markdown = render_summary_markdown(
        start=start,
        end=end,
        overview=overview,
        day_summaries=day_summaries,
        total_entries=total_entries,
        lang=lang,
        now_text=now_text,
        model_name=model_name,
    )
    _atomic_write(target, markdown)
    log(f"weekly summary written: {target}")
    return target
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_weekly_summary.py -v`
Expected: PASS (all weekly_summary tests).

- [ ] **Step 5: Commit**

```bash
git add talky/weekly_summary.py tests/test_weekly_summary.py
git commit -m "feat: run_weekly_summary orchestrator (map-reduce, atomic write)"
```

---

## Task 9: Controller idle-tick trigger + worker

**Files:**
- Modify: `talky/controller.py` (imports, `__init__` state, idle-tick hook, gating method, worker)
- Test: `tests/test_controller_hotkey_threading.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_controller_hotkey_threading.py`:

```python
from datetime import date


def test_maybe_run_weekly_summary_spawns_worker_when_due(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = _build_controller()
    controller._summaries_dir = tmp_path
    controller._last_weekly_summary_check_ts = 0.0

    called: list = []
    monkeypatch.setattr(
        controller, "_run_weekly_summary_async", lambda today: called.append(today)
    )

    controller._maybe_run_weekly_summary(time.monotonic())
    _wait_until(lambda: len(called) == 1)

    assert controller._weekly_summary_in_progress is True


def test_maybe_run_weekly_summary_skips_when_already_summarized(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from talky.weekly_summary import previous_iso_week_range, summary_path

    controller = _build_controller()
    controller._summaries_dir = tmp_path
    controller._last_weekly_summary_check_ts = 0.0
    start, end = previous_iso_week_range(date.today())
    summary_path(tmp_path, start, end).write_text("done", encoding="utf-8")

    called: list = []
    monkeypatch.setattr(
        controller, "_run_weekly_summary_async", lambda today: called.append(today)
    )

    controller._maybe_run_weekly_summary(time.monotonic())
    time.sleep(0.05)
    _app.processEvents()

    assert called == []
    assert controller._weekly_summary_in_progress is False


def test_maybe_run_weekly_summary_skips_when_in_progress(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = _build_controller()
    controller._summaries_dir = tmp_path
    controller._last_weekly_summary_check_ts = 0.0
    controller._weekly_summary_in_progress = True

    called: list = []
    monkeypatch.setattr(
        controller, "_run_weekly_summary_async", lambda today: called.append(today)
    )

    controller._maybe_run_weekly_summary(time.monotonic())
    assert called == []


def test_run_weekly_summary_async_resets_flag_and_notifies(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = _build_controller()
    controller._summaries_dir = tmp_path
    controller._weekly_summary_in_progress = True

    monkeypatch.setattr(
        "talky.controller.run_weekly_summary",
        lambda **kwargs: tmp_path / "summary-x.md",
    )
    statuses: list[str] = []
    controller.status_signal.connect(statuses.append)

    controller._run_weekly_summary_async(date(2026, 6, 2))
    _app.processEvents()

    assert controller._weekly_summary_in_progress is False
    assert any("summary-x.md" in s for s in statuses)


def test_run_weekly_summary_async_resets_flag_on_error(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = _build_controller()
    controller._summaries_dir = tmp_path
    controller._weekly_summary_in_progress = True

    def boom(**kwargs):
        raise RuntimeError("nope")

    monkeypatch.setattr("talky.controller.run_weekly_summary", boom)

    controller._run_weekly_summary_async(date(2026, 6, 2))
    assert controller._weekly_summary_in_progress is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_controller_hotkey_threading.py -k weekly_summary -v`
Expected: FAIL — `AttributeError: 'AppController' object has no attribute '_maybe_run_weekly_summary'`.

- [ ] **Step 3: Write minimal implementation**

In `talky/controller.py`, add imports near the other `talky.*` imports:

```python
from talky.models import AppSettings, SESSION_START_USAGE_MODE, list_ollama_models
from talky.weekly_summary import (
    is_week_summarized,
    previous_iso_week_range,
    run_weekly_summary,
)
```

(The existing `from talky.models import AppSettings, SESSION_START_USAGE_MODE` line is replaced by the version above that adds `list_ollama_models`.)

Add a module-level constant near the other interval constants (around line 67):

```python
_WEEKLY_SUMMARY_CHECK_INTERVAL_S = 30 * 60
```

In `AppController.__init__`, add state fields (e.g. near `self._last_periodic_maintenance_ts`):

```python
        self._summaries_dir = Path.home() / ".talky" / "summaries"
        self._last_weekly_summary_check_ts = 0.0
        self._weekly_summary_in_progress = False
```

In `_on_wake_guard_tick`, find the idle branch (currently):

```python
        if not self._is_recording and not self._is_processing:
            self._maybe_run_periodic_maintenance(now)
```

and add the weekly-summary call inside the same branch:

```python
        if not self._is_recording and not self._is_processing:
            self._maybe_run_periodic_maintenance(now)
            self._maybe_run_weekly_summary(now)
```

Add these methods to `AppController` (e.g. after `_run_periodic_maintenance`):

```python
    def _maybe_run_weekly_summary(self, now_ts: float) -> None:
        if self._weekly_summary_in_progress:
            return
        if (now_ts - self._last_weekly_summary_check_ts) < _WEEKLY_SUMMARY_CHECK_INTERVAL_S:
            return
        self._last_weekly_summary_check_ts = now_ts
        from datetime import date

        today = date.today()
        start, end = previous_iso_week_range(today)
        if is_week_summarized(self._summaries_dir, start, end):
            return
        self._weekly_summary_in_progress = True
        worker = threading.Thread(
            target=self._run_weekly_summary_async,
            args=(today,),
            daemon=True,
        )
        worker.start()

    def _weekly_summary_is_ready(self) -> bool:
        if self.is_cloud_mode:
            return False
        if self.settings.mode not in {"local", "remote"}:
            return False
        models = list_ollama_models(os.environ.get("OLLAMA_HOST", ""))
        return bool(models) and self.settings.ollama_model in models

    def _run_weekly_summary_async(self, today) -> None:
        try:
            path = run_weekly_summary(
                today=today,
                summaries_dir=self._summaries_dir,
                read_structured=self.history_store.read_structured_entries,
                summarize=lambda content, system_prompt: self.llm.summarize(
                    content, system_prompt=system_prompt
                ),
                is_ready=self._weekly_summary_is_ready,
                should_abort=lambda: self._is_recording or self._is_processing,
                ui_locale=self.settings.ui_locale,
                model_name=self.settings.ollama_model,
                now_text=datetime.now().strftime("%Y-%m-%d %H:%M"),
                log=append_debug_log,
            )
            if path is not None:
                self.status_signal.emit(f"Weekly summary generated: {path}")
        except Exception as exc:
            append_debug_log("weekly summary worker failed", exc=exc)
        finally:
            self._weekly_summary_in_progress = False
```

> Note: `append_debug_log` and `datetime` are already imported at the top of `controller.py`; `os` and `threading` are already imported.

- [ ] **Step 4: Run the new tests**

Run: `.venv/bin/python -m pytest tests/test_controller_hotkey_threading.py -k weekly_summary -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add talky/controller.py tests/test_controller_hotkey_threading.py
git commit -m "feat: trigger weekly summary from controller idle tick"
```

---

## Task 10: Full suite + manual sanity

**Files:** none (verification only)

- [ ] **Step 1: Run the entire test suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS (all tests, including pre-existing).

- [ ] **Step 2: Manual smoke (optional, requires Ollama running with the configured model)**

This forces a one-off run by faking "last week" content and an empty summaries dir:

```bash
.venv/bin/python - <<'PY'
from datetime import date
from pathlib import Path
from talky.history_store import StructuredHistoryEntry
from talky.weekly_summary import run_weekly_summary, previous_iso_week_range
from talky.llm_service import OllamaTextCleaner

out = Path.home() / ".talky" / "summaries-smoke"
def read(d):
    s, e = previous_iso_week_range(date.today())
    if d == s.strftime("%Y-%m-%d"):
        return [StructuredHistoryEntry("09:00:00", "daily", "今天写了周报功能的设计", (), ())]
    return []

llm = OllamaTextCleaner(model_name="qwen3.5:4b")  # use a model you have
p = run_weekly_summary(
    today=date.today(), summaries_dir=out, read_structured=read,
    summarize=lambda c, sp: llm.summarize(c, system_prompt=sp),
    is_ready=lambda: True, should_abort=lambda: False,
    ui_locale="mixed", model_name="qwen3.5:4b", now_text="smoke",
    log=print,
)
print("WROTE:", p)
print((p).read_text(encoding="utf-8") if p else "(skipped)")
PY
```

Expected: prints a written path and a Chinese `# 周报 ...` document. Delete `~/.talky/summaries-smoke` afterward.

- [ ] **Step 3: Final commit (if any cleanup)**

```bash
git add -A
git commit -m "chore: weekly summary + history tagging cleanup" || echo "nothing to commit"
```

---

## Notes for the implementer

- **TDD:** every task writes the test first, watches it fail, then implements. Do not skip the "verify it fails" step.
- **`.venv` Python:** always use `.venv/bin/python -m pytest ...` (the repo's venv).
- **No `ui.py` / `talky-server/` edits** — if a task seems to need them, stop and re-read the spec.
- **Cloud mode is intentionally skipped** (`_weekly_summary_is_ready` returns False) — not a bug.
- **`should_abort`** is checked between LLM steps; a long week may take many seconds — that's expected, it runs on a daemon thread and yields to recording.
```
