import { useEffect, useMemo, useRef, useState } from "react";
import { getMultiSessionReport, getSavedReport, getSingleSessionReport, listReportSessions, sendMessage, startSession } from "./api";
import type { ChatMessage, Report, ReportItem, ReportSession } from "./types";

function makeMessage(role: ChatMessage["role"], text: string): ChatMessage {
  return {
    id: `${role}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    role,
    text,
    createdAt: new Date().toISOString()
  };
}

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatDate(value?: string) {
  if (!value) return "Session completed";
  const date = new Date(value.replace(" ", "T"));
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function changeText(delta: unknown) {
  if (typeof delta !== "number") return "Change unavailable";
  if (delta < 0) return `Reduced by ${Math.abs(Math.trunc(delta))} points`;
  if (delta > 0) return `Increased by ${Math.trunc(delta)} points`;
  return "No change";
}

function buildTitle(item: ReportSession) {
  const emotion = item.emotion || "Reflection";
  return `${emotion.charAt(0).toUpperCase() + emotion.slice(1)} reflection`;
}

function buildSummary(item: ReportSession) {
  const parts: string[] = [];
  if (item.intensity_before != null && item.intensity_after != null) {
    parts.push(`Intensity ${item.intensity_before} to ${item.intensity_after}`);
  }
  const distortions = item.distortions || [];
  if (distortions.length) {
    parts.push(`Distortions: ${distortions.join(", ")}`);
  }
  return parts.join(" • ") || "Open the full report to review this session.";
}

function localReportUrl(url?: string) {
  if (!url) return "/reports";
  return url.startsWith("/reports") ? url : `/reports/session/${encodeURIComponent(url)}`;
}

function newestFirst<T extends { date?: string; session_id?: string }>(items: T[]) {
  return [...items].sort((a, b) => {
    const byDate = String(b.date || "").localeCompare(String(a.date || ""));
    if (byDate !== 0) return byDate;
    return String(b.session_id || "").localeCompare(String(a.session_id || ""));
  });
}

function AppFrame({ children, active = "welcome" }: { children: React.ReactNode; active?: "welcome" | "session" | "reports" }) {
  return (
    <div className="page-shell">
      <div className="ambient-right"></div>
      <div className="ambient-left"></div>

      <nav className="nav">
        <div className="nav-inner">
          <a className="brand" href="/">
            The Quiet Sanctuary
          </a>
          <div className="nav-links">
            <a className={active === "welcome" ? "active" : ""} href="/">
              Welcome
            </a>
            <a className={active === "session" ? "active" : ""} href="/">
              Session
            </a>
            <a className={active === "reports" ? "active" : ""} href="/reports">
              Reports
            </a>
          </div>
          <div className="nav-actions">
            <button className="icon-btn" type="button" aria-label="Settings">
              <span className="material-symbols-outlined">settings</span>
            </button>
            <button className="icon-btn" type="button" aria-label="Account">
              <span className="material-symbols-outlined">account_circle</span>
            </button>
          </div>
        </div>
      </nav>

      <main className="wrap">{children}</main>
    </div>
  );
}

function HomePage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<number | null>(null);
  const [isSessionComplete, setIsSessionComplete] = useState(false);
  const [recordUrl, setRecordUrl] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [recentRecords, setRecentRecords] = useState<ReportSession[]>([]);
  const [isStarting, setIsStarting] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isLoadingRecords, setIsLoadingRecords] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const logRef = useRef<HTMLDivElement | null>(null);

  const canStart = useMemo(() => !sessionId || isSessionComplete, [isSessionComplete, sessionId]);

  useEffect(() => {
    void refreshRecords();
  }, []);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function refreshRecords() {
    setIsLoadingRecords(true);
    try {
      const data = await listReportSessions();
      setRecentRecords(data.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load records.");
    } finally {
      setIsLoadingRecords(false);
    }
  }

  async function handleStartSession() {
    if (!canStart || isStarting) return;

    setIsStarting(true);
    setError(null);
    setMessages([]);
    setSessionId(null);
    setCurrentStep(null);
    setIsSessionComplete(false);
    setRecordUrl(null);

    try {
      const data = await startSession();
      setSessionId(data.session_id);
      setCurrentStep(data.current_step);
      setMessages([makeMessage("assistant", data.message)]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to start session.";
      setError(message);
      setMessages([makeMessage("assistant", message)]);
    } finally {
      setIsStarting(false);
    }
  }

  async function handleSend() {
    const message = draft.trim();
    if (!message || !sessionId || isSessionComplete || isSending) return;

    setDraft("");
    setIsSending(true);
    setError(null);
    setMessages((current) => [...current, makeMessage("user", message)]);

    try {
      const data = await sendMessage(sessionId, message);
      setCurrentStep(data.current_step);
      setIsSessionComplete(data.session_completed);
      setRecordUrl(data.record_url);
      setMessages((current) => [...current, makeMessage("assistant", data.message)]);
      if (data.session_completed) {
        await refreshRecords();
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Error processing message.";
      setError(message);
      setMessages((current) => [...current, makeMessage("assistant", message)]);
    } finally {
      setIsSending(false);
    }
  }

  if (sessionId) {
    return (
      <AppFrame active="session">
        <div className="conversation-shell">
          <header className="conversation-header">
            <div className="eyebrow">Current Session</div>
            <h1 className="conversation-title">Today's Reflection</h1>
            <p className="conversation-copy">Find your space to breathe and share.</p>
            <div className="session-meta-row">
              <div className="session-chip">
                <span className="material-symbols-outlined small-icon">psychology</span>
                <span>
                  Session {sessionId} · Step {currentStep}
                </span>
              </div>
              <div className="session-chip">
                <span className="material-symbols-outlined small-icon">receipt_long</span>
                <span>Thought record saved at the end</span>
              </div>
            </div>
          </header>

          <div className="panel chat-panel-card">
            <div>
              <div className="chat">
                <div className="log" ref={logRef}>
                  {messages.map((message) => (
                    <div className={`msg ${message.role}`} key={message.id}>
                      {message.role === "assistant" && (
                        <div className={`avatar ${message.role}`}>
                          <span className="material-symbols-outlined filled">spa</span>
                        </div>
                      )}
                      <div className="bubble-wrap">
                        <div className="bubble">{message.text}</div>
                        <div className="timestamp">{formatTime(message.createdAt)}</div>
                      </div>
                      {message.role === "user" && (
                        <div className={`avatar ${message.role}`}>
                          <span className="material-symbols-outlined">person</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div className="composer-shell">
                <div className="focus-row">
                  <span className="focus-label">Focus on:</span>
                  <span className="focus-chip">Emotion</span>
                  <span className="focus-chip">Situation</span>
                  <span className="focus-chip">Thoughts</span>
                  <span className="focus-chip">Evidence</span>
                </div>
                <form
                  className="composer"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void handleSend();
                  }}
                >
                  <input
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    disabled={isSessionComplete}
                    type="text"
                    placeholder="Share your thoughts here..."
                    autoComplete="off"
                  />
                  <button className="btn-primary" type="submit" disabled={isSending || isSessionComplete || !draft.trim()}>
                    <span>{isSending ? "Sending" : "Send"}</span>
                    <span className="material-symbols-outlined small-icon">send</span>
                  </button>
                </form>
                <div className="input-note">This is a safe space for reflection. Take your time.</div>
              </div>
            </div>
          </div>

          {error && !messages.some((message) => message.text === error) && <div className="error-banner">{error}</div>}

          {isSessionComplete && recordUrl && (
            <div className="completion-banner">
              <div className="completion-copy">
                Your thought record is ready to review. Open the full record to see the completed worksheet content.
              </div>
              <a className="btn-primary" href={localReportUrl(recordUrl)}>
                <span className="material-symbols-outlined small-icon">description</span>
                View Thought Record
              </a>
            </div>
          )}
        </div>
      </AppFrame>
    );
  }

  return (
    <AppFrame active="welcome">
      <section className="welcome-hero">
        <div className="eyebrow">Daily Mindfulness</div>
        <h1 className="hero-title">How are you feeling today?</h1>
        <p className="hero-copy">
          A quiet place to work through a thought record, notice patterns in your reflections, and revisit the sessions that helped you
          slow down and reframe difficult moments.
        </p>
        <div className="hero-actions">
          <button className="btn-primary" type="button" disabled={!canStart || isStarting} onClick={handleStartSession}>
            <span className="material-symbols-outlined filled">add_circle</span>
            {isStarting ? "Starting..." : "Start New Session"}
          </button>
          <a className="btn-secondary" href="/reports">
            <span className="material-symbols-outlined">description</span>
            View Reports
          </a>
        </div>
      </section>

      <div className="feature-visual">
        <img
          alt="Soft calm ocean waves at dawn"
          src="https://lh3.googleusercontent.com/aida-public/AB6AXuAoE-aG9-BVEqlSd1HRdS59rsEoLMFwWgHHARpL-WavAz3ei5VMmVtiAwQlUANFoVJaF4wbpi-PVCDDeMdY63C2KuZutk_JtXrxR9tJNy5n_In1uWtiTZ96AlRgrtqtdGzmke43qhCD7roeTjHaRD-zhlkJYlWueRQFXyCaJxu6aOcPJOdiQk4ousKLDIF6KXY8riU_Z57bR6ka9YRwdYw7WkJZPt2djr04v3jY2xiQUX1I0hZqoDpvuA1tZnK1ve5s120c4X1c_-Hu"
        />
        <div className="feature-content">
          <p className="feature-quote">"The quieter you become, the more you are able to hear."</p>
          <div className="feature-line"></div>
        </div>
      </div>

      <section className="records-grid">
        <aside className="records-sidebar">
          <h2>Recent Records</h2>
          <p>
            Your recent completed thought records. Revisit an earlier reflection or move to the full reports area when you want a broader
            view.
          </p>
          <div className="streak-card">
            <div className="streak-row">
              <span>Completed Sessions</span>
              <span>{recentRecords.length}</span>
            </div>
            <div className="streak-track">
              <div className="streak-fill" style={{ width: `${Math.min(recentRecords.length / 7, 1) * 100}%` }}></div>
            </div>
          </div>
        </aside>

        <div>
          <RecentRecordList items={recentRecords} isLoading={isLoadingRecords} />
          <div className="records-footer">
            <a className="nav-pill" href="/reports">
              View All Session Reports
              <span className="material-symbols-outlined small-icon">open_in_new</span>
            </a>
          </div>
        </div>
      </section>

      <footer className="footer-note">
        <div className="footer-pill">Your data is private, stored locally, and reviewed only inside your own sanctuary.</div>
        <div className="footer-icons">
          <span className="material-symbols-outlined">psychology</span>
          <span className="material-symbols-outlined">self_improvement</span>
          <span className="material-symbols-outlined">potted_plant</span>
        </div>
      </footer>
    </AppFrame>
  );
}

function RecentRecordList({ items, isLoading }: { items: ReportSession[]; isLoading: boolean }) {
  if (isLoading) {
    return (
      <div className="records-list">
        <div className="record-card">
          <div className="record-icon">
            <span className="material-symbols-outlined">history</span>
          </div>
          <div className="record-body">
            <h3 className="record-title">Loading records</h3>
            <p className="record-copy">Checking your completed thought records.</p>
          </div>
        </div>
      </div>
    );
  }

  if (!items.length) {
    return (
      <div className="records-list">
        <div className="record-card">
          <div className="record-icon">
            <span className="material-symbols-outlined">history</span>
          </div>
          <div className="record-body">
            <h3 className="record-title">No completed records yet</h3>
            <p className="record-copy">Start your first thought record to build your session history here.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="records-list">
      {newestFirst(items)
        .slice(0, 3)
        .map((item, idx) => (
          <a className={`record-card ${idx === 1 ? "is-highlight" : ""}`} href={`/reports/session/${item.session_id}`} key={item.session_id}>
            <div className="record-icon">
              <span className="material-symbols-outlined">{idx === 1 ? "spa" : idx === 2 ? "edit_note" : "cloud_queue"}</span>
            </div>
            <div className="record-body">
              <div className="record-top">
                <span className="record-date">{formatDate(item.date)}</span>
                <div className="record-tags">
                  <span className="tag tag-emotion">{item.emotion || "Reflection"}</span>
                  <span className="tag tag-metric">
                    {item.intensity_before != null && item.intensity_after != null
                      ? `${item.intensity_before} -> ${item.intensity_after}`
                      : "Completed"}
                  </span>
                </div>
              </div>
              <h3 className="record-title">{buildTitle(item)}</h3>
              <p className="record-copy">{buildSummary(item)}</p>
            </div>
            <div className="record-arrow">
              <span className="material-symbols-outlined">arrow_forward_ios</span>
            </div>
          </a>
        ))}
    </div>
  );
}

function ReportsHomePage() {
  const [sessions, setSessions] = useState<ReportSession[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [recentLimit, setRecentLimit] = useState(3);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadSessions() {
      try {
        const data = await listReportSessions();
        setSessions(data.items || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load sessions.");
      } finally {
        setIsLoading(false);
      }
    }

    void loadSessions();
  }, []);

  function toggleSession(sessionId: string) {
    setSelectedIds((current) => (current.includes(sessionId) ? current.filter((id) => id !== sessionId) : [...current, sessionId]));
  }

  return (
    <AppFrame active="reports">
      <section className="hero report-hero">
        <div>
          <div className="eyebrow">Session Archives</div>
          <h1 className="title">Independent Report Viewer</h1>
          <div className="meta-head">
            Open a single-session reflection or combine completed sessions into one broader report. Everything here is generated directly
            from your saved sessions.
          </div>
        </div>
        <div className="status-pill">
          <span className="status-dot"></span>
          <span>Reports Ready</span>
        </div>
      </section>

      <div className="reports-grid">
        <div className="stack">
          <div className="report-panel">
            <div className="section-title">Recent Report</div>
            <div className="hint">Open a report for the most recent completed sessions.</div>
            <div className="controls">
              <input
                type="number"
                min="1"
                max="50"
                value={recentLimit}
                onChange={(event) => setRecentLimit(Math.max(1, Math.min(50, Number(event.target.value) || 1)))}
              />
              <a className="button primary" href={`/reports/multi?mode=recent&limit=${recentLimit}`}>
                Open Recent Report
              </a>
            </div>
          </div>

          <div className="report-panel">
            <div className="section-title">Custom Report</div>
            <div className="hint">Select one or more completed sessions, then open a combined report.</div>
            <div className="controls">
              <a
                className={`button primary ${selectedIds.length ? "" : "is-disabled"}`}
                href={selectedIds.length ? `/reports/multi?mode=custom&session_ids=${encodeURIComponent(selectedIds.join(","))}` : "#"}
                onClick={(event) => {
                  if (!selectedIds.length) event.preventDefault();
                }}
              >
                {selectedIds.length ? `Open Selected Sessions (${selectedIds.length})` : "Open Selected Sessions"}
              </a>
            </div>
          </div>
        </div>

        <div className="report-panel">
          <div className="section-title">Completed Sessions</div>
          {error && <div className="empty">{error}</div>}
          {isLoading && <div className="empty">Loading sessions...</div>}
          {!isLoading && !sessions.length && <div className="empty">No completed sessions found.</div>}
          {newestFirst(sessions).map((item) => (
            <label className="session" key={item.session_id}>
              <input
                type="checkbox"
                checked={selectedIds.includes(item.session_id)}
                onChange={() => toggleSession(item.session_id)}
              />
              <div>
                <div>
                  <strong>{item.session_id}</strong>
                </div>
                <div className="meta">
                  {item.date || "N/A"} | emotion: {item.emotion || "N/A"}
                </div>
                <div className="meta">
                  Intensity: {String(item.intensity_before)} -&gt; {String(item.intensity_after)} (delta {String(item.intensity_delta)})
                </div>
                <div className="meta">Distortions: {(item.distortions || []).join(", ") || "None"}</div>
                <div className="controls">
                  <a className="button" href={`/reports/session/${item.session_id}`}>
                    View single report
                  </a>
                </div>
              </div>
            </label>
          ))}
        </div>
      </div>
    </AppFrame>
  );
}

function ReportPage({ loader }: { loader: () => Promise<Report> }) {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    loader()
      .then((data) => {
        if (isMounted) setReport(data);
      })
      .catch((err) => {
        if (isMounted) setError(err instanceof Error ? err.message : "Could not load report.");
      });
    return () => {
      isMounted = false;
    };
  }, [loader]);

  if (error) {
    return (
      <AppFrame active="reports">
        <div className="report-panel">
          <div className="section-title">Report Error</div>
          <p className="muted">{error}</p>
        </div>
      </AppFrame>
    );
  }

  if (!report) {
    return (
      <AppFrame active="reports">
        <div className="report-panel">
          <div className="section-title">Loading Report</div>
          <p className="muted">Preparing your report view.</p>
        </div>
      </AppFrame>
    );
  }

  return report.scope.report_type === "single_session" ? <SingleReportPage report={report} /> : <MultiReportPage report={report} />;
}

function SingleReportPage({ report }: { report: Report }) {
  const item = report.sessions[0] || {};
  return (
    <AppFrame active="reports">
      <ReportHero eyebrow="Session Archive" title="Single Session Report" subtitle={`Session ${item.session_id || ""} · Generated at ${report.generated_at}`} />

      <div className="report-stats-grid">
        <Stat label="Date" muted={item.date || ""} />
        <Stat label="Emotion" value={item.emotion || ""} />
        <Stat label="Intensity Before" value={String(report.metrics.intensity_before ?? "")} />
        <Stat label="Intensity After" value={String(report.metrics.intensity_after ?? "")} />
        <Stat label="Change" muted={changeText(report.metrics.intensity_delta)} />
      </div>

      <DetailPanel title="Situation">{item.situation || ""}</DetailPanel>
      <DetailPanel title="Automatic Thought">{item.automatic_thought || ""}</DetailPanel>
      <ListPanel title="Evidence For" items={item.evidence_for || []} />
      <ListPanel title="Evidence Against" items={item.evidence_against || []} />
      <ListPanel title="Distortions" items={item.distortions || []} />
      <DetailPanel title="Balanced Thought">{item.balanced_thought || ""}</DetailPanel>
      <DetailPanel title="Summary">{item.summary || ""}</DetailPanel>
    </AppFrame>
  );
}

function MultiReportPage({ report }: { report: Report }) {
  const scope = report.scope || {};
  const metrics = report.metrics || {};
  return (
    <AppFrame active="reports">
      <ReportHero eyebrow="Session Archives" title="Your Insight Report" subtitle={`Report ID ${report.report_id} · Generated at ${report.generated_at}`} />

      <div className="report-panel">
        <div className="section-title">Report Scope</div>
        <div className="muted">Mode: {scope.mode}</div>
        <div className="muted">Sessions included: {report.sessions.length}</div>
        <div className="muted">
          Date range: {scope.date_range?.start} to {scope.date_range?.end}
        </div>
      </div>

      <div className="report-stats-grid">
        <Stat label="Sessions In Scope" value={String(metrics.total_sessions_in_scope ?? report.sessions.length)} />
        <Stat label="Improved Sessions" value={String(metrics.improved_sessions ?? "")} muted={`out of ${metrics.total_sessions_in_scope ?? report.sessions.length}`} />
        <Stat label="Average Change" muted={changeText(metrics.average_intensity_delta)} />
      </div>

      <ListPanel title="Common Distortions" items={(metrics.top_distortions || []).map((item) => `${item.label}: ${item.count}`)} emptyText="None recorded" />
      <ListPanel title="Common Emotions" items={(metrics.top_emotions || []).map((item) => `${item.label}: ${item.count}`)} emptyText="None recorded" />

      <div className="report-panel">
        <div className="section-title">Sessions Included</div>
        <div className="session-list">
          {newestFirst(report.sessions).map((item) => (
            <SessionReportCard item={item} key={item.session_id} />
          ))}
        </div>
      </div>
    </AppFrame>
  );
}

function ReportHero({ eyebrow, title, subtitle }: { eyebrow: string; title: string; subtitle: string }) {
  return (
    <section className="hero report-hero">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1 className="page-title">{title}</h1>
        <div className="page-subtle">{subtitle}</div>
      </div>
      <div className="status-pill">
        <span className="status-dot"></span>
        <span>Reflection Complete</span>
      </div>
    </section>
  );
}

function Stat({ label, value, muted }: { label: string; value?: string; muted?: string }) {
  return (
    <div className="stat">
      <div className="label">{label}</div>
      {value !== undefined && <div className="value">{value}</div>}
      {muted !== undefined && <div className="muted">{muted}</div>}
    </div>
  );
}

function DetailPanel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="report-panel">
      <div className="detail-title">{title}</div>
      <p className="detail-copy">{children}</p>
    </div>
  );
}

function ListPanel({ title, items, emptyText = "None" }: { title: string; items: string[]; emptyText?: string }) {
  return (
    <div className="report-panel">
      <div className="detail-title">{title}</div>
      <ul>{items.length ? items.map((item) => <li key={item}>{item}</li>) : <li>{emptyText}</li>}</ul>
    </div>
  );
}

function SessionReportCard({ item }: { item: ReportItem }) {
  return (
    <a className="session-card" href={`/reports/session/${item.session_id}`}>
      <div className="session-top">
        <div>
          <div className="session-name">Session {item.session_id}</div>
          <div className="muted">{item.date}</div>
        </div>
        <div className="pill-row">
          <span className="pill emotion">{item.emotion}</span>
          <span className="pill">
            {item.intensity_before} -&gt; {item.intensity_after}
          </span>
        </div>
      </div>
      <div className="muted">
        <strong>Change:</strong> {changeText(item.intensity_delta)}
      </div>
      <div className="muted">
        <strong>Distortions:</strong> {(item.distortions || []).join(", ") || "None"}
      </div>
      <div className="muted">
        <strong>Balanced thought:</strong> {item.balanced_thought}
      </div>
      <div className="link-row">
        View single report <span className="material-symbols-outlined small-icon">arrow_forward</span>
      </div>
    </a>
  );
}

export default function App() {
  const path = window.location.pathname;
  const search = new URLSearchParams(window.location.search);

  if (path === "/reports") {
    return <ReportsHomePage />;
  }

  if (path.startsWith("/reports/session/")) {
    const sessionId = decodeURIComponent(path.replace("/reports/session/", ""));
    return <ReportPage loader={() => getSingleSessionReport(sessionId)} />;
  }

  if (path === "/reports/multi") {
    const mode = search.get("mode") || "recent";
    const limit = Number(search.get("limit") || "5");
    const sessionIds = (search.get("session_ids") || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    return <ReportPage loader={() => getMultiSessionReport(mode, limit, sessionIds)} />;
  }

  if (path.startsWith("/reports/")) {
    const reportId = decodeURIComponent(path.replace("/reports/", ""));
    return <ReportPage loader={() => getSavedReport(reportId)} />;
  }

  return <HomePage />;
}
