from __future__ import annotations

import sys
import pyperclip
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, QTimer, QUrl
from PyQt6.QtGui import QAction, QDesktopServices, QIcon, QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from talky.controller import AppController
from talky.dictionary_entries import DictionaryEntry, parse_dictionary_entries
from talky.hotkey import GlobalShortcutListener, label_for_hotkey_tokens
from talky.models import AppSettings
from talky.permissions import (
    check_microphone_granted,
    is_accessibility_trusted,
    request_microphone_permission,
)
from talky.version_checker import CURRENT_VERSION, VersionChecker

# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------

_ZH = {
    "save": "\u4fdd\u5b58",
    "check_accessibility": "\u65e0\u969c\u788d",
    "base_params": "\u57fa\u7840\u53c2\u6570",
    "hotkey": "\u70ed\u952e",
    "whisper_model": "Whisper \u6a21\u578b",
    "ollama_model": "Ollama \u6a21\u578b",
    "ollama_host": "Ollama \u5730\u5740",
    "asr_language": "ASR \u8bed\u8a00",
    "ui_language": "UI \u8bed\u8a00",
    "paste_delay": "\u7c98\u8d34\u5ef6\u8fdf",
    "llm_debug_stream": "LLM \u8c03\u8bd5\u6d41\u8f93\u51fa",
    "saved": "\u5df2\u4fdd\u5b58",
    "open_dashboard": "\u6253\u5f00\u9762\u677f",
    "show_last_error": "\u67e5\u770b\u6700\u8fd1\u9519\u8bef",
    "no_error_yet": "\u6682\u65e0\u9519\u8bef\u8bb0\u5f55",
    "last_error_title": "\u6700\u8fd1\u9519\u8bef",
    "copy": "\u590d\u5236",
    "close": "\u5173\u95ed",
    "quit": "\u9000\u51fa",
    "started": "\u5df2\u542f\u52a8",
    "error": "\u9519\u8bef",
    "popup_title": "\u65e0\u53ef\u7528\u7126\u70b9",
    "popup_subtitle": "\u53ef\u590d\u5236\u540e\u624b\u52a8\u7c98\u8d34",
    "copy_close": "\u590d\u5236\u5e76\u5173\u95ed",
    "permission_status": "\u6743\u9650\u72b6\u6001",
    "mic_permission": "\u9ea6\u514b\u98ce\u6743\u9650",
    "accessibility_permission": "\u8f85\u52a9\u529f\u80fd\u6743\u9650",
    "granted": "\u5df2\u6388\u6743",
    "not_granted": "\u672a\u6388\u6743",
    "request_mic_permission": "\u8bf7\u6c42\u9ea6\u514b\u98ce\u6743\u9650",
    "ui_option_english": "\u82f1\u6587",
    "ui_option_chinese": "\u4e2d\u6587",
    "hotkey_record_button": "\u5f55\u5236\u70ed\u952e\u2026",
    "hotkey_reset_default": "\u6062\u590d\u9ed8\u8ba4",
    "hotkey_custom_hint": "\u5f53\u524d\u81ea\u5b9a\u4e49\uff1a",
    "hotkey_custom_empty": "\u5c1a\u672a\u5f55\u5236\u81ea\u5b9a\u4e49\u70ed\u952e",
    # Tabs
    "home": "\u4e3b\u9875",
    "history": "\u5386\u53f2\u8bb0\u5f55",
    "dictionary": "\u8bcd\u5178",
    "configs": "\u914d\u7f6e",
    # Home
    "support_us": "\u652f\u6301\u6211\u4eec",
    "support_us_body": "Talky \u7528\u2764\u6253\u9020\uff0c\u4e0d\u5982\u53bb GitHub \u7ed9\u6211\u4eec\u70b9\u4e2a Star\uff1f",
    "star_on_github": "\u5728 GitHub \u4e0a Star",
    "update_available_msg": "\u53d1\u73b0\u65b0\u7248\u672c",
    "update_now": "\u7acb\u5373\u66f4\u65b0",
    # Dictionary
    "new_word": "\u6dfb\u52a0\u65b0\u8bcd",
    "edit_word": "\u4fee\u6539",
    "delete_word": "\u5220\u9664",
    "delete_confirm": "\u786e\u8ba4\u5220\u9664",
    "delete_confirm_msg": "\u786e\u5b9a\u8981\u5220\u9664\u6b64\u8bcd\u6761\u5417\uff1f",
    "word_label": "\u8bcd\u6761",
    "type_label": "\u7c7b\u578b",
    "plain_term": "\u666e\u901a\u8bcd\u6761",
    "person_term": "\u4eba\u540d",
    "no_words_yet": "\u6682\u65e0\u81ea\u5b9a\u4e49\u8bcd\u6761",
    # History
    "no_history": "\u6682\u65e0\u5386\u53f2\u8bb0\u5f55",
    "select_date_hint": "\u9009\u62e9\u65e5\u671f\u67e5\u770b\u8bb0\u5f55",
    # General
    "cancel": "\u53d6\u6d88",
    "ok": "\u786e\u8ba4",
}


def _tr(locale: str, en: str, key: str | None = None) -> str:
    if locale == "mixed" and key:
        return _ZH.get(key, en)
    return en


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _asset_path(name: str) -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # noqa: SLF001
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "assets" / name


def _clear_layout(layout) -> None:  # type: ignore[type-arg]
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
        elif item.layout() is not None:
            _clear_layout(item.layout())


def _entry_to_line(entry: DictionaryEntry) -> str:
    if entry.kind == "person":
        return f"person:{entry.term}"
    return entry.term


def _load_pixmap(path: Path, height: int) -> QPixmap | None:
    """Load a pixmap robustly (handles non-ASCII paths + Retina)."""
    if not path.exists():
        return None
    try:
        data = path.read_bytes()
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        if pixmap.isNull():
            return None
        ratio = QApplication.primaryScreen().devicePixelRatio() if QApplication.primaryScreen() else 2.0
        scaled = pixmap.scaledToHeight(
            int(height * ratio), Qt.TransformationMode.SmoothTransformation
        )
        scaled.setDevicePixelRatio(ratio)
        return scaled
    except Exception:
        return None


def _make_keycap(text: str) -> QLabel:
    """Small keyboard-key styled badge."""
    lbl = QLabel(text)
    lbl.setObjectName("Keycap")
    lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    return lbl


# ---------------------------------------------------------------------------
# Stylesheet — macOS native
# ---------------------------------------------------------------------------

