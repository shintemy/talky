# 设计：自动周报总结 + History 字典标签

- 状态：草稿，待用户复核
- 日期：2026-06-02
- 分支：`claude/blissful-pascal-acf93a`
- 关联代码（核实于本日 worktree）：
  - `talky/controller.py`（pipeline / idle tick / periodic maintenance）
  - `talky/history_store.py`（每日 markdown 归档）
  - `talky/llm_service.py`（`OllamaTextCleaner`）
  - `talky/dictionary_entries.py`（dictionary 解析）
  - `talky/models.py`（`AppSettings.ui_locale ∈ {"en","mixed"}`）

---

## 1. 目标 / 非目标

### 目标
本 spec 含两个**互相关联但可独立实现**的部分：

- **Part A — History 字典标签**：每条 history 写入时，按用户 dictionary 里的**人名 / 术语**对最终文本打标签并存进 history 元数据，为未来"按人物 / 按事物搜索"打基础。
- **Part B — 自动周报总结**：后台周期性地把**上一个完整自然周**（ISO 周一→周日）的全部最终输出，用本地 LLM 做"按天 map → 合成 reduce"总结，产出一份按时间范围命名的 Markdown 周报；每周仅一次，已总结则跳过。

### 非目标（v1 明确不做）
- 不在 UI（`ui.py`）里展示周报或标签搜索界面（用户：后续再整合到 UI）。
- 不回溯给历史旧记录补标签（仅对新写入生效）。
- 不为 `cloud` 模式做周报（云端无文本总结端点，详见 §3.4）。
- 不新增 `AppSettings` 字段 / 开关（YAGNI，功能默认常开）。
- 周报不按人物 / 主题分组（标签 v1 仅落 history，不进周报正文）。

---

## 2. Part A — History 字典标签

### 2.1 行为
每写一条 history，扫描**最终输出文本**中命中的 dictionary 条目，把命中的**人名**和**术语**分别记入该条目的元数据块。例：

```
## 14:32:07

模式: Vibecoding
ASR 语言: zh
人物: 张三, 李四
术语: Kubernetes

最终输出

...
```

### 2.2 命中检测（新纯函数）
新增 `talky/dictionary_entries.py`：

```python
def match_dictionary_tags(
    text: str, entries: list[DictionaryEntry]
) -> tuple[list[str], list[str]]:
    """Return (matched_persons, matched_terms) appearing in text.

    - person = entry.kind == "person"; term = 其余
    - 匹配规则：含 CJK 字符的词用子串包含；纯 ASCII 词用单词边界正则（\bterm\b, 忽略大小写）以降低误命中
    - 去重，保持 dictionary 中出现顺序
    """
```

理由：复用已有 `DictionaryEntry` / `parse_dictionary_entries` / `extract_person_terms`。匹配只读最终文本，不改文本。

> 假设（已核实）：经过 `apply_phonetic_dictionary` / 云端同等处理后，dictionary 词通常会原样出现在最终文本中，故子串/词边界匹配可行。
> 验证命令：`grep -n "apply_phonetic_dictionary" talky/controller.py talky-server/main.py`

### 2.3 数据模型与渲染（`history_store.py`）
- `HistoryEntryMetadata` 增加两个字段：`matched_persons: tuple[str, ...] = ()`、`matched_terms: tuple[str, ...] = ()`（用 tuple 维持 frozen dataclass 不可变）。
- `HistoryStore.append(...)` 增加两个 keyword 入参 `matched_persons` / `matched_terms`，透传进 metadata。
- `_format_metadata_block` 增加渲染：`人物: a, b` / `术语: x, y`（仅在非空时输出，标签沿用现有元数据块的中文标签风格，与 locale 无关）。

### 2.4 反向解析（供 Part B 与未来搜索）
新增 `HistoryStore.read_structured_entries(date_str) -> list[StructuredHistoryEntry]`，其中：

```python
@dataclass(frozen=True)
class StructuredHistoryEntry:
    time_str: str            # "HH:MM:SS"
    usage_mode: str          # daily/vibecoding/translation/""（无则空）
    final_text: str          # 仅"最终输出"正文（无 raw、无元数据块）
    matched_persons: tuple[str, ...]
    matched_terms: tuple[str, ...]
```

