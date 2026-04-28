from __future__ import annotations

import html
import os
import sys
from pathlib import Path
import json
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from agent import CBTAgent
import report_service

app = FastAPI()
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
    session_ids: list[str] = []
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


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CBT Thought Record Chat</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 0; background: #0b1220; color: #e7eefc; }
    .wrap { max-width: 900px; margin: 0 auto; padding: 24px; }
    .top { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .title { font-size: 18px; font-weight: 650; }
    .meta { font-size: 12px; opacity: .8; }
    .hidden { display: none; }
    .panel { margin-top: 16px; display: grid; grid-template-columns: 1fr 320px; gap: 16px; }
    .chat { background: #0f1a30; border: 1px solid #1e2b47; border-radius: 12px; padding: 12px; height: 70vh; display: flex; flex-direction: column; }
    .log { flex: 1; overflow: auto; padding: 8px; }
    .msg { margin: 10px 0; display: flex; }
    .msg.user { justify-content: flex-end; }
    .bubble { max-width: 78%; padding: 10px 12px; border-radius: 12px; line-height: 1.4; white-space: pre-wrap; }
    .msg.user .bubble { background: #2b67ff; color: white; border-bottom-right-radius: 4px; }
    .msg.assistant .bubble { background: #182544; border: 1px solid #24355a; border-bottom-left-radius: 4px; }
    .composer { display: flex; gap: 8px; padding: 8px; border-top: 1px solid #1e2b47; }
    input[type="text"] { flex: 1; padding: 12px 12px; border-radius: 10px; border: 1px solid #2a3b63; background: #0b1326; color: #e7eefc; outline: none; }
    button { padding: 12px 14px; border-radius: 10px; border: 1px solid #2a3b63; background: #122046; color: #e7eefc; cursor: pointer; }
    button:hover { background: #172a5a; }
    button.primary { background: #2b67ff; border-color: #2b67ff; color: white; }
    button.primary:hover { background: #2459da; border-color: #2459da; }
    button:disabled { opacity: .55; cursor: not-allowed; }
    .side { background: #0f1a30; border: 1px solid #1e2b47; border-radius: 12px; padding: 12px; height: 70vh; overflow: auto; }
    pre { margin: 0; font-size: 12px; white-space: pre-wrap; word-break: break-word; }
    @media (max-width: 900px) {
      .panel { grid-template-columns: 1fr; }
      .side { height: auto; }
      .chat { height: 65vh; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div>
        <div class="title">CBT Thought Record Chat</div>
        <div class="meta" id="meta">Session: (not started)</div>
      </div>
      <div style="display:flex; gap:8px;">
        <button id="newBtn">New Session</button>
        <a id="reportsBtn" href="/reports" style="padding:12px 14px; border-radius:10px; border:1px solid #2a3b63; background:#122046; color:#e7eefc; cursor:pointer; text-decoration:none; display:inline-flex; align-items:center;">View Reports</a>
        <button id="viewBtn" class="primary hidden">View Thought Record</button>
      </div>
    </div>

    <div id="startScreen" style="margin-top:16px; padding:16px; background:#0f1a30; border:1px solid #1e2b47; border-radius:12px;">
      <div style="font-size:14px; opacity:.9; line-height:1.5;">
        Choose what you want to do next.
      </div>
      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:12px; margin-top:16px;">
        <div style="padding:16px; background:#13203a; border:1px solid #24355a; border-radius:12px;">
          <div style="font-size:16px; font-weight:650;">Start Thought Record</div>
          <div style="font-size:13px; opacity:.82; line-height:1.5; margin-top:8px;">
            Begin a guided CBT thought record and save the completed session automatically.
          </div>
          <div style="margin-top:14px;">
            <button id="startBtn" class="primary">New Session</button>
          </div>
        </div>
        <div style="padding:16px; background:#13203a; border:1px solid #24355a; border-radius:12px;">
          <div style="font-size:16px; font-weight:650;">View Reports</div>
          <div style="font-size:13px; opacity:.82; line-height:1.5; margin-top:8px;">
            Review single-session and multi-session reports generated directly from completed sessions.
          </div>
          <div style="margin-top:14px;">
            <a href="/reports" style="padding:12px 14px; border-radius:10px; border:1px solid #2a3b63; background:#122046; color:#e7eefc; text-decoration:none; display:inline-flex; align-items:center;">Open Reports</a>
          </div>
        </div>
      </div>
    </div>

    <div class="panel hidden" id="chatPanel">
      <div class="chat">
        <div class="log" id="log"></div>
        <div class="composer">
          <input id="input" type="text" placeholder="Type your message..." autocomplete="off" />
          <button class="primary" id="sendBtn">Send</button>
        </div>
      </div>

      <div class="side">
        <div class="meta" style="margin-bottom:8px;">thought_record</div>
        <pre id="record">{}</pre>
      </div>
    </div>
  </div>

<script>
  let sessionId = null;
  let currentStep = null;
  let sessionCompleted = false;
  let recordUrl = null;
  const logEl = document.getElementById('log');
  const inputEl = document.getElementById('input');
  const sendBtn = document.getElementById('sendBtn');
  const newBtn = document.getElementById('newBtn');
  const startBtn = document.getElementById('startBtn');
  const viewBtn = document.getElementById('viewBtn');
  const startScreen = document.getElementById('startScreen');
  const chatPanel = document.getElementById('chatPanel');
  const recordEl = document.getElementById('record');
  const metaEl = document.getElementById('meta');

  function addMsg(role, text) {
    const row = document.createElement('div');
    row.className = 'msg ' + role;
    const b = document.createElement('div');
    b.className = 'bubble';
    b.textContent = text;
    row.appendChild(b);
    logEl.appendChild(row);
    logEl.scrollTop = logEl.scrollHeight;
  }

  function setRecord(obj) {
    recordEl.textContent = JSON.stringify(obj, null, 2);
  }

  function setMeta() {
    metaEl.textContent = sessionId ? `Session: ${sessionId} | Step: ${currentStep}` : 'Session: (not started)';
  }

  function setUiState() {
    const hasSession = !!sessionId;
    startScreen.classList.toggle('hidden', hasSession);
    chatPanel.classList.toggle('hidden', !hasSession);
    sendBtn.disabled = !hasSession || sessionCompleted;
    inputEl.disabled = !hasSession || sessionCompleted;
    newBtn.disabled = hasSession && !sessionCompleted;
    startBtn.disabled = hasSession && !sessionCompleted;
    viewBtn.classList.toggle('hidden', !sessionCompleted || !recordUrl);
    setMeta();
  }

  async function startSession() {
    if (sessionId && !sessionCompleted) return;
    logEl.innerHTML = '';
    setRecord({});
    sessionId = null;
    currentStep = null;
    sessionCompleted = false;
    recordUrl = null;
    setMeta();
    setUiState();

    const res = await fetch('/api/start', { method: 'POST' });
    if (!res.ok) {
      const msg = await res.text();
      addMsg('assistant', msg || 'Failed to start session.');
      return;
    }
    const data = await res.json();
    sessionId = data.session_id;
    currentStep = data.current_step;
    setMeta();
    setRecord(data.thought_record);
    addMsg('assistant', data.message);
    setUiState();
  }

  async function sendMessage() {
    const text = inputEl.value.trim();
    if (!text || !sessionId || sessionCompleted) return;
    inputEl.value = '';
    addMsg('user', text);

    const res = await fetch('/api/message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, message: text })
    });
    if (!res.ok) {
      addMsg('assistant', 'Error processing message.');
      return;
    }
    const data = await res.json();
    currentStep = data.current_step;
    sessionCompleted = data.session_completed;
    recordUrl = data.record_url;
    setMeta();
    setRecord(data.thought_record);
    addMsg('assistant', data.message);
    setUiState();
  }

  sendBtn.addEventListener('click', sendMessage);
  newBtn.addEventListener('click', startSession);
  startBtn.addEventListener('click', startSession);
  viewBtn.addEventListener('click', () => {
    if (!recordUrl) return;
    window.location.href = recordUrl;
  });
  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendMessage();
  });

  setUiState();
</script>
</body>
</html>"""


@app.post("/api/start", response_model=StartResponse)
def start() -> StartResponse:
    global _active_session_id
    if _active_session_id is not None and _active_session_id in _agents and _active_session_id not in _completed_sessions:
        raise HTTPException(status_code=409, detail="A session is already in progress. Finish it before starting a new one.")
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
    assistant_msg = result["message"]
    step_completed = result["step_completed"]
    session_completed = result["session_completed"]
    record_url = f"/record/{agent.session_id}" if agent.session_status == "completed" else None
    if session_completed:
        global _active_session_id
        _completed_sessions.add(agent.session_id)
        if _active_session_id == agent.session_id:
            _active_session_id = None

    return MessageResponse(
        session_id=agent.session_id,
        message=assistant_msg,
        current_step=agent.current_step,
        step_completed=step_completed,
        session_completed=session_completed,
        record_url=record_url,
        thought_record=agent.thought_record,
    )


@app.get("/record/{session_id}", response_class=HTMLResponse)
def record_page(session_id: str) -> str:
    agent = _agents.get(session_id)
    if agent is None:
        p = Path(config.SESSIONS_DIR) / f"session_{session_id}.json"
        if not p.exists():
            raise HTTPException(status_code=404, detail="Session not found.")
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("session_status") != "completed":
            raise HTTPException(status_code=403, detail="Session not completed.")
        record = data.get("thought_record", {})
    else:
        if agent.session_status != "completed":
            raise HTTPException(status_code=403, detail="Session not completed.")
        record = agent.thought_record

    def fmt(v: Any) -> str:
        if isinstance(v, list):
            return "<br/>".join([str(x) for x in v])
        return str(v)

    rows = []
    for k in [
        "date",
        "situation",
        "emotion",
        "intensity_before",
        "automatic_thought",
        "evidence_for",
        "evidence_against",
        "distortions",
        "balanced_thought",
        "intensity_after",
        "summary",
    ]:
        if k in record:
            rows.append(f"<tr><td>{k}</td><td>{fmt(record.get(k))}</td></tr>")

    table_rows = "\n".join(rows)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Thought Record</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 0; background: #0b1220; color: #e7eefc; }}
    .wrap {{ max-width: 900px; margin: 0 auto; padding: 24px; }}
    .top {{ display:flex; align-items:center; justify-content:space-between; gap:12px; }}
    a {{ color:#9bb7ff; text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 16px; background:#0f1a30; border: 1px solid #1e2b47; border-radius: 12px; overflow: hidden; }}
    td {{ padding: 12px; border-bottom: 1px solid #1e2b47; vertical-align: top; }}
    td:first-child {{ width: 220px; opacity: .85; }}
    tr:last-child td {{ border-bottom: none; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div>
        <div style="font-size:18px; font-weight:650;">Thought Record</div>
        <div style="font-size:12px; opacity:.8;">Session: {session_id}</div>
      </div>
      <div><a href="/">Back to Chat</a></div>
    </div>
    <table>
      {table_rows}
    </table>
  </div>
</body>
</html>"""


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
        raise HTTPException(status_code=400, detail="session_ids is required for custom mode")

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
        report_url=f"/reports/{report['report_id']}",
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


@app.get("/api/reports/{report_id}")
def get_report(report_id: str) -> dict[str, Any]:
    try:
        return report_service.load_report(report_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Report not found.") from exc


def _render_report_page(report: dict[str, Any]) -> str:
    scope = report.get("scope") or {}
    metrics = report.get("metrics") or {}
    sessions = report.get("sessions") or []
    report_type = scope.get("report_type") or "multi_session"
    report_id = report.get("report_id")

    def esc(value: Any) -> str:
        return html.escape("" if value is None else str(value))

    def reduction_value(delta: Any) -> int | None:
        if isinstance(delta, (int, float)):
            if delta < 0:
                return int(abs(delta))
            if delta > 0:
                return -int(delta)
            return 0
        return None

    def change_text(delta: Any) -> str:
        value = reduction_value(delta)
        if value is None:
            return "Change unavailable"
        if value > 0:
            return f"Reduced by {value} points"
        if value < 0:
            return f"Increased by {abs(value)} points"
        return "No change"

    def render_lines(items: list[str]) -> str:
        if not items:
            return "<li>None</li>"
        return "".join(f"<li>{esc(item)}</li>" for item in items)

    def render_distribution(items: list[dict[str, Any]]) -> str:
        if not items:
            return "<li>None</li>"
        return "".join(
            f"<li><strong>{esc(item.get('label'))}</strong>: {esc(item.get('count'))}</li>"
            for item in items
        )

    if report_type == "single_session":
        item = sessions[0] if sessions else {}
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Session Report {esc(item.get("session_id"))}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 0; background: #0b1220; color: #e7eefc; }}
    .wrap {{ max-width: 920px; margin: 0 auto; padding: 24px; }}
    .top {{ display:flex; align-items:flex-start; justify-content:space-between; gap:12px; }}
    .panel {{ margin-top: 16px; background:#0f1a30; border:1px solid #1e2b47; border-radius: 12px; padding: 16px; }}
    .grid {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 16px; }}
    .stat {{ background:#13203a; border:1px solid #24355a; border-radius: 10px; padding: 12px; }}
    .label {{ font-size: 12px; opacity: .8; }}
    .value {{ font-size: 24px; font-weight: 650; margin-top: 4px; }}
    .card-title {{ font-size: 15px; font-weight: 650; margin-bottom: 8px; }}
    .muted {{ font-size: 12px; opacity: .8; margin-top: 4px; }}
    a {{ color:#9bb7ff; text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    ul {{ margin: 8px 0 0 18px; }}
    p {{ line-height: 1.6; white-space: pre-wrap; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div>
        <div style="font-size:22px; font-weight:700;">Single Session Report</div>
        <div class="muted">Session: {esc(item.get("session_id"))}</div>
        <div class="muted">Generated at: {esc(report.get("generated_at"))}</div>
      </div>
      <div><a href="/reports">Back to Reports</a></div>
    </div>

    <div class="grid">
      <div class="stat">
        <div class="label">Date</div>
        <div class="muted">{esc(item.get("date"))}</div>
      </div>
      <div class="stat">
        <div class="label">Emotion</div>
        <div class="value">{esc(item.get("emotion"))}</div>
      </div>
      <div class="stat">
        <div class="label">Before</div>
        <div class="value">{esc(metrics.get("intensity_before"))}</div>
      </div>
      <div class="stat">
        <div class="label">After</div>
        <div class="value">{esc(metrics.get("intensity_after"))}</div>
      </div>
      <div class="stat">
        <div class="label">Change</div>
        <div class="muted">{esc(change_text(metrics.get("intensity_delta")))}</div>
      </div>
    </div>

    <div class="panel">
      <div class="card-title">Situation</div>
      <p>{esc(item.get("situation"))}</p>
    </div>

    <div class="panel">
      <div class="card-title">Automatic Thought</div>
      <p>{esc(item.get("automatic_thought"))}</p>
    </div>

    <div class="panel">
      <div class="card-title">Evidence For</div>
      <ul>{render_lines(item.get("evidence_for") or [])}</ul>
    </div>

    <div class="panel">
      <div class="card-title">Evidence Against</div>
      <ul>{render_lines(item.get("evidence_against") or [])}</ul>
    </div>

    <div class="panel">
      <div class="card-title">Distortions</div>
      <ul>{render_lines(item.get("distortions") or [])}</ul>
    </div>

    <div class="panel">
      <div class="card-title">Balanced Thought</div>
      <p>{esc(item.get("balanced_thought"))}</p>
    </div>

    <div class="panel">
      <div class="card-title">Summary</div>
      <p>{esc(item.get("summary"))}</p>
    </div>
  </div>
</body>
</html>"""

    def render_sessions(items: list[dict[str, Any]]) -> str:
        if not items:
            return "<p>No sessions included.</p>"
        cards = []
        for item in items:
            distortions = ", ".join(item.get("distortions") or []) or "None"
            cards.append(
                f"""
                <a class="card card-link" href="{esc(item.get("session_report_url"))}">
                  <div class="card-title">Session {esc(item.get("session_id"))}</div>
                  <div class="muted">{esc(item.get("date"))} | emotion: {esc(item.get("emotion"))}</div>
                  <div><strong>Intensity</strong>: {esc(item.get("intensity_before"))} -> {esc(item.get("intensity_after"))}</div>
                  <div><strong>Change</strong>: {esc(change_text(item.get("intensity_delta")))}</div>
                  <div><strong>Distortions</strong>: {esc(distortions)}</div>
                  <div><strong>Balanced thought</strong>: {esc(item.get("balanced_thought"))}</div>
                </a>
                """
            )
        return "\n".join(cards)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Report {esc(report_id)}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 0; background: #0b1220; color: #e7eefc; }}
    .wrap {{ max-width: 1000px; margin: 0 auto; padding: 24px; }}
    .top {{ display:flex; align-items:flex-start; justify-content:space-between; gap:12px; }}
    .grid {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 16px; }}
    .panel {{ margin-top: 16px; background:#0f1a30; border:1px solid #1e2b47; border-radius: 12px; padding: 16px; }}
    .card {{ background:#13203a; border:1px solid #24355a; border-radius: 10px; padding: 12px; margin-top: 12px; }}
    .card-link {{ display:block; color:inherit; text-decoration:none; }}
    .card-link:hover {{ border-color:#4c7bff; background:#17274a; text-decoration:none; }}
    .stat {{ background:#13203a; border:1px solid #24355a; border-radius: 10px; padding: 12px; }}
    .label {{ font-size: 12px; opacity: .8; }}
    .value {{ font-size: 24px; font-weight: 650; margin-top: 4px; }}
    .muted {{ font-size: 12px; opacity: .8; margin-top: 4px; }}
    .card-title {{ font-size: 15px; font-weight: 650; margin-bottom: 6px; }}
    a {{ color:#9bb7ff; text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    ul {{ margin: 8px 0 0 18px; }}
    pre {{ white-space: pre-wrap; line-height: 1.5; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div>
        <div style="font-size:22px; font-weight:700;">Saved Report</div>
        <div class="muted">Report ID: {esc(report.get("report_id"))}</div>
        <div class="muted">Generated at: {esc(report.get("generated_at"))}</div>
      </div>
      <div><a href="/reports">Back to Reports</a></div>
    </div>

    <div class="panel">
      <div class="card-title">Scope</div>
      <div class="muted">Mode: {esc(scope.get("mode"))}</div>
      <div class="muted">Sessions included: {esc(len(sessions))}</div>
      <div class="muted">Date range: {esc((scope.get("date_range") or {}).get("start"))} to {esc((scope.get("date_range") or {}).get("end"))}</div>
    </div>

    <div class="grid">
      <div class="stat">
        <div class="label">Sessions In Scope</div>
        <div class="value">{esc(metrics.get("total_sessions_in_scope"))}</div>
      </div>
      <div class="stat">
        <div class="label">Improved Sessions</div>
        <div class="value">{esc(metrics.get("improved_sessions"))}</div>
        <div class="muted">out of {esc(metrics.get("total_sessions_in_scope"))}</div>
      </div>
      <div class="stat">
        <div class="label">Average Change</div>
        <div class="muted">{esc(change_text(metrics.get("average_intensity_delta")))}</div>
      </div>
    </div>

    <div class="panel">
      <div class="card-title">Common Distortions</div>
      <ul>{render_distribution(metrics.get("top_distortions") or [])}</ul>
    </div>

    <div class="panel">
      <div class="card-title">Common Emotions</div>
      <ul>{render_distribution(metrics.get("top_emotions") or [])}</ul>
    </div>

    <div class="panel">
      <div class="card-title">Sessions Included</div>
      {render_sessions(sessions)}
    </div>
  </div>
</body>
</html>"""


@app.get("/reports", response_class=HTMLResponse)
def reports_home_page() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Report Viewer</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 0; background: #0b1220; color: #e7eefc; }
    .wrap { max-width: 1040px; margin: 0 auto; padding: 24px; }
    .top { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; }
    .panel { margin-top: 16px; background:#0f1a30; border:1px solid #1e2b47; border-radius: 12px; padding: 16px; }
    .grid { display:grid; grid-template-columns: 280px 1fr; gap: 16px; margin-top: 16px; }
    .card { background:#13203a; border:1px solid #24355a; border-radius:10px; padding:12px; }
    .session { display:flex; gap:12px; align-items:flex-start; padding:12px; border:1px solid #24355a; border-radius:10px; background:#13203a; margin-top:12px; }
    .session:hover { border-color:#4c7bff; }
    .meta { font-size:12px; opacity:.8; margin-top:4px; }
    .title { font-size:22px; font-weight:700; }
    .section-title { font-size:15px; font-weight:650; margin-bottom:8px; }
    .controls { display:flex; gap:8px; flex-wrap:wrap; margin-top:12px; }
    .stack > * + * { margin-top: 10px; }
    input[type="number"] { width: 100%; box-sizing: border-box; padding: 10px 12px; border-radius: 10px; border: 1px solid #2a3b63; background: #0b1326; color: #e7eefc; }
    button, a.button { padding: 11px 14px; border-radius: 10px; border: 1px solid #2a3b63; background: #122046; color: #e7eefc; cursor: pointer; text-decoration:none; display:inline-block; }
    button:hover, a.button:hover { background: #172a5a; }
    button.primary { background: #2b67ff; border-color: #2b67ff; color: white; }
    button.primary:hover { background: #2459da; border-color: #2459da; }
    button:disabled { opacity:.55; cursor:not-allowed; }
    .hint { font-size:12px; opacity:.78; line-height:1.5; }
    .empty { opacity:.8; }
    @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div>
        <div class="title">Independent Report Viewer</div>
        <div class="meta">Reports here are generated directly from completed sessions.</div>
      </div>
      <div><a class="button" href="/">Back to Chat</a></div>
    </div>

    <div class="grid">
      <div class="stack">
        <div class="panel">
          <div class="section-title">Recent Report</div>
          <div class="hint">Open a report for the most recent completed sessions.</div>
          <div class="controls">
            <input id="recentLimit" type="number" min="1" max="50" value="3" />
            <button id="recentBtn" class="primary">Open Recent Report</button>
          </div>
        </div>

        <div class="panel">
          <div class="section-title">Custom Report</div>
          <div class="hint">Select two or more completed sessions, then open a combined report.</div>
          <div class="controls">
            <button id="customBtn" class="primary" disabled>Open Selected Sessions</button>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="section-title">Completed Sessions</div>
        <div id="sessionList" class="empty">Loading sessions...</div>
      </div>
    </div>
  </div>

<script>
  const sessionListEl = document.getElementById('sessionList');
  const customBtn = document.getElementById('customBtn');
  const recentBtn = document.getElementById('recentBtn');
  const recentLimitEl = document.getElementById('recentLimit');
  let sessions = [];

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text ?? '';
    return div.innerHTML;
  }

  function getSelectedIds() {
    return Array.from(document.querySelectorAll('input[name="sessionSelect"]:checked')).map(x => x.value);
  }

  function updateCustomButton() {
    const ids = getSelectedIds();
    customBtn.disabled = ids.length === 0;
    customBtn.textContent = ids.length > 0 ? `Open Selected Sessions (${ids.length})` : 'Open Selected Sessions';
  }

  function renderSessions() {
    if (!sessions.length) {
      sessionListEl.innerHTML = '<div class="empty">No completed sessions found.</div>';
      updateCustomButton();
      return;
    }

    sessionListEl.innerHTML = sessions.map(item => {
      const distortions = (item.distortions || []).join(', ') || 'None';
      return `
        <label class="session">
          <input type="checkbox" name="sessionSelect" value="${escapeHtml(item.session_id)}" />
          <div>
            <div><strong>${escapeHtml(item.session_id)}</strong></div>
            <div class="meta">${escapeHtml(item.date || 'N/A')} | emotion: ${escapeHtml(item.emotion || 'N/A')}</div>
            <div class="meta">Intensity: ${escapeHtml(String(item.intensity_before))} -> ${escapeHtml(String(item.intensity_after))} (delta ${escapeHtml(String(item.intensity_delta))})</div>
            <div class="meta">Distortions: ${escapeHtml(distortions)}</div>
            <div class="controls">
              <a class="button" href="/reports/session/${encodeURIComponent(item.session_id)}">View single report</a>
            </div>
          </div>
        </label>
      `;
    }).join('');

    document.querySelectorAll('input[name="sessionSelect"]').forEach(box => {
      box.addEventListener('change', updateCustomButton);
    });
    updateCustomButton();
  }

  async function loadSessions() {
    const res = await fetch('/api/report-sessions');
    if (!res.ok) {
      sessionListEl.innerHTML = '<div class="empty">Failed to load sessions.</div>';
      return;
    }
    const data = await res.json();
    sessions = data.items || [];
    renderSessions();
  }

  recentBtn.addEventListener('click', () => {
    const limit = Math.max(1, Math.min(50, Number(recentLimitEl.value) || 3));
    window.location.href = `/reports/multi?mode=recent&limit=${limit}`;
  });

  customBtn.addEventListener('click', () => {
    const ids = getSelectedIds();
    if (!ids.length) return;
    window.location.href = `/reports/multi?mode=custom&session_ids=${encodeURIComponent(ids.join(','))}`;
  });

  loadSessions();
</script>
</body>
</html>"""


@app.get("/reports/session/{session_id}", response_class=HTMLResponse)
def single_session_report_page(session_id: str) -> str:
    report = report_service.generate_report(mode="single", session_ids=[session_id], persist=False)
    return _render_report_page(report)


@app.get("/reports/multi", response_class=HTMLResponse)
def multi_session_report_page(
    mode: str = Query(default="recent"),
    limit: int = Query(default=5, ge=1, le=50),
    session_ids: str | None = Query(default=None),
) -> str:
    normalized_mode = (mode or "recent").strip().lower()
    if normalized_mode not in {"recent", "custom"}:
        raise HTTPException(status_code=400, detail="mode must be 'recent' or 'custom'")

    selected_ids = None
    if normalized_mode == "custom":
        selected_ids = [item.strip() for item in (session_ids or "").split(",") if item.strip()]
        if not selected_ids:
            raise HTTPException(status_code=400, detail="session_ids is required when mode=custom")

    try:
        report = report_service.generate_report(
            mode=normalized_mode,
            limit=limit,
            session_ids=selected_ids,
            persist=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _render_report_page(report)


@app.get("/reports/{report_id}", response_class=HTMLResponse)
def report_page(report_id: str) -> str:
    try:
        report = report_service.load_report(report_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Report not found.") from exc
    return _render_report_page(report)