NATIVE_STYLESHEET = """
/* ---- Global ---- */
QWidget {
    font-family: -apple-system, "SF Pro Text", "Helvetica Neue", "PingFang SC";
    font-size: 13px;
    color: #1D1D1F;
}

/* ---- Segmented tab bar ---- */
QFrame#SegmentedBar {
    background: rgba(0, 0, 0, 0.06);
    border-radius: 6px;
}

QPushButton#SegmentTab {
    background: transparent;
    color: #86868B;
    font-size: 12px;
    font-weight: 500;
    padding: 5px 18px;
    border-radius: 5px;
    border: none;
    min-width: 56px;
}

QPushButton#SegmentTab:checked {
    background: #FFFFFF;
    color: #ED4A20;
    font-weight: 600;
}

QPushButton#SegmentTab:hover:!checked {
    color: #1D1D1F;
}

/* ---- Form controls ---- */
QLineEdit, QComboBox, QSpinBox {
    border: 1px solid #D1D1D6;
    border-radius: 5px;
    background: #FFFFFF;
    padding: 4px 8px;
    min-height: 22px;
    selection-background-color: rgba(237, 74, 32, 0.3);
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 2px solid rgba(237, 74, 32, 0.55);
    padding: 3px 7px;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 20px;
    right: 4px;
    border: none;
}

QSpinBox::up-button, QSpinBox::down-button {
    border: none;
    width: 16px;
}

QSpinBox::up-button { subcontrol-position: top right; }
QSpinBox::down-button { subcontrol-position: bottom right; }

/* ---- Buttons ---- */
QPushButton {
    border: none;
    border-radius: 5px;
    padding: 5px 12px;
    font-weight: 500;
    font-size: 13px;
}

QPushButton#PrimaryButton {
    background: #ED4A20;
    color: #FFFFFF;
    font-weight: 600;
}

QPushButton#PrimaryButton:hover {
    background: #F45B2F;
}

QPushButton#SecondaryButton {
    background: #F2F2F7;
    color: #1D1D1F;
    border: 1px solid #D1D1D6;
}

QPushButton#SecondaryButton:hover {
    background: #E5E5EA;
}

QPushButton#LinkButton {
    background: transparent;
    color: #ED4A20;
    border: none;
    padding: 2px 0px;
    font-weight: 500;
    font-size: 12px;
}

QPushButton#LinkButton:hover {
    color: #F45B2F;
}

/* ---- Typography ---- */
QLabel#WindowTitle {
    font-size: 28px;
    font-weight: 800;
    color: #1D1D1F;
}

QLabel#VersionLabel {
    font-size: 12px;
    font-weight: 300;
    color: #AEAEB2;
}

QLabel#WindowSubtitle {
    font-size: 12px;
    color: #86868B;
}

QLabel#CardTitle {
    font-size: 13px;
    font-weight: 600;
    color: #1D1D1F;
}

QLabel#FormLabel {
    font-size: 13px;
    color: #3A3A3C;
}

/* ---- Keycap badge ---- */
QLabel#Keycap {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FCFCFC, stop:1 #ECECEC);
    border-top: 1px solid #D8D8DC;
    border-left: 1px solid #C7C7CC;
    border-right: 1px solid #C7C7CC;
    border-bottom: 2px solid #AEAEB2;
    border-radius: 4px;
    padding: 2px 7px;
    font-size: 12px;
    font-family: "SF Mono", "Menlo", monospace;
    font-weight: 600;
    color: #3A3A3C;
}

/* ---- Section frame ---- */
QFrame#SectionFrame {
    background: #FFFFFF;
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 10px;
}

/* ---- History sidebar ---- */
QPushButton#DateItem {
    background: transparent;
    color: #3A3A3C;
    font-size: 12px;
    font-weight: 500;
    padding: 6px 10px;
    border-radius: 5px;
    border: none;
    text-align: left;
}

QPushButton#DateItem:checked {
    background: rgba(237, 74, 32, 0.08);
    color: #ED4A20;
    font-weight: 600;
}

QPushButton#DateItem:hover:!checked {
    background: rgba(0, 0, 0, 0.04);
}

/* ---- Chat bubble ---- */
QFrame#ChatBubble {
    background: #F2F2F7;
    border: none;
    border-radius: 14px;
    border-top-left-radius: 4px;
}

/* ---- Word card ---- */
QFrame#WordCard {
    background: #FFFFFF;
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 6px;
}

QPushButton#WordActionButton {
    background: transparent;
    color: #86868B;
    font-size: 11px;
    font-weight: 500;
    padding: 1px 6px;
    border-radius: 4px;
    border: none;
}

QPushButton#WordActionButton:hover {
    background: rgba(237, 74, 32, 0.08);
    color: #ED4A20;
}

/* ---- Update banner ---- */
QFrame#UpdateBanner {
    background: rgba(237, 74, 32, 0.06);
    border: 1px solid rgba(237, 74, 32, 0.15);
    border-radius: 8px;
}

/* ---- Instruction / Refer card ---- */
QFrame#InstructionCard, QFrame#ReferCard {
    background: #FFFFFF;
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 8px;
}

/* ---- Radio & Checkbox ---- */
QRadioButton {
    spacing: 6px;
    font-size: 13px;
    color: #1D1D1F;
}

QCheckBox {
    spacing: 6px;
    font-size: 13px;
}

/* ---- Scroll bars ---- */
QScrollArea {
    background: transparent;
    border: none;
}

QScrollBar:vertical {
    width: 7px;
    background: transparent;
}

QScrollBar::handle:vertical {
    background: rgba(0, 0, 0, 0.12);
    border-radius: 3px;
    min-height: 24px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    height: 0;
    background: transparent;
}

QScrollBar:horizontal {
    height: 0;
}

/* ---- Text views ---- */
QPlainTextEdit {
    border: 1px solid #D1D1D6;
    border-radius: 5px;
    background: #FFFFFF;
    padding: 6px;
    font-family: "SF Mono", "Menlo", monospace;
    font-size: 12px;
    selection-background-color: rgba(237, 74, 32, 0.3);
}

QTextEdit#ResultPanel {
    background: #FFFFFF;
    border: 1px solid #D1D1D6;
    border-radius: 5px;
    padding: 6px;
}

/* ---- Message boxes ---- */
QMessageBox {
    background: #FFFFFF;
}

QMessageBox QLabel {
    color: #1D1D1F;
}

QMessageBox QPushButton {
    background: #F2F2F7;
    color: #1D1D1F;
    border: 1px solid #D1D1D6;
    border-radius: 5px;
    padding: 4px 14px;
    min-width: 60px;
}

/* ---- Popup card ---- */
QFrame#PopupCard {
    background: rgba(255, 255, 255, 245);
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 12px;
}
"""


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------


class CustomHotkeyCaptureDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Record custom hotkey")
        self.setModal(True)
        self.resize(420, 140)
        self.captured_tokens: list[str] = []

        self.info = QLabel("Press and hold your desired hotkey now...")
        self.info.setObjectName("WindowSubtitle")
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addWidget(self.info)
        self.setLayout(layout)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        tokens = self._tokens_from_event(event)
        if tokens:
            self.captured_tokens = tokens
            self.info.setText(f"Captured: {label_for_hotkey_tokens(tokens)}")
            QTimer.singleShot(120, self.accept)
            return
        super().keyPressEvent(event)

    def _tokens_from_event(self, event) -> list[str]:
        tokens: set[str] = set()
        mods = event.modifiers()
        if mods & Qt.KeyboardModifier.AltModifier:
            tokens.add("alt")
        if mods & Qt.KeyboardModifier.ControlModifier:
            tokens.add("ctrl")
        if mods & Qt.KeyboardModifier.ShiftModifier:
            tokens.add("shift")
        if mods & Qt.KeyboardModifier.MetaModifier:
            tokens.add("cmd")
        return sorted(tokens)


