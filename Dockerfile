FROM node:22-alpine AS frontend-build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend ./
RUN npm run build


FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Hong_Kong
ENV LLM_PROVIDER=ollama
ENV LLM_MODEL=gemma2:9b
ENV LLM_URL=http://host.docker.internal:11434/api/generate

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-cache --no-install-project

COPY backend ./backend
COPY --from=frontend-build /app/frontend/dist ./frontend_dist
COPY .env.example ./.env.example

RUN mkdir -p sessions reports

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "backend.api_app:app", "--host", "0.0.0.0", "--port", "8000"]
