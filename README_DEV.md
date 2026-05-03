# TRA / doubaotest 使用说明（Terminal + Web）

本仓库当前主要用于验证一个 CBT Thought Record Agent 的“终端交互版”和“网页交互版”两种运行方式。两者复用同一套核心逻辑：`CBTAgent.extract_and_fill()`（抽取并更新 thought_record）+ `CBTAgent.respond()`（生成下一轮对话引导）。用户发送第一条消息后，session 会保存为本地 JSON；只打开新 session 但没有输入内容时不会保存空文件。

如果只是想把项目跑起来并交给别人使用，优先看独立运行说明：[RUNNING.md](RUNNING.md)。里面包含 Docker、Ollama、API 模式、Windows/macOS/Linux 运行命令和主要功能说明，中英文都有。

目录位置：
- 终端版入口：`doubaotest/backend/main.py`
- API 后端入口：`doubaotest/backend/api_app.py`
- 旧版一体化网页入口：`doubaotest/backend/web_app.py`
- React 前端：`doubaotest/frontend/`
- 核心 Agent：`doubaotest/backend/agent.py`
- 会话保存目录：`doubaotest/sessions/`（用户开始输入后写入 `session_<session_id>.json`）
- 报告保存目录：`doubaotest/reports/`（点击 `Save Report` 后写入 `report_<report_id>.json`）

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

### 3) 配置（backend/config.py）

本项目把“可变项”集中放在 `backend/config.py` 里，`backend/config.py` 中写的就是默认值（default）。用户要修改行为时，直接改 `backend/config.py` 即可。

- 切换模型名：修改 `LLM_MODEL`
- 切换 Ollama 地址：修改 `LLM_URL`
- 切换对话保存目录：修改 `SESSIONS_DIR`
- 切换调用方式（Ollama / API）：修改 `LLM_PROVIDER`

默认配置为 Ollama：
- `LLM_PROVIDER = "ollama"`
- `LLM_URL = "http://localhost:11434/api/generate"`
- `LLM_MODEL = "gemma2:9b"`

本地开发时，如果没有额外设置环境变量，就会使用上面的默认值。Docker 镜像会在容器内部设置 Docker 专用默认值，因此不会影响本地两个 terminal 的开发运行方式。

#### Ollama 模型说明

本项目不会打包或内置任何 Ollama 模型。模型由用户根据自己的电脑性能和使用需求，在本机 Ollama 中自行下载；项目只会读取 `backend/config.py` 里的 `LLM_MODEL` 配置，并调用本地 Ollama 服务。

如果你使用的是 Ollama，请先安装并启动 Ollama，然后拉取你想使用的模型。例如当前默认配置是 `gemma2:9b`：

```bash
ollama serve
ollama pull gemma2:9b
```

如果你想换成其他模型，例如 `qwen2.5:7b`，需要先在 Ollama 中下载：

```bash
ollama pull qwen2.5:7b
```

然后在 `backend/config.py` 中修改：

```python
LLM_MODEL = "qwen2.5:7b"
```

只要模型已经存在于本机 Ollama 中，并且模型名和 `LLM_MODEL` 完全一致，项目就可以使用该模型运行。

如果你使用 API（OpenAI-compatible）：
- `LLM_PROVIDER = "openai_compatible"`（前端 Settings 中显示为 `API`）
- `LLM_URL` 设置为你的 API Base URL（例如 `https://api.openai.com/v1` 或兼容服务的地址）
- `LLM_MODEL` 设置为你要使用的模型名
- 并在环境变量里设置 `API_KEY_ENV_VAR` 指向的 key（默认读取 `OPENAI_API_KEY`）

### 4) API Key 环境变量怎么设置

项目不会把真实 API key 写进代码或 `app_settings.json`。代码只保存环境变量名，例如 `OPENAI_API_KEY`。真正的 key 推荐放在项目根目录 `.env` 文件中，或者临时 export 到终端环境。

推荐方式：复制 `.env.example` 为 `.env`：

```bash
cp .env.example .env
```

然后编辑 `.env`：

```text
OPENAI_API_KEY=你的真实 key
```

后端会在读取 settings 时自动加载项目根目录 `.env`。`.env` 已加入 `.gitignore`，不要提交真实 key。

临时方式：macOS / Linux / zsh 中 export：


```bash
export OPENAI_API_KEY="你的真实 key"
uv run uvicorn backend.api_app:app --reload --port 8000
```