class WordEditDialog(QDialog):
    """Add or edit a dictionary word."""

    def __init__(
        self,
        parent: QWidget | None = None,
        term: str = "",
        kind: str = "term",
        locale: str = "en",
    ) -> None:
        super().__init__(parent)
        self._locale = locale
        is_new = not term
        self.setWindowTitle(
            _tr(locale, "Add Word", "new_word") if is_new
            else _tr(locale, "Edit Word", "edit_word")
        )
        self.setModal(True)
        self.resize(380, 190)
        self.setStyleSheet(NATIVE_STYLESHEET)

        self.term_input = QLineEdit(term)
        self.term_input.setPlaceholderText(
            _tr(locale, "Enter word or phrase...", None)
        )

        self.kind_combo = QComboBox()
        self.kind_combo.addItem(
            _tr(locale, "Plain term", "plain_term"), userData="term"
        )
        self.kind_combo.addItem(
            _tr(locale, "Person name", "person_term"), userData="person"
        )
        if kind == "person":
            self.kind_combo.setCurrentIndex(1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(_tr(locale, "Cancel", "cancel"))
        cancel_btn.setObjectName("SecondaryButton")
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton(_tr(locale, "OK", "ok"))
        ok_btn.setObjectName("PrimaryButton")
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        word_lbl = QLabel(_tr(locale, "Word", "word_label"))
        word_lbl.setObjectName("FormLabel")
        layout.addWidget(word_lbl)
        layout.addWidget(self.term_input)
        type_lbl = QLabel(_tr(locale, "Type", "type_label"))
        type_lbl.setObjectName("FormLabel")
        layout.addWidget(type_lbl)
        layout.addWidget(self.kind_combo)
        layout.addLayout(btn_row)

    def get_result(self) -> tuple[str, str]:
        return self.term_input.text().strip(), str(self.kind_combo.currentData())


# ---------------------------------------------------------------------------
# Word card
# ---------------------------------------------------------------------------


class DictionaryWordCard(QFrame):
    def __init__(
        self,
        index: int,
        entry: DictionaryEntry,
        on_edit,  # type: ignore[type-arg]
        on_delete,  # type: ignore[type-arg]
        locale: str = "en",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._index = index
        self.setObjectName("WordCard")
        self.setFixedHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 6, 0)
        layout.setSpacing(6)

        if entry.kind == "person":
            initial = entry.term[0].upper() if entry.term else "P"
            badge = QLabel(initial)
            badge.setFixedSize(22, 22)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                "background: rgba(237,74,32,0.08); border-radius: 11px;"
                " font-size: 11px; font-weight: 600; color: #ED4A20;"
            )
            layout.addWidget(badge)

        term_label = QLabel(entry.term)
        term_label.setStyleSheet("font-size: 13px; font-weight: 500;")
        layout.addWidget(term_label)
        layout.addStretch()

        self._edit_btn = QPushButton(_tr(locale, "Edit", "edit_word"))
        self._edit_btn.setObjectName("WordActionButton")
        self._edit_btn.setFixedHeight(22)
        self._edit_btn.setVisible(False)
        self._edit_btn.clicked.connect(lambda: on_edit(self._index))

        self._del_btn = QPushButton(_tr(locale, "Delete", "delete_word"))
        self._del_btn.setObjectName("WordActionButton")
        self._del_btn.setFixedHeight(22)
        self._del_btn.setVisible(False)
        self._del_btn.clicked.connect(lambda: on_delete(self._index))

        layout.addWidget(self._edit_btn)
        layout.addWidget(self._del_btn)

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self._edit_btn.setVisible(True)
        self._del_btn.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._edit_btn.setVisible(False)
        self._del_btn.setVisible(False)
        super().leaveEvent(event)


# ---------------------------------------------------------------------------
# Tab 1 — Home
# ---------------------------------------------------------------------------


class HomeTab(QWidget):
    def __init__(self, controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._locale = controller.settings.ui_locale

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = _load_pixmap(_asset_path("talky-logo.png"), 96)
        if pixmap is not None:
            logo_label.setPixmap(pixmap)
        layout.addWidget(logo_label)

        title = QLabel("Talky")
        title.setObjectName("WindowTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        version_label = QLabel(f"v{CURRENT_VERSION}")
        version_label.setObjectName("VersionLabel")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)

        layout.addSpacing(4)

        instruction_card = QFrame()
        instruction_card.setObjectName("InstructionCard")
        ic_layout = QVBoxLayout(instruction_card)
        ic_layout.setContentsMargins(16, 14, 16, 14)
        ic_layout.setSpacing(10)

        _hint_style = "font-size: 13px; color: #3A3A3C;"

        line1 = QHBoxLayout()
        line1.setSpacing(5)
        line1.setContentsMargins(0, 0, 0, 0)
        line1.addStretch()
        _l1a = QLabel("Hold")
        _l1a.setStyleSheet(_hint_style)
        line1.addWidget(_l1a)
        line1.addWidget(_make_keycap("Fn"))
        _l1b = QLabel("to dictate. Release to transcribe.")
        _l1b.setStyleSheet(_hint_style)
        line1.addWidget(_l1b)
        line1.addStretch()
        ic_layout.addLayout(line1)

        line2 = QHBoxLayout()
        line2.setSpacing(5)
        line2.setContentsMargins(0, 0, 0, 0)
        line2.addStretch()
        _l2a = QLabel("Press")
        _l2a.setStyleSheet(_hint_style)
        line2.addWidget(_l2a)
        line2.addWidget(_make_keycap("\u2303"))
        line2.addWidget(_make_keycap("\u2325"))
        line2.addWidget(_make_keycap("\u2318"))
        _l2b = QLabel("to open Dashboard.")
        _l2b.setStyleSheet(_hint_style)
        line2.addWidget(_l2b)
        line2.addStretch()
        ic_layout.addLayout(line2)

        layout.addWidget(instruction_card)

        # Update banner (hidden by default)
        self._update_banner = QFrame()
        self._update_banner.setObjectName("UpdateBanner")
        self._update_banner.setVisible(False)
        ub_layout = QHBoxLayout(self._update_banner)
        ub_layout.setContentsMargins(12, 10, 12, 10)
        self._update_text = QLabel()
        self._update_text.setObjectName("WindowSubtitle")
        self._update_text.setWordWrap(True)
        self._update_button = QPushButton(
            _tr(self._locale, "Update Now", "update_now")
        )
        self._update_button.setObjectName("PrimaryButton")
        self._update_url = ""
        self._update_button.clicked.connect(self._on_update_clicked)
        ub_layout.addWidget(self._update_text, 1)
        ub_layout.addWidget(self._update_button)
        layout.addWidget(self._update_banner)

        support_card = QFrame()
        support_card.setObjectName("SectionFrame")
        sc_layout = QVBoxLayout(support_card)
        sc_layout.setContentsMargins(14, 12, 14, 14)
        sc_layout.setSpacing(8)

        self._support_title = QLabel(
            _tr(self._locale, "Support Us", "support_us")
        )
        self._support_title.setObjectName("CardTitle")
        sc_layout.addWidget(self._support_title)

        body_row = QHBoxLayout()
        body_row.setSpacing(5)
        body_row.setContentsMargins(0, 0, 0, 0)
        heart = QLabel("\u2764\ufe0f")
        heart.setStyleSheet("font-size: 14px;")
        heart.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        body_row.addWidget(heart)
        self._support_body = QLabel(
            _tr(
                self._locale,
                "Talky is built with love \u2014 why not give us a star on GitHub?",
                "support_us_body",
            )
        )
        self._support_body.setWordWrap(True)
        self._support_body.setStyleSheet("font-size: 13px; color: #3A3A3C;")
        body_row.addWidget(self._support_body, 1)
        sc_layout.addLayout(body_row)

        self._github_button = QPushButton(
            "\u2605  " + _tr(self._locale, "Star on GitHub", "star_on_github")
        )
        self._github_button.setObjectName("SecondaryButton")
        self._github_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._github_button.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://github.com/shintemy/talky")
            )
        )
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.addWidget(self._github_button)
        btn_row.addStretch()
        sc_layout.addLayout(btn_row)

        layout.addWidget(support_card)

        layout.addStretch(1)

        self._version_checker = VersionChecker()
        self._version_checker.update_available.connect(self._on_update_available)
        QTimer.singleShot(1500, self._version_checker.check_async)

    def _on_update_available(self, version: str, url: str) -> None:
        self._update_url = url
        msg = _tr(self._locale, "New version available", "update_available_msg")
        self._update_text.setText(f"{msg}: v{version}")
        self._update_button.setText(
            _tr(self._locale, "Update Now", "update_now")
        )
        self._update_banner.setVisible(True)

    def _on_update_clicked(self) -> None:
        if self._update_url:
            QDesktopServices.openUrl(QUrl(self._update_url))

    def update_locale(self, locale: str) -> None:
        self._locale = locale
        self._support_title.setText(_tr(locale, "Support Us", "support_us"))
        self._support_body.setText(
            _tr(
                locale,
                "Talky is built with love \u2014 why not give us a star on GitHub?",
                "support_us_body",
            )
        )
        self._github_button.setText(
            "\u2605  " + _tr(locale, "Star on GitHub", "star_on_github")
        )
        self._update_button.setText(_tr(locale, "Update Now", "update_now"))


