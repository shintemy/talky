# DMG 版 Talky：局域网 Ollama（Mac mini 跑模型，MacBook 跑 Talky）

适用场景：**Mac mini** 上运行 **Ollama**（提供 LLM），**MacBook** 上安装 **Talky DMG**，在本机完成 **Whisper 语音识别**，仅把 **LLM 清理** 请求发到 Mac mini。

> **与 Cloud 模式的区别**  
> - **本教程（Local + 远程 Ollama）**：ASR（Whisper）在 **MacBook**，LLM 在 **Mac mini**。  
> - **Cloud 模式**：音频上传到 **Talky Cloud 服务器**，ASR + LLM 都在服务端；需 `talky-server` + API Key，见仓库内 `talky-server/README.md`。

---

## 前置条件

| 项目 | 说明 |
|------|------|
| 两台 Mac | 同一局域网（同一 Wi‑Fi 或有线同网段） |
| MacBook | Apple Silicon，已安装 Talky DMG（如 `Talky-*-unsigned.dmg`） |
| Mac mini | 已安装 Ollama，且已 `ollama pull` 所需模型 |
| Whisper | **仍在 MacBook**：首次使用需在 Talky 内完成 Whisper 模型下载或指定路径 |

---

## 第一步：在 Mac mini 上暴露 Ollama（局域网可访问）

1. 终止可能占用端口的旧进程（可选）：

   ```bash
   pkill ollama
   ```

2. **监听所有网卡**（否则默认只监听 `127.0.0.1`，其他机器连不上）：

   ```bash
   OLLAMA_HOST=0.0.0.0:11434 ollama serve
   ```

   建议长期运行可配合 `launchd`、tmux 或开机脚本；此处不展开。

3. 确认监听正确：

   ```bash
   lsof -nP -iTCP:11434 -sTCP:LISTEN
   ```

   预期出现 `*:11434` 或 `0.0.0.0:11434`。

4. 确认模型已就绪：

   ```bash
   ollama list
   ```

   记下要用的**完整模型名**（例如 `qwen3.5:9b`），稍后在 Talky 里必须**一字不差**填写。

5. **防火墙**：若 `系统设置 → 网络 → 防火墙` 开启，需允许 **Ollama** 入站，或临时关闭防火墙做连通性测试。

---

## 第二步：获取 Mac mini 的局域网 IP

在 **Mac mini** 终端执行：

```bash
ipconfig getifaddr en0
```

若无输出，可试 `en1`（视网络接口而定）。  
也可在 **系统设置 → 网络** 中查看当前网络的 IP。

下文用 **`192.168.31.210`** 作为示例，请替换为你的实际 IP。

---

## 第三步：在 MacBook 上验证能访问 Mac mini 的 Ollama

在 **MacBook** 终端执行（替换 IP）：

```bash
nc -vz 192.168.31.210 11434
curl -sS http://192.168.31.210:11434/api/tags
```

- `nc` 应显示连接成功。  
- `curl` 应返回 JSON，内含 `models` 列表。

若此处失败，请先排查：IP 是否正确、是否同网、Mac mini 防火墙、`OLLAMA_HOST` 是否为 `0.0.0.0:11434`。

---

## 第四步：在 Talky（DMG）里填写配置

1. 打开 **Talky**（从「应用程序」或 Launchpad 启动）。

2. 打开 **Dashboard**（默认快捷键：**Control + Option + Command**，或点击菜单栏图标 → 相关入口）。

3. 进入 **Configs** 标签页。

4. **Processing Mode** 选择 **Local (Free)**（不要选 Cloud）。

5. 填写以下字段：

   | 字段 | 填写说明 |
   |------|----------|
   | **Ollama Host** | `http://192.168.31.210:11434`（`http://` + Mac mini IP + `:11434`） |
   | **Ollama Model** | 与 Mac mini 上 `ollama list` 中的名称**完全一致** |
   | **Whisper Model** | 本机 Whisper 路径或 Hugging Face 仓库 ID（ASR 在 MacBook 运行） |

6. 关闭 Dashboard 窗口。**Configs 为自动保存**（关闭即写入 `~/.talky/settings.json`）。

7. 若尚未下载 Whisper 模型，首次按住 **fn** 录音时会出现 **模型设置**向导，按提示下载或指定模型路径。

---

## 第五步：使用与成功现象

1. 在目标 App（备忘录、浏览器、IDE 等）中聚焦输入框。  
2. **按住 fn**（或你在 Configs 中设置的热键）说话。  
3. **松开** 后等待处理。  
4. 预期：文本出现在当前输入框；若无焦点，可能出现**悬浮复制面板**。

逻辑简述：**Whisper 在 MacBook 转写 → 文本发往 Mac mini 的 Ollama 做清理 → 结果写回并粘贴**。

---

## 常见问题

### `LLM` 报错或超时

- 确认 Mac mini 上 `ollama serve` 仍在运行且 `OLLAMA_HOST=0.0.0.0:11434`。  
- 确认 **Ollama Model** 与 `ollama list` 一致。  
- 在 MacBook 上再次执行 `curl http://<IP>:11434/api/tags` 做快速体检。

### `ASR` / Whisper 报错

- 属于 **MacBook 本机** 模型问题，与 Mac mini 无关。检查 **Whisper Model** 路径、磁盘空间、首次下载是否完成。

### 仅 LLM 走远程，会不会泄露整段录音？

- 录音与 ASR 在 **本机**；仅 **转写后的文本**（及词典相关上下文）会发给 Ollama。具体以你使用的 Ollama 模型与网络环境为准。

### 与 `LAN_OLLAMA_GUIDE.zh.md` 里 `start_talky.command` 的关系

- **源码 / 命令行用户**可用 `start_talky.command --remote ...` 一键切换（见该文档）。  
- **DMG 用户**无该脚本，请在 **Dashboard → Configs** 中按本教程填写 **Ollama Host / Model**，效果等价（均为 Local 模式 + 远端 Ollama）。

---

## 相关链接

- 局域网流程（命令行 / `start_talky.command`）：[LAN_OLLAMA_GUIDE.zh.md](../LAN_OLLAMA_GUIDE.zh.md)  
- Talky Cloud 服务端：[talky-server/README.md](../talky-server/README.md)  
- 预编译 DMG：[GitHub Releases](https://github.com/shintemy/talky/releases)（内测构建为 *unsigned*，首次打开需在「隐私与安全性」中允许）
