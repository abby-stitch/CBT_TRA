import json
import os
from datetime import datetime
from typing import Any


def save_session(
    *,
    session_id: str,
    current_step: int,
    session_status: str,
    safety_state: str,
    safety_reason: str | None,
    last_safety_warning_turn: int,
    thought_record: dict[str, Any],
    chat_history: list[dict[str, Any]],
    turns: list[dict[str, Any]],
    sessions_dir: str = "sessions",
    user_context: str = "",
) -> str:
    os.makedirs(sessions_dir, exist_ok=True)
    session_data = {
        "session_id": session_id,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "current_step": current_step,
        "session_status": session_status,
        "safety_state": safety_state,
        "safety_reason": safety_reason,
        "last_safety_warning_turn": last_safety_warning_turn,
        "user_context": user_context,
        "thought_record": thought_record,
        "chat_history": chat_history,
        "turns": turns,
    }
    file_path = f"{sessions_dir}/session_{session_id}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(session_data, f, indent=2, ensure_ascii=False)
    return file_path