# ---------------------------------------------------------------------------
# Tab 2 — History
# ---------------------------------------------------------------------------


class HistoryTab(QWidget):
    def __init__(self, controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._locale = controller.settings.ui_locale
        self._selected_date: str | None = None
        self._date_buttons: dict[int, str] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        # Left: date sidebar
        left_panel = QWidget()
        left_panel.setFixedWidth(150)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        date_scroll = QScrollArea()
        date_scroll.setWidgetResizable(True)
        date_scroll.setFrameShape(QFrame.Shape.NoFrame)
        date_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        date_scroll.setStyleSheet("background: transparent;")
        self._date_list_widget = QWidget()
        self._date_list_widget.setStyleSheet("background: transparent;")
        self._date_list_layout = QVBoxLayout(self._date_list_widget)
        self._date_list_layout.setContentsMargins(0, 0, 0, 0)
        self._date_list_layout.setSpacing(2)
        self._date_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        date_scroll.setWidget(self._date_list_widget)
        left_layout.addWidget(date_scroll)

        self._date_button_group = QButtonGroup(self)
        self._date_button_group.setExclusive(True)
        self._date_button_group.idClicked.connect(self._on_date_selected)

        # Vertical separator
        separator = QFrame()
        separator.setFixedWidth(1)
        separator.setStyleSheet("background: rgba(0, 0, 0, 0.08);")

        # Right: entries
        self._right_stack = QStackedWidget()

        placeholder = QLabel(
            _tr(self._locale, "Select a date to view history", "select_date_hint")
        )
        placeholder.setObjectName("WindowSubtitle")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder_label = placeholder

        entry_scroll = QScrollArea()
        entry_scroll.setWidgetResizable(True)
        entry_scroll.setFrameShape(QFrame.Shape.NoFrame)
        entry_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._entry_list_widget = QWidget()
        self._entry_list_layout = QVBoxLayout(self._entry_list_widget)
        self._entry_list_layout.setContentsMargins(12, 4, 4, 4)
        self._entry_list_layout.setSpacing(8)
        self._entry_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        entry_scroll.setWidget(self._entry_list_widget)

        self._right_stack.addWidget(placeholder)
        self._right_stack.addWidget(entry_scroll)
        self._right_stack.setCurrentIndex(0)

        layout.addWidget(left_panel)
        layout.addWidget(separator)
        layout.addWidget(self._right_stack, 1)

    def refresh(self) -> None:
        dates = self.controller.history_store.list_dates()
        self._rebuild_date_list(dates)
        if self._selected_date and self._selected_date in dates:
            idx = dates.index(self._selected_date)
            btn = self._date_button_group.button(idx)
            if btn:
                btn.setChecked(True)
            self._load_entries(self._selected_date)
        else:
            self._selected_date = None
            _clear_layout(self._entry_list_layout)
            self._right_stack.setCurrentIndex(0)

    def _rebuild_date_list(self, dates: list[str]) -> None:
        for btn in self._date_button_group.buttons():
            self._date_button_group.removeButton(btn)
        _clear_layout(self._date_list_layout)
        self._date_buttons.clear()

        if not dates:
            no_label = QLabel(_tr(self._locale, "No history yet", "no_history"))
            no_label.setObjectName("WindowSubtitle")
            no_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._date_list_layout.addWidget(no_label)
            return

        for i, date_str in enumerate(dates):
            btn = QPushButton(date_str)
            btn.setCheckable(True)
            btn.setObjectName("DateItem")
            self._date_button_group.addButton(btn, i)
            self._date_list_layout.addWidget(btn)
            self._date_buttons[i] = date_str
        self._date_list_layout.addStretch()

    def _on_date_selected(self, button_id: int) -> None:
        date_str = self._date_buttons.get(button_id)
        if not date_str:
            return
        self._selected_date = date_str
        self._load_entries(date_str)

    def _load_entries(self, date_str: str) -> None:
        _clear_layout(self._entry_list_layout)
        entries = self.controller.history_store.read_entries(date_str)
        if not entries:
            empty = QLabel(_tr(self._locale, "No entries for this date", None))
            empty.setObjectName("WindowSubtitle")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._entry_list_layout.addWidget(empty)
        else:
            for time_str, text in entries:
                bubble = QFrame()
                bubble.setObjectName("ChatBubble")
                bubble_layout = QVBoxLayout(bubble)
                bubble_layout.setContentsMargins(12, 8, 12, 8)
                bubble_layout.setSpacing(3)

                time_label = QLabel(time_str)
                time_label.setStyleSheet(
                    "font-size: 11px; font-weight: 500; color: #86868B;"
                )
                text_label = QLabel(text)
                text_label.setWordWrap(True)
                text_label.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse
                )
                text_label.setStyleSheet("font-size: 13px; color: #1D1D1F;")

                bubble_layout.addWidget(time_label)
                bubble_layout.addWidget(text_label)

                row = QHBoxLayout()
                row.setContentsMargins(0, 0, 0, 0)
                row.addWidget(bubble, 4)
                row.addStretch(1)
                self._entry_list_layout.addLayout(row)
        self._entry_list_layout.addStretch()
        self._right_stack.setCurrentIndex(1)

    def update_locale(self, locale: str) -> None:
        self._locale = locale
        self._placeholder_label.setText(
            _tr(locale, "Select a date to view history", "select_date_hint")
        )


# ---------------------------------------------------------------------------
# Tab 3 — Dictionary
# ---------------------------------------------------------------------------


