# 设计：从 Obsidian 自动检测 Vault（按钮）

- 状态：草稿，设计已在对话中确认
- 日期：2026-06-03
- 分支：`feature/obsidian-vault-autodetect`
- 承接：`docs/superpowers/specs/2026-06-03-obsidian-weekly-export-design.md`（Obsidian 导出功能）。本 spec 加一个"少手动选路径"的便捷入口。

## 关联事实（实测于 2026-06-03 本机）

| 假设 | 验证 | 结果 |
| --- | --- | --- |
| Obsidian vault 注册表路径 | `ls "~/Library/Application Support/obsidian/obsidian.json"` | ✅ 存在 |
| 注册表结构：`vaults` map，每项有 `path`/`ts`/`open` | python 解析真实文件 | ✅ 每项键正好是 `['open','path','ts']`；本机 1 个 vault，`open: true`，在 iCloud |
| Talky 非沙盒、ad-hoc 签名、已用 TCC（mic/input-monitoring） | `codesign -dv dist/Talky.app`；`PlistBuddy Info.plist` | ✅ `Signature=adhoc`，无 sandbox key，bundle `com.talky.app` |
| 读 Application Support 不需授权；写 iCloud Drive 受 TCC 保护 | macOS TCC 机制 | Application Support 非保护目录；`~/Library/Mobile Documents`(iCloud) 受保护 |
| 系统文件选择框选中的路径由 powerbox 自动授权（即使在受保护目录） | macOS powerbox 机制（现有 Choose Vault… 已依赖此点能写 iCloud vault） | ✅ 机制确定 |

## 1. 目标 / 非目标

### 目标
给现有「Obsidian 同步」区块加一个 **「从 Obsidian 检测 Vault」** 按钮，省去用户在文件选择框里满硬盘找 vault：
- 点按钮 → Talky 读 `obsidian.json` 找到**当前打开**（`open: true`，否则 `ts` 最新）的 vault；
- → 弹出文件选择框，**预定位到该 vault**；
- → 用户点「打开」**确认**（这一下经 powerbox **授予写权限**）→ 路径填入并持久化（复用现有 `obsidian_vault_path` 流程）。

### 非目标（v1）
- **不**在启动/打开面板时自动读 obsidian.json 自动预填（用户决策：自动读可能拿不到 powerbox 写授权，且不符合"点击才授权"的预期）。
- **不**绕过文件选择框直接写检测到的路径（那样 iCloud 写可能被 TCC 拦/弹不可控的框）。授权必须由用户在系统选择框里点击确认完成。
- 不解析 Obsidian 的其它配置（插件、主题等）。
- 不支持非 macOS 路径（Talky 是 macOS-only app）。

## 2. 纯函数模块 `talky/obsidian_vault.py`（新增，无 Qt）

```python
def obsidian_config_path() -> Path:
    """macOS Obsidian 注册表文件路径。"""
    return Path.home() / "Library" / "Application Support" / "obsidian" / "obsidian.json"


def detect_default_vault(config_path: Path | None = None) -> str | None:
    """返回当前/最近打开的 Obsidian vault 路径；无法确定时返回 None。

    选择规则：优先 open == True 的；并列/无 open 时取 ts 最大的。
    容错：文件缺失 / JSON 损坏 / vaults 为空 / 条目缺 path → None。
    config_path 可注入以便测试（默认用 obsidian_config_path()）。
    """
```

- 纯读 + 纯逻辑，便于单测（注入临时 obsidian.json）。
- 只读 Application Support，**不触碰 iCloud vault**（不在此阶段做 is_dir 等可能触发 TCC 的操作）。

## 3. UI（`ConfigsTab`，`talky/ui.py`）

### 3.1 按钮
在「Obsidian 同步」区块的路径行里，**Choose Vault…** 旁边加一个 **「从 Obsidian 检测」** 按钮（SecondaryButton 风格）。

### 3.2 共享 helper（DRY，重构现有 `_choose_obsidian_vault`）
抽出一个私有方法，二者复用（仅起始目录 + 标题不同）：

