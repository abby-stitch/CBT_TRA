# TRA / doubaotest 使用说明（Terminal + Web）

本仓库当前主要用于验证一个 CBT Thought Record Agent 的“终端交互版”和“网页交互版”两种运行方式。两者复用同一套核心逻辑：`CBTAgent.extract_and_fill()`（抽取并更新 thought_record）+ `CBTAgent.respond()`（生成下一轮对话引导），并在每一轮对话后把会话保存为 JSON 文件。

目录位置：
- 终端版入口：`doubaotest/main.py`
- 网页版入口：`doubaotest/web_app.py`
- 核心 Agent：`doubaotest/agent.py`
- 会话保存目录：`doubaotest/sessions/`（每轮都会写入 `session_<session_id>.json`）

---

## 运行前准备

### 1) Python 版本
- Python >= 3.12（见 `pyproject.toml`）

### 2) 安装依赖

如果你用 `uv`：

```bash
uv sync
```

如果你用 `pip`（需要你自行创建/激活 venv，再安装）：

```bash
pip install -e .
```

### 3) 配置（config.py）

本项目把“可变项”集中放在 `config.py` 里，`config.py` 中写的就是默认值（default）。用户要修改行为时，直接改 `config.py` 即可。

- 切换模型名：修改 `LLM_MODEL`
- 切换 Ollama 地址：修改 `LLM_URL`
- 切换对话保存目录：修改 `SESSIONS_DIR`
- 切换调用方式（Ollama / API）：修改 `LLM_PROVIDER`

默认配置为 Ollama：
- `LLM_PROVIDER = "ollama"`
- `LLM_URL = "http://localhost:11434/api/generate"`
- `LLM_MODEL = "gemma2:9b"`

如果你使用的是 Ollama，请确保 Ollama 在运行，并且已拉取你在 `LLM_MODEL` 中设置的模型：

```bash
ollama serve
ollama pull gemma2:9b
```

如果你使用 API（OpenAI-compatible）：
- `LLM_PROVIDER = "openai_compatible"`
- `LLM_URL` 设置为你的 API Base URL（例如 `https://api.openai.com/v1` 或兼容服务的地址）
- `LLM_MODEL` 设置为你要使用的模型名
- 并在环境变量里设置 `API_KEY_ENV_VAR` 指向的 key（默认读取 `OPENAI_API_KEY`）

---

## Terminal 版本怎么用

Terminal 版本就是把一次 CBT 会话当作一个循环：你每输入一段文字，Agent 会抽取能填的字段、判断当前 Step 是否完成、然后给出下一句引导，并在每一轮保存 session JSON。

### 启动方式

推荐在 `doubaotest/` 目录下运行（因为脚本用相对导入 `from agent import CBTAgent`）：

```bash
cd doubaotest
python main.py
```

### 交互方式

- 程序启动后会先输出一句开场白（Step 1）
- 你在 `You:` 后输入文字（可以一次输入很多信息，例如 situation+emotion+intensity+thought）
- 每轮都会：
  - 更新 `thought_record`
  - `Hard-Check` 判断当前 Step 是否完成（完成则 Step + 1）
  - 输出下一轮问题
  - 把数据写入 `sessions/session_<session_id>.json`

### 退出

输入以下任意一个即可退出：
- `exit`
- `quit`

结束后会打印 session 文件路径。

---

## Web App 版本怎么用

Web App 的目标是把 Terminal 里的“输入/输出循环”改成“浏览器 UI + HTTP 接口”：
- 浏览器输入框：相当于 Terminal 的 `input("You: ")`
- 后端接口 `/api/message`：相当于 Terminal 每一轮循环的处理逻辑
- 右侧 thought_record 面板：实时显示当前 JSON 表单

### 启动方式（FastAPI + Uvicorn）

同样推荐在 `doubaotest/` 目录下启动：

```bash
cd doubaotest
uvicorn web_app:app --reload --port 8000
```

打开浏览器访问：
- http://127.0.0.1:8000/

### 页面怎么用

1. 点击 `New Session` 开始会话（会创建一个新的 `CBTAgent`）
2. 在输入框输入内容并发送
3. 右侧 `thought_record` 会实时刷新
4. 当 Step 全部完成后，会出现 `View Thought Record` 按钮
5. 点击 `View Thought Record` 会跳转到 `/record/<session_id>`，以表格形式展示最终记录

### 网页版的关键接口（便于调试）

- `GET /`：返回页面（HTML/CSS/JS 是直接写在 `web_app.py` 的字符串里）
- `POST /api/start`：创建新 session，返回开场白 + 初始 thought_record
- `POST /api/message`：处理一轮用户消息（抽取、hard-check、生成回复、保存 session）
- `GET /record/{session_id}`：展示最终 thought record（只允许已完成的 session）

---

## 数据保存位置

每轮对话都会保存会话 JSON 到 `SESSIONS_DIR` 指定的目录下（默认 `sessions/`，见 `config.py`）：

- `sessions/session_<session_id>.json`

文件内容包含：
- `thought_record`（核心表单）
- `chat_history`（消息级别历史）
- `turns`（每一轮的 step_before/step_after/user/assistant 事件日志）

---

## 独立报告功能怎么用

如果你不想先做网页前端，可以直接把“报告生成”当作独立功能使用。当前仓库已经提供独立脚本：

- `report_cli.py`

它会直接读取 `sessions/` 里的已完成 session，并把结果保存到 `reports/`。

### 1) 查看哪些 completed sessions 可以拿来做报告

```bash
python3 report_cli.py list-sessions
```

### 2) 生成单个 session 报告

```bash
python3 report_cli.py generate --mode single --session-id 20260427_223447
```

### 3) 生成最近 N 个 session 的汇总报告

```bash
python3 report_cli.py generate --mode recent --limit 5
```

### 4) 自定义多个 session 生成报告

```bash
python3 report_cli.py generate --mode custom --session-ids 20260424_172104,20260424_173332,20260427_223447
```

### 5) 如果只想先测试结构，不调用 LLM 总结

```bash
python3 report_cli.py generate --mode recent --limit 5 --no-llm-summary
```

### 6) 直接在网页查看报告效果

启动服务：

```bash
uvicorn web_app:app --reload --port 8000
```

然后在浏览器打开：

- 报告入口页（推荐）：
  - `http://127.0.0.1:8000/reports`
- 单个 session 报告：
  - `http://127.0.0.1:8000/reports/session/20260427_223447`
- 多个 session 报告（最近 N 个）：
  - `http://127.0.0.1:8000/reports/multi?mode=recent&limit=3`
- 多个 session 报告（自定义 session）：
  - `http://127.0.0.1:8000/reports/multi?mode=custom&session_ids=20260424_172104,20260426_234844,20260427_223447`

### 当前建议的开发顺序

建议你先把报告功能当成独立后端能力完成：

1. session 筛选逻辑
2. 单 session / 多 session 报告结构
3. 报告保存与读取
4. 最后再单独做前端页面，把这些能力接进去

这样网页只负责“展示”和“选择”，不会反过来限制你的功能设计。
