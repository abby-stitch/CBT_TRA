import json
import re
from typing import Callable


def semantic_safety_check(
    *,
    call_llm: Callable[[str, float], str],
    safety_prompt: str,
    recent_turns: str,
    user_input: str,
    fallback_patterns: list[tuple[str, str]],
) -> tuple[str, str | None, str]:
    prompt = f"""
{safety_prompt}

RECENT TURNS:
{recent_turns}
USER INPUT:
{user_input}
"""
    raw = call_llm(prompt, 0.1)
    try:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            data = json.loads(re.sub(r",\s*\}", "}", match.group(0)))
            risk = data.get("risk_level")
            reason = data.get("reason")
            if risk in {"normal", "supportive_warning", "acute_warning"}:
                return risk, reason, "llm"
    except Exception:
        pass

    text = user_input.lower()
    for pattern, _ in fallback_patterns:
        if re.search(pattern, text):
            return "acute_warning", "fallback pattern matched acute-risk phrase", "fallback"
    return "normal", None, "default"


def should_include_safety_note(*, risk_level: str, last_safety_warning_turn: int, turns_len: int) -> bool:
    if risk_level == "acute_warning":
        return True
    if risk_level != "supportive_warning":
        return False
    if last_safety_warning_turn == 0:
        return True
    return (turns_len - last_safety_warning_turn) >= 2


def support_guidance_line(risk_level: str) -> str:
    if risk_level == "acute_warning":
        return "If you might be unsafe right now, please reach out to a trusted person, local emergency help, or professional support as soon as you can."
    if risk_level == "supportive_warning":
        return "If these thoughts start to feel unsafe or overwhelming, please consider reaching out to someone you trust or to professional support."
    return ""


def ensure_support_guidance(message: str, risk_level: str, include_safety_note: bool) -> str:
    if not include_safety_note:
        return message
    guidance = support_guidance_line(risk_level)
    if not guidance:
        return message
    lowered = message.lower()
    if any(
        token in lowered
        for token in [
            "professional support",
            "someone you trust",
            "trusted person",
            "emergency help",
            "reach out",
            "resources available",
            "people who care",
            "unsafe right now",
            "overwhelming",
        ]
    ):
        return message
    return f"{message}\n\n{guidance}"
