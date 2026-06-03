# 设计：周报手动导出到 Obsidian

- 状态：草稿，待用户复核
- 日期：2026-06-03
- 分支：`main`（实施时另开 feature 分支）
- 承接：`docs/superpowers/specs/2026-06-02-weekly-summary-and-history-tagging-design.md` §8「周报 UI 整合（后续单独 spec）」——本 spec 即该后续的第一步。

## 关联代码（核实于 2026-06-03 当前工作树）

| 假设 | 验证命令 | 结果 |
| --- | --- | --- |
| 周报文件落在 `~/.talky/summaries/`，名为 `summary-START_END.md` | `grep -n "summary_filename\|_summaries_dir" talky/weekly_summary.py talky/controller.py` | ✅ `weekly_summary.py:20` `summary_filename`；`controller.py:202` `_summaries_dir = Path.home()/".talky"/"summaries"` |
| `AppSettings` 是 `@dataclass(slots=True)`，`to_dict` 走 `asdict`，新字段需在 `from_dict` 显式取 | `grep -n "class AppSettings\|def from_dict\|asdict" talky/models.py` | ✅ `models.py:60/88/134` |
| 设置持久化走 `config_store` JSON | `grep -n "settings_for_disk\|to_dict\|from_dict" talky/config_store.py` | ✅ `config_store.py:13-40` |
| Configs 设置面在 `ConfigsTab` | `grep -n "class ConfigsTab" talky/ui.py` | ✅ `ui.py:1538` |
| vault = 本地纯 `.md` 文件夹，Obsidian 自动收录外部新增文件，无需插件/API | docs.obsidian.md / obsidian.md/help/vault（WebFetch 核实 2026-06-03） | ✅ vault 即「本地文件系统上的一个文件夹」 |

---

## 1. 目标 / 非目标

### 目标
给已有的「自动周报」加一个**手动导出到 Obsidian** 的出口，便于把每周总结沉淀成个人知识库：

- 在 Configs tab 一次性设置 Obsidian **vault 文件夹路径**。
- 一个**「导出周报到 Obsidian」按钮**：一键把 `~/.talky/summaries/` 里**所有尚未导出**的周报，同步进 `<vault>/Talky/`，文件名沿用现有时间范围命名。
- 写入时在文件顶部加 **YAML front-matter**（日期范围 + tags），让 Obsidian 能按标签聚合 / Dataview 检索 / 进知识图谱。

### 非目标（v1 明确不做）
- 不做自动同步（用户选定：**手动触发**）。
- 不做周报列表 / 预览 UI（用户选定：**Configs 里一个按钮**的极简形态）。
- 不依赖 Obsidian 插件、URI scheme 或本地 REST API——只做纯文件写入（vault 自动收录）。
- 不改周报本身的生成逻辑（`weekly_summary.py` 的生成不动，只新增"读已生成文件 → 灌进 vault"）。
- 不做"已导出清单"状态文件——去重靠目标文件存在性（见 §6）。
- vault 子文件夹名硬编码为 `Talky`，v1 不做可配置（YAGNI）。

---

## 2. 设置项（`AppSettings`，`talky/models.py:60`）

新增一个字段：

```python
obsidian_vault_path: str = ""   # 空 = 未配置
```

- `from_dict` 加一行：`obsidian_vault_path=str(data.get("obsidian_vault_path", "")),`
- `to_dict` 走 `asdict`，**无需改**。
- `settings_for_disk` 走 `replace`，自动带上，**无需改**。
- 持久化与读取全部复用现有 `config_store` JSON 机制，零额外管线。

---

## 3. 纯逻辑模块 `talky/obsidian_export.py`（新增，无 Qt）

与 `weekly_summary.py` 同风格：纯函数 + 一个 orchestrator，UI/clock 全注入，便于单测。

