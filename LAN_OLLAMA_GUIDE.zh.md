# 局域网大模型流程（LAN Ollama）

适用场景：`Mac mini` 提供 Ollama 模型服务，`MacBook` 运行 Talky（录音 + ASR + 调用远端 LLM）。

## Step 1（Mac mini）：准备 Ollama 服务与模型

```bash
ollama --version
ollama ls
pkill ollama
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

在 Mac mini 另开终端验证监听地址：

```bash
lsof -nP -iTCP:11434 -sTCP:LISTEN
```

预期：`*:11434` 或 `0.0.0.0:11434`

## Step 2（Mac mini）：获取局域网 IP

```bash
ipconfig getifaddr en1
```

若 `en1` 无输出，可尝试：

```bash
ipconfig getifaddr en0
```

## Step 3（MacBook）：验证网络连通与远端 API

```bash
nc -vz <局域网IP> 11434
curl http://<局域网IP>:11434/api/tags
```

预期：
- `nc` 显示 `succeeded`
- `curl` 返回模型列表（例如 `qwen3.5:4b`）

## Step 4（MacBook）：一行命令切到局域网模式并自动重启

```bash
cd /path/to/talky
./start_talky.command --remote "http://<局域网IP>:11434" --model "qwen3.5:4b" --restart
```

## Step 5：成功信号

日志出现以下内容即表示流程成功：
- `mode: remote`
- `Using Ollama model: qwen3.5:4b`
- `ASR elapsed`、`LLM elapsed`、`Final text`

## 快速排查

- `bind: address already in use`
  - 说明 `11434` 已被占用，先 `pkill ollama` 再执行 Step 1。
- `nc` 不通
  - 检查 Mac mini 防火墙和路由器是否启用客户端隔离。
- `curl /api/tags` 通，但 Talky 报 model not found
  - 确认 `--model` 与 `ollama ls` 返回的模型名完全一致。