如果想长期生效，可以写入 `~/.zshrc`：

```bash
echo 'export OPENAI_API_KEY="你的真实 key"' >> ~/.zshrc
source ~/.zshrc
```

Windows PowerShell 临时设置：

```powershell
$env:OPENAI_API_KEY="你的真实 key"
uv run uvicorn backend.api_app:app --reload --port 8000
```

在前端右上角 settings 里：

- `Provider` 选 `API`
- `API / Ollama URL` 填 API base URL，例如 `https://api.openai.com/v1`
- `Model` 填模型名
- `API key env var` 填 `OPENAI_API_KEY`

如果你用的是其他兼容服务，也可以把环境变量名改成别的，例如 `MY_API_KEY`。只要 settings 里的 `API key env var` 和终端里设置的环境变量名一致即可。

### 5) 路径为什么可以换电脑

前端 settings 里默认显示的是相对路径：

```text
sessions
reports
```

后端会在运行时把相对路径解析到当前项目根目录。例如在你的电脑上会变成：

```text
/Users/abbyliang/2025/hku/sem2/projects/tra_test/sessions
/Users/abbyliang/2025/hku/sem2/projects/tra_test/reports
```

在别人的电脑上会自动变成对方项目所在目录下的 `sessions/` 和 `reports/`。这部分逻辑在 `backend/app_settings.py` 的 `_resolve_data_dir()`。

只有当你手动填写绝对路径时，才会固定到某台电脑的具体路径。

### 6) 去哪里看这些功能写在代码哪里

前端：

- 页面和路由：`frontend/src/App.tsx`
- 前端调用后端 API：`frontend/src/api.ts`
- 前端数据类型：`frontend/src/types.ts`
- 页面样式：`frontend/src/styles.css`

后端：

- FastAPI API：`backend/api_app.py`
- 模型、路径、个人背景设置读写：`backend/app_settings.py`
- 默认配置：`backend/config.py`
- CBT 对话流程：`backend/agent.py`
- CBT prompt / Beck-style thought-record 步骤：`backend/prompts.py`
- 报告生成：`backend/report_service.py`
- session 文件写入：`backend/storage.py`

右上角按钮：

- settings 图标：修改模型、API URL、保存路径
- 人像图标：填写个人 CBT 背景信息，作为新 session 的可选上下文

顶部导航右侧会显示当前 settings 中的模型名，例如 `gemma2:9b` 或 `gpt-4o`。Conversation 页面和 report 页面也会记录并显示实际使用的 LLM：

- conversation 使用的 LLM 写入 session JSON 的 `conversation_llm`
- report generation 使用的 LLM 写入 report JSON 的 `report_llm`

---

## Docker 单镜像运行

本项目现在提供单 Docker 镜像打包方式。镜像内会先构建 React 前端，再由 FastAPI 同时提供：

- `/api/...` 后端接口
- `/`、`/sessions`、`/reports` 等 React 页面

Docker 镜像默认按“本机 Ollama + `gemma2:9b`”配置：

```text
Provider: ollama
Model: gemma2:9b
URL: http://host.docker.internal:11434/api/generate
```

因此 Docker 用户只要本机已经安装 Ollama 并下载 `gemma2:9b`，通常不需要先去 settings 修改 URL。

构建镜像：

```bash
docker build -t cbt-thought-record-agent .
```

最小运行方式：

```bash
docker run --rm -p 8000:8000 cbt-thought-record-agent
```

打开：

```text
http://localhost:8000
```

推荐运行方式是把本地数据目录挂载出来，避免容器删除后丢失 sessions 和 reports：

```bash
mkdir -p sessions reports
docker run --rm \
  -p 8000:8000 \
  -v "$PWD/sessions:/app/sessions" \
  -v "$PWD/reports:/app/reports" \
  cbt-thought-record-agent
```

如果使用 OpenAI-compatible API，先复制 `.env.example`：

```bash
cp .env.example .env
```

`.env` 中填写：

```text
OPENAI_API_KEY=你的真实 key
```

运行时传入 `.env`：

```bash
mkdir -p sessions reports
docker run --rm \
  -p 8000:8000 \
  --env-file .env \
  -v "$PWD/sessions:/app/sessions" \
  -v "$PWD/reports:/app/reports" \
  cbt-thought-record-agent
```

如果想让页面 settings 也在容器重建后保留，可以额外挂载 `app_settings.json`：