- 解析逻辑：在现有 `## HH:MM:SS` 分段基础上，剥离元数据块、若存在 `最终输出 / 原文` 结构则只取"最终输出"段，否则取整段正文。
- 现有 `read_entries()` 与 UI History tab **保持不动**（零回归），新方法是 additive。

### 2.5 集成点（`controller.py`）
唯一改动点在 `_process_pipeline` 调用 `history_store.append(...)` 处（约 `controller.py:1024`）：

- 在 append 前，用 `parse_dictionary_entries(self.settings.custom_dictionary)` + `match_dictionary_tags(final_text, entries)` 算出标签，作为新参数传入。
- 覆盖全部模式：daily / vibecoding / translation / cloud（都走这一处 append）。

> 注意：cloud 模式的 `final_text` 也在此打标签（标签靠本地 dictionary 匹配，与 ASR/LLM 在云或本地无关）。

### 2.6 边界
- dictionary 为空 → 标签为空 → 元数据块不输出标签行（行为同今日）。
- 同一词多次出现 → 标签去重一次。
- 纯 ASCII 词作为另一个词的子串（如 `go` in `google`）→ 用词边界正则规避。

---

## 3. Part B — 自动周报总结

### 3.1 触发（后台周期，复用现有 idle tick）
- 复用 `_on_wake_guard_tick`（每 5s，[controller.py:495]）中"**不录音、不处理**"的 idle 分支——该分支已调用 `_maybe_run_periodic_maintenance`。
- 在同一 idle 分支新增 `_maybe_run_weekly_summary(now)`：
  - 自身限频：维护 `_last_weekly_summary_check_ts`，**最多每 ~30min 评估一次**（避免频繁就绪探测 HTTP）。
  - 若 `_weekly_summary_in_progress` 为真 → 跳过（防重入）。
  - 计算上周范围 → `is_week_summarized` 为假 → 置 in-progress 标志 → 起 **daemon worker 线程** 跑 orchestrator。
- worker 结束（成功/失败/中止）后清 in-progress 标志。

### 3.2 周界定（纯函数）
`talky/weekly_summary.py`：

```python
def previous_iso_week_range(today: date) -> tuple[date, date]:
    """返回 today 所在周的上一周 (周一, 周日)。
    this_monday = today - timedelta(days=today.weekday())
    prev_monday = this_monday - timedelta(days=7)
    return prev_monday, prev_monday + timedelta(days=6)
    """
```

- 始终只盯"最近一个已完整结束的周"，目标每周滚动前移。
- 用 `date.today()`（系统本地日期）作为 `today`，但 orchestrator 接受注入的 `today` 以便测试（含跨年/年初 ISO 边界）。

### 3.3 就绪判断（注入式，复用 dictionary/ollama 工具）
- orchestrator 接受注入的 `is_ready() -> bool`。
- controller 提供实现：`mode in {local, remote}` 且 `list_ollama_models(host)` 非空 且 配置的 `ollama_model` 在列表中（即用户已记下的那套判断，复用 `talky.models.list_ollama_models`）。
- 不就绪 → orchestrator 直接返回 `None`（**静默跳过**），仅写 `append_debug_log`，不弹窗；下次评估重试。
- `cloud` 模式 → controller 的 `is_ready()` 直接返回 False（§3.4）。

### 3.4 模式适配
- `local` / `remote`：有可用 Ollama 文本模型 → 跑。
- `cloud`：云端 `/api/process` 是"音频→文本"，无文本总结端点 → **跳过**（debug log 记录）。v1 不为 cloud 实现周报。

> 验证命令（确认云端确无文本总结端点）：`grep -n "@app\|def \|/api/" talky-server/main.py`

### 3.5 内容收集（用 Part A 的结构化读）
`collect_week_outputs(read_structured, start, end) -> list[DayOutputs]`：

- 遍历 start..end 的 7 个日期，对存在的日子调 `read_structured_entries(date)`。
- 每天聚合成一个 `DayOutputs(date, weekday_label, entries)`，entries 按时间升序。
- 仅取 `final_text` 非空者；无任何条目的天跳过。
- 整周零条目 → orchestrator 返回 `None`（不写文件，debug log）。