class DictionaryTab(QWidget):
    def __init__(self, controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._locale = controller.settings.ui_locale
        self._entries: list[DictionaryEntry] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 8, 24, 8)
        outer.setSpacing(12)

        top_row = QHBoxLayout()
        self._new_word_btn = QPushButton(
            "+ " + _tr(self._locale, "New Word", "new_word")
        )
        self._new_word_btn.setObjectName("SecondaryButton")
        self._new_word_btn.clicked.connect(self._on_add_word)
        top_row.addWidget(self._new_word_btn)
        top_row.addStretch()
        outer.addLayout(top_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent;")
        self._grid_container = QWidget()
        self._grid_container.setStyleSheet("background: transparent;")
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)
        self._grid_layout.setSpacing(6)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._grid_layout.setColumnStretch(0, 1)
        self._grid_layout.setColumnStretch(1, 1)
        self._grid_layout.setColumnStretch(2, 1)
        scroll.setWidget(self._grid_container)
        outer.addWidget(scroll, 1)

        self._empty_label = QLabel(
            _tr(self._locale, "No custom words yet", "no_words_yet")
        )
        self._empty_label.setObjectName("WindowSubtitle")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setVisible(False)
        outer.addWidget(self._empty_label)

        self.refresh_from_settings(controller.settings)

    def refresh_from_settings(self, settings: AppSettings) -> None:
        raw_lines = [ln for ln in settings.custom_dictionary if ln.strip()]
        self._entries = parse_dictionary_entries(raw_lines)
        self._rebuild_grid()

    def _rebuild_grid(self) -> None:
        _clear_layout(self._grid_layout)
        self._empty_label.setVisible(not self._entries)
        for i, entry in enumerate(self._entries):
            card = DictionaryWordCard(
                index=i, entry=entry,
                on_edit=self._on_edit_word,
                on_delete=self._on_delete_word,
                locale=self._locale,
            )
            self._grid_layout.addWidget(card, i // 3, i % 3)

    def _on_add_word(self) -> None:
        dialog = WordEditDialog(parent=self, locale=self._locale)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        term, kind = dialog.get_result()
        if not term:
            return
        self._entries.append(DictionaryEntry(term=term, kind=kind))
        self._save_and_rebuild()

    def _on_edit_word(self, index: int) -> None:
        if index < 0 or index >= len(self._entries):
            return
        entry = self._entries[index]
        dialog = WordEditDialog(
            parent=self, term=entry.term, kind=entry.kind, locale=self._locale
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        term, kind = dialog.get_result()
        if not term:
            return
        self._entries[index] = DictionaryEntry(term=term, kind=kind)
        self._save_and_rebuild()

    def _on_delete_word(self, index: int) -> None:
        if index < 0 or index >= len(self._entries):
            return
        entry = self._entries[index]
        reply = QMessageBox.question(
            self,
            _tr(self._locale, "Confirm Delete", "delete_confirm"),
            _tr(self._locale, "Delete this word?", "delete_confirm_msg")
            + f'\n\n"{entry.term}"',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        del self._entries[index]
        self._save_and_rebuild()

    def _save_and_rebuild(self) -> None:
        lines = [_entry_to_line(e) for e in self._entries]
        self.controller.update_dictionary(lines)
        self._rebuild_grid()

    def update_locale(self, locale: str) -> None:
        self._locale = locale
        self._new_word_btn.setText("+ " + _tr(locale, "New Word", "new_word"))
        self._empty_label.setText(_tr(locale, "No custom words yet", "no_words_yet"))
        self._rebuild_grid()


# ---------------------------------------------------------------------------
# Tab 4 — Configs (auto-save on dashboard close)
# ---------------------------------------------------------------------------

_HOTKEY_OPTIONS = [
    ("fn", "Fn / Globe (Default)", "fn"),
    ("right_option", "Right Option", "\u2325"),
    ("right_command", "Right Command", "\u2318"),
    ("command_option", "Command + Option", "\u2318 \u2325"),
    ("custom", "Custom", None),
]


class ConfigsTab(QWidget):
    def __init__(self, controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._locale = controller.settings.ui_locale
        self._form_labels: list[tuple[QLabel, str, str]] = []
        self._custom_hotkey_tokens: list[str] = []

        # ---- Hotkey radio group ----
        self._hotkey_button_group = QButtonGroup(self)
        self._hotkey_mode_map: dict[int, str] = {}
        self._hotkey_id_for_mode: dict[str, int] = {}

        hotkey_group = QVBoxLayout()
        hotkey_group.setSpacing(4)
        hotkey_group.setContentsMargins(0, 0, 0, 0)

        for i, (mode, label_text, keycap_text) in enumerate(_HOTKEY_OPTIONS):
            self._hotkey_mode_map[i] = mode
            self._hotkey_id_for_mode[mode] = i

            row = QHBoxLayout()
            row.setSpacing(8)
            row.setContentsMargins(0, 0, 0, 0)
            radio = QRadioButton(label_text)
            self._hotkey_button_group.addButton(radio, i)
            row.addWidget(radio)
            if keycap_text:
                row.addWidget(_make_keycap(keycap_text))
            row.addStretch()
            hotkey_group.addLayout(row)

        self._custom_area = QWidget()
        custom_row = QHBoxLayout(self._custom_area)
        custom_row.setContentsMargins(22, 2, 0, 0)
        custom_row.setSpacing(8)
        self.hotkey_record_button = QPushButton(
            _tr(self._locale, "Record Hotkey\u2026", "hotkey_record_button")
        )
        self.hotkey_record_button.setObjectName("SecondaryButton")
        self.hotkey_record_button.clicked.connect(self._begin_custom_hotkey_record)
        self.hotkey_custom_preview = QLabel("")
        self.hotkey_custom_preview.setObjectName("WindowSubtitle")
        custom_row.addWidget(self.hotkey_record_button)
        custom_row.addWidget(self.hotkey_custom_preview)
        custom_row.addStretch()
        hotkey_group.addWidget(self._custom_area)

        reset_row = QHBoxLayout()
        reset_row.setContentsMargins(0, 2, 0, 0)
        self.hotkey_reset_link = QPushButton(
            _tr(self._locale, "Reset to Default", "hotkey_reset_default")
        )
        self.hotkey_reset_link.setObjectName("LinkButton")
        self.hotkey_reset_link.clicked.connect(self._reset_default_hotkey)
        reset_row.addWidget(self.hotkey_reset_link)
        reset_row.addStretch()
        hotkey_group.addLayout(reset_row)

        self.hotkey_widget = QWidget()
        self.hotkey_widget.setLayout(hotkey_group)

        self._hotkey_button_group.idClicked.connect(self._on_hotkey_mode_changed)

        # ---- Other form widgets ----
        self.whisper_model_input = QLineEdit()
        self.ollama_model_input = QLineEdit()
        self.ollama_host_input = QLineEdit()
        self.ollama_host_input.setPlaceholderText("http://127.0.0.1:11434")
        self.language_input = QLineEdit()

        self.ui_locale_combo = QComboBox()
        self.ui_locale_combo.addItem(
            _tr(self._locale, "English", "ui_option_english"), userData="en"
        )
        self.ui_locale_combo.addItem(
            _tr(self._locale, "Chinese", "ui_option_chinese"), userData="mixed"
        )

        self.paste_delay_input = QSpinBox()
        self.paste_delay_input.setRange(50, 2000)
        self.paste_delay_input.setSuffix(" ms")

        self.llm_debug_stream_checkbox = QCheckBox()

        # ---- Permission widgets ----
        self.mic_permission_label = QLabel(
            _tr(self._locale, "Microphone", "mic_permission")
        )
        self.mic_permission_label.setObjectName("FormLabel")
        self.mic_permission_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.mic_status_value_label = QLabel("")

        self.ax_permission_label = QLabel(
            _tr(self._locale, "Accessibility", "accessibility_permission")
        )
        self.ax_permission_label.setObjectName("FormLabel")
        self.ax_permission_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.ax_status_value_label = QLabel("")

        self.permission_button = QPushButton(
            _tr(self._locale, "Check Accessibility", "check_accessibility")
        )
        self.permission_button.setObjectName("SecondaryButton")
        self.permission_button.clicked.connect(self._check_accessibility)

        self.request_mic_button = QPushButton(
            _tr(self._locale, "Request Microphone Permission", "request_mic_permission")
        )
        self.request_mic_button.setObjectName("SecondaryButton")
        self.request_mic_button.clicked.connect(self._request_microphone_permission)

        # ---- Form grid (right-aligned labels) ----
        form = QGridLayout()
        form.setColumnMinimumWidth(0, 120)
        form.setColumnStretch(0, 0)
        form.setColumnStretch(1, 1)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)

        fields = [
            ("Record Hotkey", "hotkey", self.hotkey_widget),
            ("Whisper Model", "whisper_model", self.whisper_model_input),
            ("ASR Language", "asr_language", self.language_input),
            ("Ollama Host", "ollama_host", self.ollama_host_input),
            ("Ollama Model", "ollama_model", self.ollama_model_input),
            ("UI Language", "ui_language", self.ui_locale_combo),
            ("Auto Paste Delay", "paste_delay", self.paste_delay_input),
            ("LLM Debug Stream", "llm_debug_stream", self.llm_debug_stream_checkbox),
        ]
        for row_idx, (en_text, key, widget) in enumerate(fields):
            label = QLabel(_tr(self._locale, en_text, key))
            label.setObjectName("FormLabel")
            v_align = (
                Qt.AlignmentFlag.AlignTop if row_idx == 0
                else Qt.AlignmentFlag.AlignVCenter
            )
            label.setAlignment(Qt.AlignmentFlag.AlignRight | v_align)
            form.addWidget(label, row_idx, 0)
            form.addWidget(widget, row_idx, 1)
            self._form_labels.append((label, en_text, key))

        # ---- Permission grid ----
        perm_grid = QGridLayout()
        perm_grid.setColumnMinimumWidth(0, 120)
        perm_grid.setColumnStretch(0, 0)
        perm_grid.setColumnStretch(1, 0)
        perm_grid.setColumnStretch(2, 1)
        perm_grid.setHorizontalSpacing(12)
        perm_grid.setVerticalSpacing(8)
        perm_grid.addWidget(self.mic_permission_label, 0, 0)
        perm_grid.addWidget(self.mic_status_value_label, 0, 1)
        perm_grid.addWidget(self.request_mic_button, 0, 2)
        perm_grid.addWidget(self.ax_permission_label, 1, 0)
        perm_grid.addWidget(self.ax_status_value_label, 1, 1)
        perm_grid.addWidget(self.permission_button, 1, 2)

        # ---- Assemble layout ----
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 12, 24, 16)
        content_layout.setSpacing(16)

        params_section = QFrame()
        params_section.setObjectName("SectionFrame")
        ps_layout = QVBoxLayout(params_section)
        ps_layout.setContentsMargins(16, 14, 16, 14)
        ps_layout.setSpacing(10)
        self._params_card_title = QLabel(
            _tr(self._locale, "Base Parameters", "base_params")
        )
        self._params_card_title.setObjectName("CardTitle")
        ps_layout.addWidget(self._params_card_title)
        ps_layout.addLayout(form)
        content_layout.addWidget(params_section)

        perm_section = QFrame()
        perm_section.setObjectName("SectionFrame")
        pm_layout = QVBoxLayout(perm_section)
        pm_layout.setContentsMargins(16, 14, 16, 14)
        pm_layout.setSpacing(10)
        self._perm_title = QLabel(
            _tr(self._locale, "Permission Status", "permission_status")
        )
        self._perm_title.setObjectName("CardTitle")
        pm_layout.addWidget(self._perm_title)
        pm_layout.addLayout(perm_grid)
        content_layout.addWidget(perm_section)

        content_layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

        self.load_from_settings(controller.settings)

    # ---- data load ----

    def load_from_settings(self, settings: AppSettings) -> None:
        self._locale = settings.ui_locale
        self._apply_locale_texts()
        self._custom_hotkey_tokens = [
            t.strip().lower() for t in settings.custom_hotkey if t.strip()
        ]
        button_id = self._hotkey_id_for_mode.get(settings.hotkey, 0)
        btn = self._hotkey_button_group.button(button_id)
        if btn:
            btn.setChecked(True)
        self._apply_hotkey_control_state()
        self.whisper_model_input.setText(settings.whisper_model)
        self.ollama_host_input.setText(settings.ollama_host)
        self.ollama_model_input.setText(settings.ollama_model)
        self.language_input.setText(settings.language)
        locale_idx = self.ui_locale_combo.findData(settings.ui_locale)
        self.ui_locale_combo.setCurrentIndex(0 if locale_idx < 0 else locale_idx)
        self.paste_delay_input.setValue(settings.auto_paste_delay_ms)
        self.llm_debug_stream_checkbox.setChecked(settings.llm_debug_stream)
        self._refresh_permission_status()

    def collect_settings(self) -> AppSettings:
        """Read current form values and return an AppSettings object."""
        checked_id = self._hotkey_button_group.checkedId()
        hotkey_mode = self._hotkey_mode_map.get(checked_id, "fn")
        custom_hotkey = list(self._custom_hotkey_tokens)
        if hotkey_mode == "custom":
            valid, _, normalized = self._validate_custom_hotkey(set(custom_hotkey))
            if valid:
                custom_hotkey = normalized
            else:
                hotkey_mode = self.controller.settings.hotkey
                custom_hotkey = list(self.controller.settings.custom_hotkey)

        return AppSettings(
            custom_dictionary=self.controller.settings.custom_dictionary,
            hotkey=hotkey_mode,
            custom_hotkey=custom_hotkey,
            whisper_model=self.whisper_model_input.text().strip() or "./local_whisper_model",
            ollama_model=self.ollama_model_input.text().strip() or "qwen3.5:9b",
            ollama_host=(
                self.ollama_host_input.text().strip().rstrip("/")
                or "http://127.0.0.1:11434"
            ),
            ui_locale=str(self.ui_locale_combo.currentData()),
            language=self.language_input.text().strip() or "zh",
            auto_paste_delay_ms=self.paste_delay_input.value(),
            llm_debug_stream=self.llm_debug_stream_checkbox.isChecked(),
            sample_rate=self.controller.settings.sample_rate,
            channels=self.controller.settings.channels,
        )

    # ---- locale ----

    def _apply_locale_texts(self) -> None:
        self._params_card_title.setText(
            _tr(self._locale, "Base Parameters", "base_params")
        )
        self._perm_title.setText(
            _tr(self._locale, "Permission Status", "permission_status")
        )
        self.mic_permission_label.setText(
            _tr(self._locale, "Microphone", "mic_permission")
        )
        self.ax_permission_label.setText(
            _tr(self._locale, "Accessibility", "accessibility_permission")
        )
        self.permission_button.setText(
            _tr(self._locale, "Check Accessibility", "check_accessibility")
        )
        self.request_mic_button.setText(
            _tr(self._locale, "Request Microphone Permission", "request_mic_permission")
        )
        self.hotkey_record_button.setText(
            _tr(self._locale, "Record Hotkey\u2026", "hotkey_record_button")
        )
        self.hotkey_reset_link.setText(
            _tr(self._locale, "Reset to Default", "hotkey_reset_default")
        )
        self.ui_locale_combo.setItemText(
            0, _tr(self._locale, "English", "ui_option_english")
        )
        self.ui_locale_combo.setItemText(
            1, _tr(self._locale, "Chinese", "ui_option_chinese")
        )
        for label, en_text, key in self._form_labels:
            label.setText(_tr(self._locale, en_text, key))
        self._refresh_custom_hotkey_preview()

    # ---- hotkey helpers ----

    def _on_hotkey_mode_changed(self, _button_id: int) -> None:
        self._apply_hotkey_control_state()

    def _apply_hotkey_control_state(self) -> None:
        checked_id = self._hotkey_button_group.checkedId()
        is_custom = self._hotkey_mode_map.get(checked_id) == "custom"
        self._custom_area.setVisible(is_custom)
        self._refresh_custom_hotkey_preview()

    def _refresh_custom_hotkey_preview(self) -> None:
        if not self._custom_hotkey_tokens:
            self.hotkey_custom_preview.setText(
                _tr(self._locale, "No custom hotkey recorded yet.", "hotkey_custom_empty")
            )
            return
        value = label_for_hotkey_tokens(self._custom_hotkey_tokens)
        prefix = _tr(self._locale, "Custom:", "hotkey_custom_hint")
        self.hotkey_custom_preview.setText(f"{prefix} {value}")

    def _begin_custom_hotkey_record(self) -> None:
        dialog = CustomHotkeyCaptureDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        valid, reason, tokens = self._validate_custom_hotkey(set(dialog.captured_tokens))
        if not valid:
            QMessageBox.warning(self, "Talky", reason)
            self._refresh_custom_hotkey_preview()
            return
        self._custom_hotkey_tokens = tokens
        self._refresh_custom_hotkey_preview()
        QMessageBox.information(
            self, "Talky",
            f"Custom hotkey recorded: {label_for_hotkey_tokens(tokens)}",
        )

    def _validate_custom_hotkey(self, tokens: set[str]) -> tuple[bool, str, list[str]]:
        filtered = sorted(t for t in tokens if t)
        if not filtered:
            return False, "No valid key detected. Hold modifiers or function keys.", []
        if len(filtered) == 1 and filtered[0] in {"space", "enter"}:
            return False, "Single typing key is not allowed for hold-to-talk.", []
        token_set = set(filtered)
        if "cmd" in token_set and "space" in token_set:
            return False, "Cmd+Space conflicts with system shortcuts. Choose another hotkey.", []
        stable_tokens = {"alt", "cmd", "ctrl", "shift", "fn"}
        normalized = [t for t in filtered if t in stable_tokens]
        if not normalized:
            return False, "Only modifier keys are supported for custom hotkey.", []
        return True, "", normalized

    def _reset_default_hotkey(self) -> None:
        default_id = self._hotkey_id_for_mode.get("fn", 0)
        btn = self._hotkey_button_group.button(default_id)
        if btn:
            btn.setChecked(True)
        self._apply_hotkey_control_state()

    # ---- permission ----

    def _refresh_permission_status(self) -> None:
        mic_ok, _ = check_microphone_granted()
        ax_ok = is_accessibility_trusted(prompt=False)

        granted_text = _tr(self._locale, "Granted", "granted")
        denied_text = _tr(self._locale, "Not Granted", "not_granted")
        ok_style = "color: #34C759; font-weight: 600; font-size: 12px;"
        fail_style = "color: #FF3B30; font-weight: 600; font-size: 12px;"

        self.mic_status_value_label.setText(
            f"\u2713 {granted_text}" if mic_ok else f"\u2717 {denied_text}"
        )
        self.mic_status_value_label.setStyleSheet(ok_style if mic_ok else fail_style)

        self.ax_status_value_label.setText(
            f"\u2713 {granted_text}" if ax_ok else f"\u2717 {denied_text}"
        )
        self.ax_status_value_label.setStyleSheet(ok_style if ax_ok else fail_style)

        self.request_mic_button.setVisible(not mic_ok)
        self.permission_button.setVisible(not ax_ok)

    def _check_accessibility(self) -> None:
        is_accessibility_trusted(prompt=True)
        self._refresh_permission_status()

    def _request_microphone_permission(self) -> None:
        granted, detail = request_microphone_permission()
        self._refresh_permission_status()
        if granted:
            QMessageBox.information(self, "Talky", "Microphone permission granted.")
            return
        QMessageBox.warning(
            self, "Talky",
            "Microphone permission missing."
            + "\nSystem Settings > Privacy & Security > Microphone."
            + (f"\nDetails: {detail}" if detail else ""),
        )


# ---------------------------------------------------------------------------
# Dashboard Window (tabbed)
# ---------------------------------------------------------------------------


class SettingsWindow(QWidget):
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self._locale = controller.settings.ui_locale
        self._fade_in_animation: QPropertyAnimation | None = None

        self.setWindowTitle("Talky Dashboard")
        self.resize(720, 580)

        close_shortcut = QShortcut(QKeySequence.StandardKey.Close, self)
        close_shortcut.activated.connect(self.close)

        # ---- Segmented tab bar ----
        tab_bar_frame = QFrame()
        tab_bar_frame.setObjectName("SegmentedBar")
        tab_bar_layout = QHBoxLayout(tab_bar_frame)
        tab_bar_layout.setContentsMargins(3, 3, 3, 3)
        tab_bar_layout.setSpacing(1)

        self._tab_buttons: list[QPushButton] = []
        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)

        tab_keys = [
            ("Home", "home"),
            ("History", "history"),
            ("Dictionary", "dictionary"),
            ("Configs", "configs"),
        ]
        for i, (en, key) in enumerate(tab_keys):
            btn = QPushButton(_tr(self._locale, en, key))
            btn.setCheckable(True)
            btn.setObjectName("SegmentTab")
            self._tab_buttons.append(btn)
            self._tab_group.addButton(btn, i)
            tab_bar_layout.addWidget(btn)
        self._tab_buttons[0].setChecked(True)
        self._tab_keys = tab_keys

        # ---- Tab content ----
        self._stack = QStackedWidget()
        self._home_tab = HomeTab(controller)
        self._history_tab = HistoryTab(controller)
        self._dictionary_tab = DictionaryTab(controller)
        self._configs_tab = ConfigsTab(controller)

        self._stack.addWidget(self._home_tab)
        self._stack.addWidget(self._history_tab)
        self._stack.addWidget(self._dictionary_tab)
        self._stack.addWidget(self._configs_tab)

        self._tab_group.idClicked.connect(self._on_tab_changed)

        # ---- Layout (native — no wrapper container) ----
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 16)
        root.setSpacing(10)

        tab_row = QHBoxLayout()
        tab_row.addStretch()
        tab_row.addWidget(tab_bar_frame)
        tab_row.addStretch()
        root.addLayout(tab_row)

        root.addWidget(self._stack, 1)

        self.setStyleSheet(NATIVE_STYLESHEET)

        self.controller.settings_updated.connect(self.load_from_settings)
        self.load_from_settings(self.controller.settings)

    def _on_tab_changed(self, tab_id: int) -> None:
        self._stack.setCurrentIndex(tab_id)
        if tab_id == 1:
            self._history_tab.refresh()
        elif tab_id == 2:
            self._dictionary_tab.refresh_from_settings(self.controller.settings)

    def load_from_settings(self, settings: AppSettings) -> None:
        self._locale = settings.ui_locale
        for i, (en, key) in enumerate(self._tab_keys):
            self._tab_buttons[i].setText(_tr(self._locale, en, key))
        self._home_tab.update_locale(self._locale)
        self._history_tab.update_locale(self._locale)
        self._dictionary_tab.refresh_from_settings(settings)
        self._configs_tab.load_from_settings(settings)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._auto_save_configs()
        super().closeEvent(event)

    def _auto_save_configs(self) -> None:
        new_settings = self._configs_tab.collect_settings()
        if new_settings.to_dict() == self.controller.settings.to_dict():
            return
        self.controller.update_settings(new_settings)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._configs_tab._refresh_permission_status()  # noqa: SLF001
        self.setWindowOpacity(0.0)
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(180)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._fade_in_animation = anim


