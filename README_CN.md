# CBT Thought Record

A local web app that guides users through a structured CBT thought record, saves sessions on the user's machine, and generates reflection reports from completed records.

This project is a self-reflection and study prototype. It is not a medical device, diagnostic tool, therapy replacement, or emergency support service.

## 中文简介

CBT Thought Record 是一个本地运行的 CBT 思维记录辅助工具。用户可以围绕一个具体情绪事件完成结构化 thought record，包括 situation、emotion、automatic thought、evidence、distortions、balanced thought 和 intensity re-rating。

项目支持：

- 本地 Ollama 模型或 OpenAI-compatible API
- 多个未完成 session 同时保存，并可之后继续
- completed sessions 的单 session / 多 session 报告生成
- 本地 JSON 保存，不上传用户数据
- Docker 单镜像运行

## Quick Start

For a step-by-step bilingual guide, use [RUNNING.md](RUNNING.md). It includes Docker installation, Ollama installation, Windows/macOS/Linux commands, API mode, and troubleshooting.

Short Docker flow:

```bash
docker build --no-cache -t cbt-thought-record-agent .
mkdir -p sessions reports
docker run --rm \
  -p 8000:8000 \
  -e TZ=Asia/Hong_Kong \
  -v "$PWD/sessions:/app/sessions" \
  -v "$PWD/reports:/app/reports" \
  cbt-thought-record-agent
```

Open:

```text
http://localhost:8000
```

Default Docker configuration uses local Ollama:

```text
Provider: ollama
Model: gemma2:9b
URL: http://host.docker.internal:11434/api/generate
```

Before running with Ollama, install Ollama and pull the default model:

```bash
ollama pull gemma2:9b
```

Official installation links:

- Docker: https://docs.docker.com/installation/
- Ollama: https://ollama.com/download/

## Features

- **Guided thought record**: The assistant walks through the CBT thought record steps one turn at a time.
- **Local sessions**: Sessions are saved as JSON files under `sessions/` after the user sends a message.
- **Resume in-progress work**: `in_progress` sessions stay in the archive and can be resumed later.
- **Reports**: Completed sessions can be used to generate single-session or multi-session reports.
- **Saved reports**: Generated reports can be saved locally under `reports/` and reopened without regenerating LLM content.
- **Settings**: Switch between local Ollama and API mode, edit model names, URLs, data folders, and API key environment variable names.
- **Personal context**: Optional user-provided context can be included in new conversations and report summaries.

## Run Locally for Development

Backend:

```bash
uv sync
uv run uvicorn backend.api_app:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

The Vite frontend proxies `/api/...` requests to `http://127.0.0.1:8000`.

## Configuration

Default local development settings are in [backend/config.py](backend/config.py):

```python
LLM_PROVIDER = "ollama"
LLM_URL = "http://localhost:11434/api/generate"
LLM_MODEL = "gemma2:9b"
API_KEY_ENV_VAR = "OPENAI_API_KEY"
```

Runtime settings changed in the web UI are saved to `app_settings.json`, which is intentionally ignored by git.

For API mode, copy the example env file and set your real key locally:

```bash
cp .env.example .env
```

```text
OPENAI_API_KEY=your_real_api_key
```

In Settings, choose:

```text
Provider: API
API / Ollama URL: https://api.openai.com/v1
Model: your_model_name
API key env var: OPENAI_API_KEY
```

Other OpenAI-compatible providers can be used by replacing the URL with their compatible base URL or full `/chat/completions` endpoint.

## Data and Privacy

The project stores user data locally:

- `sessions/session_<id>.json`
- `reports/report_<id>.json`
- `app_settings.json`
- `.env`

These files are ignored by git and should not be uploaded to GitHub. If you need example data, create anonymized sample files separately.

## Project Structure

```text
backend/
  agent.py            Core CBT agent workflow
  api_app.py          FastAPI JSON API and production frontend serving
  report_service.py   Report data aggregation and LLM report summary
  storage.py          Session JSON saving
frontend/
  src/                React frontend
Dockerfile            Single-image Docker build
RUNNING.md            End-user run guide
README_DEV.md         Longer development notes and history
```

## Main Routes

- `/` - start a thought record
- `/sessions` - session archive and resume flow
- `/reports` - report generation page
- `/reports/saved` - saved reports
- `/reports/session/<session_id>` - single-session report preview
- `/reports/multi?...` - multi-session report preview

## Notes

- Empty sessions are not saved.
- Completed sessions can generate reports.
- In-progress sessions can be resumed and do not block starting a new session.
- Report generation calls the configured report LLM; saving or reopening saved reports does not call the LLM again.
- Docker runs in a container, so timezone is set with `TZ=Asia/Hong_Kong` by default and can be overridden with `-e TZ=<timezone>`.

## Documentation

- [RUNNING.md](RUNNING.md): user-facing run guide in English and Chinese
- [README_DEV.md](README_DEV.md): longer project notes and implementation details
- [demonstration.md](demonstration.md): current work record and demo notes