### 3.6 总结管线（按天 map-reduce）
- **map（每天，最多 7 次 LLM）**：把当天所有最终输出按时间拼成结构化文本（`HH:MM 模式 文本`），调 `llm.summarize(...)` 得当天小结。
- **reduce（1 次 LLM）**：把各天小结拼接，调 `llm.summarize(...)` 得周概览。
- 每次 LLM 调用用现成 `run_with_timeout`（[talky/task_timeout.py]）包超时：日 map ~60s、reduce ~90s。
- **中止协作**：orchestrator 接受注入 `should_abort() -> bool`；在每次 day-map 前、reduce 前检查。controller 传 `lambda: self._is_recording or self._is_processing`——用户一开始录音即中止本次（不写半成品），下轮重试。

### 3.7 LLM 调用（`llm_service.py` 新增方法）
新增 `OllamaTextCleaner.summarize`（照搬 `clean()` 的流式累加 + sanitize，已核实 `_chat_with_fallback` 签名）：

```python
def summarize(self, content: str, *, system_prompt: str, num_predict: int = 600) -> str:
    stream = self._chat_with_fallback(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        think=False, stream=True,
        options={"temperature": 0.3, "num_predict": num_predict, "top_p": 0.9},
    )
    parts = []
    for chunk in stream:
        piece = chunk.get("message", {}).get("content", "") or ""
        if piece:
            parts.append(piece)
    return _sanitize_llm_surface_text("".join(parts).strip())
```

map / reduce 的 system prompt 在 `weekly_summary.py` 构建（中文/英文按 §3.8）。

### 3.8 语言（按 UI 设置，可扩展多语言）
- `summary_language_for_locale(ui_locale: str) -> Lang`，当前映射：`"mixed" → 中文`、`"en"（及其他）→ English`。
- 该映射同时驱动：① 给 LLM 的语言指令；② Markdown 静态标签（标题/概览/按天/星期名）。
- 将来 UI 支持更多 locale，只扩展此映射 + 标签表，其余不动。

> 假设（已核实）：UI 语言存于 `settings.ui_locale ∈ {"en","mixed"}`，`"mixed"` = 中文（`_tr` 逻辑，[ui.py:202-203]）。
> 验证命令：`grep -n "ui_locale\|def _tr\|userData=\"mixed\"" talky/ui.py talky/models.py`

### 3.9 产物、命名、去重、原子写
- 目录：`~/.talky/summaries/`。
- 文件名：`summary_filename(start, end) -> "summary-2026-05-25_2026-05-31.md"`。
- **去重**：`is_week_summarized(dir, start, end)` = 目标文件存在且非空。
- **原子写**：先写 `*.md.tmp` 再 `os.replace` 为最终名（避免崩溃留半成品挡住重试）。
- Markdown 结构（语言按 §3.8，下示中文）：

```markdown
# 周报 2026-05-25 ~ 2026-05-31

> 生成于 2026-06-01 · 模型 qwen3.5:9b · 共 N 条输出 / 覆盖 M 天

## 概览
<reduce 输出>

## 按天
### 05-25 周一
<当天 map 小结>
...
```

- 生成成功 → 经 `controller.status_signal.emit(...)` 推送一条含路径的提示（TrayApp 现有 `_show_status` 会显示为托盘通知）。

### 3.10 错误处理
- 任一 LLM step 失败 / 超时 → 中止本次，**不写文件**，记 `append_debug_log` + `append_error_report`；下轮重试。
- worker 全程 try/except 包裹，异常不外溢、不影响主流程。
- 与正常转写的 Ollama 调用可能短暂并发；靠 `should_abort`（录音/处理中即停）+ in-progress 单例标志降低重叠，v1 接受偶发排队。

---

## 4. 文件改动清单

### 新增
- `talky/weekly_summary.py` — 纯函数（周范围 / 命名 / 判重 / 收集 / prompt 构建 / md 渲染 / 语言映射）+ orchestrator `run_weekly_summary(...)`（依赖全注入）。
- `tests/test_weekly_summary.py`
- `docs/superpowers/specs/2026-06-02-weekly-summary-and-history-tagging-design.md`（本文件）