# ---------------------------------------------------------------------------
# System Tray
# ---------------------------------------------------------------------------


class TrayApp:
    def __init__(self, controller: AppController, settings_window: SettingsWindow) -> None:
        self.controller = controller
        self.settings_window = settings_window
        self.result_popup = ResultPopupWindow()
        self._last_error_message = ""
        self._external_show_signal_path = Path.home() / ".talky" / "show_settings.signal"
        self._external_show_signal_timer: QTimer | None = None
        self.dictionary_shortcut_listener = GlobalShortcutListener(
            on_trigger=self.controller.request_show_settings
        )

        icon = self._load_tray_icon()
        self.tray = QSystemTrayIcon(icon)
        self.tray.setToolTip("Talky - Local Voice Input Assistant")

        menu = QMenu()
        locale = self.controller.settings.ui_locale
        self.open_action = QAction(
            _tr(locale, "Dashboard", "open_dashboard"), menu
        )
        self.show_last_error_action = QAction(
            _tr(locale, "Show Last Error", "show_last_error"), menu
        )
        self.quit_action = QAction(_tr(locale, "Quit", "quit"), menu)
        menu.addAction(self.open_action)
        menu.addAction(self.show_last_error_action)
        menu.addSeparator()
        menu.addAction(self.quit_action)

        self.open_action.triggered.connect(self.show_settings)
        self.show_last_error_action.triggered.connect(self._show_last_error_dialog)
        self.quit_action.triggered.connect(self.quit_app)
        self.show_last_error_action.setEnabled(False)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)

        self._ready_for_tray_click = False

        self.controller.status_signal.connect(self._show_status)
        self.controller.error_signal.connect(self._show_error)
        self.controller.show_result_popup_signal.connect(self._show_result_popup)
        self.controller.show_settings_window_signal.connect(self.show_settings)
        self.controller.settings_updated.connect(self._on_settings_updated)

    def _load_tray_icon(self) -> QIcon:
        icon_2x_path = _asset_path("tray_icon@2x.png")
        icon_path = _asset_path("tray_icon.png")
        if icon_2x_path.exists():
            pixmap = QPixmap(str(icon_2x_path))
            pixmap.setDevicePixelRatio(2.0)
            icon = QIcon(pixmap)
        elif icon_path.exists():
            icon = QIcon(str(icon_path))
        else:
            icon = self.settings_window.style().standardIcon(
                QStyle.StandardPixmap.SP_MediaVolume
            )
        icon.setIsMask(True)
        return icon

    def show(self) -> None:
        self.tray.show()
        self.dictionary_shortcut_listener.start()
        self._start_external_show_signal_watcher()
        QTimer.singleShot(1500, self._enable_tray_click)
        locale = self.controller.settings.ui_locale
        self._show_status(_tr(locale, "Talky started. Hold hotkey to record.", "started"))

    def _enable_tray_click(self) -> None:
        self._ready_for_tray_click = True

    def show_settings(self) -> None:
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def quit_app(self) -> None:
        import multiprocessing.resource_tracker
        import os
        import signal as _signal

        if self._external_show_signal_timer is not None:
            self._external_show_signal_timer.stop()
            self._external_show_signal_timer = None
        try:
            self._external_show_signal_path.unlink(missing_ok=True)
        except Exception:
            pass
        self.dictionary_shortcut_listener.stop()
        self.controller.stop()
        self.tray.hide()

        for child in multiprocessing.active_children():
            try:
                child.terminate()
                child.join(timeout=1)
                if child.is_alive():
                    child.kill()
            except Exception:
                pass
        try:
            tracker_pid = getattr(
                multiprocessing.resource_tracker._resource_tracker, "_pid", None
            )
            if tracker_pid:
                os.kill(tracker_pid, _signal.SIGTERM)
        except Exception:
            pass

        QApplication.quit()
        os._exit(0)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if not self._ready_for_tray_click:
            return

    def _show_status(self, message: str) -> None:
        self.tray.showMessage("Talky", message, QSystemTrayIcon.MessageIcon.Information, 1200)

    def _show_error(self, message: str) -> None:
        locale = self.controller.settings.ui_locale
        self._last_error_message = message
        self.show_last_error_action.setEnabled(True)
        summary = message.strip().splitlines()[0] if message.strip() else message
        if len(summary) > 220:
            summary = summary[:220] + "..."
        self.tray.showMessage(
            f"Talky {_tr(locale, 'Error', 'error')}",
            summary,
            QSystemTrayIcon.MessageIcon.Warning,
            3000,
        )

    def _show_last_error_dialog(self) -> None:
        locale = self.controller.settings.ui_locale
        if not self._last_error_message:
            QMessageBox.information(
                self.settings_window, "Talky",
                _tr(locale, "No error yet.", "no_error_yet"),
            )
            return

        dialog = QDialog(self.settings_window)
        dialog.setWindowTitle(_tr(locale, "Last Error", "last_error_title"))
        dialog.resize(760, 360)

        layout = QVBoxLayout(dialog)
        details = QPlainTextEdit()
        details.setReadOnly(True)
        details.setPlainText(self._last_error_message)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        copy_button = QPushButton(_tr(locale, "Copy", "copy"))
        close_button = QPushButton(_tr(locale, "Close", "close"))
        copy_button.clicked.connect(lambda: pyperclip.copy(self._last_error_message))
        close_button.clicked.connect(dialog.accept)
        button_row.addWidget(copy_button)
        button_row.addWidget(close_button)

        layout.addWidget(details)
        layout.addLayout(button_row)
        dialog.exec()

    def _show_result_popup(self, text: str) -> None:
        self.result_popup.show_text(text, self.controller.settings.ui_locale)

    def _on_settings_updated(self, settings: AppSettings) -> None:
        locale = settings.ui_locale
        self.open_action.setText(_tr(locale, "Dashboard", "open_dashboard"))
        self.show_last_error_action.setText(
            _tr(locale, "Show Last Error", "show_last_error")
        )
        self.quit_action.setText(_tr(locale, "Quit", "quit"))

    def _start_external_show_signal_watcher(self) -> None:
        if self._external_show_signal_timer is not None:
            return
        try:
            self._external_show_signal_path.unlink(missing_ok=True)
        except Exception:
            pass
        timer = QTimer()
        timer.setInterval(400)
        timer.timeout.connect(self._check_external_show_signal)
        timer.start()
        self._external_show_signal_timer = timer

    def _check_external_show_signal(self) -> None:
        try:
            if not self._external_show_signal_path.exists():
                return
            self._external_show_signal_path.unlink(missing_ok=True)
            self.show_settings()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Result Popup
