from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agent import CBTAgent
from backend import report_service

app = FastAPI(title="TRA Test API")

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
    llm_error: str | None


class ReportListResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/start", response_model=StartResponse)
def start() -> StartResponse:
    global _active_session_id
    if (
        _active_session_id is not None
        and _active_session_id in _agents
        and _active_session_id not in _completed_sessions
    ):
        raise HTTPException(
            status_code=409,
            detail="A session is already in progress. Finish it before starting a new one.",
        )

    agent = CBTAgent(step=1)
    first_msg = agent.respond(None)
    agent.chat_history.append({"role": "assistant", "content": first_msg})
    agent.save_session()
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
    agent = _agents.get(req.session_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Unknown session_id")
    if req.session_id in _completed_sessions:
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
    )


@app.get("/api/report-sessions")
def report_sessions() -> dict[str, Any]:
    items = report_service.list_completed_sessions()
    return {"items": items, "total": len(items)}


@app.post("/api/reports/generate", response_model=GenerateReportResponse)
def generate_report(req: GenerateReportRequest) -> GenerateReportResponse:
    mode = (req.mode or "recent").strip().lower()
    if mode not in {"single", "recent", "custom"}:
        raise HTTPException(status_code=400, detail="mode must be 'single', 'recent' or 'custom'")
    if mode in {"single", "custom"} and not req.session_ids:
        raise HTTPException(status_code=400, detail="session_ids is required for this mode")

    try:
        report = report_service.generate_report(
            mode=mode,
            limit=req.limit,
            session_ids=req.session_ids,
            include_llm_summary=req.include_llm_summary,
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
        llm_error=report.get("llm_error"),
    )


@app.get("/api/reports", response_model=ReportListResponse)
def list_reports() -> ReportListResponse:
    items = report_service.list_reports()
    return ReportListResponse(items=items, total=len(items))


@app.get("/api/reports/session/{session_id}")
def single_session_report(session_id: str) -> dict[str, Any]:
    try:
        return report_service.generate_report(mode="single", session_ids=[session_id], persist=False)
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
        return report_service.generate_report(
            mode=normalized_mode,
            limit=limit,
            session_ids=selected_ids,
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