### 修改
- `talky/dictionary_entries.py` — `+ match_dictionary_tags(...)`。
- `talky/history_store.py` — `HistoryEntryMetadata` 加字段；`append(...)` 加参；`_format_metadata_block` 加渲染；`+ read_structured_entries(...)` 与 `StructuredHistoryEntry`。
- `talky/llm_service.py` — `OllamaTextCleaner.+ summarize(...)`。
- `talky/controller.py` — append 处算标签并传入；idle tick 加 `_maybe_run_weekly_summary` + worker `_run_weekly_summary_async`；加 `_last_weekly_summary_check_ts` / `_weekly_summary_in_progress`。
- `tests/test_history_store.py`、`tests/test_dictionary_entries.py` — 补标签相关用例。

### 不动
- `talky/ui.py`（零改动）。
- `talky-server/`（零改动）。
- 现有 `HistoryStore.read_entries` 与 History tab 行为。

---

## 5. orchestrator 接口（依赖注入，便于单测）

```python
def run_weekly_summary(
    *,
    today: date,
    summaries_dir: Path,
    read_structured: Callable[[str], list[StructuredHistoryEntry]],  # 取自 HistoryStore
    summarize: Callable[[str, str], str],                            # (content, system_prompt) -> text
    is_ready: Callable[[], bool],
    should_abort: Callable[[], bool],
    ui_locale: str,
    model_name: str,
    run_step: Callable[[Callable, float, str], str] = run_with_timeout,
    now_text: str = "",        # 报告头的"生成于"，由调用方注入（避免纯函数里取时钟）
) -> Path | None:
    """跑完返回写出的周报路径；跳过（已总结/不就绪/空周/中止/失败）返回 None。"""
```

> 说明：`now`/`date.today()` 等时钟取值放在 controller 注入，`weekly_summary.py` 内部尽量纯，便于确定性测试。

---

## 6. 测试计划

### `tests/test_weekly_summary.py`（纯逻辑，无 Qt / 无 Ollama）
- `previous_iso_week_range`：常规周；跨年（如 1 月初上溯到去年 12 月）；周一当天。
- `summary_filename` / `is_week_summarized`（含空文件视为未总结）。
- `collect_week_outputs`：多天、部分空天、整周空。
- map / reduce prompt 构建：中文与英文（`ui_locale` = `mixed` / `en`）。
- `render_summary_markdown`：标签语言切换、按天分节、计数头。
- `summary_language_for_locale`：`mixed→中文`、`en→English`、未知 locale→English（兜底）。
- orchestrator：用 fake `summarize`（回显）+ fake `read_structured` + tmp dir，覆盖：正常生成、已总结跳过、不就绪跳过、空周跳过、`should_abort` 中途中止不写文件、`summarize` 抛错不写文件、原子写（无 `.tmp` 残留）。

### `tests/test_history_store.py`（增量）
- `append` 带 `matched_persons/terms` → 元数据块正确渲染。
- `read_structured_entries` → 正确剥离元数据块 / 取"最终输出"段 / 解析标签；无标签、无 raw 的 daily 条目也正确。

### `tests/test_dictionary_entries.py`（增量）
- `match_dictionary_tags`：CJK 子串命中、ASCII 词边界（`go` 不命中 `google`）、person/term 分类、去重与顺序。

### controller 集成（沿用现有 mock 套路）
- idle tick 到期且未总结 → 起 worker（mock orchestrator）。
- in-progress / cloud / 录音中 → 跳过。

---

## 7. 已解决的决策（澄清记录）
- 触发：后台周期检查（复用 6h/idle 维护机制，不依赖启动）。
- 周界定：ISO 周一→周日，仅上一个完整周。
- 内容：三模式全部最终输出，按时间排序。
- 产物：独立 `~/.talky/summaries/` + 托盘通知；文件存在即去重；不上 UI。
- 语言：按 `ui_locale` 映射（`mixed`=中文 / `en`=英文），可扩展。
- 标签：人名 + 术语，仅落 history 供未来搜索；周报不专门用标签。
- 总结策略：按天 map-reduce。

## 8. 未决 / 后续
- 周报 / 标签搜索的 UI 整合（后续单独 spec）。
- 旧 history 回溯打标签（后续）。
- cloud 模式周报（需云端加文本总结端点）。
- 是否加 `weekly_summary_enabled` 开关（按需再加）。
