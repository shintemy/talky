# Talky — Implemented Features (Client + Server)

This document summarizes behavior shipped in the **main** branch as of the session that closed **2026-03-26** (startup gate, remote Ollama fixes, recommended-model overrides, and related server health). Use it as a checklist for **DMG / release** alignment and QA.

---

## 1. Startup & modes

| Area | Behavior |
|------|----------|
| **Local mode** | Does not start tray / hotkey / pipeline until Ollama preflight passes: reachable host, at least one model (via `/api/tags`). |
| **Cloud mode** | Does not start until `verify_cloud_server()` succeeds: `GET /api/health` with `status: ok`, non-empty `whisper_model` and `llm_model`, and valid `X-API-Key` when the server has keys configured. |
| **First-run wizard** | Full `OnboardingWizard`: local install vs **Connect remote**, remote host test, model selection, recommended model download hints. |
| **Returning users** | `QMessageBox` loops for not-running / no-model; **Quit** uses `NoRole` so primary action (re-check) appears first on macOS. |
| **Exit on failure** | Preflight failure → `main()` returns `1` (no half-started app). |

**Modules:** `main.py`, `talky/startup_gate.py`, `talky/onboarding.py`

---

## 2. Recommended Ollama model (no app rebuild to change)

| Mechanism | Details |
|-----------|---------|
| **Code default** | `talky/models.py` → `RECOMMENDED_OLLAMA_MODEL` |
| **Remote JSON** | Env `TALKY_RECOMMENDED_OLLAMA_JSON_URL` — fetched once per process (~8s timeout); merge over builtin. |
| **Local file** | `~/.talky/recommended_ollama.json` — wins over URL for any field it sets. |
| **Schema** | `model` / `model_name`, optional `library_url` / `ollama_library_url`, optional `pull_command` / `pull`. |
| **UI** | Wizard model page + returning-user “no model” dialog; optional **View on Ollama.com** when `library_url` is set. |
| **Defaults** | `AppSettings.ollama_model` default and settings UI empty fallback use `recommended_model_name()`. |

**Module:** `talky/recommended_ollama.py`

---

## 3. Ollama client (local & LAN)

| Issue fixed | Implementation |
|-------------|----------------|
| Global `ollama.chat()` ignored `OLLAMA_HOST` | `OllamaTextCleaner` uses `ollama.Client(host=OLLAMA_HOST)`; same for `check_ollama_reachable()` → `Client(host).list()`. |
| HTTP fallback | Unchanged: `_chat_via_http` for `/api/chat` when SDK still fails. |

**Modules:** `talky/llm_service.py`, `talky/permissions.py`

---

## 4. Paste & foreground

| Issue fixed | Implementation |
|-------------|----------------|
| Paste from worker thread failed on macOS | `paste_to_front_signal` + `QueuedConnection` → `_do_paste_to_front()` on Qt main thread. |

**Module:** `talky/controller.py`

---

## 5. Talky Cloud server (`talky-server`)

| Endpoint | Behavior |
|----------|----------|
| **`GET /api/health`** | If `api_keys.json` has entries → requires `X-API-Key`; returns `whisper_model` + `llm_model`; **503** `degraded` if either model string empty. |
| **`POST /api/process`** | Unchanged (audio → ASR → LLM). |

**Module:** `talky-server/main.py`

---

## 6. Cloud client verification

| Item | Details |
|------|---------|
| **`verify_cloud_server()`** | Validates health JSON and both model fields; used by startup gate and `CloudProcessService.health_check()`. |

**Module:** `talky/remote_service.py`

---

## 7. Known follow-ups (not blockers)

- **Wizard page 0 vs `NOT_RUNNING`:** If only the Ollama **CLI/app** is present but not running, the wizard may open on the “install Ollama” page instead of mode selection; workaround is uninstall CLI or use **Connect remote** from a clean `NOT_INSTALLED` path. (Optional code fix: always start mode selection on first run.)
- **DMG visual polish:** `TODO(DMG/visual)` in `talky/onboarding.py` — low-contrast `#555` helper text on dark sheets; align with final app stylesheet before signed release.

---

## 8. DMG build (separate worktree)

Packaging lives on branch **`feature/dmg-unsigned-prototype`** (git worktree: `.worktrees/feature-dmg-unsigned-prototype/`).

**Syncing client code from `main`:** A plain `git merge main` often conflicts (DMG `main.py` adds single-instance lock, `aboutToQuit` cleanup, debug log, mic timer, NSAppearance). A reliable approach:

1. Copy these paths from the **main repo** into the worktree (overwrite):  
   `talky/controller.py`, `talky/llm_service.py`, `talky/permissions.py`, `talky/remote_service.py`, `talky/models.py`, `talky/onboarding.py`, `talky/ui.py`, `talky/startup_gate.py`, `talky/recommended_ollama.py`, and the matching `tests/` files plus this `docs/FEATURES.md`.
2. **Merge manually** worktree `main.py`: keep DMG-only blocks (`fcntl` lock, `append_debug_log`, Foundation/AppKit, `_cleanup_on_quit`, mic `QTimer`) and insert **`startup_gate`** (`ensure_cloud_ready` / `ensure_local_ollama_ready`) **before** `AppController` is constructed, with **`return 1`** on failure; use **`QMessageBox.warning`** for accessibility (not tray) when the tray is not ready yet; **remove** the old inline onboarding block (wizard is inside `ensure_local_ollama_ready`).

**Build:**

```bash
cd .worktrees/feature-dmg-unsigned-prototype
./scripts/build_unsigned_dmg.sh "0.4.0-local-gate.1"   # example version tag
```

Output: `release/Talky-<version>-unsigned.dmg`. If **`hdiutil create` times out**, the **`.app` in `dist/`** may still be valid — re-run the script or repeat the DMG steps after closing other disk-heavy tasks.

See also: `docs/DMG_LAN_OLLAMA.md` for Mac mini + MacBook Ollama host setup.
