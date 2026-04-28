from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

import config


def _reports_dir() -> Path:
    reports_dir = getattr(config, "REPORTS_DIR", "reports")
    p = Path(reports_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


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


def generate_report(
    *,
    mode: str = "recent",
    limit: int = 5,
    session_ids: list[str] | None = None,
    include_llm_summary: bool = False,
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
        "llm_error": None,
        "include_llm_summary": include_llm_summary,
    }
    if persist:
        save_report(report_data)
    return report_data


def save_report(report_data: dict[str, Any]) -> Path:
    report_id = str(report_data.get("report_id") or datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    path = _reports_dir() / f"report_{report_id}.json"
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
    path = _reports_dir() / f"report_{report_id}.json"
    if not path.exists():
        raise FileNotFoundError(report_id)
    return _load_json(path)
