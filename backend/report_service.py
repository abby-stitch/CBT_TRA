from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

from backend import config
from backend import llm_io


def _reports_dir() -> Path:
    reports_dir = getattr(config, "REPORTS_DIR", "reports")
    p = Path(reports_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _safe_report_path(report_id: str) -> Path:
    clean_id = str(report_id or "").strip()
    if not clean_id or "/" in clean_id or "\\" in clean_id or clean_id.startswith("."):
        raise FileNotFoundError(report_id)
    return _reports_dir() / f"report_{clean_id}.json"


def _sessions_dir() -> Path:
    sessions_dir = getattr(config, "SESSIONS_DIR", "sessions")
    return Path(sessions_dir)


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except Exception:
            return None
    return None


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _session_sort_key(data: dict[str, Any]) -> tuple[str, str]:
    thought_record = data.get("thought_record") or {}
    return (
        str(thought_record.get("date") or ""),
        str(data.get("session_id") or ""),
    )


def load_all_sessions() -> list[dict[str, Any]]:
    sessions_dir = _sessions_dir()
    if not sessions_dir.exists():
        return []

    out: list[dict[str, Any]] = []
    for path in sorted(sessions_dir.glob("session_*.json")):
        try:
            out.append(_load_json(path))
        except Exception:
            continue
    out.sort(key=_session_sort_key)
    return out


def completed_sessions() -> list[dict[str, Any]]:
    return [s for s in load_all_sessions() if s.get("session_status") == "completed"]


def list_completed_sessions() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for session_data in completed_sessions():
        record = session_data.get("thought_record") or {}
        before = _safe_int(record.get("intensity_before"))
        after = _safe_int(record.get("intensity_after"))
        delta = after - before if before is not None and after is not None else None
        out.append(
            {
                "session_id": str(session_data.get("session_id") or ""),
                "date": record.get("date"),
                "emotion": record.get("emotion") or None,
                "distortions": list(record.get("distortions") or []),
                "intensity_before": before,
                "intensity_after": after,
                "intensity_delta": delta,
                "has_summary": bool(record.get("summary")),
            }
        )
    return out


def select_sessions(
    *,
    mode: str = "recent",
    limit: int = 5,
    session_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    sessions = completed_sessions()
    if not sessions:
        return []

    if mode == "single":
        if not session_ids:
            return []
        target_id = str(session_ids[0])
        return [s for s in sessions if str(s.get("session_id")) == target_id]

    if mode == "custom":
        wanted = set(session_ids or [])
        return [s for s in sessions if str(s.get("session_id")) in wanted]

    limit = max(1, min(int(limit), 50))
    return sessions[-limit:]


def _single_session_report_item(session_data: dict[str, Any]) -> dict[str, Any]:
    record = session_data.get("thought_record") or {}
    before = _safe_int(record.get("intensity_before"))
    after = _safe_int(record.get("intensity_after"))
    delta = after - before if before is not None and after is not None else None
    return {
        "session_id": str(session_data.get("session_id") or ""),
        "date": record.get("date"),
        "situation": record.get("situation") or None,
        "emotion": record.get("emotion") or None,
        "intensity_before": before,
        "automatic_thought": record.get("automatic_thought") or None,
        "evidence_for": list(record.get("evidence_for") or []),
        "evidence_against": list(record.get("evidence_against") or []),
        "distortions": list(record.get("distortions") or []),
        "balanced_thought": record.get("balanced_thought") or None,
        "intensity_after": after,
        "intensity_delta": delta,
        "summary": record.get("summary") or None,
        "session_report_url": f"/reports/session/{str(session_data.get('session_id') or '')}",
    }


def _multi_session_card_item(session_data: dict[str, Any]) -> dict[str, Any]:
    record = session_data.get("thought_record") or {}
    before = _safe_int(record.get("intensity_before"))
    after = _safe_int(record.get("intensity_after"))
    delta = after - before if before is not None and after is not None else None
    return {
        "session_id": str(session_data.get("session_id") or ""),
        "date": record.get("date"),
        "emotion": record.get("emotion") or None,
        "intensity_before": before,
        "intensity_after": after,
        "intensity_delta": delta,
        "distortions": list(record.get("distortions") or []),
        "balanced_thought": record.get("balanced_thought") or None,
        "session_report_url": f"/reports/session/{str(session_data.get('session_id') or '')}",
    }


def _distribution_from_counter(counter: Counter[str], total: int, top_n: int = 10) -> list[dict[str, Any]]:
    if total <= 0:
        return []
    return [
        {
            "label": label,
            "count": count,
            "ratio": round(count / total, 2),
        }
        for label, count in counter.most_common(top_n)
    ]


def _trend_points(sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for s in sessions:
        record = s.get("thought_record") or {}
        before = _safe_int(record.get("intensity_before"))
        after = _safe_int(record.get("intensity_after"))
        delta = after - before if before is not None and after is not None else None
        points.append(
            {
                "session_id": str(s.get("session_id") or ""),
                "date": record.get("date"),
                "emotion": record.get("emotion") or None,
                "before": before,
                "after": after,
                "delta": delta,
                "distortions": list(record.get("distortions") or []),
            }
        )
    return points


def _distortion_trends(sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not sessions:
        return []

    points = _trend_points(sessions)
    all_labels = sorted({d for p in points for d in p["distortions"]})
    if not all_labels:
        return []

    split = max(1, len(points) // 2)
    earlier = points[:split]
    later = points[split:]
    if not later:
        later = points[-split:]

    trends: list[dict[str, Any]] = []
    for label in all_labels:
        earlier_count = sum(1 for p in earlier if label in p["distortions"])
        later_count = sum(1 for p in later if label in p["distortions"])
        if later_count > earlier_count:
            direction = "up"
        elif later_count < earlier_count:
            direction = "down"
        else:
            direction = "flat"

        current_streak = 0
        for p in reversed(points):
            if label in p["distortions"]:
                current_streak += 1
            else:
                break

        trends.append(
            {
                "label": label,
                "total_count": sum(1 for p in points if label in p["distortions"]),
                "earlier_count": earlier_count,
                "later_count": later_count,
                "direction": direction,
                "current_streak": current_streak,
            }
        )

    trends.sort(key=lambda item: (-item["total_count"], item["label"]))
    return trends


def _summary_metrics(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    items = [_multi_session_card_item(s) for s in sessions]
    before_values = [x["intensity_before"] for x in items if x["intensity_before"] is not None]
    after_values = [x["intensity_after"] for x in items if x["intensity_after"] is not None]
    deltas = [x["intensity_delta"] for x in items if x["intensity_delta"] is not None]
    improved = [x for x in items if x["intensity_delta"] is not None and x["intensity_delta"] < 0]

    emotion_counter = Counter(x["emotion"] for x in items if x["emotion"])
    distortion_counter = Counter(
        distortion
        for x in items
        for distortion in x["distortions"]
    )

    return {
        "total_sessions_in_scope": len(items),
        "average_intensity_before": round(mean(before_values), 2) if before_values else None,
        "average_intensity_after": round(mean(after_values), 2) if after_values else None,
        "average_intensity_delta": round(mean(deltas), 2) if deltas else None,
        "improved_sessions": len(improved),
        "top_emotions": _distribution_from_counter(emotion_counter, len(items), top_n=5),
        "top_distortions": _distribution_from_counter(distortion_counter, len(items), top_n=8),
        "emotion_trend": _trend_points(sessions),
        "distortion_trends": _distortion_trends(sessions),
    }


def _report_summary_payload(report_type: str, items: list[dict[str, Any]], metrics: dict[str, Any]) -> dict[str, Any]:
    if report_type == "single_session":
        item = items[0] if items else {}
        return {
            "report_type": report_type,
            "session": {
                "date": item.get("date"),
                "situation": item.get("situation"),
                "emotion": item.get("emotion"),
                "intensity_before": item.get("intensity_before"),
                "intensity_after": item.get("intensity_after"),
                "intensity_delta": item.get("intensity_delta"),
                "automatic_thought": item.get("automatic_thought"),
                "evidence_for": item.get("evidence_for"),
                "evidence_against": item.get("evidence_against"),
                "distortions": item.get("distortions"),
                "balanced_thought": item.get("balanced_thought"),
                "summary": item.get("summary"),
            },
        }

    return {
        "report_type": report_type,
        "metrics": {
            "total_sessions_in_scope": metrics.get("total_sessions_in_scope"),
            "improved_sessions": metrics.get("improved_sessions"),
            "average_intensity_delta": metrics.get("average_intensity_delta"),
            "top_emotions": metrics.get("top_emotions"),
            "top_distortions": metrics.get("top_distortions"),
            "distortion_trends": metrics.get("distortion_trends"),
        },
        "sessions": [
            {
                "date": item.get("date"),
                "emotion": item.get("emotion"),
                "intensity_before": item.get("intensity_before"),
                "intensity_after": item.get("intensity_after"),
                "intensity_delta": item.get("intensity_delta"),
                "distortions": item.get("distortions"),
                "balanced_thought": item.get("balanced_thought"),
            }
            for item in items
        ],
    }


def _generate_llm_report_summary(
    *,
    report_type: str,
    items: list[dict[str, Any]],
    metrics: dict[str, Any],
    user_context: str = "",
) -> tuple[str | None, list[str], str | None]:
    payload = _report_summary_payload(report_type, items, metrics)
    context = user_context.strip()
    profile_block = context if context else "No user profile was provided."
    prompt = f"""
You are writing the synthesis section for a CBT Thought Record report.
This is a self-reflection support tool, not therapy, diagnosis, or medical advice.

OPTIONAL USER PROFILE:
{profile_block}

REPORT DATA:
{json.dumps(payload, ensure_ascii=False, indent=2)}

RULES:
- Use the profile only as optional background.
- Do not diagnose, label personality, or make claims about the user's mental health.
- Do not infer fixed traits such as "you are an anxious person" or "you have a disorder."
- Prefer careful wording such as "in these records, a pattern appears..." or "a useful next practice focus may be..."
- If profile and session data conflict, trust the session data.
- Make the synthesis the most important part of the report: interpret the record, not just restate fields.
- For a single-session report, mention the main emotional shift, the automatic thought pattern, and one grounded next reflection focus.
- For a multi-session report, mention recurring stressors, emotions, distortions, or balanced-thought progress only when supported by the data.
- Action items must be gentle CBT practice suggestions based only on the report data. Do not give medical advice.
- Output ONLY valid JSON, no markdown:
{{"synthesis":"one warm paragraph, 90-150 words","action_items":["short practical item 1","short practical item 2","short practical item 3"]}}
"""
    try:
        raw = llm_io.call_llm(
            provider=config.LLM_PROVIDER,
            url=config.LLM_URL,
            model=config.LLM_MODEL,
            prompt=prompt,
            temperature=0.4,
            api_key_env_var=config.API_KEY_ENV_VAR,
            timeout_s=90.0,
        ).strip()
    except Exception as exc:
        return None, [], str(exc)

    if not raw:
        return None, [], "LLM returned an empty summary."
    if raw.startswith("Error:"):
        return None, [], raw

    try:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end >= start:
            data = json.loads(raw[start : end + 1])
            synthesis = data.get("synthesis")
            action_items = data.get("action_items") or []
            if isinstance(action_items, str):
                action_items = [action_items]
            clean_items = [str(item).strip() for item in action_items if str(item).strip()][:3]
            if isinstance(synthesis, str) and synthesis.strip():
                return synthesis.strip(), clean_items, None
    except Exception:
        pass

    return raw, [], None


def generate_report(
    *,
    mode: str = "recent",
    limit: int = 5,
    session_ids: list[str] | None = None,
    include_llm_summary: bool = False,
    user_context: str = "",
    persist: bool = True,
) -> dict[str, Any]:
    sessions = select_sessions(mode=mode, limit=limit, session_ids=session_ids)
    if not sessions:
        raise ValueError("No completed sessions available for report generation.")

    report_type = "single_session" if len(sessions) == 1 else "multi_session"
    items = (
        [_single_session_report_item(sessions[0])]
        if report_type == "single_session"
        else [_multi_session_card_item(s) for s in sessions]
    )
    scope = {
        "mode": mode,
        "requested_limit": limit if mode == "recent" else None,
        "session_ids": [item["session_id"] for item in items],
        "report_type": report_type,
        "date_range": {
            "start": items[0].get("date"),
            "end": items[-1].get("date"),
        },
    }
    if report_type == "single_session":
        metrics = {
            "intensity_before": items[0].get("intensity_before"),
            "intensity_after": items[0].get("intensity_after"),
            "intensity_delta": items[0].get("intensity_delta"),
        }
    else:
        metrics = _summary_metrics(sessions)

    report_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    report_data = {
        "report_id": report_id,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "scope": scope,
        "metrics": metrics,
        "sessions": items,
        "llm_summary": None,
        "llm_action_items": [],
        "llm_error": None,
        "include_llm_summary": include_llm_summary,
        "profile_context_used": bool(user_context.strip()),
    }
    if include_llm_summary:
        summary, action_items, error = _generate_llm_report_summary(
            report_type=report_type,
            items=items,
            metrics=metrics,
            user_context=user_context,
        )
        report_data["llm_summary"] = summary
        report_data["llm_action_items"] = action_items
        report_data["llm_error"] = error
    if persist:
        save_report(report_data)
    return report_data


def save_report(report_data: dict[str, Any]) -> Path:
    report_id = str(report_data.get("report_id") or datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    report_data["report_id"] = report_id
    path = _safe_report_path(report_id)
    path.write_text(json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def list_reports() -> list[dict[str, Any]]:
    reports_dir = _reports_dir()
    out: list[dict[str, Any]] = []
    for path in sorted(reports_dir.glob("report_*.json")):
        try:
            data = _load_json(path)
        except Exception:
            continue
        out.append(
            {
                "report_id": data.get("report_id"),
                "generated_at": data.get("generated_at"),
                "scope": data.get("scope") or {},
                "sessions_count": len(data.get("sessions") or []),
                "has_llm_summary": bool(data.get("llm_summary")),
            }
        )
    out.sort(key=lambda item: str(item.get("generated_at") or ""), reverse=True)
    return out


def load_report(report_id: str) -> dict[str, Any]:
    path = _safe_report_path(report_id)
    if not path.exists():
        raise FileNotFoundError(report_id)
    return _load_json(path)


def delete_report(report_id: str) -> None:
    path = _safe_report_path(report_id)
    if not path.exists():
        raise FileNotFoundError(report_id)
    path.unlink()
