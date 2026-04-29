from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

LLM_PROVIDER = "ollama"
LLM_URL = "http://localhost:11434/api/generate"
LLM_MODEL = "gemma3:27b"

API_KEY_ENV_VAR = "OPENAI_API_KEY"
SESSIONS_DIR = str(PROJECT_ROOT / "sessions")
REPORTS_DIR = str(PROJECT_ROOT / "reports")