```bash
touch app_settings.json
docker run --rm \
  -p 8000:8000 \
  --env-file .env \
  -v "$PWD/app_settings.json:/app/app_settings.json" \
  -v "$PWD/sessions:/app/sessions" \
  -v "$PWD/reports:/app/reports" \
  cbt-thought-record-agent
```

如果使用本机 Ollama，模型仍然需要用户在本机安装和下载：

```bash
ollama pull gemma2:9b
```

Docker 镜像默认设置 `TZ=Asia/Hong_Kong`，所以 session 和 report 时间会按香港时间写入。部署到其他时区时，可以运行容器时加 `-e TZ=<timezone>` 覆盖。

Docker 镜像已经默认使用下面这个 URL：

```text
http://host.docker.internal:11434/api/generate
```

不要在 Docker settings 里填 `http://localhost:11434/api/generate`，因为 Docker 容器里的 `localhost` 指的是容器自己。如果页面 settings 之前保存过旧 URL，可以手动改回 `http://host.docker.internal:11434/api/generate`。

Linux 如果无法识别 `host.docker.internal`，运行容器时加：

```bash
--add-host=host.docker.internal:host-gateway
```

---

## Terminal 版本怎么用

Terminal 版本就是把一次 CBT 会话当作一个循环：你每输入一段文字，Agent 会抽取能填的字段、判断当前 Step 是否完成、然后给出下一句引导，并在每一轮保存 session JSON。

### 启动方式

推荐在 `doubaotest/` 目录下运行：

```bash
cd doubaotest
uv run python -m backend.main
```

### 交互方式

- 程序启动后会先输出一句开场白（Step 1）
- 你在 `You:` 后输入文字（可以一次输入很多信息，例如 situation+emotion+intensity+thought）
- 用户发送第一条消息后，每轮都会：
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
- 首页：先提示用户选择一个最近情绪明显变化的具体时刻，再开始 Thought Record
- 浏览器输入框：相当于 Terminal 的 `input("You: ")`
- 后端接口 `/api/message`：相当于 Terminal 每一轮循环的处理逻辑
- React 前端当前以聊天引导为主；每轮仍会在后端抽取并保存 `thought_record`，完成后可进入报告页查看结构化结果

### 启动方式（FastAPI + Uvicorn）

旧版一体化 FastAPI 页面仍然保留，推荐只作为对照使用：

```bash
cd doubaotest
uv run uvicorn backend.web_app:app --reload --port 8000
```

如果只想启动给新前端使用的 API-only 后端，使用：

```bash
uv run uvicorn backend.api_app:app --reload --port 8000
```

`backend/api_app.py` 只保留 JSON API，不包含 `backend/web_app.py` 里直接拼接的 HTML/CSS/JS 页面。

新的 React 前端在 `frontend/` 目录下。第一次运行需要安装依赖：

```bash
cd frontend
npm install
npm run dev
```

然后打开：

- http://127.0.0.1:5173/

开发时前端会通过 Vite proxy 把 `/api/...` 请求转发到 `http://127.0.0.1:8000`，所以需要同时启动上面的 `backend.api_app` 后端。

React 前端目前接管这些页面：

- `/`
- `/sessions`
- `/reports`
- `/reports/saved`
- `/reports/session/<session_id>`
- `/reports/multi?mode=recent&limit=3`
- `/reports/multi?mode=custom&session_ids=<id1,id2>`

旧的 `backend/web_app.py` 仍然保留，主要作为迁移前的一体化页面对照。

打开 React 前端访问：
- http://127.0.0.1:5173/

### 页面怎么用

1. 在首页选择一个最近让情绪明显变化的具体时刻；如果事情持续了一段时间，先聚焦情绪最强烈的片刻
2. 点击 `Start Thought Record` 开始会话（会创建一个新的 `CBTAgent`）
3. 在输入框像聊天一样输入内容并发送；前端会显示当前 session、step、聊天记录和基础记录焦点
4. 第一条用户消息发送后，后端会抽取可填写的信息、更新 `thought_record`、判断当前 step 是否完成，并保存 session JSON
5. 当 Step 全部完成后，会出现 `View Thought Record` 按钮
6. 点击 `View Thought Record` 会跳转到 `/sessions?session_id=<session_id>`，查看该 session 的结构化 thought record 内容，不会调用 report LLM
7. 在 session 详情页点击 `Generate Report` 才会生成 single session report
8. 在 `/reports` 可以生成 recent/custom multi-session report，也可以展开或进入 saved reports
9. 在 `/reports/saved` 可以查看或删除已保存 report。删除 report 不会修改 session

