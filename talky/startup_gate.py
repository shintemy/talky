"""Strict startup checks: do not start tray/hotkey until local Ollama or cloud API is usable."""

from __future__ import annotations

import os
import subprocess

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from talky.config_store import AppConfigStore
from talky.macos_ui import activate_foreground_app, prepare_qt_modal_for_macos
from talky.models import AppSettings
from talky.preflight import OllamaStatus, detect_system_locale, run_preflight_check
from talky.remote_service import verify_cloud_server


def apply_ollama_host_from_settings(settings: AppSettings) -> None:
    host = (settings.ollama_host or "http://127.0.0.1:11434").strip().rstrip("/")
    if not host:
        host = "http://127.0.0.1:11434"
    os.environ["OLLAMA_HOST"] = host


def _is_local_ollama_host(host: str) -> bool:
    value = (host or "").strip().lower()
    return value in {
        "",
        "http://127.0.0.1:11434",
        "http://localhost:11434",
        "http://[::1]:11434",
    }


def _build_unready_local_prompt(
    *,
    status: OllamaStatus,
    mode: str,
    host: str,
    zh: bool,
) -> tuple[str, str, bool, bool, bool]:
    """Build copy and button visibility for local/remote Ollama warning.

    Returns:
        (title, body, show_remote_button, show_download_button, show_open_button)
    """
    if status == OllamaStatus.NOT_INSTALLED:
        title = (
            "本地模式未检测到 Ollama。"
            if zh and mode == "local"
            else "Local mode requires Ollama on this Mac."
            if mode == "local"
            else "Ollama service is not available."
        )
        if mode == "local":
            body = (
                f"当前地址：{host}\n\n请先安装并启动 Ollama。你可以点击「打开 Ollama」，"
                "或在终端运行 `ollama serve`。"
                if zh
                else f"Host: {host}\n\nPlease install and start Ollama on this Mac. "
                "Click 'Open Ollama', or run `ollama serve` in Terminal."
            )
        else:
            body = (
                f"当前地址：{host}\n\n请确认该远端地址可访问，或点击「连接远端 Ollama…」重新配置。"
                if zh
                else f"Host: {host}\n\nVerify this remote host is reachable, or use "
                "'Connect remote Ollama…' to reconfigure."
            )
        return title, body, mode == "remote", True, mode == "local"

    if status == OllamaStatus.NOT_RUNNING:
        if mode == "local":
            title = "本地模式无法连接到 Ollama。" if zh else "Cannot reach local Ollama."
            body = (
                f"当前地址：{host}\n\n请启动 Ollama（可点击「打开 Ollama」），"
                "或在终端运行 `ollama serve`。"
                if zh
                else f"Host: {host}\n\nStart Ollama (you can click 'Open Ollama'), "
                "or run `ollama serve` in Terminal."
            )
            return title, body, False, False, _is_local_ollama_host(host)
        title = "无法连接远端 Ollama。" if zh else "Cannot reach remote Ollama."
        body = (
            f"当前地址：{host}\n\n请确认远端 Ollama 已启动并且网络可达。"
            if zh
            else f"Host: {host}\n\nMake sure remote Ollama is running and reachable."
        )
        return title, body, True, False, False

    title = (
        "Ollama 已连接，但未检测到可用模型。"
        if zh
        else "Ollama is reachable but no models were found."
    )
    body = (
        f"当前地址：{host}\n\n请在终端执行 `ollama pull <模型名>` 后再试录音。"
        if zh
        else f"Host: {host}\n\nRun `ollama pull <model>` in Terminal, then try again."
    )
    return title, body, mode == "remote", False, False


def _try_open_local_ollama_app() -> None:
    try:
        subprocess.Popen(["open", "-a", "Ollama"])  # noqa: S603,S607
    except Exception:
        pass