```python
from __future__ import annotations
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

SUMMARY_RE = re.compile(r"^summary-(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.md$")
DEFAULT_SUBFOLDER = "Talky"


def parse_summary_range(filename: str) -> tuple[date, date] | None:
    """从 summary-START_END.md 解析出 (start, end)；不匹配返回 None。"""


def build_front_matter(start: date, end: date, *, lang: str) -> str:
    """构造 YAML front-matter 块（含结尾换行），见 §5。"""


def prepend_front_matter(markdown: str, start: date, end: date, *, lang: str) -> str:
    """在周报正文前拼 front-matter；若正文已以 '---' 开头则不重复加。"""


@dataclass(frozen=True)
class ExportResult:
    exported: tuple[str, ...] = ()          # 新写入的目标文件名
    skipped: tuple[str, ...] = ()           # 已存在被跳过的文件名
    failed: tuple[tuple[str, str], ...] = () # (文件名, 错误信息)


def export_all_summaries(
    *,
    summaries_dir: Path,
    vault_path: Path,
    lang: str,
    subfolder: str = DEFAULT_SUBFOLDER,
) -> ExportResult:
    """把 summaries_dir 下所有 summary-*.md 同步进 <vault>/<subfolder>/。

    - 目标已存在 → skipped（不覆盖，保护用户在 Obsidian 里的编辑）。
    - 不存在 → 解析日期 → prepend front-matter → 原子写 → exported。
    - 单个文件出错（坏文件名 / 写失败）→ failed，不中断其余。
    - 文件名不符合 SUMMARY_RE → 忽略（不计入任何桶）。
    """
```

> 原子写沿用 `weekly_summary._atomic_write` 同款思路（`*.tmp` + `os.replace`），避免崩溃留半成品。可在本模块内复制一份小工具或从 `weekly_summary` 导入。

---

## 4. UI（`ConfigsTab`，`talky/ui.py:1538`）

在 Configs 里新增一小块「Obsidian 同步」，与现有控件风格一致（`_tr(locale, en, key)` 取文案）：

- **Vault 文件夹行**：只读路径显示（空时显示占位文案）+「选择…」按钮 → `QFileDialog.getExistingDirectory` 选 vault 根目录 → 写入 `settings.obsidian_vault_path` → 经现有 `_save_settings` 持久化。
- **「导出周报到 Obsidian」按钮**：
  - vault 未设置或路径不存在 → 按钮**禁用**（设置/选定有效路径后启用），避免无效点击。
  - 点击 → 调 controller 暴露的一个方法（见 §5 wiring）→ 同步执行 `export_all_summaries`（本地小文件 IO，毫秒级，不需起线程）。
  - 结果用轻量提示（`QMessageBox` 或现有 status 提示）：`已导出 N 份，跳过 M 份（已存在）`；有 `failed` 则附失败文件名。
- 新增 i18n 文案 key（zh/en）：区块标题、「选择…」、「导出周报到 Obsidian」、结果模板、错误模板。

### Wiring（controller）
ConfigsTab 不直接碰文件系统逻辑，而是调用 controller 上一个薄方法，例如：

```python
def export_weekly_summaries_to_obsidian(self) -> ExportResult:
    vault = Path(self.settings.obsidian_vault_path)
    lang = summary_language_for_locale(self.settings.ui_locale)
    return export_all_summaries(
        summaries_dir=self._summaries_dir, vault_path=vault, lang=lang
    )
```

复用 `_summaries_dir`（`controller.py:202`）与 `summary_language_for_locale`（`weekly_summary.py:36`），与周报生成端语言口径一致。

---

## 5. front-matter 格式

从文件名解析出起止日期后，在正文前 prepend：

```yaml
---
title: "周报 2026-05-25 ~ 2026-05-31"
date_range: "2026-05-25/2026-05-31"
date: 2026-05-31
tags: [Talky, 周报]
source: Talky
---
```

- `date` 取 end（周日），便于 Obsidian 按日期排序 / 日记联动。
- `tags` 第二项按 `lang`：`zh → 周报`、`en → weekly`（第一项恒为 `Talky`）。
- `title` 文案随 `lang`（中文「周报」/ 英文「Weekly Report」）。
- 周报正文（`# 周报 …` 起）原样跟在 front-matter 之后，不改动。

---

## 6. 去重与边界

### 去重（无状态，存在性判断）
- 目标 = `<vault>/Talky/<原文件名>`；**存在即 skip**，不存在才写。
- 选型理由：① 无需额外状态文件；② 若用户在 Obsidian 里删了某篇，下次点导出会**重新补回**（符合"同步/补全知识库"心智）；③ 若用户改过某篇，重导出不会覆盖其编辑。
- 备选「另存已导出清单」被否：删了 vault 笔记就再也补不回来，且多一套状态要维护。

