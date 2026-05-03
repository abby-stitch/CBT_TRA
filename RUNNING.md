# CBT Thought Record - Run Guide

中文说明见下半部分。

## English

### What This Project Does

CBT Thought Record is a local self-reflection web app. It guides one CBT-style thought record, saves session JSON files locally, and can generate single-session or multi-session reports from completed records.

It is not a medical, diagnostic, or emergency-care tool.

### 1. Install Docker

Docker is used so you do not need to install Python, Node.js, or frontend dependencies manually.

Install Docker from the official documentation:

- Docker install overview: https://docs.docker.com/installation/
- Docker Desktop: https://docs.docker.com/desktop/
- Docker Desktop for Windows: https://docs.docker.com/desktop/setup/install/windows-install/
- Docker Engine for Linux: https://docs.docker.com/en/latest/installation/

After installation, open Docker Desktop or start the Docker service, then verify:

```bash
docker --version
```

### 2. Install Ollama

The default local model provider is Ollama. Install it from the official Ollama documentation:

- Ollama documentation: https://docs.ollama.com/
- Ollama download page: https://ollama.com/download/
- Ollama quickstart: https://docs.ollama.com/quickstart
- Ollama GitHub: https://github.com/ollama/ollama

After installing Ollama, download the default model:

```bash
ollama pull gemma2:9b
```

Make sure Ollama is running. You can check:

```bash
ollama list
```

The app inside Docker connects to Ollama on the host machine through:

```text
http://host.docker.internal:11434/api/generate
```

On Linux Docker Engine, if `host.docker.internal` does not work, add this option to `docker run`:

```bash
--add-host=host.docker.internal:host-gateway
```

### 3. Build the App Image

Open a terminal in the project folder:

```bash
cd path/to/tra_test
```

Build the Docker image:

```bash
docker build --no-cache -t cbt-thought-record-agent .
```

Use `--no-cache` when you want to make sure Docker picks up the latest frontend and backend changes.

### 4. Run the App

macOS / Linux:

```bash
mkdir -p sessions reports
docker run --rm \
  -p 8000:8000 \
  -e TZ=Asia/Hong_Kong \
  -v "$PWD/sessions:/app/sessions" \
  -v "$PWD/reports:/app/reports" \
  cbt-thought-record-agent
```

Windows PowerShell:

```powershell
mkdir sessions -ErrorAction SilentlyContinue
mkdir reports -ErrorAction SilentlyContinue
docker run --rm `
  -p 8000:8000 `
  -e TZ=Asia/Hong_Kong `
  -v "${PWD}/sessions:/app/sessions" `
  -v "${PWD}/reports:/app/reports" `
  cbt-thought-record-agent
```

Then open:

```text
http://localhost:8000
```

The `sessions/` and `reports/` folders are mounted from your computer into the container, so your records stay on your machine even after the container stops.

### 5. Optional: Keep Settings After Restart

If you want model settings and profile text to persist after rebuilding or restarting the container, mount `app_settings.json` too.

macOS / Linux:

```bash
touch app_settings.json
docker run --rm \
  -p 8000:8000 \
  -e TZ=Asia/Hong_Kong \
  -v "$PWD/app_settings.json:/app/app_settings.json" \
  -v "$PWD/sessions:/app/sessions" \
  -v "$PWD/reports:/app/reports" \
  cbt-thought-record-agent
```

Windows PowerShell:

```powershell
New-Item app_settings.json -ItemType File -Force
docker run --rm `
  -p 8000:8000 `
  -e TZ=Asia/Hong_Kong `
  -v "${PWD}/app_settings.json:/app/app_settings.json" `
  -v "${PWD}/sessions:/app/sessions" `
  -v "${PWD}/reports:/app/reports" `
  cbt-thought-record-agent
```

### 6. Optional: Use an API Instead of Ollama

This app can also use OpenAI-compatible APIs such as OpenAI, Volcano Engine, Alibaba Cloud Bailian, and similar providers.

Copy the example env file:

```bash
cp .env.example .env
```

Put your real key in `.env`:

```text
OPENAI_API_KEY=your_real_api_key
```

Run Docker with the env file:

```bash
docker run --rm \
  -p 8000:8000 \
  -e TZ=Asia/Hong_Kong \
  --env-file .env \
  -v "$PWD/sessions:/app/sessions" \
  -v "$PWD/reports:/app/reports" \
  cbt-thought-record-agent
