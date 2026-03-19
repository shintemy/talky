# Talky — DMG 安装指南

Talky 是一款本地语音输入助手，专为 macOS Apple Silicon 设计。
按住热键说话，松开后自动识别、润色并粘贴文字到当前应用。

## 系统要求

- **macOS 13 (Ventura)** 或更高版本
- **Apple Silicon** 芯片（M1 / M2 / M3 / M4 系列）
- 至少 **16 GB** 内存（推荐，运行 Whisper Large + Ollama 9B 模型）
- 至少 **10 GB** 可用磁盘空间

## 安装前准备

### 1. 安装 Ollama

Talky 使用 Ollama 运行本地大语言模型来润色语音识别结果。

1. 前往 [ollama.com/download](https://ollama.com/download) 下载并安装。
2. 安装完成后，拉取默认模型：

```bash
ollama pull qwen3.5:9b
```

验证 Ollama 正在运行：

```bash
ollama list
```

应能看到 `qwen3.5:9b` 或你选择的模型。

### 2. 准备 Whisper 语音识别模型

Talky 使用 MLX Whisper 做本地语音识别。有两种方式获取模型：

**方式 A：使用 HuggingFace 自动下载（推荐，需联网）**

安装 Talky 后，在 Dashboard → Configs 的 Whisper Model 栏填入：

```
mlx-community/whisper-large-v3-mlx
```

首次录音时会自动从 HuggingFace 下载模型（约 3 GB），之后会缓存在本地。

如果你在中国大陆，可能需要设置 HuggingFace 镜像：

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

**方式 B：手动放置模型文件**

如果你已有模型文件，放到以下路径：

```
~/.talky/local_whisper_model/
├── config.json
└── weights.npz
```

Dashboard → Configs 中 Whisper Model 保持默认值 `./local_whisper_model` 即可。

## 安装 Talky

1. 双击打开 `.dmg` 文件。
2. 将 `Talky.app` 拖入 `Applications` 文件夹。
3. 打开 `应用程序` 中的 `Talky`。
4. 首次打开时 macOS 会提示"无法验证开发者"（因为未签名），按以下步骤放行：
   - 打开 **系统设置 → 隐私与安全性**
   - 找到 Talky 的提示，点击 **仍要打开**
5. 授予以下权限（系统会依次弹窗询问）：
   - **麦克风** — 语音录入必需
   - **辅助功能** — 全局热键和自动粘贴必需
   - **输入监控** — 全局热键监听必需

## 日常使用

### Menu Bar 图标

启动后，屏幕右上角 Menu Bar 会出现 Talky 的气泡图标。点击可看到菜单：

- **Dashboard** — 打开主面板（含 Home / History / Dictionary / Configs）
- **Show Last Error** — 查看最近一次错误详情
- **Quit** — 退出 Talky

### 语音输入

1. 按住 **fn**（Globe 键）开始录音
2. 对着麦克风说话
3. 松开 fn → 自动处理：语音识别 → LLM 润色 → 粘贴到当前光标位置

如果当前没有可粘贴的目标窗口，会弹出浮动面板显示结果，可手动复制。

### 快捷键

| 快捷键 | 功能 |
|--------|------|
| 按住 **fn** | 录音（按下开始，松开结束） |
| **Control + Option + Command** | 打开 Dashboard |
| **Command + W** | 关闭 Dashboard（当窗口获得焦点时） |

### Dashboard 面板

通过 Menu Bar 菜单或快捷键打开。包含四个 Tab：

- **Home** — 产品 Logo、操作引导、Refer friends 占位、版本更新提示
- **History** — 按日期查看语音识别输出记录（存储在 `~/.talky/history/`）
- **Dictionary** — 自定义词典管理：添加、修改、删除词条（支持 `person:名字` 格式）
- **Configs** — 基础配置，关闭面板时自动保存

Configs 可配置项：

- **Record Hotkey** — 录音热键（fn / Right Option / 自定义组合键）
- **Whisper Model** — 语音识别模型路径或 HuggingFace repo ID
- **ASR Language** — 语音识别语言（默认 `zh`）
- **Ollama Host** — Ollama 服务地址（默认 `http://127.0.0.1:11434`）
- **Ollama Model** — LLM 模型名称（默认 `qwen3.5:9b`）
- **Auto Paste Delay** — 粘贴延迟（毫秒）

## 常见问题

### 麦克风权限弹窗没有出现

1. 打开终端，执行：
   ```bash
   tccutil reset Microphone
   ```
2. 重新打开 Talky，应会弹出授权弹窗。

### 录音后提示"audio too quiet"

- 检查系统设置中的输入设备是否选对（内建麦克风 vs 外接设备）。
- 检查系统设置 → 声音 → 输入音量是否太低。

### 录音后提示 Ollama 相关错误

- 确认 Ollama 正在运行：`ollama list`
- 确认模型已拉取：`ollama pull qwen3.5:9b`
- 如果使用远程 Ollama，在 Dashboard → Configs 中修改 Ollama Host 地址。

### fn 键没有反应

fn（Globe）键在部分 macOS 配置下可能不稳定。Talky 会自动回退到 Right Option 键，并弹出通知。你也可以在 Dashboard → Configs 中手动切换热键。

### 提示"Accessibility permission missing"

打开 **系统设置 → 隐私与安全性 → 辅助功能**，找到 Talky 并开启。如果已存在但不生效，先移除再重新添加。

## 卸载

1. 从 `应用程序` 文件夹删除 `Talky.app`。
2. 清理配置文件（可选）：
   ```bash
   rm -rf ~/.talky
   ```
