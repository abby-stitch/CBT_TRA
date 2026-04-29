import json
import os
import re
import requests
from typing import Any


def call_llm(
    *,
    provider: str,
    url: str,
    model: str,
    prompt: str,
    temperature: float = 0.7,
    api_key_env_var: str,
    timeout_s: float = 60.0,
) -> str:
    provider = (provider or "").strip().lower()
    url = (url or "").strip()
    model = (model or "").strip()

    if not provider:
        return "Error: missing provider (set config.LLM_PROVIDER)"
    if not url:
        return "Error: missing url (set config.LLM_URL)"
    if not model:
        return "Error: missing model (set config.LLM_MODEL)"

    if provider == "ollama":
        payload = {"model": model, "prompt": prompt, "stream": False, "temperature": temperature}
        try:
            res = requests.post(url, json=payload, timeout=timeout_s)
            data = res.json()
            return str(data.get("response", "")).strip()
        except Exception as e:
            return f"Error: {e}"

    if provider in {"openai_compatible", "api"}:
        base = url.rstrip("/")
        endpoint = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
        api_key = os.getenv(api_key_env_var or "", "").strip()
        if not api_key:
            return f"Error: missing API key in env var {api_key_env_var}"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        try:
            res = requests.post(endpoint, headers=headers, json=payload, timeout=timeout_s)
            data = res.json()
            choices = data.get("choices") or []
            if choices and isinstance(choices, list):
                msg = choices[0].get("message") or {}
                content = msg.get("content")
                if isinstance(content, str):
                    return content.strip()
            return f"Error: unexpected API response format: {json.dumps(data)[:300]}"
        except Exception as e:
            return f"Error: {e}"

    return f"Error: unsupported provider {provider}"


def extract_first_json_object(text: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    json_str = re.sub(r",\s*\}", "}", match.group(0))
    try:
        return json.loads(json_str)
    except Exception:
        return None