```

In the app, open Settings and choose:

```text
Provider: API
API / Ollama URL: https://api.openai.com/v1
Model: your_model_name
API key env var: OPENAI_API_KEY
```

For non-OpenAI providers, replace the URL with that provider's OpenAI-compatible base URL or full `/chat/completions` URL.

### 7. Main Features

- Home: start a new thought record session.
- Conversation: answer step-by-step CBT thought record questions.
- Session Archive: review completed, stopped, and in-progress sessions.
- Resume Session: click an in-progress session to continue it later.
- Reports: generate single-session or multi-session reports from completed sessions.
- Saved Reports: reopen saved reports without regenerating LLM content.
- Settings: switch between Ollama and API, edit model name, URL, data folders, and API key env var.
- Personal Context: add optional background context for new sessions and reports.

### 8. Troubleshooting

If the page is blank after rebuilding, stop the old container, rebuild with `--no-cache`, and hard refresh the browser.

```bash
docker ps
docker stop <container_id>
docker build --no-cache -t cbt-thought-record-agent .
```

If Docker cannot connect to Ollama:

- Confirm Ollama is running on the host machine.
- Confirm `ollama pull gemma2:9b` has completed.
- In Docker settings, use `http://host.docker.internal:11434/api/generate`, not `http://localhost:11434/api/generate`.
- On Linux Docker Engine, add `--add-host=host.docker.internal:host-gateway`.

If the report/session time looks wrong, set the container timezone:

```bash
-e TZ=Asia/Hong_Kong
```

Old JSON files keep the time they were originally written with; only new sessions and reports use the new timezone.

## 中文

### 这个项目是什么

CBT Thought Record 是一个本地运行的自我反思网页应用。它会引导用户完成一个 CBT thought record，把 session 保存成本地 JSON 文件，并可以基于 completed sessions 生成单个或多个 session 的报告。

它不是医疗、诊断或紧急干预工具。

### 1. 安装 Docker

项目推荐用 Docker 运行，这样使用者不需要手动安装 Python、Node.js 或前端依赖。

请从 Docker 官方文档安装：

- Docker 安装总览：https://docs.docker.com/installation/
- Docker Desktop：https://docs.docker.com/desktop/
- Windows 安装说明：https://docs.docker.com/desktop/setup/install/windows-install/
- Linux Docker Engine：https://docs.docker.com/en/latest/installation/

安装后打开 Docker Desktop，或启动 Docker 服务，然后检查：

```bash
docker --version
```

### 2. 安装 Ollama

项目默认使用本地 Ollama 模型。请从 Ollama 官方文档安装：

- Ollama 文档：https://docs.ollama.com/
- Ollama 下载页：https://ollama.com/download/
- Ollama Quickstart：https://docs.ollama.com/quickstart
- Ollama GitHub：https://github.com/ollama/ollama

安装后下载默认模型：

```bash
ollama pull gemma2:9b
```

确认 Ollama 正在运行：

```bash
ollama list
```

Docker 容器内会通过下面这个地址访问宿主机上的 Ollama：

```text
http://host.docker.internal:11434/api/generate
```

如果是在 Linux Docker Engine 上运行，并且 `host.docker.internal` 不可用，需要在 `docker run` 里加：

```bash
--add-host=host.docker.internal:host-gateway
```

### 3. 构建项目镜像

在项目文件夹中打开 terminal：

```bash
cd path/to/tra_test
```

构建 Docker 镜像：

```bash
docker build --no-cache -t cbt-thought-record-agent .
```

如果刚修改过前端或后端代码，建议保留 `--no-cache`，确保 Docker 使用最新代码。

### 4. 运行项目

macOS / Linux：