### 边界 / 错误处理
- vault 路径已失效（被移走/删除）→ UI 报错提示重选，不抛异常到主流程。
- `summaries_dir` 无任何周报 → 返回空 `ExportResult` → UI 提示「暂无周报可导出」。
- 单文件写入失败（权限等）→ 计入 `failed`，其余继续；UI 列出失败项。
- 目录下混入不符合命名的 `.md` → `SUMMARY_RE` 不匹配 → 忽略。
- 全流程 try/except 包裹于 controller 方法，导出失败不影响录音/转写主流程。

---

## 7. 文件改动清单

### 新增
- `talky/obsidian_export.py` — `parse_summary_range` / `build_front_matter` / `prepend_front_matter` / `ExportResult` / `export_all_summaries`。
- `tests/test_obsidian_export.py`。
- `docs/superpowers/specs/2026-06-03-obsidian-weekly-export-design.md`（本文件）。

### 修改
- `talky/models.py` — `AppSettings` 加 `obsidian_vault_path` 字段 + `from_dict` 取值。
- `talky/controller.py` — 加薄方法 `export_weekly_summaries_to_obsidian()`。
- `talky/ui.py` — `ConfigsTab` 加 vault 选择行 + 导出按钮 + 结果提示；新增 i18n key。
- `tests/test_config_store.py`（或就近测试）— `obsidian_vault_path` 往返不丢。

### 不动
- `talky/weekly_summary.py`（生成逻辑零改动）。
- `talky-server/`、其余 tab。

---

## 8. 测试计划

### `tests/test_obsidian_export.py`（纯逻辑，无 Qt / 无 Ollama）
- `parse_summary_range`：合法名 → 正确 `(start, end)`；非法名 / 非 `.md` → `None`。
- `build_front_matter` / `prepend_front_matter`：zh 与 en 的 title/tags；正文已以 `---` 开头时不重复加。
- `export_all_summaries`（用 `tmp_path` 造 summaries_dir + 假 vault）：
  - 正常：多份全新 → 全部 exported，目标内容含 front-matter + 原文。
  - 去重：目标已存在 → skipped，且**不覆盖**已存在内容。
  - 空 summaries_dir → 空结果。
  - 混入坏文件名 → 被忽略，不进任何桶。
  - 自动建 `<vault>/Talky/` 子目录。
  - 原子写：无 `.tmp` 残留。

### 设置往返
- `AppSettings.from_dict({...,"obsidian_vault_path":"/p"}).to_dict()` 保留该值；缺省为 `""`。

### UI（按项目现有 UI 测试套路，可选轻量）
- vault 未设 → 导出按钮禁用 / 提示。
- mock controller 方法返回 `ExportResult` → 结果文案正确（N/M/failed）。

---

## 9. 验证步骤（human-flow 优先）

1. **人工**：构造几份周报（或用现有 `~/.talky/summaries/` 内容），运行 app → Configs → 选一个本地 Obsidian vault → 点「导出周报到 Obsidian」。
2. **人工**：打开 Obsidian，确认出现 `Talky/` 文件夹，里面是 `summary-START_END.md`，每篇顶部有 front-matter，且能在标签面板看到 `Talky` / `周报` 标签。
3. **人工**：再点一次导出 → 提示「跳过 M 份（已存在）」，已有笔记内容不被覆盖。
4. **自动**：`pytest tests/test_obsidian_export.py`。

---

## 10. 已解决的决策（澄清记录）
- 触发：**手动**（Configs 里按钮），非自动同步。
- 入口：**极简**——Configs 一个按钮 + 一个 vault 路径设置，不做列表/预览。
- 范围：**一键同步全部**未导出周报（已存在跳过）。
- 去重：**目标文件存在性**判断（无状态，可补回，不覆盖编辑）。
- front-matter：**加**（date_range / date / tags[Talky, 周报|weekly] / source）。
- 子文件夹：硬编码 `Talky`。

## 11. 未决 / 后续
- 周报预览 / 列表 UI（若日后想"看一眼再导"）。
- 子文件夹名 / front-matter 字段可配置化（按需）。
- 自动同步开关（若日后想免手动）。
