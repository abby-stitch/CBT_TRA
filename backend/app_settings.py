from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend import config

SETTINGS_PATH = config.PROJECT_ROOT / "app_settings.json"


def _default_settings() -> dict[str, str]:
    return {
        "llm_provider": config.LLM_PROVIDER,
        "llm_url": config.LLM_URL,
        "llm_model": config.LLM_MODEL,
        "api_key_env_var": config.API_KEY_ENV_VAR,
        "sessions_dir": "sessions",
        "reports_dir": "reports",
        "user_context": "",
    }


def load_settings() -> dict[str, str]:
    settings = _default_settings()
    if SETTINGS_PATH.exists():
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            for key, value in data.items():
                if key in settings and isinstance(value, str):
                    settings[key] = value
        except Exception:
            pass
    apply_settings(settings)
    return settings


def save_settings(updates: dict[str, Any]) -> dict[str, str]:
    settings = load_settings()
    for key in settings:
        value = updates.get(key)
        if isinstance(value, str):
            settings[key] = value.strip() if key != "user_context" else value.strip()
    apply_settings(settings)
    SETTINGS_PATH.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
    return settings


def apply_settings(settings: dict[str, str]) -> None:
    config.LLM_PROVIDER = settings.get("llm_provider") or config.LLM_PROVIDER
    config.LLM_URL = settings.get("llm_url") or config.LLM_URL
    config.LLM_MODEL = settings.get("llm_model") or config.LLM_MODEL
    config.API_KEY_ENV_VAR = settings.get("api_key_env_var") or config.API_KEY_ENV_VAR
    config.SESSIONS_DIR = _resolve_data_dir(settings.get("sessions_dir"), config.SESSIONS_DIR)
    config.REPORTS_DIR = _resolve_data_dir(settings.get("reports_dir"), config.REPORTS_DIR)


def _resolve_data_dir(value: str | None, fallback: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return fallback
    path = Path(raw)
    if not path.is_absolute():
        path = config.PROJECT_ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return str(path)