```python
def _prompt_vault_dir(self, start_dir: str, title_en: str, title_key: str) -> None:
    chosen = QFileDialog.getExistingDirectory(
        self, _tr(self._locale, title_en, title_key), start_dir
    )  # 不传 DontUseNativeDialog —— 必须用原生框才有 powerbox 授权
    if not chosen:
        return
    self._obsidian_vault_path = chosen
    self._refresh_obsidian_state()
    self._save_settings(quiet=True)
```

- `_choose_obsidian_vault` → `self._prompt_vault_dir(self._obsidian_vault_path or str(Path.home()), "Choose Obsidian Vault", "obsidian_choose_title")`
- `_detect_obsidian_vault`（新）：
  ```python
  detected = detect_default_vault()
  if not detected:
      QMessageBox.information(self, "Talky", _tr(self._locale,
          "Couldn't find an Obsidian vault. Open a vault in Obsidian first.",
          "obsidian_detect_none"))
      return
  self._prompt_vault_dir(detected, "Confirm Obsidian Vault", "obsidian_detect_confirm_title")
  ```

> 选择框以 `directory=detected` 打开 → 用户直接「打开」即返回该 vault → powerbox 授予写权限。选择框由系统进程运行，可定位 iCloud 目录，即使 app 尚无访问权。

### 3.3 i18n（新增 `_ZH` 键 + EN fallback）
- `obsidian_detect`: "从 Obsidian 检测"
- `obsidian_detect_confirm_title`: "确认 Obsidian Vault"
- `obsidian_detect_none`: "没找到 Obsidian 的 vault（请先在 Obsidian 里打开一个 vault）。"

并在 `_apply_locale_texts` 里刷新新按钮文案。

## 4. 边界
- obsidian.json 缺失 / 损坏 / 无 vault → 检测返回 None → 提示文案，不崩溃。
- 检测到的 vault 路径已不存在（被移走）→ 选择框定位失败时由系统框回退到默认位置，用户可手动导航；不特殊处理。
- 用户在选择框点「取消」→ 不改任何状态。
- 不改动导出逻辑（`obsidian_export.py`）与 `AppSettings`（复用现有 `obsidian_vault_path`）。

## 5. 文件改动
### 新增
- `talky/obsidian_vault.py` — `obsidian_config_path` + `detect_default_vault`。
- `tests/test_obsidian_vault.py`。
- 本 spec + 对应 plan。
### 修改
- `talky/ui.py` — `ConfigsTab`：加检测按钮；抽 `_prompt_vault_dir`；重构 `_choose_obsidian_vault`；加 `_detect_obsidian_vault`；3 个 i18n 键 + `_apply_locale_texts` 刷新。
### 不动
- `talky/obsidian_export.py`、`talky/models.py`、`talky/controller.py`、Info.plist/entitlements（无需新增权限）。

## 6. 测试
### `tests/test_obsidian_vault.py`（纯逻辑，注入临时 obsidian.json）
- `detect_default_vault`：单 vault `open:true` → 该路径；多 vault 取 `open:true` 那个；无 open 时取 `ts` 最大；文件缺失 → None；JSON 损坏 → None；`vaults` 为空 → None；条目缺 `path` → 跳过。
- `obsidian_config_path` 指向 `~/Library/Application Support/obsidian/obsidian.json`。
### UI
- 不做单测（沿用本仓库 UI 不单测惯例）；走人工验证。

## 7. 验证（human-flow 优先）
1. 自动：`.venv/bin/python -m pytest tests/test_obsidian_vault.py -q`。
2. 人工：重新打包安装 → Configs → Obsidian 同步 → 点「从 Obsidian 检测」→ 选择框应**已定位到你的 Obsidian vault** → 点「打开」→ 路径填入、导出按钮变红可用 → 点导出 → 确认 iCloud vault 的 `Talky/` 下出现周报（首次写若弹 iCloud 访问框，授权后成功）。
3. 人工反例：检测在没装/没打开过 Obsidian 的环境 → 提示"没找到 vault"，不崩溃。

## 8. 已确认决策
- 不自动预填，改**显式按钮**（授权在点击后由用户在系统选择框确认）。
- 检测 = 读 obsidian.json 定位 + 选择框预定位 + 用户确认授权（powerbox）。
- 选 `open:true`，否则 `ts` 最新。
- 复用现有 `obsidian_vault_path` 持久化，无需新设置/新权限。
