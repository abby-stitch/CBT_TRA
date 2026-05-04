from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend import app_settings
from backend.agent import CBTAgent
from backend.knowledge_base import DistortionKnowledge
from backend import report_service

app = FastAPI(title="TRA Test API")
FRONTEND_DIST = PROJECT_ROOT / "frontend_dist"

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_agents: dict[str, CBTAgent] = {}
_active_session_id: str | None = None
_completed_sessions: set[str] = set()


class StartResponse(BaseModel):
    session_id: str
    message: str
    current_step: int
    thought_record: dict[str, Any]


class MessageRequest(BaseModel):
    session_id: str
    message: str


class MessageResponse(BaseModel):
    session_id: str
    message: str
    current_step: int
    step_completed: bool
    session_completed: bool
    record_url: str | None
    thought_record: dict[str, Any]
    can_undo: bool = False
    undo_count: int = 0
    undo_limit: int = 3


class GenerateReportRequest(BaseModel):
    mode: str = "recent"
    limit: int = 5
    session_ids: list[str] = Field(default_factory=list)
    include_llm_summary: bool = False


class GenerateReportResponse(BaseModel):
    report_id: str
    report_url: str
    generated_at: str
    scope: dict[str, Any]
    metrics: dict[str, Any]
    sessions: list[dict[str, Any]]
    llm_summary: str | None
    llm_action_items: list[str] = Field(default_factory=list)
    llm_error: str | None


class ReportListResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int


class DeleteReportResponse(BaseModel):
    ok: bool
    report_id: str


class DeleteSessionResponse(BaseModel):
    ok: bool
    session_id: str


class ResumeSessionResponse(BaseModel):
    session_id: str
    current_step: int
    session_status: str
    thought_record: dict[str, Any]
    chat_history: list[dict[str, Any]]
    conversation_llm: dict[str, Any] = Field(default_factory=dict)
    can_undo: bool = False
    undo_count: int = 0
    undo_limit: int = 3


class AppSettings(BaseModel):
    llm_provider: str
    llm_url: str
    llm_model: str
    api_key_env_var: str
    sessions_dir: str
    reports_dir: str
    user_context: str = ""


class AppSettingsUpdate(BaseModel):
    llm_provider: str | None = None
    llm_url: str | None = None
    llm_model: str | None = None
    api_key_env_var: str | None = None
    sessions_dir: str | None = None
    reports_dir: str | None = None
    user_context: str | None = None


def _agent_from_session_data(session_data: dict[str, Any], session_id: str, *, use_saved_llm: bool = True) -> CBTAgent:
    llm_meta = session_data.get("conversation_llm") or {}
    agent = CBTAgent(
        step=int(session_data.get("current_step") or 1),
        initial_record=session_data.get("thought_record") or None,
        model=llm_meta.get("model") if use_saved_llm else None,
        url=llm_meta.get("url") if use_saved_llm else None,
        llm_provider=llm_meta.get("provider") if use_saved_llm else None,
        api_key_env_var=llm_meta.get("api_key_env_var") if use_saved_llm else None,
        user_context=session_data.get("user_context") or "",
    )
    agent.session_id = str(session_data.get("session_id") or session_id)
    agent.chat_history = list(session_data.get("chat_history") or [])
    agent.turns = list(session_data.get("turns") or [])
    agent.session_status = str(session_data.get("session_status") or "in_progress")
    agent.safety_state = str(session_data.get("safety_state") or "normal")
    agent.safety_reason = session_data.get("safety_reason")
    agent.last_safety_warning_turn = int(session_data.get("last_safety_warning_turn") or 0)
    agent.undo_stack = list(session_data.get("undo_stack") or [])
    return agent


def _session_id_exists(session_id: str) -> bool:
    if session_id in _agents:
        return True
    try:
        report_service.load_session(session_id)
    except FileNotFoundError:
        return False
    return True


