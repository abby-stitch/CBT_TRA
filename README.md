# CBT Thought Record

A local web app for guided CBT thought records. The app walks users through a structured reflection flow, saves session data on the user's machine, and generates reports from completed records.

This is a self-reflection and academic prototype. It is not a medical device, diagnostic tool, therapy replacement, or emergency support service.

## Overview

CBT Thought Record helps users work through one emotionally significant situation at a time:

- describe the situation
- name the main emotion and initial intensity
- identify the automatic thought
- examine evidence for and against the thought
- identify possible cognitive distortions
- write a more balanced thought
- re-rate the emotion and review a final summary

The project runs locally with either Ollama or an OpenAI-compatible API. Sessions and reports are stored as local JSON files.

## Preview

### Home

![Home page](docs/screenshots/home.png)

### Session

![Thought record session](docs/screenshots/session.png)

### Reports

![Reports page](docs/screenshots/report.png)

## Quick Start

For a detailed bilingual setup guide, see [RUNNING.md](RUNNING.md).

There are two intended ways to use this project:

- **Users** run the Docker image and use the app in the browser.
- **Developers** clone the repository and run backend/frontend separately while editing code.

### 1. Install Docker and Ollama

Official links:

- Docker installation: https://docs.docker.com/installation/
- Ollama download: https://ollama.com/download/

Pull the default local model:

```bash
ollama pull gemma2:9b
```

### 2. Run from Docker Hub

Create local data folders and run the published image:

```bash
mkdir -p sessions reports
docker run --rm \
  -p 8000:8000 \
  -e TZ=Asia/Hong_Kong \
  -v "$PWD/sessions:/app/sessions" \
  -v "$PWD/reports:/app/reports" \
  liangabby/cbt-thought-record-agent:latest
```

Open:

```text
http://localhost:8000
```

Docker will download the image automatically if it is not already on the user's machine.

Docker Hub:

```text
https://hub.docker.com/r/liangabby/cbt-thought-record-agent
```

The Docker image defaults to local Ollama:

```text
Provider: ollama
Model: gemma2:9b
URL: http://host.docker.internal:11434/api/generate
```

## Main Features

- **Guided CBT workflow**: one structured thought record per session.
- **Local storage**: session and report JSON files stay on the user's machine.
- **Session archive**: completed, stopped, and in-progress sessions are listed locally.
- **Resume support**: in-progress sessions can be resumed later.
- **Report generation**: completed sessions can generate single-session or multi-session reports.
- **Distortion overview**: the Reports page shows recorded cognitive distortions ranked by frequency.
- **Saved reports**: saved reports can be reopened without calling the LLM again.
- **Model settings**: switch between Ollama and API mode from the UI.
- **Personal context**: optional user-provided background can be included in new sessions and report summaries.
- **Distortion guide**: cognitive distortion definitions are available from the top-left book icon and inside Step 4.

## Running with an API

The API mode uses an OpenAI-compatible chat completions format.

Copy the environment template:

```bash
cp .env.example .env
```

Add your real key:

```text
OPENAI_API_KEY=your_real_api_key
```

Run with the env file:

```bash
docker run --rm \
  -p 8000:8000 \
  -e TZ=Asia/Hong_Kong \
  --env-file .env \
  -v "$PWD/sessions:/app/sessions" \
  -v "$PWD/reports:/app/reports" \
  liangabby/cbt-thought-record-agent:latest
```

In the app Settings panel:

```text
Provider: API
API / Ollama URL: https://api.openai.com/v1
Model: your_model_name
API key env var: OPENAI_API_KEY
```

Other OpenAI-compatible providers can be used by replacing the URL with the provider's compatible base URL or full `/chat/completions` endpoint.

## Development

Docker is not needed for local development. Run the backend and frontend in two terminals.

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

The Vite dev server proxies `/api/...` requests to `http://127.0.0.1:8000`.

To rebuild the Docker image from source after changing code:

```bash
docker build --no-cache -t cbt-thought-record-agent .
```

Then run it by replacing `liangabby/cbt-thought-record-agent:latest` with `cbt-thought-record-agent` in the Docker command above.

## Configuration

Default local development settings are in [backend/config.py](backend/config.py):

```python
LLM_PROVIDER = "ollama"
LLM_URL = "http://localhost:11434/api/generate"
LLM_MODEL = "gemma2:9b"
API_KEY_ENV_VAR = "OPENAI_API_KEY"
```

Runtime settings changed in the web UI are saved to `app_settings.json`, which is ignored by git.

## Data and Privacy

The app stores local runtime data in:

- `sessions/session_<id>.json`
- `reports/report_<id>.json`
- `app_settings.json`
- `.env`

These files are ignored by git and should not be uploaded to GitHub. If example data is needed, create separate anonymized samples.

## Project Structure

```text
backend/
  agent.py            Core CBT agent workflow
  api_app.py          FastAPI API and production frontend serving
  knowledge_base.py   CBT step guidance and distortion definitions
  report_service.py   Report aggregation and LLM report synthesis
  storage.py          Session JSON persistence
frontend/
  src/                React frontend
  src/distortionGuide.ts  Static frontend distortion guide for instant Step 4 display
Dockerfile            Single-image Docker build
RUNNING.md            Bilingual end-user run guide
README_CN.md          Chinese project overview
README_DEV.md         Longer development notes
```

## Routes

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
- Report generation calls the configured report LLM.
- Saving or reopening a saved report does not call the LLM again.
- Docker timezone defaults to `Asia/Hong_Kong` and can be overridden with `-e TZ=<timezone>`.

## Documentation

- [RUNNING.md](RUNNING.md): bilingual run guide
- [README_CN.md](README_CN.md): Chinese project overview
- [README_DEV.md](README_DEV.md): detailed development notes
- [demonstration.md](demonstration.md): demo and implementation record