### 网页版的关键接口（便于调试）

- `GET /api/health`：健康检查
- `POST /api/start`：创建新 session，返回开场白 + 初始 thought_record
- `POST /api/message`：处理一轮用户消息（抽取、hard-check、生成回复、保存 session）
- `GET /api/report-sessions`：列出 completed sessions
- `GET /api/sessions`：列出 session archive 中已保存且有用户输入的 sessions，包括 `completed`、`in_progress`、`stopped`
- `GET /api/sessions/{session_id}`：读取 session 的 thought record，不调用 LLM
- `POST /api/sessions/{session_id}/resume`：恢复 `in_progress` session，回到 conversation 继续
- `DELETE /api/sessions/{session_id}`：删除本地 session JSON，不修改已保存 report
- `GET /api/reports/session/{session_id}`：生成单个 session 的报告数据，会调用 report LLM
- `GET /api/reports/multi`：生成多 session 的报告数据，会调用 report LLM
- `POST /api/reports/save`：保存当前已经生成好的 report JSON，不重新调用 LLM
- `GET /api/reports/{report_id}`：读取已保存 report，不调用 LLM
- `DELETE /api/reports/{report_id}`：删除已保存 report，不修改 session

---

## 数据保存位置

用户发送第一条消息后，会话 JSON 会保存到 `SESSIONS_DIR` 指定的目录下（默认项目根目录的 `sessions/`，见 `backend/config.py`）：

- `sessions/session_<session_id>.json`

文件内容包含：
- `thought_record`（核心表单）
- `chat_history`（消息级别历史）
- `turns`（每一轮的 step_before/step_after/user/assistant 事件日志）
- `conversation_llm`（conversation 实际使用的 provider/model/url）

---

## 独立报告功能怎么用

如果你不想先做网页前端，可以直接把“报告生成”当作独立功能使用。当前仓库已经提供独立脚本：

- `backend/report_cli.py`

它会直接读取 `sessions/` 里的已完成 session，并把结果保存到 `reports/`。

网页端的报告逻辑是：

- `Generate Report` 会调用 LLM 生成 report summary 和 action items
- `Save Report` 只保存当前 report，不再次调用 LLM
- `Saved Reports` 只读取本地 JSON
- `Delete Report` 只删除 `reports/report_<report_id>.json`，不影响 `sessions/`

### 1) 查看哪些 completed sessions 可以拿来做报告

```bash
uv run python -m backend.report_cli list-sessions
```

### 2) 生成单个 session 报告

```bash
uv run python -m backend.report_cli generate --mode single --session-id 20260427_223447
```

### 3) 生成最近 N 个 session 的汇总报告

```bash
uv run python -m backend.report_cli generate --mode recent --limit 5
```

### 4) 自定义多个 session 生成报告

```bash
uv run python -m backend.report_cli generate --mode custom --session-ids 20260424_172104,20260424_173332,20260427_223447
```

### 5) 如果只想先测试结构，不调用 LLM 总结

```bash
uv run python -m backend.report_cli generate --mode recent --limit 5
```

### 6) 直接在网页查看报告效果

启动服务：

```bash
uv run uvicorn backend.api_app:app --reload --port 8000
```

然后在浏览器打开：

- 报告入口页（推荐）：
  - `http://127.0.0.1:5173/reports`
- 单个 session 报告：
  - `http://127.0.0.1:5173/reports/session/20260427_223447`
- 多个 session 报告（最近 N 个）：
  - `http://127.0.0.1:5173/reports/multi?mode=recent&limit=3`
- 多个 session 报告（自定义 session）：
  - `http://127.0.0.1:5173/reports/multi?mode=custom&session_ids=20260424_172104,20260426_234844,20260427_223447`

### 提交前检查

提交或打包前请确认：

1. `.env` 没有被提交，真实 API key 只放在本地。
2. `app_settings.json` 没有被提交。
3. `sessions/session_*.json` 和 `reports/report_*.json` 默认不提交；如需展示样例，请先匿名化并改成单独 sample 文件。
4. 运行 `uv run python -m compileall backend`。
5. 运行 `cd frontend && npm run build`。
