# 设计：优先使用已装本地 Ollama 模型（不再强推 qwen3.5）

- 状态：草稿，待用户复核
- 日期：2026-06-03
- 类型：行为修复（systematic-debugging 根因已定位）

## 1. 问题与根因（已实证）

App 会把"未安装 qwen3.5"判定为"没有可用模型"，从而把用户推向"在 Terminal 下载 qwen3.5"，即便本地已装 gemma4:e2b 可用。

根因链（证据）：
- `talky/models.py:12` `RECOMMENDED_OLLAMA_MODEL = "qwen3.5:9b"`；`models.py:49` `ollama_model` 默认 = `_default_ollama_model()` → qwen3.5。
- `talky/preflight.py:28-30`：`required and required not in models → NO_MODEL`。**只认精确配置模型，无视其他已装模型。**
  - 实证（本机仅装 gemma4:e2b）：`run_preflight_check(required_model="qwen3.5:9b") → NO_MODEL`；`required="" → READY`；`required="gemma4:e2b" → READY`。
- 下载动作（`osascript ... 'do script "ollama pull qwen3.5:9b"'`）在 `talky/onboarding.py:553-558`（向导第 3 页按钮 :463）与 `:1131-1142`（returning-user "配置模型不可用" 分支），由 `ensure_local_ollama_ready`（`startup_gate.py:212/221/243`）触发。该启动调用已被 `be77711` 从 main.py 摘除（纯启动+Daily 不再自动弹），但同一错误逻辑仍活在：
  - `talky/ui.py:2255-2298 _ensure_llm_mode_ready_or_revert` + `:2353-2384 _validate_mode_ready`（切到 vibecoding/translation 时 `ollama_model not in models` 即拦/回退）。
  - `talky/main.py:442 _deferred_local_ollama_recheck`（精确模型不在即弹提示+开设置）。
  - 运行时 LLM 用 `settings.ollama_model`（qwen3.5），未装则调用失败。

**一句话根因：`ollama_model` 钉死硬编码 qwen3.5，且"就绪"被定义为"恰好装了 qwen3.5"而非"有任意可用本地模型"。**

## 2. 目标 / 非目标

### 目标（用户诉求）
- 不强制用户下载 qwen3.5。
- 本地已有任意模型时，**优先静默采用已装的本地模型**（用户已确认：silent auto-adopt）。
- 覆盖**全部活跃路径**（用户已确认范围）。

### 非目标
- 不改 `RECOMMENDED_OLLAMA_MODEL`：qwen3.5 仍作为**零模型**时的"建议下载"项（建议，非强制）。
- 不改 `run_preflight_check` 的契约（它仍诚实回答"指定模型在不在"）；改的是"调用前先解析/绑定到已装模型"。
- 不重构 OnboardingWizard 的首启分页内部（该路径在 main.py 已半死；只改 returning-user 分支 + 解析逻辑）。

## 3. 设计

### 3.1 核心纯函数（单点收敛）
`talky/models.py` 新增：
```python
def resolve_installed_model(configured: str, host: str = "") -> str:
    """优先已装模型：配置模型已装→保持；未装但有别的→采用已装的第一个；一个都没装→保留 configured。"""
    models = list_ollama_models(host)
    if not models:
        return configured              # 零模型 → 保留推荐值（供"建议下载"）
    if configured and configured in models:
        return configured              # 配置已装 → 保持
    return models[0]                   # 配置未装但有别的 → 静默采用
```
纯函数（仅依赖 `list_ollama_models`），易测、无 UI/Qt 依赖。

### 3.2 接入点（把"硬卡 qwen3.5"换成"先解析/绑定"）

