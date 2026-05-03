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

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend import config
from backend.agent import CBTAgent
from backend import report_service

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
  <title>CBT Thought Record</title>
  <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@200;300;400;500;600;700;800&display=swap" rel="stylesheet" />
  <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
  <style>
    :root {
      --on-primary-fixed: #354339;
      --outline-variant: #9db6c1;
      --tertiary-container: #faf3e5;
      --surface-tint: #546257;
      --on-background: #1e363f;
      --on-surface-variant: #4b636d;
      --background: #f3fbff;
      --surface: #f3fbff;
      --surface-container-lowest: #ffffff;
      --surface-container-low: #e9f5fc;
      --surface-container: #e0f0f9;
      --surface-container-high: #d7ecf5;
      --surface-container-highest: #cde7f2;
      --primary: #546257;
      --primary-dim: #48564c;
      --primary-container: #d7e6d9;
      --on-primary: #ecfcee;
      --outline: #667e89;
      --tertiary: #635f54;
      --on-tertiary-container: #605b51;
      --secondary-container: #ffdbd0;
      --on-surface: #1e363f;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: 'Manrope', sans-serif;
      background: var(--background);
      color: var(--on-surface);
      selection-background-color: var(--primary-container);
    }
    a { color: inherit; }
    .material-symbols-outlined {
      font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
    }
    .page-shell {
      position: relative;
      min-height: 100vh;
      overflow: hidden;
    }
    .ambient-right,
    .ambient-left {
      position: fixed;
      border-radius: 9999px;
      filter: blur(120px);
      z-index: -1;
      pointer-events: none;
    }
    .ambient-right {
      top: 20%;
      right: -120px;
      width: 380px;
      height: 380px;
      background: rgba(84, 98, 87, 0.08);
    }
    .ambient-left {
      bottom: 16%;
      left: -120px;
      width: 420px;
      height: 420px;
      background: rgba(255, 219, 208, 0.18);
    }
    .nav {
      position: fixed;
      top: 0;
      width: 100%;
      z-index: 50;
      backdrop-filter: blur(20px);
      background: rgba(243, 251, 255, 0.82);
      box-shadow: 0 1px 0 rgba(157, 182, 193, 0.15);
    }
    .nav-inner,
    .wrap {
      width: min(1440px, calc(100% - 48px));
      margin: 0 auto;
    }
    .nav-inner {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 24px 0;
    }
    .brand {
      font-size: 1.25rem;
      font-weight: 800;
      letter-spacing: -0.03em;
      color: var(--on-background);
    }
    .nav-links {
      display: flex;
      align-items: center;
      gap: 32px;
      font-weight: 600;
      color: var(--on-surface-variant);
    }
    .nav-links a {
      text-decoration: none;
      transition: color .25s ease;
    }
    .nav-links a.active {
      color: var(--on-background);
      border-bottom: 2px solid var(--primary);
      padding-bottom: 4px;
    }
    .nav-actions {
      display: flex;
      align-items: center;
      gap: 16px;
      color: var(--primary);
    }
    .icon-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 40px;
      height: 40px;
      border-radius: 9999px;
      border: none;
      background: transparent;
      color: inherit;
    }
    .wrap {
      padding: 128px 0 96px;
    }
    .meta { font-size: 12px; color: var(--on-surface-variant); opacity: .9; }
    .hidden { display: none; }
    .welcome-hero {
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      margin-bottom: 72px;
    }
    .eyebrow {
      font-size: 12px;
      letter-spacing: .1em;
      text-transform: uppercase;
      color: var(--on-surface-variant);
      margin-bottom: 16px;
    }
    .hero-title {
      max-width: 820px;
      font-size: clamp(3rem, 8vw, 5.25rem);
      line-height: 1.08;
      font-weight: 300;
      letter-spacing: -0.05em;
      margin: 0 0 24px;
      color: var(--on-background);
    }
    .hero-copy {
      max-width: 660px;
      color: var(--on-surface-variant);
      font-size: 1.05rem;
      line-height: 1.7;
      margin-bottom: 32px;
    }
    .hero-actions {
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 14px;
    }
    .btn-primary,
    .btn-secondary,
    .reports-link,
    .nav-pill {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      border-radius: 14px;
      padding: 15px 22px;
      text-decoration: none;
      font-weight: 700;
      transition: transform .25s ease, box-shadow .25s ease, background .25s ease;
      cursor: pointer;
    }
    .btn-primary {
      border: none;
      color: var(--on-primary);
      background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dim) 100%);
      box-shadow: 0 16px 30px rgba(84, 98, 87, 0.16);
    }
    .btn-secondary,
    .reports-link {
      color: var(--on-background);
      background: rgba(255,255,255,0.55);
      border: 1px solid rgba(157, 182, 193, 0.3);
    }
    .btn-primary:hover,
    .btn-secondary:hover,
    .reports-link:hover {
      transform: translateY(-1px);
    }
    .feature-visual {
      position: relative;
      height: 380px;
      border-radius: 24px;
      overflow: hidden;
      background: var(--surface-container-low);
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 72px;
    }
    .feature-visual img {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      object-fit: cover;
      opacity: .58;
    }
    .feature-visual::after {
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(135deg, rgba(192,223,237,.55), rgba(243,251,255,.1));
    }
    .feature-content {
      position: relative;
      z-index: 1;
      max-width: 620px;
      padding: 32px;
      text-align: center;
    }
    .feature-quote {
      font-size: 1.2rem;
      line-height: 1.8;
      font-style: italic;
      color: var(--on-surface-variant);
    }
    .feature-line {
      width: 96px;
      height: 1px;
      margin: 28px auto 0;
      background: rgba(157, 182, 193, 0.4);
    }
    .records-grid {
      display: grid;
      grid-template-columns: 280px 1fr;
      gap: 48px;
      align-items: start;
    }
    .records-sidebar h2 {
      margin: 0 0 12px;
      font-size: 2rem;
      line-height: 1.1;
      letter-spacing: -0.04em;
    }
    .records-sidebar p {
      margin: 0 0 24px;
      font-size: .95rem;
      line-height: 1.7;
      color: var(--on-surface-variant);
    }
    .streak-card {
      padding: 24px;
      border-radius: 18px;
      background: rgba(233, 245, 252, 0.9);
    }
    .streak-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: .72rem;
      text-transform: uppercase;
      letter-spacing: .14em;
      font-weight: 800;
      color: rgba(75, 99, 109, 0.78);
      margin-bottom: 12px;
    }
    .streak-track {
      height: 4px;
      border-radius: 9999px;
      background: rgba(157, 182, 193, 0.24);
      overflow: hidden;
    }
    .streak-fill {
      height: 100%;
      width: 0%;
      background: var(--primary);
      border-radius: inherit;
    }
    .records-list {
      display: flex;
      flex-direction: column;
      gap: 20px;
    }
    .record-card {
      display: flex;
      gap: 24px;
      align-items: flex-start;
      padding: 28px;
      border-radius: 18px;
      text-decoration: none;
      color: inherit;
      background: rgba(255, 255, 255, 0.72);
      border: 1px solid rgba(157, 182, 193, 0.18);
      box-shadow: 0 18px 30px rgba(30, 54, 63, 0.04);
      transition: transform .25s ease, box-shadow .25s ease, border-color .25s ease;
    }
    .record-card:hover {
      transform: translateY(-2px);
      border-color: rgba(84, 98, 87, 0.24);
      box-shadow: 0 24px 36px rgba(30, 54, 63, 0.08);
    }
    .record-card.is-highlight {
      background: rgba(215, 236, 245, 0.9);
    }
    .record-icon {
      flex: 0 0 64px;
      width: 64px;
      height: 64px;
      border-radius: 9999px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      background: var(--surface-container);
      color: var(--primary);
    }
    .record-body {
      flex: 1;
      min-width: 0;
    }
    .record-top {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      margin-bottom: 10px;
    }
    .record-date {
      font-size: .72rem;
      text-transform: uppercase;
      letter-spacing: .14em;
      color: var(--on-surface-variant);
    }
    .record-tags {
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 8px;
    }
    .tag {
      padding: 7px 12px;
      border-radius: 9999px;
      font-size: .75rem;
      font-weight: 700;
      white-space: nowrap;
    }
    .tag-emotion {
      background: var(--tertiary-container);
      color: var(--on-tertiary-container);
    }
    .tag-metric {
      background: var(--surface-container-highest);
      color: var(--on-surface-variant);
    }
    .record-title {
      margin: 0 0 10px;
      font-size: 1.25rem;
      line-height: 1.35;
      font-weight: 700;
      letter-spacing: -0.03em;
    }
    .record-copy {
      margin: 0;
      color: var(--on-surface-variant);
      line-height: 1.7;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .record-arrow {
      align-self: center;
      color: var(--outline-variant);
    }
    .records-footer {
      padding-top: 12px;
      text-align: center;
    }
    .records-footer a {
      color: var(--primary);
      text-decoration: none;
      font-weight: 700;
    }
    .footer-note {
      margin-top: 88px;
      text-align: center;
    }
    .footer-pill {
      display: inline-block;
      padding: 14px 22px;
      border-radius: 9999px;
      background: rgba(233, 245, 252, 0.9);
      color: var(--on-surface-variant);
      font-size: .92rem;
      font-weight: 600;
    }
    .footer-icons {
      display: flex;
      justify-content: center;
      gap: 26px;
      margin-top: 26px;
      color: var(--outline);
    }
    .conversation-shell {
      display: flex;
      flex-direction: column;
      min-height: calc(100vh - 164px);
    }
    .conversation-header {
      margin-bottom: 28px;
      text-align: center;
    }
    .conversation-header .eyebrow {
      margin-bottom: 10px;
    }
    .conversation-title {
      margin: 0;
      font-size: clamp(2rem, 5vw, 3rem);
      font-weight: 700;
      letter-spacing: -0.05em;
      color: var(--on-background);
    }
    .conversation-copy {
      margin: 10px 0 0;
      color: var(--on-surface-variant);
      font-size: 1rem;
    }
    .session-meta-row {
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 10px;
      margin-top: 18px;
    }
    .session-chip {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 14px;
      border-radius: 9999px;
      background: rgba(233, 245, 252, 0.95);
      color: var(--on-surface-variant);
      font-size: .82rem;
      font-weight: 700;
    }
    .panel { margin-top: 8px; display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; align-items: start; }
    .chat {
      background: rgba(255,255,255,0.68);
      border: 1px solid rgba(157,182,193,.2);
      border-radius: 24px;
      padding: 18px;
      height: 68vh;
      display: flex;
      flex-direction: column;
      box-shadow: 0 22px 36px rgba(30, 54, 63, 0.05);
    }
    .log {
      flex: 1;
      overflow: auto;
      padding: 8px 6px 8px 0;
      display: flex;
      flex-direction: column;
      gap: 22px;
    }
    .msg { display: flex; align-items: flex-end; gap: 14px; }
    .msg.user { justify-content: flex-end; }
    .avatar {
      flex: 0 0 42px;
      width: 42px;
      height: 42px;
      border-radius: 9999px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }
    .avatar.assistant {
      background: var(--primary-container);
      color: var(--primary);
    }
    .avatar.user {
      background: var(--surface-container-low);
      color: var(--outline);
      order: 2;
    }
    .bubble-wrap {
      max-width: min(78%, 720px);
    }
    .bubble {
      padding: 18px 20px;
      border-radius: 18px;
      line-height: 1.7;
      white-space: pre-wrap;
      box-shadow: 0 8px 20px rgba(30, 54, 63, 0.03);
      font-size: 1rem;
    }
    .msg.user .bubble-wrap { order: 1; }
    .msg.user .bubble {
      background: var(--surface-container-highest);
      color: var(--on-surface);
      border-bottom-right-radius: 6px;
    }
    .msg.assistant .bubble {
      background: var(--primary-container);
      color: var(--on-primary-fixed);
      border: 1px solid rgba(157,182,193,.18);
      border-bottom-left-radius: 6px;
    }
    .timestamp {
      margin-top: 8px;
      font-size: .75rem;
      color: rgba(75, 99, 109, 0.72);
    }
    .msg.user .timestamp {
      text-align: right;
    }
    .composer-shell {
      position: sticky;
      bottom: 0;
      margin-top: 20px;
    }
    .focus-row {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      margin-bottom: 12px;
      padding: 0 4px;
    }
    .focus-label {
      font-size: .72rem;
      text-transform: uppercase;
      letter-spacing: .14em;
      font-weight: 800;
      color: rgba(75, 99, 109, 0.72);
      margin-right: 4px;
    }
    .focus-chip {
      padding: 8px 14px;
      border-radius: 9999px;
      background: var(--tertiary-container);
      color: var(--on-tertiary-container);
      font-size: .82rem;
      font-weight: 700;
    }
    .composer {
      display: flex;
      gap: 10px;
      padding: 10px;
      border-radius: 20px;
      background: rgba(205, 231, 242, 0.48);
      box-shadow: inset 0 1px 0 rgba(255,255,255,.5);
    }
    input[type="text"] {
      flex: 1;
      padding: 16px 18px;
      border-radius: 16px;
      border: 1px solid rgba(157,182,193,.25);
      background: rgba(255,255,255,.82);
      color: var(--on-surface);
      outline: none;
      font-family: inherit;
      font-size: 1rem;
    }
    button { font-family: inherit; }
    button:disabled { opacity: .55; cursor: not-allowed; }
    .input-note {
      margin-top: 10px;
      text-align: center;
      font-size: .8rem;
      color: rgba(75, 99, 109, 0.72);
    }
    .completion-banner {
      margin-top: 18px;
      padding: 18px 20px;
      border-radius: 20px;
      background: rgba(215,236,245,.72);
      border: 1px solid rgba(157,182,193,.18);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    .completion-copy {
      color: var(--on-surface-variant);
      line-height: 1.7;
      font-size: .95rem;
    }
    pre { margin: 0; font-size: 12px; white-space: pre-wrap; word-break: break-word; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    @media (max-width: 900px) {
      .nav-inner, .wrap { width: min(100% - 32px, 1440px); }
      .nav-links { display: none; }
      .records-grid { grid-template-columns: 1fr; gap: 28px; }
      .panel { grid-template-columns: 1fr; }
      .chat { height: 62vh; }
      .feature-visual { height: 300px; }
      .record-top { flex-direction: column; }
      .record-tags { justify-content: flex-start; }
      .record-card { padding: 22px; gap: 18px; }
      .wrap { padding-top: 116px; }
      .bubble-wrap { max-width: 88%; }
      .completion-banner { flex-direction: column; align-items: flex-start; }
    }
  </style>
</head>
<body>
  <div class="page-shell">
    <div class="ambient-right"></div>
    <div class="ambient-left"></div>

    <nav class="nav">
      <div class="nav-inner">
        <div class="brand">CBT Thought Record</div>
        <div class="nav-links">
          <a href="/" class="active">Welcome</a>
          <a href="#" id="sessionLink">Session</a>
          <a href="/reports">Reports</a>
        </div>
        <div class="nav-actions">
          <button class="icon-btn" type="button" aria-label="Settings"><span class="material-symbols-outlined">settings</span></button>
          <button class="icon-btn" type="button" aria-label="Account"><span class="material-symbols-outlined">account_circle</span></button>
        </div>
      </div>
    </nav>

    <main class="wrap">
      <div id="welcomePage">
        <section class="welcome-hero">
          <div class="eyebrow">Daily Mindfulness</div>
          <h1 class="hero-title">How are you feeling today?</h1>
          <p class="hero-copy">
            A quiet place to work through a thought record, notice patterns in your reflections,
            and revisit the sessions that helped you slow down and reframe difficult moments.
          </p>
          <div class="hero-actions">
            <button id="startBtn" class="btn-primary" type="button">
              <span class="material-symbols-outlined" style="font-variation-settings: 'FILL' 1;">add_circle</span>
              Start New Session
            </button>
            <a id="reportsBtn" class="btn-secondary" href="/reports">
              <span class="material-symbols-outlined">description</span>
              View Reports
            </a>
          </div>
        </section>

        <div class="feature-visual">
          <img
            alt="Soft calm ocean waves at dawn"
            src="https://lh3.googleusercontent.com/aida-public/AB6AXuAoE-aG9-BVEqlSd1HRdS59rsEoLMFwWgHHARpL-WavAz3ei5VMmVtiAwQlUANFoVJaF4wbpi-PVCDDeMdY63C2KuZutk_JtXrxR9tJNy5n_In1uWtiTZ96AlRgrtqtdGzmke43qhCD7roeTjHaRD-zhlkJYlWueRQFXyCaJxu6aOcPJOdiQk4ousKLDIF6KXY8riU_Z57bR6ka9YRwdYw7WkJZPt2djr04v3jY2xiQUX1I0hZqoDpvuA1tZnK1ve5s120c4X1c_-Hu"
          />
          <div class="feature-content">
            <p class="feature-quote">"The quieter you become, the more you are able to hear."</p>
            <div class="feature-line"></div>
          </div>
        </div>

        <section class="records-grid">
          <aside class="records-sidebar">
            <h2>Recent Records</h2>
            <p>
              Your recent completed thought records. Revisit an earlier reflection or move to the
              full reports area when you want a broader view.
            </p>
            <div class="streak-card">
              <div class="streak-row">
                <span>Completed Sessions</span>
                <span id="sessionCount">0</span>
              </div>
              <div class="streak-track">
                <div id="sessionFill" class="streak-fill"></div>
              </div>
            </div>
          </aside>

          <div>
            <div id="recentRecords" class="records-list"></div>
            <div class="records-footer">
              <a class="nav-pill" href="/reports">
                View All Session Reports
                <span class="material-symbols-outlined" style="font-size:18px;">open_in_new</span>
              </a>
            </div>
          </div>
        </section>

        <footer class="footer-note">
          <div class="footer-pill">Your data is private, stored locally, and reviewed only inside your own sanctuary.</div>
          <div class="footer-icons">
            <span class="material-symbols-outlined">psychology</span>
            <span class="material-symbols-outlined">self_improvement</span>
            <span class="material-symbols-outlined">potted_plant</span>
          </div>
        </footer>
      </div>

      <div class="conversation-shell hidden" id="chatPanel">
        <header class="conversation-header">
          <div class="eyebrow">Current Session</div>
          <h1 class="conversation-title">Today's Reflection</h1>
          <p class="conversation-copy">Find your space to breathe and share.</p>
          <div class="session-meta-row">
            <div class="session-chip">
              <span class="material-symbols-outlined" style="font-size:18px;">psychology</span>
              <span id="sessionMeta">Session not started</span>
            </div>
            <div class="session-chip">
              <span class="material-symbols-outlined" style="font-size:18px;">receipt_long</span>
              <span>Thought record saved at the end</span>
            </div>
          </div>
        </header>

        <div class="panel">
          <div>
            <div class="chat">
              <div class="log" id="log"></div>
            </div>
            <div class="composer-shell">
              <div class="focus-row">
                <span class="focus-label">Focus on:</span>
                <span class="focus-chip">Emotion</span>
                <span class="focus-chip">Situation</span>
                <span class="focus-chip">Thoughts</span>
                <span class="focus-chip">Evidence</span>
              </div>
              <div class="composer">
                <input id="input" type="text" placeholder="Share your thoughts here..." autocomplete="off" />
                <button class="btn-primary" id="sendBtn" type="button">
                  <span>Send</span>
                  <span class="material-symbols-outlined" style="font-size:18px;">send</span>
                </button>
              </div>
              <div class="input-note">This is a safe space for reflection. Take your time.</div>
            </div>
          </div>
        </div>

        <div id="completionBanner" class="completion-banner hidden">
          <div class="completion-copy">
            Your thought record is ready to review. Open the full record to see the completed worksheet content.
          </div>
          <button id="viewBtn" class="btn-primary" type="button">
            <span class="material-symbols-outlined" style="font-size:18px;">description</span>
            View Thought Record
          </button>
        </div>
      </div>

      <button id="newBtn" class="hidden" type="button"></button>
    </main>
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
  const welcomePage = document.getElementById('welcomePage');
  const chatPanel = document.getElementById('chatPanel');
  const recentRecordsEl = document.getElementById('recentRecords');
  const sessionCountEl = document.getElementById('sessionCount');
  const sessionFillEl = document.getElementById('sessionFill');
  const sessionLink = document.getElementById('sessionLink');
  const sessionMetaEl = document.getElementById('sessionMeta');
  const completionBannerEl = document.getElementById('completionBanner');

  function addMsg(role, text) {
    const row = document.createElement('div');
    row.className = 'msg ' + role;
    const avatar = document.createElement('div');
    avatar.className = 'avatar ' + role;
    const icon = document.createElement('span');
    icon.className = 'material-symbols-outlined';
    icon.style.fontVariationSettings = role === 'assistant' ? "'FILL' 1" : "'FILL' 0";
    icon.textContent = role === 'assistant' ? 'spa' : 'person';
    avatar.appendChild(icon);

    const wrap = document.createElement('div');
    wrap.className = 'bubble-wrap';
    const b = document.createElement('div');
    b.className = 'bubble';
    b.textContent = text;
    wrap.appendChild(b);

    const stamp = document.createElement('div');
    stamp.className = 'timestamp';
    stamp.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    wrap.appendChild(stamp);

    if (role === 'assistant') {
      row.appendChild(avatar);
      row.appendChild(wrap);
    } else {
      row.appendChild(wrap);
      row.appendChild(avatar);
    }
    logEl.appendChild(row);
    logEl.scrollTop = logEl.scrollHeight;
  }

  function setRecord(obj) {
    return obj;
  }

  function formatDate(value) {
    if (!value) return 'Session completed';
    const date = new Date(value.replace(' ', 'T'));
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString([], {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  function buildTitle(item) {
    const emotion = item.emotion || 'Reflection';
    return `${emotion.charAt(0).toUpperCase() + emotion.slice(1)} reflection`;
  }

  function buildSummary(item) {
    const parts = [];
    if (item.intensity_before != null && item.intensity_after != null) {
      parts.push(`Intensity ${item.intensity_before} to ${item.intensity_after}`);
    }
    const distortions = item.distortions || [];
    if (distortions.length) {
      parts.push(`Distortions: ${distortions.join(', ')}`);
    }
    return parts.join(' • ') || 'Open the full report to review this session.';
  }

  function renderRecentRecords(items) {
    if (!items.length) {
      recentRecordsEl.innerHTML = `
        <div class="record-card">
          <div class="record-icon"><span class="material-symbols-outlined">history</span></div>
          <div class="record-body">
            <h3 class="record-title">No completed records yet</h3>
            <p class="record-copy">Start your first thought record to build your session history here.</p>
          </div>
        </div>
      `;
      sessionCountEl.textContent = '0';
      sessionFillEl.style.width = '0%';
      return;
    }

    sessionCountEl.textContent = String(items.length);
    sessionFillEl.style.width = `${Math.min(items.length / 7, 1) * 100}%`;

    recentRecordsEl.innerHTML = items.slice(-3).reverse().map((item, idx) => {
      const emotion = item.emotion || 'Reflection';
      const distortions = item.distortions || [];
      return `
        <a class="record-card ${idx === 1 ? 'is-highlight' : ''}" href="/reports/session/${encodeURIComponent(item.session_id)}">
          <div class="record-icon">
            <span class="material-symbols-outlined">${idx === 1 ? 'spa' : idx === 2 ? 'edit_note' : 'cloud_queue'}</span>
          </div>
          <div class="record-body">
            <div class="record-top">
              <span class="record-date">${formatDate(item.date)}</span>
              <div class="record-tags">
                <span class="tag tag-emotion">${emotion}</span>
                <span class="tag tag-metric">${item.intensity_before != null && item.intensity_after != null ? `${item.intensity_before} -> ${item.intensity_after}` : 'Completed'}</span>
              </div>
            </div>
            <h3 class="record-title">${buildTitle(item)}</h3>
            <p class="record-copy">${buildSummary(item)}</p>
          </div>
          <div class="record-arrow">
            <span class="material-symbols-outlined">arrow_forward_ios</span>
          </div>
        </a>
      `;
    }).join('');
  }

  async function loadRecentRecords() {
    try {
      const res = await fetch('/api/report-sessions');
      if (!res.ok) throw new Error('failed');
      const data = await res.json();
      renderRecentRecords(data.items || []);
    } catch (err) {
      recentRecordsEl.innerHTML = `
        <div class="record-card">
          <div class="record-icon"><span class="material-symbols-outlined">error</span></div>
          <div class="record-body">
            <h3 class="record-title">Could not load recent records</h3>
            <p class="record-copy">You can still start a new session or open the report viewer.</p>
          </div>
        </div>
      `;
    }
  }

  function setUiState() {
    const hasSession = !!sessionId;
    welcomePage.classList.toggle('hidden', hasSession);
    chatPanel.classList.toggle('hidden', !hasSession);
    sendBtn.disabled = !hasSession || sessionCompleted;
    inputEl.disabled = !hasSession || sessionCompleted;
    startBtn.disabled = hasSession && !sessionCompleted;
    if (completionBannerEl) {
      completionBannerEl.classList.toggle('hidden', !sessionCompleted || !recordUrl);
    }
    if (sessionMetaEl) {
      sessionMetaEl.textContent = hasSession ? `Session ${sessionId} · Step ${currentStep}` : 'Session not started';
    }
    if (sessionLink) {
      sessionLink.classList.toggle('active', hasSession);
      if (hasSession) {
        sessionLink.setAttribute('href', '#');
      } else {
        sessionLink.setAttribute('href', '/');
      }
    }
  }

  async function startSession() {
    if (sessionId && !sessionCompleted) return;
    logEl.innerHTML = '';
    setRecord({});
    sessionId = null;
    currentStep = null;
    sessionCompleted = false;
    recordUrl = null;
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
    addMsg('assistant', data.message);
    if (sessionCompleted && recordUrl) {
      viewBtn.onclick = () => { window.location.href = recordUrl; };
    }
    setUiState();
  }

  sendBtn.addEventListener('click', sendMessage);
  newBtn.addEventListener('click', startSession);
  startBtn.addEventListener('click', startSession);
  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendMessage();
  });

  loadRecentRecords();
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
    try:
        report = report_service.generate_report(mode="single", session_ids=[session_id], persist=False)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Session not found or not completed.") from exc
    return _render_report_page(report)


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
            return "<li>None recorded</li>"
        return "".join(
            f"<li><strong>{esc(item.get('label'))}</strong>: {esc(item.get('count'))}</li>"
            for item in items
        )

    page_css = """
    :root {
      --on-primary-fixed: #354339;
      --outline-variant: #9db6c1;
      --tertiary-container: #faf3e5;
      --on-tertiary-container: #605b51;
      --on-background: #1e363f;
      --on-surface-variant: #4b636d;
      --background: #f3fbff;
      --surface-container-low: #e9f5fc;
      --surface-container: #e0f0f9;
      --surface-container-high: #d7ecf5;
      --surface-container-highest: #cde7f2;
      --primary: #546257;
      --primary-dim: #48564c;
      --primary-container: #d7e6d9;
      --on-primary: #ecfcee;
      --outline: #667e89;
      --on-surface: #1e363f;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: 'Manrope', sans-serif; background: var(--background); color: var(--on-surface); }
    .page-shell { position: relative; min-height: 100vh; overflow: hidden; }
    .ambient-right, .ambient-left { position: fixed; border-radius: 9999px; filter: blur(120px); z-index: -1; pointer-events: none; }
    .ambient-right { top: 18%; right: -120px; width: 380px; height: 380px; background: rgba(84, 98, 87, 0.08); }
    .ambient-left { bottom: 14%; left: -120px; width: 420px; height: 420px; background: rgba(255, 219, 208, 0.18); }
    .nav { position: fixed; top: 0; width: 100%; z-index: 50; backdrop-filter: blur(20px); background: rgba(243, 251, 255, 0.82); box-shadow: 0 1px 0 rgba(157, 182, 193, 0.15); }
    .nav-inner, .wrap { width: min(1180px, calc(100% - 48px)); margin: 0 auto; }
    .nav-inner { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 24px 0; }
    .brand { font-size: 1.25rem; font-weight: 800; letter-spacing: -0.03em; color: var(--on-background); text-decoration: none; }
    .nav-links { display: flex; align-items: center; gap: 32px; font-weight: 600; color: var(--on-surface-variant); }
    .nav-links a { text-decoration: none; color: inherit; }
    .nav-links a.active { color: var(--on-background); border-bottom: 2px solid var(--primary); padding-bottom: 4px; }
    .nav-actions { display: flex; align-items: center; gap: 16px; color: var(--primary); }
    .icon-btn { display: inline-flex; align-items: center; justify-content: center; width: 40px; height: 40px; border-radius: 9999px; background: transparent; border: none; color: inherit; }
    .material-symbols-outlined { font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24; }
    .wrap { padding: 128px 0 88px; }
    .hero { display:flex; align-items:flex-end; justify-content:space-between; gap:24px; margin-bottom: 28px; }
    .eyebrow { font-size: 12px; letter-spacing: .12em; text-transform: uppercase; color: var(--on-surface-variant); margin-bottom: 12px; }
    .page-title { margin: 0; font-size: clamp(2.6rem, 6vw, 4.6rem); line-height: 1.04; letter-spacing: -0.06em; color: var(--on-background); }
    .page-subtle { margin-top: 10px; color: var(--on-surface-variant); font-size: .95rem; line-height: 1.7; }
    .status-pill { display:inline-flex; align-items:center; gap:8px; padding: 10px 16px; border-radius: 9999px; background: var(--tertiary-container); color: var(--on-tertiary-container); font-size: .86rem; font-weight: 700; }
    .status-dot { width: 8px; height: 8px; border-radius: 9999px; background: var(--primary); }
    .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-top: 16px; }
    .panel { margin-top: 18px; background: rgba(255,255,255,.68); border: 1px solid rgba(157,182,193,.2); border-radius: 24px; padding: 22px; box-shadow: 0 22px 36px rgba(30,54,63,.05); }
    .stat { background: rgba(215,236,245,.74); border: 1px solid rgba(157,182,193,.18); border-radius: 18px; padding: 18px; }
    .label { font-size: .74rem; text-transform: uppercase; letter-spacing: .14em; color: rgba(75,99,109,.72); font-weight: 800; }
    .value { font-size: 2rem; font-weight: 800; letter-spacing: -0.04em; margin-top: 8px; color: var(--on-background); }
    .muted { color: var(--on-surface-variant); font-size: .92rem; line-height: 1.6; margin-top: 6px; }
    .section-title { font-size: 1.1rem; font-weight: 800; letter-spacing: -0.03em; margin-bottom: 10px; }
    .detail-title { font-size: .78rem; text-transform: uppercase; letter-spacing: .14em; color: rgba(75,99,109,.72); font-weight: 800; margin-bottom: 10px; }
    .detail-copy, p { margin: 0; white-space: pre-wrap; line-height: 1.8; color: var(--on-surface); }
    ul { margin: 0; padding-left: 20px; color: var(--on-surface); line-height: 1.8; }
    .session-list { display:flex; flex-direction:column; gap:16px; }
    .session-card { display:block; text-decoration:none; color:inherit; background: rgba(215,236,245,.52); border: 1px solid rgba(157,182,193,.18); border-radius: 20px; padding: 20px; transition: transform .25s ease, box-shadow .25s ease, border-color .25s ease; }
    .session-card:hover { transform: translateY(-2px); border-color: rgba(84,98,87,.24); box-shadow: 0 20px 32px rgba(30,54,63,.06); }
    .session-top { display:flex; justify-content:space-between; gap:14px; align-items:flex-start; margin-bottom: 10px; }
    .session-name { font-size: 1.02rem; font-weight: 800; letter-spacing: -0.02em; }
    .pill-row { display:flex; flex-wrap:wrap; gap:8px; }
    .pill { display:inline-flex; align-items:center; padding: 7px 12px; border-radius: 9999px; background: var(--surface-container-highest); color: var(--on-surface-variant); font-size: .76rem; font-weight: 700; }
    .pill.emotion { background: var(--tertiary-container); color: var(--on-tertiary-container); }
    .link-row { margin-top: 12px; color: var(--primary); font-weight: 700; display:inline-flex; align-items:center; gap:8px; }
    @media (max-width: 900px) {
      .nav-inner, .wrap { width: min(100% - 32px, 1180px); }
      .nav-links { display:none; }
      .hero { flex-direction: column; align-items: flex-start; }
      .session-top { flex-direction: column; }
    }
    """

    if report_type == "single_session":
        item = sessions[0] if sessions else {}
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Session Report {esc(item.get("session_id"))}</title>
  <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@200;300;400;500;600;700;800&display=swap" rel="stylesheet" />
  <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
  <style>
    {page_css}
  </style>
</head>
<body>
  <div class="page-shell">
    <div class="ambient-right"></div>
    <div class="ambient-left"></div>
    <nav class="nav">
      <div class="nav-inner">
        <a class="brand" href="/">CBT Thought Record</a>
        <div class="nav-links">
          <a href="/">Welcome</a>
          <a href="/">Session</a>
          <a href="/reports" class="active">Reports</a>
        </div>
        <div class="nav-actions">
          <button class="icon-btn" type="button"><span class="material-symbols-outlined">settings</span></button>
          <button class="icon-btn" type="button"><span class="material-symbols-outlined">account_circle</span></button>
        </div>
      </div>
    </nav>
    <main class="wrap">
      <section class="hero">
        <div>
          <div class="eyebrow">Session Archive</div>
          <h1 class="page-title">Single Session Report</h1>
          <div class="page-subtle">Session {esc(item.get("session_id"))} · Generated at {esc(report.get("generated_at"))}</div>
        </div>
        <div class="status-pill"><span class="status-dot"></span><span>Reflection Complete</span></div>
      </section>

      <div class="grid">
        <div class="stat"><div class="label">Date</div><div class="muted">{esc(item.get("date"))}</div></div>
        <div class="stat"><div class="label">Emotion</div><div class="value">{esc(item.get("emotion"))}</div></div>
        <div class="stat"><div class="label">Intensity Before</div><div class="value">{esc(metrics.get("intensity_before"))}</div></div>
        <div class="stat"><div class="label">Intensity After</div><div class="value">{esc(metrics.get("intensity_after"))}</div></div>
        <div class="stat"><div class="label">Change</div><div class="muted">{esc(change_text(metrics.get("intensity_delta")))}</div></div>
      </div>

      <div class="panel"><div class="detail-title">Situation</div><p class="detail-copy">{esc(item.get("situation"))}</p></div>
      <div class="panel"><div class="detail-title">Automatic Thought</div><p class="detail-copy">{esc(item.get("automatic_thought"))}</p></div>
      <div class="panel"><div class="detail-title">Evidence For</div><ul>{render_lines(item.get("evidence_for") or [])}</ul></div>
      <div class="panel"><div class="detail-title">Evidence Against</div><ul>{render_lines(item.get("evidence_against") or [])}</ul></div>
      <div class="panel"><div class="detail-title">Distortions</div><ul>{render_lines(item.get("distortions") or [])}</ul></div>
      <div class="panel"><div class="detail-title">Balanced Thought</div><p class="detail-copy">{esc(item.get("balanced_thought"))}</p></div>
      <div class="panel"><div class="detail-title">Summary</div><p class="detail-copy">{esc(item.get("summary"))}</p></div>
    </main>
  </div>
</body>
</html>"""

    def render_sessions(items: list[dict[str, Any]]) -> str:
        if not items:
            return "<p class=\"muted\">No sessions included.</p>"
        cards = []
        for item in items:
            distortions = ", ".join(item.get("distortions") or []) or "None"
            cards.append(
                f"""
                <a class="session-card" href="{esc(item.get("session_report_url"))}">
                  <div class="session-top">
                    <div>
                      <div class="session-name">Session {esc(item.get("session_id"))}</div>
                      <div class="muted">{esc(item.get("date"))}</div>
                    </div>
                    <div class="pill-row">
                      <span class="pill emotion">{esc(item.get("emotion"))}</span>
                      <span class="pill">{esc(item.get("intensity_before"))} -> {esc(item.get("intensity_after"))}</span>
                    </div>
                  </div>
                  <div class="muted"><strong>Change:</strong> {esc(change_text(item.get("intensity_delta")))}</div>
                  <div class="muted"><strong>Distortions:</strong> {esc(distortions)}</div>
                  <div class="muted"><strong>Balanced thought:</strong> {esc(item.get("balanced_thought"))}</div>
                  <div class="link-row">View single report <span class="material-symbols-outlined" style="font-size:18px;">arrow_forward</span></div>
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
  <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@200;300;400;500;600;700;800&display=swap" rel="stylesheet" />
  <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
  <style>
    {page_css}
  </style>
</head>
<body>
  <div class="page-shell">
    <div class="ambient-right"></div>
    <div class="ambient-left"></div>
    <nav class="nav">
      <div class="nav-inner">
        <a class="brand" href="/">CBT Thought Record</a>
        <div class="nav-links">
          <a href="/">Welcome</a>
          <a href="/">Session</a>
          <a href="/reports" class="active">Reports</a>
        </div>
        <div class="nav-actions">
          <button class="icon-btn" type="button"><span class="material-symbols-outlined">settings</span></button>
          <button class="icon-btn" type="button"><span class="material-symbols-outlined">account_circle</span></button>
        </div>
      </div>
    </nav>
    <main class="wrap">
      <section class="hero">
        <div>
          <div class="eyebrow">Session Archives</div>
          <h1 class="page-title">Your Insight Report</h1>
          <div class="page-subtle">Report ID {esc(report.get("report_id"))} · Generated at {esc(report.get("generated_at"))}</div>
        </div>
        <div class="status-pill"><span class="status-dot"></span><span>Reflection Complete</span></div>
      </section>

      <div class="panel">
        <div class="section-title">Report Scope</div>
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
        <div class="section-title">Common Distortions</div>
        <ul>{render_distribution(metrics.get("top_distortions") or [])}</ul>
      </div>

      <div class="panel">
        <div class="section-title">Common Emotions</div>
        <ul>{render_distribution(metrics.get("top_emotions") or [])}</ul>
      </div>

      <div class="panel">
        <div class="section-title">Sessions Included</div>
        <div class="session-list">{render_sessions(sessions)}</div>
      </div>
    </main>
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
  <title>CBT Thought Record | Reports</title>
  <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@200;300;400;500;600;700;800&display=swap" rel="stylesheet" />
  <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
  <style>
    :root {
      --outline-variant: #9db6c1;
      --tertiary-container: #faf3e5;
      --on-tertiary-container: #605b51;
      --on-background: #1e363f;
      --on-surface-variant: #4b636d;
      --background: #f3fbff;
      --surface-container-low: #e9f5fc;
      --surface-container-high: #d7ecf5;
      --surface-container-highest: #cde7f2;
      --primary: #546257;
      --primary-dim: #48564c;
      --on-primary: #ecfcee;
      --on-surface: #1e363f;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: 'Manrope', sans-serif; background: var(--background); color: var(--on-surface); }
    .page-shell { position: relative; min-height: 100vh; overflow: hidden; }
    .ambient-right, .ambient-left { position: fixed; border-radius: 9999px; filter: blur(120px); z-index: -1; pointer-events: none; }
    .ambient-right { top: 18%; right: -120px; width: 380px; height: 380px; background: rgba(84, 98, 87, 0.08); }
    .ambient-left { bottom: 14%; left: -120px; width: 420px; height: 420px; background: rgba(255, 219, 208, 0.18); }
    .nav { position: fixed; top: 0; width: 100%; z-index: 50; backdrop-filter: blur(20px); background: rgba(243, 251, 255, 0.82); box-shadow: 0 1px 0 rgba(157, 182, 193, 0.15); }
    .nav-inner, .wrap { width: min(1180px, calc(100% - 48px)); margin: 0 auto; }
    .nav-inner { display:flex; align-items:center; justify-content:space-between; gap:16px; padding:24px 0; }
    .brand { font-size:1.25rem; font-weight:800; letter-spacing:-0.03em; color:var(--on-background); text-decoration:none; }
    .nav-links { display:flex; align-items:center; gap:32px; font-weight:600; color:var(--on-surface-variant); }
    .nav-links a { text-decoration:none; color:inherit; }
    .nav-links a.active { color: var(--on-background); border-bottom: 2px solid var(--primary); padding-bottom: 4px; }
    .nav-actions { display:flex; align-items:center; gap:16px; color:var(--primary); }
    .icon-btn { display:inline-flex; align-items:center; justify-content:center; width:40px; height:40px; border-radius:9999px; background:transparent; border:none; color:inherit; }
    .material-symbols-outlined { font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24; }
    .wrap { padding: 128px 0 88px; }
    .hero { display:flex; align-items:flex-end; justify-content:space-between; gap:24px; margin-bottom: 28px; }
    .eyebrow { font-size:12px; letter-spacing:.12em; text-transform:uppercase; color:var(--on-surface-variant); margin-bottom:12px; }
    .title { margin:0; font-size: clamp(2.6rem, 6vw, 4.6rem); line-height:1.04; letter-spacing:-0.06em; color:var(--on-background); }
    .meta-head { margin-top:10px; color:var(--on-surface-variant); font-size:.96rem; line-height:1.7; max-width: 760px; }
    .status-pill { display:inline-flex; align-items:center; gap:8px; padding:10px 16px; border-radius:9999px; background:var(--tertiary-container); color:var(--on-tertiary-container); font-size:.86rem; font-weight:700; }
    .status-dot { width:8px; height:8px; border-radius:9999px; background:var(--primary); }
    .grid { display:grid; grid-template-columns: 300px 1fr; gap: 18px; margin-top: 16px; }
    .panel { margin-top: 16px; background: rgba(255,255,255,.68); border:1px solid rgba(157,182,193,.2); border-radius: 24px; padding: 22px; box-shadow: 0 22px 36px rgba(30,54,63,.05); }
    .session { display:flex; gap:14px; align-items:flex-start; padding:18px; border:1px solid rgba(157,182,193,.18); border-radius:20px; background: rgba(215,236,245,.52); margin-top:12px; }
    .session:hover { border-color: rgba(84,98,87,.24); }
    .meta { font-size: .9rem; color: var(--on-surface-variant); margin-top:6px; line-height:1.6; }
    .section-title { font-size:1.1rem; font-weight:800; letter-spacing:-0.03em; margin-bottom:10px; }
    .controls { display:flex; gap:10px; flex-wrap:wrap; margin-top:14px; }
    .stack > * + * { margin-top: 12px; }
    input[type="number"] { width: 100%; box-sizing: border-box; padding: 14px 16px; border-radius: 16px; border: 1px solid rgba(157,182,193,.25); background: rgba(255,255,255,.82); color: var(--on-surface); font-family: inherit; }
    button, a.button { padding: 14px 18px; border-radius: 14px; border: 1px solid rgba(157,182,193,.25); background: rgba(255,255,255,.8); color: var(--on-surface); cursor: pointer; text-decoration:none; display:inline-block; font-family: inherit; font-weight: 700; }
    button.primary { background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dim) 100%); color: var(--on-primary); border: none; box-shadow: 0 16px 30px rgba(84, 98, 87, 0.16); }
    button:disabled { opacity:.55; cursor:not-allowed; }
    .hint { font-size:.9rem; color: var(--on-surface-variant); line-height:1.7; }
    .empty { color: var(--on-surface-variant); }
    .quick-link { color: var(--primary); text-decoration:none; font-weight:700; display:inline-flex; align-items:center; gap:8px; margin-top:10px; }
    @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } .nav-inner, .wrap { width: min(100% - 32px, 1180px); } .nav-links { display:none; } .hero { flex-direction: column; align-items:flex-start; } }
  </style>
</head>
<body>
  <div class="page-shell">
    <div class="ambient-right"></div>
    <div class="ambient-left"></div>
    <nav class="nav">
      <div class="nav-inner">
        <a class="brand" href="/">CBT Thought Record</a>
        <div class="nav-links">
          <a href="/">Welcome</a>
          <a href="/">Session</a>
          <a href="/reports" class="active">Reports</a>
        </div>
        <div class="nav-actions">
          <button class="icon-btn" type="button"><span class="material-symbols-outlined">settings</span></button>
          <button class="icon-btn" type="button"><span class="material-symbols-outlined">account_circle</span></button>
        </div>
      </div>
    </nav>
    <main class="wrap">
      <section class="hero">
        <div>
          <div class="eyebrow">Session Archives</div>
          <h1 class="title">Independent Report Viewer</h1>
          <div class="meta-head">Open a single-session reflection or combine completed sessions into one broader report. Everything here is generated directly from your saved sessions.</div>
        </div>
        <div class="status-pill"><span class="status-dot"></span><span>Reports Ready</span></div>
      </section>

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
            <div class="hint">Select one or more completed sessions, then open a combined report.</div>
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
    </main>
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
