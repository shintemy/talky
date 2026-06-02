from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class HistoryEntryMetadata:
    usage_mode: str = ""
    asr_language: str = ""
    translation_output_language: str = ""
    debug_audio_path: str = ""
    matched_persons: tuple[str, ...] = ()
    matched_terms: tuple[str, ...] = ()


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


class HistoryStore:
    def __init__(self, history_dir: Path) -> None:
        self.history_dir = history_dir

    def migrate_from(self, legacy_dirs: list[Path]) -> bool:
        """
        Copy legacy markdown history files into current history_dir once.
        Returns True if any file was migrated.
        """
        migrated = False
        self.history_dir.mkdir(parents=True, exist_ok=True)
        for legacy_dir in legacy_dirs:
            if legacy_dir.resolve() == self.history_dir.resolve():
                continue
            if not legacy_dir.exists() or not legacy_dir.is_dir():
                continue
            for src in legacy_dir.glob("*.md"):
                dst = self.history_dir / src.name
                if dst.exists():
                    continue
                try:
                    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
                    migrated = True
                except Exception:
                    continue
        return migrated

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
        timestamp = now or datetime.now()
        self.history_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.history_dir / f"{timestamp:%Y-%m-%d}.md"
        metadata = HistoryEntryMetadata(
            usage_mode=(usage_mode or "").strip(),
            asr_language=(asr_language or "").strip(),
            translation_output_language=(translation_output_language or "").strip(),
            debug_audio_path=self._normalize_debug_audio_path(debug_audio_path),
            matched_persons=tuple(matched_persons),
            matched_terms=tuple(matched_terms),
        )
        entry = self._format_entry(
            text=text,
            timestamp=timestamp,
            raw_text=raw_text,
            metadata=metadata,
        )
        with file_path.open("a", encoding="utf-8") as f:
            f.write(entry)
        return file_path

    def list_dates(self) -> list[str]:
        """Return date strings (YYYY-MM-DD) sorted newest first."""
        if not self.history_dir.exists():
            return []
        files = sorted(self.history_dir.glob("*.md"), reverse=True)
        return [f.stem for f in files]

    def read_entries(self, date_str: str) -> list[tuple[str, str]]:
        """Return (time_str, text) tuples for a given date, newest first."""
        file_path = self.history_dir / f"{date_str}.md"
        if not file_path.exists():
            return []
        content = file_path.read_text(encoding="utf-8")
        entries: list[tuple[str, str]] = []
        parts = re.split(
            r"^## (\d{2}:\d{2}:\d{2})\s*$", content, flags=re.MULTILINE
        )
        i = 1
        while i < len(parts) - 1:
            time_str = parts[i].strip()
            text = parts[i + 1].strip()
            if time_str:
                entries.append((time_str, text))
            i += 2
        entries.reverse()
        return entries

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

    @staticmethod
    def _normalize_debug_audio_path(debug_audio_path: str | Path | None) -> str:
        if not debug_audio_path:
            return ""
        try:
            return str(Path(debug_audio_path).expanduser().resolve())
        except Exception:
            return str(debug_audio_path)

    @staticmethod
    def _format_usage_mode_label(usage_mode: str) -> str:
        mapping = {
            "daily": "Daily",
            "vibecoding": "Vibecoding",
            "translation": "Translation",
        }
        return mapping.get(usage_mode.strip().lower(), usage_mode or "Unknown")

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

    def _format_entry(
        self,
        text: str,
        timestamp: datetime,
        raw_text: str = "",
        metadata: HistoryEntryMetadata | None = None,
    ) -> str:
        safe_text = text.strip()
        safe_raw_text = raw_text.strip()
        meta_block = self._format_metadata_block(metadata or HistoryEntryMetadata())
        if safe_raw_text:
            safe_text = f"最终输出\n\n{safe_text}\n\n原文\n\n{safe_raw_text}"
        body = f"{meta_block}{safe_text}" if meta_block else safe_text
        return f"## {timestamp:%H:%M:%S}\n\n{body}\n\n"