def alert_if_local_ollama_unready(config_store: AppConfigStore) -> bool:
    """When opening Settings in local mode, warn if Ollama is not usable.

    Startup only checks once; this covers later changes (Ollama stopped, wrong host, etc.).

    Returns True if the user saved a new host via Connect remote — caller should reload controller.
    """
    settings = config_store.load()
    if settings.mode not in {"local", "remote"}:
        return False

    apply_ollama_host_from_settings(settings)

    from talky.onboarding import RemoteOllamaConnectDialog

    status = run_preflight_check(required_model=settings.ollama_model)
    if status == OllamaStatus.READY:
        return False

    locale = detect_system_locale()
    zh = locale == "zh"
    host = (settings.ollama_host or "http://127.0.0.1:11434").strip()

    main, info, show_remote_btn, show_download_btn, show_open_btn = _build_unready_local_prompt(
        status=status,
        mode=settings.mode,
        host=host,
        zh=zh,
    )

    box = QMessageBox()
    box.setWindowTitle("Talky")
    box.setIcon(QMessageBox.Icon.Warning)
    box.setText(main)
    box.setInformativeText(info)
    btn_ok = box.addButton("知道了" if zh else "OK", QMessageBox.ButtonRole.AcceptRole)
    btn_remote = None
    if show_remote_btn:
        btn_remote = box.addButton(
            "连接远端 Ollama…" if zh else "Connect remote Ollama…",
            QMessageBox.ButtonRole.ActionRole,
        )
    dl_btn = None
    if show_download_btn:
        dl_btn = box.addButton(
            "打开下载页" if zh else "Open download page",
            QMessageBox.ButtonRole.ActionRole,
        )
    open_btn = None
    if show_open_btn:
        open_btn = box.addButton(
            "打开 Ollama" if zh else "Open Ollama",
            QMessageBox.ButtonRole.ActionRole,
        )
    box.setDefaultButton(btn_ok)
    prepare_qt_modal_for_macos(box)
    box.exec()
    clicked = box.clickedButton()
    if open_btn is not None and clicked == open_btn:
        _try_open_local_ollama_app()
        return False
    if dl_btn is not None and clicked == dl_btn:
        QDesktopServices.openUrl(QUrl("https://ollama.com/download"))
        return False
    if btn_remote is not None and clicked == btn_remote:
        dlg = RemoteOllamaConnectDialog(config_store, locale=locale)
        prepare_qt_modal_for_macos(dlg)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return True
    return False


def ensure_local_ollama_ready(config_store: AppConfigStore) -> bool:
    from PyQt6.QtWidgets import QDialog

    from talky.onboarding import OnboardingWizard, show_returning_user_prompt

    settings = config_store.load()
    apply_ollama_host_from_settings(settings)
    status = run_preflight_check(required_model=settings.ollama_model)
    if status == OllamaStatus.READY:
        return True

    locale = detect_system_locale()
    is_first_run = not config_store.config_path.exists()
    zh = locale == "zh"

    if is_first_run:
        wizard = OnboardingWizard(
            config_store=config_store,
            ollama_status=status,
            locale=locale,
        )
        prepare_qt_modal_for_macos(wizard)
        if wizard.exec() != QDialog.DialogCode.Accepted:
            return False
        settings = config_store.load()
        apply_ollama_host_from_settings(settings)
        if run_preflight_check(required_model=settings.ollama_model) != OllamaStatus.READY:
            QMessageBox.warning(
                None,
                "Talky",
                "Ollama is still not ready. Finish setup and open Talky again."
                if not zh
                else "Ollama 仍未就绪，请完成设置后重新打开 Talky。",
            )
            return False
        return True

    activate_foreground_app()
    if not show_returning_user_prompt(
        status,
        locale=locale,
        config_store=config_store,
        expected_model=settings.ollama_model,
    ):
        return False
    settings = config_store.load()
    apply_ollama_host_from_settings(settings)
    if run_preflight_check(required_model=settings.ollama_model) != OllamaStatus.READY:
        QMessageBox.warning(
            None,
            "Talky",
            "Ollama is still not ready. Fix the issue and open Talky again."
            if not zh
            else "Ollama 仍未就绪，请解决问题后重新打开 Talky。",
        )
        return False
    return True


_CLOUD_ZH = {
    "title": "Talky 云端",
    "url": "API 地址",
    "key": "API 密钥",
    "test": "检测连接",
    "ok": "继续",
    "cancel": "取消",
    "need_test": "请先点击「检测连接」并等待成功。",
    "hint": "填写地址与密钥后点击「检测连接」。服务器须返回可用的语音识别与语言模型信息。",
}


def _cloud_tr(locale: str, key: str, en: str) -> str:
    if locale == "zh":
        return _CLOUD_ZH.get(key, en)
    return en