# ---------------------------------------------------------------------------


class ResultPopupWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(560, 360)
        self._fade_animation: QPropertyAnimation | None = None
        self._slide_animation: QPropertyAnimation | None = None

        self.text_view = QTextEdit()
        self.text_view.setObjectName("ResultPanel")
        self.text_view.setReadOnly(True)
        self.text_view.setPlaceholderText("Generated content will appear here.")

        self.title = QLabel("No Focus Target Detected")
        self.title.setObjectName("CardTitle")
        self.subtitle = QLabel("Result is ready. Copy and paste manually.")
        self.subtitle.setObjectName("WindowSubtitle")

        self.copy_close_button = QPushButton("Copy and Close")
        self.copy_close_button.setObjectName("PrimaryButton")
        self.copy_close_button.clicked.connect(self._copy_and_close)

        root = QVBoxLayout()
        root.setContentsMargins(10, 10, 10, 10)

        card = QFrame()
        card.setObjectName("PopupCard")
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 12)
        shadow.setColor(Qt.GlobalColor.gray)
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 16)
        card_layout.addWidget(self.title)
        card_layout.addWidget(self.subtitle)
        card_layout.addWidget(self.text_view)
        card_layout.addWidget(self.copy_close_button)
        root.addWidget(card)
        self.setLayout(root)
        self.setStyleSheet(NATIVE_STYLESHEET)

    def show_text(self, text: str, locale: str) -> None:
        self.title.setText(_tr(locale, "No Focus Target Detected", "popup_title"))
        self.subtitle.setText(_tr(locale, "Result is ready. Copy and paste manually.", "popup_subtitle"))
        self.copy_close_button.setText(_tr(locale, "Copy and Close", "copy_close"))
        self.text_view.setPlainText(text)
        self._move_to_bottom_right()
        end_rect = self.geometry()
        start_rect = QRect(end_rect.x(), end_rect.y() + 18, end_rect.width(), end_rect.height())
        self.setGeometry(start_rect)
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self.activateWindow()
        self._animate_popup(start_rect, end_rect)

    def _copy_and_close(self) -> None:
        pyperclip.copy(self.text_view.toPlainText())
        self.close()

    def _move_to_bottom_right(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        x = rect.x() + rect.width() - self.width() - 24
        y = rect.y() + rect.height() - self.height() - 24
        self.move(x, y)

    def _animate_popup(self, start_rect: QRect, end_rect: QRect) -> None:
        fade = QPropertyAnimation(self, b"windowOpacity")
        fade.setDuration(190)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        fade.start()
        self._fade_animation = fade

        slide = QPropertyAnimation(self, b"geometry")
        slide.setDuration(190)
        slide.setStartValue(start_rect)
        slide.setEndValue(end_rect)
        slide.setEasingCurve(QEasingCurve.Type.OutCubic)
        slide.start()
        self._slide_animation = slide