1. **运行时自动绑定 + 持久化（最关键）** — `talky/controller.py`
   - 新增 `_auto_adopt_installed_model()`：`resolve_installed_model(settings.ollama_model, host)`；若结果与当前不同 → 更新 `settings.ollama_model`、`config_store.save(settings)`、重建 LLM（`OllamaTextCleaner` 用新模型名）、`settings_updated.emit`（排队到主线程）。
   - **在后台线程调用**（并入现有 `_warm_up_models_async` 的 worker，或在 `start()` 后起一个 daemon），避免 `list_ollama_models` 的最长 5s HTTP 阻塞启动。
   - 仅本地/远程模式执行（cloud 跳过）。

2. **切到 vibecoding/translation** — `talky/ui.py _ensure_llm_mode_ready_or_revert`
   - 当 `mode in {local,remote}` 且配置模型不在已装列表、但**列表非空** → 调 `resolve_installed_model` 绑定到已装模型（写回 combo + 走正常保存），**放行**。
   - 仅当 **Ollama 不可达** 或 **零模型** 时才弹"Ollama Required"并回退 Daily。
   - `_validate_mode_ready` 相应调整：零模型/不可达 → 不就绪；配置模型缺失但有别的 → 视为可绑定（不再直接判失败）。

3. **启动后 recheck** — `talky/main.py _deferred_local_ollama_recheck`
   - 先 `resolve_installed_model` 再判就绪：有任意已装模型即视为 OK，不再因"非 qwen3.5"弹提示/开设置。

4. **returning-user 提示** — `talky/onboarding.py show_returning_user_prompt`
   - "配置模型不可用但有其他模型"分支（:1083+）：**默认自动绑定**到已装模型并返回就绪，不再把"下载 qwen3.5"摆为主行动。
   - 仅"零模型"分支保留"建议下载推荐模型"。

### 3.3 不变量
- 有任意本地模型 → 永不弹/触发模型下载。
- 仅"Ollama 在跑但零模型"时，才建议（非强制）下载推荐模型。
- 多模型且配置缺失时取 `models[0]`（Ollama 返回序）；用户可在 Settings 改。后续可加更聪明的挑选（避开 embedding 等），本期不做（YAGNI）。

## 4. 文件改动清单
- 改 `talky/models.py`：`+ resolve_installed_model`。
- 改 `talky/controller.py`：`+ _auto_adopt_installed_model`，后台调用 + 持久化 + 重建 LLM。
- 改 `talky/ui.py`：`_ensure_llm_mode_ready_or_revert` / `_validate_mode_ready` 自动绑定。
- 改 `talky/main.py`：`_deferred_local_ollama_recheck` 先解析再判就绪。
- 改 `talky/onboarding.py`：`show_returning_user_prompt` 的"配置不可用但有其他"分支自动绑定。
- 测试：`tests/test_models.py`（或既有就近文件）测 `resolve_installed_model`；`tests/test_controller_hotkey_threading.py` 测自动绑定+持久化；mode-switch/preflight 相关补测。

## 5. 测试计划
- `resolve_installed_model`（纯函数）：配置已装→保持；配置缺失+有别的→取 models[0]；零模型→保留 configured；空 configured + 有模型→取 models[0]。
- controller `_auto_adopt_installed_model`：配置=qwen3.5、已装=[gemma4] → 绑定 gemma4 + 持久化（用 fake config store + monkeypatch list_ollama_models）；配置已装 → 不变不存盘；cloud 模式 → 跳过。
- ui mode-switch：配置缺失但有模型 → 不弹框、自动绑定、放行（用既有 _build_window mock 套路）；零模型 → 仍拦+回退 Daily。
- 回归：现有 `test_onboarding_preflight` / `test_startup_gate` 等不破。
- 注意：仓库有 8 个 pre-existing 失败（与本改动无关），完成门槛 = 不新增失败 + 新测试全绿。

## 6. 已确认决策
- 配置模型缺失但有其他 → 静默自动采用（不弹窗/不下载）。
- 覆盖范围 → 全部活跃路径。
- qwen3.5 保留为零模型时的建议下载项。