def _ensure_unique_session_id(agent: CBTAgent) -> None:
    base_id = agent.session_id
    suffix = 2
    while _session_id_exists(agent.session_id):
        agent.session_id = f"{base_id}_{suffix}"
        suffix += 1


def _get_or_restore_in_progress_agent(session_id: str) -> CBTAgent | None:
    agent = _agents.get(session_id)
    if agent is not None:
        return agent

    try:
        session_data = report_service.load_session(session_id)
    except FileNotFoundError:
        return None

    if session_data.get("session_status") != "in_progress":
        return None

    app_settings.load_settings()
    agent = _agent_from_session_data(session_data, session_id, use_saved_llm=False)
    _agents[agent.session_id] = agent
    return agent


def _finalize_if_ready(agent: CBTAgent) -> bool:
    global _active_session_id
    if agent.session_status != "in_progress":
        return False
    if agent.current_step < 7 or not agent.is_ready_for_final_summary():
        return False

    summary = agent.finalize_session()
    if not agent.chat_history or agent.chat_history[-1].get("content") != summary:
        agent.chat_history.append({"role": "assistant", "content": summary})
    agent.save_session()
    _completed_sessions.add(agent.session_id)
    if _active_session_id == agent.session_id:
        _active_session_id = None
    return True


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/settings", response_model=AppSettings)
def get_settings() -> AppSettings:
    return AppSettings(**app_settings.load_settings())


@app.get("/api/distortions")
def list_distortions() -> dict[str, Any]:
    return {"items": DistortionKnowledge.get_distortion_items()}


@app.put("/api/settings", response_model=AppSettings)
def update_settings(req: AppSettingsUpdate) -> AppSettings:
    return AppSettings(**app_settings.save_settings(req.model_dump(exclude_none=True)))


@app.post("/api/start", response_model=StartResponse)
def start() -> StartResponse:
    global _active_session_id
    settings = app_settings.load_settings()
    agent = CBTAgent(step=1, user_context=settings.get("user_context") or "")
    _ensure_unique_session_id(agent)
    first_msg = agent.respond(None)
    agent.chat_history.append({"role": "assistant", "content": first_msg})
    _agents[agent.session_id] = agent
    _active_session_id = agent.session_id

    return StartResponse(
        session_id=agent.session_id,
        message=first_msg,
        current_step=agent.current_step,
        thought_record=agent.thought_record,
    )