class CloudSetupDialog(QDialog):
    """Block until user tests and saves working cloud API URL + key."""

    def __init__(
        self,
        config_store: AppConfigStore,
        *,
        locale: str = "en",
        error_hint: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._config_store = config_store
        self._locale = locale
        self._verified = False

        self.setWindowTitle(_cloud_tr(locale, "title", "Talky Cloud"))
        self.setMinimumWidth(480)

        from talky.ui import IOS26_STYLESHEET

        self.setStyleSheet(IOS26_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)

        intro = QLabel(
            _cloud_tr(
                locale,
                "hint",
                "Enter your server URL and API key, then use Test connection. "
                "The server must report ready ASR and LLM models.",
            )
        )
        intro.setWordWrap(True)
        intro.setObjectName("WindowSubtitle")
        layout.addWidget(intro)

        layout.addWidget(QLabel(_cloud_tr(locale, "url", "API URL")))
        self._url = QLineEdit()
        self._url.setPlaceholderText("https://api.example.com:8000")
        layout.addWidget(self._url)

        layout.addWidget(QLabel(_cloud_tr(locale, "key", "API key")))
        self._key = QLineEdit()
        self._key.setEchoMode(QLineEdit.EchoMode.Password)
        self._key.setPlaceholderText("sk-...")
        layout.addWidget(self._key)

        self._status = QLabel(error_hint or "")
        self._status.setWordWrap(True)
        self._status.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self._status)

        row = QHBoxLayout()
        test_btn = QPushButton(_cloud_tr(locale, "test", "Test connection"))
        test_btn.setObjectName("PrimaryButton")
        test_btn.clicked.connect(self._on_test)
        row.addWidget(test_btn)
        row.addStretch()
        layout.addLayout(row)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton(_cloud_tr(locale, "cancel", "Cancel"))
        cancel_btn.setObjectName("SecondaryButton")
        cancel_btn.clicked.connect(self.reject)
        self._ok_btn = QPushButton(_cloud_tr(locale, "ok", "Continue"))
        self._ok_btn.setObjectName("PrimaryButton")
        self._ok_btn.setEnabled(False)
        self._ok_btn.clicked.connect(self._on_ok)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._ok_btn)
        layout.addLayout(btn_row)

        s = config_store.load()
        self._url.setText(s.cloud_api_url.strip())
        self._key.setText(s.cloud_api_key)

    def _on_test(self) -> None:
        self._verified = False
        self._ok_btn.setEnabled(False)
        url = self._url.text().strip()
        key = self._key.text().strip()
        ok, err, data = verify_cloud_server(url, key)
        if ok and data:
            wm = data.get("whisper_model", "")
            lm = data.get("llm_model", "")
            self._status.setText(
                f"OK — ASR: {wm}\nLLM: {lm}"
                if self._locale != "zh"
                else f"连接成功 — 语音: {wm}\n语言模型: {lm}"
            )
            self._status.setStyleSheet("color: #1a7f37; font-size: 12px;")
            self._verified = True
            self._ok_btn.setEnabled(True)
        else:
            self._status.setText(err or "Connection failed.")
            self._status.setStyleSheet("color: #b00020; font-size: 12px;")

    def _on_ok(self) -> None:
        if not self._verified:
            QMessageBox.warning(
                self,
                "Talky",
                _cloud_tr(self._locale, "need_test", "Use Test connection and wait for success first."),
            )
            return
        url = self._url.text().strip().rstrip("/")
        key = self._key.text().strip()
        settings = self._config_store.load()
        settings.mode = "cloud"
        settings.cloud_api_url = url
        settings.cloud_api_key = key
        self._config_store.save(settings)
        self.accept()


def ensure_whisper_ready(config_store: AppConfigStore) -> bool:
    """Block until Whisper model is locally cached. Shows ModelSetupDialog if missing."""
    from talky.asr_service import is_whisper_model_cached
    from talky.macos_ui import prepare_qt_modal_for_macos

    settings = config_store.load()
    if settings.mode == "cloud":
        return True
    if is_whisper_model_cached(settings.whisper_model):
        return True

    from talky.ui import ModelSetupDialog

    dialog = ModelSetupDialog(locale=settings.ui_locale)

    def _on_configured(model_name: str) -> None:
        s = config_store.load()
        s.whisper_model = model_name
        config_store.save(s)

    dialog.model_configured.connect(_on_configured)
    prepare_qt_modal_for_macos(dialog)
    result = dialog.exec()
    if result == QDialog.DialogCode.Accepted:
        return True
    settings = config_store.load()
    return is_whisper_model_cached(settings.whisper_model)


def ensure_cloud_ready(config_store: AppConfigStore) -> bool:
    from PyQt6.QtWidgets import QDialog

    from talky.onboarding import detect_system_locale

    locale = detect_system_locale()
    last_err = ""

    while True:
        settings = config_store.load()
        if settings.mode != "cloud":
            return True

        url = settings.cloud_api_url.strip()
        key = settings.cloud_api_key.strip()
        if url and key:
            ok, err, _ = verify_cloud_server(url, key)
            if ok:
                return True
            last_err = err or "Cloud server check failed."
        else:
            last_err = (
                "Enter the cloud API URL and API key."
                if locale != "zh"
                else "请填写云端 API 地址和密钥。"
            )

        dlg = CloudSetupDialog(
            config_store,
            locale=locale,
            error_hint=last_err,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False