```bash
mkdir -p sessions reports
docker run --rm \
  -p 8000:8000 \
  -e TZ=Asia/Hong_Kong \
  -v "$PWD/sessions:/app/sessions" \
  -v "$PWD/reports:/app/reports" \
  cbt-thought-record-agent
```

Windows PowerShell：

```powershell
mkdir sessions -ErrorAction SilentlyContinue
mkdir reports -ErrorAction SilentlyContinue
docker run --rm `
  -p 8000:8000 `
  -e TZ=Asia/Hong_Kong `
  -v "${PWD}/sessions:/app/sessions" `
  -v "${PWD}/reports:/app/reports" `
  cbt-thought-record-agent
```

然后打开：

```text
http://localhost:8000
```

这里把本机的 `sessions/` 和 `reports/` 挂载进容器，所以容器停止后，记录和报告仍然保存在本机。

### 5. 可选：保留 Settings

如果希望容器重启或重新打包后仍保留页面 settings 和 personal context，可以额外挂载 `app_settings.json`。

macOS / Linux：

```bash
touch app_settings.json
docker run --rm \
  -p 8000:8000 \
  -e TZ=Asia/Hong_Kong \
  -v "$PWD/app_settings.json:/app/app_settings.json" \
  -v "$PWD/sessions:/app/sessions" \
  -v "$PWD/reports:/app/reports" \
  cbt-thought-record-agent
```

Windows PowerShell：

```powershell
New-Item app_settings.json -ItemType File -Force
docker run --rm `
  -p 8000:8000 `
  -e TZ=Asia/Hong_Kong `
  -v "${PWD}/app_settings.json:/app/app_settings.json" `
  -v "${PWD}/sessions:/app/sessions" `
  -v "${PWD}/reports:/app/reports" `
  cbt-thought-record-agent
```

### 6. 可选：使用 API 而不是 Ollama

项目也可以使用 OpenAI-compatible API，例如 OpenAI、火山引擎、阿里云百炼等。

复制 `.env.example`：

```bash
cp .env.example .env
```

在 `.env` 中填写真实 key：

```text
OPENAI_API_KEY=your_real_api_key
```

运行 Docker 时传入 `.env`：

```bash
docker run --rm \
  -p 8000:8000 \
  -e TZ=Asia/Hong_Kong \
  --env-file .env \
  -v "$PWD/sessions:/app/sessions" \
  -v "$PWD/reports:/app/reports" \
  cbt-thought-record-agent
```

在网页 Settings 中选择：

```text
Provider: API
API / Ollama URL: https://api.openai.com/v1
Model: your_model_name
API key env var: OPENAI_API_KEY
```

如果使用其他 OpenAI-compatible provider，把 URL 改成对应服务的 base URL 或完整 `/chat/completions` URL。

### 7. 主要功能

- Home：首页，可以开始新的 thought record session。
- Conversation：按步骤完成 CBT thought record。
- Session Archive：查看 completed、stopped 和 in-progress sessions。
- Resume Session：点击未完成 session 可以继续之前的对话。
- Reports：基于 completed sessions 生成单 session 或多 session 报告。
- Saved Reports：查看已经保存的报告，不重新调用 LLM。
- Settings：切换 Ollama / API，修改模型名、URL、数据目录和 API key 环境变量名。
- Personal Context：填写可选个人背景，用于新 session 和 report summary。

### 8. 常见问题

如果重新打包后页面空白，通常是旧容器或浏览器缓存导致的。先停掉旧容器，重新 build，再硬刷新浏览器。

```bash
docker ps
docker stop <container_id>
docker build --no-cache -t cbt-thought-record-agent .
```

如果 Docker 连不上 Ollama：

- 确认宿主机上的 Ollama 正在运行。
- 确认已经运行 `ollama pull gemma2:9b`。
- Docker settings 中应使用 `http://host.docker.internal:11434/api/generate`，不要用 `http://localhost:11434/api/generate`。
- Linux Docker Engine 需要加 `--add-host=host.docker.internal:host-gateway`。

如果 session/report 时间不对，运行容器时设置时区：

```bash
-e TZ=Asia/Hong_Kong
```

旧 JSON 文件的时间不会自动改变；只有新生成的 session 和 report 会使用新的时区。