@app.post("/api/message", response_model=MessageResponse)
def message(req: MessageRequest) -> MessageResponse:
    agent = _get_or_restore_in_progress_agent(req.session_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Unknown session_id")
    if agent.session_status != "in_progress":
        raise HTTPException(status_code=409, detail="This session is already closed.")

    result = agent.process_user_turn(req.message)
    session_completed = result["session_completed"]
    record_url = f"/reports/session/{agent.session_id}" if agent.session_status == "completed" else None

    if session_completed:
        global _active_session_id
        _completed_sessions.add(agent.session_id)
        if _active_session_id == agent.session_id:
            _active_session_id = None

    return MessageResponse(
        session_id=agent.session_id,
        message=result["message"],
        current_step=agent.current_step,
        step_completed=result["step_completed"],
        session_completed=session_completed,
        record_url=record_url,
        thought_record=agent.thought_record,
        can_undo=agent.can_undo(),
        undo_count=agent.undo_count(),
        undo_limit=agent.UNDO_LIMIT,
    )


@app.get("/api/report-sessions")
def report_sessions() -> dict[str, Any]:
    items = report_service.list_completed_sessions()
    return {"items": items, "total": len(items)}


@app.get("/api/sessions")
def list_sessions() -> dict[str, Any]:
    app_settings.load_settings()
    items: list[dict[str, Any]] = []
    for session_data in reversed(report_service.load_all_sessions()):
        if session_data.get("session_status") == "in_progress" and int(session_data.get("current_step") or 1) >= 7:
            agent = _agents.get(str(session_data.get("session_id") or ""))
            if agent is None:
                agent = _agent_from_session_data(session_data, str(session_data.get("session_id") or ""))
                _agents[agent.session_id] = agent
            if _finalize_if_ready(agent):
                session_data = report_service.load_session(agent.session_id)

        has_user_input = any((msg.get("role") == "user" and str(msg.get("content") or "").strip()) for msg in session_data.get("chat_history") or [])
        if not has_user_input and not session_data.get("turns"):
            continue
        record = session_data.get("thought_record") or {}
        items.append(
            {
                "session_id": str(session_data.get("session_id") or ""),
                "last_updated": session_data.get("last_updated"),
                "current_step": session_data.get("current_step"),
                "session_status": session_data.get("session_status"),
                "conversation_llm": session_data.get("conversation_llm") or {},
                "date": record.get("date"),
                "emotion": record.get("emotion") or None,
                "situation": record.get("situation") or None,
                "automatic_thought": record.get("automatic_thought") or None,
                "intensity_before": record.get("intensity_before"),
                "intensity_after": record.get("intensity_after"),
                "distortions": list(record.get("distortions") or []),
                "balanced_thought": record.get("balanced_thought") or None,
            }
        )
    return {"items": items, "total": len(items)}


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    app_settings.load_settings()
    try:
        return report_service.load_session(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found.") from exc


@app.post("/api/sessions/{session_id}/undo", response_model=ResumeSessionResponse)
def undo_last_input(session_id: str) -> ResumeSessionResponse:
    global _active_session_id
    app_settings.load_settings()
    agent = _get_or_restore_in_progress_agent(session_id)
    if agent is None:
        try:
            session_data = report_service.load_session(session_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        agent = _agent_from_session_data(session_data, session_id)

    if not agent.undo_last_turn():
        raise HTTPException(status_code=409, detail="There is no previous input to undo for this session.")

    _agents[agent.session_id] = agent
    if agent.session_status == "in_progress":
        _active_session_id = agent.session_id
    elif _active_session_id == agent.session_id:
        _active_session_id = None

    return ResumeSessionResponse(
        session_id=agent.session_id,
        current_step=agent.current_step,
        session_status=agent.session_status,
        thought_record=agent.thought_record,
        chat_history=agent.chat_history,
        conversation_llm={
            "provider": agent.llm_provider,
            "model": agent.model,
            "url": agent.url,
            "api_key_env_var": agent.api_key_env_var,
        },
        can_undo=agent.can_undo(),
        undo_count=agent.undo_count(),
        undo_limit=agent.UNDO_LIMIT,
    )


@app.post("/api/sessions/{session_id}/resume", response_model=ResumeSessionResponse)
def resume_session(session_id: str) -> ResumeSessionResponse:
    global _active_session_id
    app_settings.load_settings()
    try:
        session_data = report_service.load_session(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found.") from exc

    if session_data.get("session_status") != "in_progress":
        raise HTTPException(status_code=409, detail="Only in-progress sessions can be resumed.")

    agent = _agent_from_session_data(session_data, session_id, use_saved_llm=False)

    _agents[agent.session_id] = agent
    if _finalize_if_ready(agent):
        _active_session_id = None
    else:
        _active_session_id = agent.session_id

    return ResumeSessionResponse(
        session_id=agent.session_id,
        current_step=agent.current_step,
        session_status=agent.session_status,
        thought_record=agent.thought_record,
        chat_history=agent.chat_history,
        conversation_llm={
            "provider": agent.llm_provider,
            "model": agent.model,
            "url": agent.url,
            "api_key_env_var": agent.api_key_env_var,
        },
        can_undo=agent.can_undo(),
        undo_count=agent.undo_count(),
        undo_limit=agent.UNDO_LIMIT,
    )


@app.delete("/api/sessions/{session_id}", response_model=DeleteSessionResponse)
def delete_session(session_id: str) -> DeleteSessionResponse:
    global _active_session_id
    try:
        report_service.delete_session(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found.") from exc

    _agents.pop(session_id, None)
    _completed_sessions.discard(session_id)
    if _active_session_id == session_id:
        _active_session_id = None
    return DeleteSessionResponse(ok=True, session_id=session_id)


@app.post("/api/reports/generate", response_model=GenerateReportResponse)
def generate_report(req: GenerateReportRequest) -> GenerateReportResponse:
    mode = (req.mode or "recent").strip().lower()
    if mode not in {"single", "recent", "custom"}:
        raise HTTPException(status_code=400, detail="mode must be 'single', 'recent' or 'custom'")
    if mode in {"single", "custom"} and not req.session_ids:
        raise HTTPException(status_code=400, detail="session_ids is required for this mode")

    try:
        settings = app_settings.load_settings()
        report = report_service.generate_report(
            mode=mode,
            limit=req.limit,
            session_ids=req.session_ids,
            include_llm_summary=req.include_llm_summary,
            user_context=settings.get("user_context") or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return GenerateReportResponse(
        report_id=report["report_id"],
        report_url=f"/api/reports/{report['report_id']}",
        generated_at=report["generated_at"],
        scope=report["scope"],
        metrics=report["metrics"],
        sessions=report["sessions"],
        llm_summary=report.get("llm_summary"),
        llm_action_items=list(report.get("llm_action_items") or []),
        llm_error=report.get("llm_error"),
    )


@app.get("/api/reports", response_model=ReportListResponse)
def list_reports() -> ReportListResponse:
    items = report_service.list_reports()
    return ReportListResponse(items=items, total=len(items))


@app.post("/api/reports/save")
def save_report(report: dict[str, Any]) -> dict[str, Any]:
    if not report.get("sessions"):
        raise HTTPException(status_code=400, detail="Report data is missing sessions.")
    try:
        report_service.save_report(report)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail="Invalid report id.") from exc
    return report


@app.get("/api/reports/session/{session_id}")
def single_session_report(session_id: str) -> dict[str, Any]:
    try:
        settings = app_settings.load_settings()
        return report_service.generate_report(
            mode="single",
            session_ids=[session_id],
            include_llm_summary=True,
            user_context=settings.get("user_context") or "",
            persist=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Session not found or not completed.") from exc


@app.get("/api/reports/multi")
def multi_session_report(
    mode: str = Query(default="recent"),
    limit: int = Query(default=5, ge=1, le=50),
    session_ids: str | None = Query(default=None),
) -> dict[str, Any]:
    normalized_mode = (mode or "recent").strip().lower()
    if normalized_mode not in {"recent", "custom"}:
        raise HTTPException(status_code=400, detail="mode must be 'recent' or 'custom'")

    selected_ids = None
    if normalized_mode == "custom":
        selected_ids = [item.strip() for item in (session_ids or "").split(",") if item.strip()]
        if not selected_ids:
            raise HTTPException(status_code=400, detail="session_ids is required when mode=custom")

    try:
        settings = app_settings.load_settings()
        return report_service.generate_report(
            mode=normalized_mode,
            limit=limit,
            session_ids=selected_ids,
            include_llm_summary=True,
            user_context=settings.get("user_context") or "",
            persist=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/reports/{report_id}")
def get_report(report_id: str) -> dict[str, Any]:
    try:
        return report_service.load_report(report_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Report not found.") from exc


@app.delete("/api/reports/{report_id}", response_model=DeleteReportResponse)
def delete_report(report_id: str) -> DeleteReportResponse:
    try:
        report_service.delete_report(report_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Report not found.") from exc
    return DeleteReportResponse(ok=True, report_id=report_id)


if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    def _frontend_index() -> FileResponse:
        return FileResponse(
            FRONTEND_DIST / "index.html",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")

        requested_file = FRONTEND_DIST / full_path
        if requested_file == FRONTEND_DIST / "index.html":
            return _frontend_index()
        if requested_file.is_file():
            return FileResponse(requested_file)

        return _frontend_index()
