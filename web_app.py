from __future__ import annotations

import os
import sys
from pathlib import Path
import json
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from agent import CBTAgent

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
        <button id="viewBtn" class="primary hidden">View Thought Record</button>
      </div>
    </div>

    <div id="startScreen" style="margin-top:16px; padding:16px; background:#0f1a30; border:1px solid #1e2b47; border-radius:12px;">
      <div style="font-size:14px; opacity:.9; line-height:1.5;">
        Click <strong>New Session</strong> to start a guided CBT thought record. Your session will be saved automatically.
      </div>
      <div style="margin-top:12px;">
        <button id="startBtn" class="primary">New Session</button>
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
        raise HTTPException(status_code=409, detail="This session is already completed.")

    agent.chat_history.append({"role": "user", "content": req.message})
    prev_step = agent.current_step
    step_completed = agent.extract_and_fill(req.message)
    if step_completed:
        agent.current_step += 1
    assistant_msg = agent.respond(req.message, step_completed=step_completed, step_before=prev_step)
    agent.chat_history.append({"role": "assistant", "content": assistant_msg})
    agent.turns.append(
        {
            "step_before": prev_step,
            "step_after": agent.current_step,
            "user": req.message,
            "assistant": assistant_msg,
        }
    )
    agent.save_session()

    session_completed = agent.current_step == 7
    record_url = f"/record/{agent.session_id}" if session_completed else None
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
    if session_id not in _completed_sessions:
        raise HTTPException(status_code=403, detail="Session not completed.")
    agent = _agents.get(session_id)
    if agent is None:
        p = Path("sessions") / f"session_{session_id}.json"
        if not p.exists():
            raise HTTPException(status_code=404, detail="Session not found.")
        data = json.loads(p.read_text(encoding="utf-8"))
        record = data.get("thought_record", {})
    else:
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
        "predicted_distortion",
        "distortions",
        "balanced_thought",
        "intensity_after",
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

