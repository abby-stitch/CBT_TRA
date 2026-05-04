import { useEffect, useMemo, useRef, useState } from "react";
import {
  deleteSavedReport,
  deleteSession,
  getMultiSessionReport,
  getSavedReport,
  getSettings,
  getSingleSessionReport,
  getSession,
  listSessions,
  listSavedReports,
  listReportSessions,
  resumeSession,
  saveGeneratedReport,
  sendMessage,
  startSession,
  undoLastInput,
  updateSettings
} from "./api";
import { DISTORTION_GUIDE_ITEMS } from "./distortionGuide";
import type { AppSettings, ChatMessage, DistortionGuideItem, LlmMetadata, Report, ReportItem, ReportSession, SavedReportSummary, SessionArchiveItem, SessionDetail } from "./types";

function makeMessage(role: ChatMessage["role"], text: string): ChatMessage {
  return {
    id: `${role}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    role,
    text,
    createdAt: new Date().toISOString()
  };
}

function messagesFromHistory(history?: Array<{ role?: string; content?: string }>) {
  return (history || [])
    .filter((item) => item.role === "assistant" || item.role === "user")
    .map((item, idx) => ({
      id: `${item.role}-${idx}-${Math.random().toString(16).slice(2)}`,
      role: item.role as ChatMessage["role"],
      text: item.content || "",
      createdAt: new Date().toISOString()
    }));
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
  return parts.join(" • ") || "Open the thought record to review this session.";
}

function savedReportTitle(item: SavedReportSummary) {
  const scope = item.scope || {};
  const type = scope.report_type === "single_session" ? "Single Session Report" : "Progress Report";
  const count = item.sessions_count ?? scope.session_ids?.length ?? 0;
  return count ? `${type} · ${count} session${count === 1 ? "" : "s"}` : type;
}

function savedReportSummary(item: SavedReportSummary) {
  const scope = item.scope || {};
  if (scope.report_type === "single_session") {
    const sessionDate = scope.date_range?.start || scope.date_range?.end;
    return sessionDate ? `Session date: ${sessionDate}` : "Session date unavailable";
  }
  const mode = scope.mode ? `Mode: ${scope.mode}` : "Saved report";
  const range = scope.date_range?.start && scope.date_range?.end ? `${scope.date_range.start} to ${scope.date_range.end}` : "Date range unavailable";
  return `${mode} · ${range}`;
}

function collectActionItems(value: unknown): string[] {
  const out: string[] = [];
  const visit = (item: unknown) => {
    if (out.length >= 3) return;
    if (typeof item === "string") {
      const text = item.trim();
      if (text) out.push(text);
      return;
    }
    if (Array.isArray(item)) {
      item.forEach(visit);
      return;
    }
    if (item && typeof item === "object") {
      const record = item as Record<string, unknown>;
      visit(record.text ?? record.item ?? record.action ?? record.title);
    }
  };
  visit(value);
  return out.slice(0, 3);
}

function parseGeneratedReportJson(value?: string | null) {
  if (!value) return null;
  let text = value.trim();
  if (text.startsWith("```")) {
    text = text.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/i, "").trim();
  }
  const start = text.indexOf("{");
  const end = text.lastIndexOf("}");
  const candidates = [text, start >= 0 && end >= start ? text.slice(start, end + 1) : ""].filter(Boolean);

  for (const candidate of candidates) {
    try {
      let data: unknown = JSON.parse(candidate);
      if (typeof data === "string") data = JSON.parse(data);
      if (data && typeof data === "object") {
        const record = data as Record<string, unknown>;
        const synthesis = typeof record.synthesis === "string" ? record.synthesis.trim() : typeof record.summary === "string" ? record.summary.trim() : "";
        const actionItems = collectActionItems(record.action_items ?? record.actions);
        if (synthesis || actionItems.length) return { synthesis, actionItems };
      }
    } catch {
      // Try the next candidate.
    }
  }

  const synthesisMatch = text.match(/"(?:synthesis|summary|llm_summary)"\s*:\s*"((?:\\.|[^"\\])*)"/s);
  const actionMatch = text.match(/"(?:action_items|actions)"\s*:\s*(\[.*)/s);
  const synthesis = synthesisMatch ? decodeJsonishString(synthesisMatch[1]) : "";
  let actionItems: string[] = [];
  if (actionMatch) {
    const rawActions = actionMatch[1];
    const end = rawActions.lastIndexOf("]");
    const candidate = end >= 0 ? rawActions.slice(0, end + 1) : rawActions;
    try {
      actionItems = collectActionItems(JSON.parse(candidate));
    } catch {
      actionItems = collectActionItems([...candidate.matchAll(/"((?:\\.|[^"\\])*)"/g)].map((match) => decodeJsonishString(match[1])));
    }
  }
  if (synthesis || actionItems.length) return { synthesis, actionItems };
  return null;
}

function decodeJsonishString(value: string) {
  try {
    return JSON.parse(`"${value}"`).trim();
  } catch {
    return value.replace(/\\"/g, '"').replace(/\\n/g, "\n").trim();
  }
}

function generatedReportText(report: Report) {
  const parsed = parseGeneratedReportJson(report.llm_summary);
  return parsed?.synthesis || report.llm_summary || (report.llm_error ? `Generated summary unavailable: ${report.llm_error}` : "No generated summary is available for this report.");
}

function defaultActionItems(report: Report) {
  const first = report.sessions[0] || {};
  if (report.scope.report_type === "single_session") {
    const thought = first.automatic_thought || "the original automatic thought";
    return [
      `When this theme returns, briefly name the thought as "${thought}" before responding to it.`,
      "Revisit the evidence against the thought and add one concrete fact if a new example appears.",
      "Practice writing one balanced thought that is realistic rather than simply positive."
    ];
  }
  return [
    "Review the most common distortion label before the next thought record session.",
    "Notice whether similar situations keep appearing across recent records.",
    "Keep a short list of balanced thoughts that felt believable enough to reuse."
  ];
}

function reportActionItems(report: Report) {
  const generated = report.llm_action_items || [];
  const parsed = parseGeneratedReportJson(report.llm_summary);
  return generated.length ? generated.slice(0, 3) : parsed?.actionItems.length ? parsed.actionItems : defaultActionItems(report);
}

function llmLabel(meta?: LlmMetadata | null) {
  if (!meta) return "LLM unavailable";
  const provider = meta.provider || "";
  const model = meta.model || "";
  if (!provider && !model) return "LLM unavailable";
  if (provider === "ollama") return model ? `Ollama · ${model}` : "Ollama";
  if (provider === "openai_compatible" || provider === "api") return model ? `API · ${model}` : "API";
  return [provider, model].filter(Boolean).join(" · ");
}

function sessionDetailUrl(sessionId?: string | null) {
  return sessionId ? `/sessions?session_id=${encodeURIComponent(sessionId)}` : "/sessions";
}

function newestFirst<T extends { date?: string; session_id?: string }>(items: T[]) {
  return [...items].sort((a, b) => {
    const byDate = String(b.date || "").localeCompare(String(a.date || ""));
    if (byDate !== 0) return byDate;
    return String(b.session_id || "").localeCompare(String(a.session_id || ""));
  });
}

function distortionStats(items: ReportSession[]) {
  const counts = new Map<string, number>();
  items.forEach((item) => {
    (item.distortions || []).forEach((label) => {
      const normalized = String(label || "").trim();
      if (!normalized) return;
      counts.set(normalized, (counts.get(normalized) || 0) + 1);
    });
  });
  return [...counts.entries()]
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

function AppFrame({ children, active = "welcome" }: { children: React.ReactNode; active?: "welcome" | "session" | "reports" }) {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isDistortionGuideOpen, setIsDistortionGuideOpen] = useState(false);
  const [activeSettings, setActiveSettings] = useState<AppSettings | null>(null);

  useEffect(() => {
    getSettings()
      .then((data) => setActiveSettings(data))
      .catch(() => setActiveSettings(null));
  }, []);

  const modelBadge = activeSettings
    ? activeSettings.llm_provider === "ollama"
      ? activeSettings.llm_model || "Ollama"
      : activeSettings.llm_model || "API"
    : "Model";
  const modelBadgeTitle = activeSettings
    ? `Provider: ${activeSettings.llm_provider}; Model: ${activeSettings.llm_model}`
    : "Model settings";

  return (
    <div className="page-shell">
      <div className="ambient-right"></div>
      <div className="ambient-left"></div>

      <nav className="nav">
        <div className="nav-inner">
          <div className="brand-stack">
            <a className="brand" href="/">
              CBT Thought Record
            </a>
            <button className="brand-sub-link" type="button" onClick={() => setIsDistortionGuideOpen(true)}>
              <span className="material-symbols-outlined small-icon">menu_book</span>
              Cognitive distortion definitions
            </button>
          </div>
          <div className="nav-links">
            <a className={active === "welcome" ? "active" : ""} href="/">
              Home
            </a>
            <a className={active === "session" ? "active" : ""} href="/sessions">
              Session
            </a>
            <a className={active === "reports" ? "active" : ""} href="/reports">
              Reports
            </a>
          </div>
          <div className="nav-actions">
            <span className="model-badge" title={modelBadgeTitle}>
              <span className="material-symbols-outlined small-icon">memory</span>
              {modelBadge}
            </span>
            <button className="icon-btn" type="button" aria-label="Settings" onClick={() => setIsSettingsOpen(true)}>
              <span className="material-symbols-outlined">settings</span>
            </button>
            <button className="icon-btn" type="button" aria-label="Personal context" onClick={() => setIsProfileOpen(true)}>
              <span className="material-symbols-outlined">account_circle</span>
            </button>
          </div>
        </div>
      </nav>

      <main className="wrap">{children}</main>
      {isSettingsOpen && <SettingsDialog onClose={() => setIsSettingsOpen(false)} onSaved={setActiveSettings} />}
      {isProfileOpen && <ProfileDialog onClose={() => setIsProfileOpen(false)} />}
      {isDistortionGuideOpen && <DistortionGuideDialog onClose={() => setIsDistortionGuideOpen(false)} />}
    </div>
  );
}

function LearnThoughtRecordDialog({ onClose }: { onClose: () => void }) {
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="About CBT thought records">
      <section className="settings-modal learn-modal">
        <div className="settings-head">
          <div>
            <div className="eyebrow">CBT Thought Record</div>
            <h2>Learn more about this exercise</h2>
          </div>
          <button className="icon-btn" type="button" aria-label="Close" onClick={onClose}>
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        <div className="learn-grid">
          <section>
            <h3>What this tool does</h3>
            <p>
              This app guides one structured CBT thought record. It helps you write down a difficult situation, notice the
              automatic thought connected to the emotion, examine evidence, identify possible thinking patterns, and write a
              more balanced response.
            </p>
          </section>

          <section>
            <h3>The flow</h3>
            <ol className="learn-steps">
              <li>Situation, emotion, intensity, and automatic thought</li>
              <li>Evidence that seems to support the thought</li>
              <li>Evidence that does not support the thought</li>
              <li>Possible cognitive distortions</li>
              <li>A balanced or alternative thought</li>
              <li>Re-rate the original emotion</li>
              <li>Review the completed record</li>
            </ol>
          </section>

          <section>
            <h3>Why an agent helps</h3>
            <p>
              CBT thought records are usually learned from books or worksheets, but they can be hard to start and hard to
              continue when emotions are already intense. The agent keeps the worksheet structure visible and asks for one
              piece at a time.
            </p>
          </section>

          <section>
            <h3>Boundaries</h3>
            <p>
              This is a self-reflection and recording tool. It does not diagnose, treat, or replace professional support. If
              you feel unsafe or at risk of harming yourself, seek immediate help from local emergency services or a trusted
              support person.
            </p>
          </section>
        </div>

        <div className="learn-resources">
          <h3>Official resources</h3>
          <div className="resource-links">
            <a href="https://learn.beckinstitute.org/cms/delivery/media/MCPNPP5FFGJVDJ7C74SMXCMM5CWY" target="_blank" rel="noreferrer">
              Beck Institute CBT Worksheet Packet
            </a>
            <a href="https://beckinstitute.org/cbt-resources/resources-for-professionals-and-students/cbtresources/" target="_blank" rel="noreferrer">
              Beck Institute CBT: Basics and Beyond resources
            </a>
            <a href="https://cares.beckinstitute.org/wp-content/uploads/sites/2/2021/06/Coping-with-Depression.pdf" target="_blank" rel="noreferrer">
              Beck Institute Cares Coping with Depression, including thinking errors definitions
            </a>
          </div>
        </div>
      </section>
    </div>
  );
}

function DistortionGuideDialog({ onClose }: { onClose: () => void }) {
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Cognitive distortion definitions">
      <section className="settings-modal distortion-modal">
        <div className="settings-head">
          <div>
            <div className="eyebrow">Cognitive Distortions</div>
            <h2>Definitions used in this thought record</h2>
          </div>
          <button className="icon-btn" type="button" aria-label="Close cognitive distortion guide" onClick={onClose}>
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>
        <p className="modal-intro">
          These labels are based on Beck Institute CBT worksheet resources and describe possible patterns in a specific automatic thought.
          They are used for self-reflection, not diagnosis.
        </p>
        <div className="distortion-guide-grid modal-guide-grid">
          {DISTORTION_GUIDE_ITEMS.map((item) => (
            <article className="distortion-guide-item" key={item.label}>
              <strong>{item.label}</strong>
              <p>{item.definition}</p>
              <span>{item.example}</span>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function useSettingsForm() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [status, setStatus] = useState("Loading...");

  useEffect(() => {
    getSettings()
      .then((data) => {
        setSettings(data);
        setStatus("");
      })
      .catch((err) => setStatus(err instanceof Error ? err.message : "Could not load settings."));
  }, []);

  function setField(key: keyof AppSettings, value: string) {
    setSettings((current) => (current ? { ...current, [key]: value } : current));
  }

  async function saveSettings(nextSettings = settings) {
    if (!nextSettings) return undefined;
    setStatus("Saving...");
    try {
      const next = await updateSettings(nextSettings);
      setSettings(next);
      setStatus("Saved. New sessions will use these settings.");
      return next;
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Could not save settings.");
      return undefined;
    }
  }

  return { settings, setField, saveSettings, status };
}

function SettingsDialog({ onClose, onSaved }: { onClose: () => void; onSaved?: (settings: AppSettings) => void }) {
  const { settings, setField, saveSettings, status } = useSettingsForm();

  function handleProviderChange(provider: string) {
    setField("llm_provider", provider);
    setField("llm_url", provider === "ollama" ? "http://localhost:11434/api/generate" : "https://api.openai.com/v1");
  }

  async function handleSave(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = await saveSettings();
    if (next) onSaved?.(next);
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Project settings">
      <form className="settings-modal" onSubmit={handleSave}>
        <div className="settings-head">
          <div>
            <div className="eyebrow">Local Project Settings</div>
            <h2>Model and storage</h2>
          </div>
          <button className="icon-btn" type="button" aria-label="Close settings" onClick={onClose}>
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        {!settings ? (
          <p className="muted">{status}</p>
        ) : (
          <>
            <div className="settings-grid">
              <label>
                Provider
                <select
                  value={settings.llm_provider === "api" ? "openai_compatible" : settings.llm_provider}
                  onChange={(event) => handleProviderChange(event.target.value)}
                >
                  <option value="ollama">Ollama</option>
                  <option value="openai_compatible">API</option>
                </select>
              </label>
              <label>
                Model
                <input value={settings.llm_model} onChange={(event) => setField("llm_model", event.target.value)} />
              </label>
              <label className="settings-wide">
                API / Ollama URL
                <input value={settings.llm_url} onChange={(event) => setField("llm_url", event.target.value)} />
              </label>
              <label>
                API key env var
                <input value={settings.api_key_env_var} onChange={(event) => setField("api_key_env_var", event.target.value)} />
              </label>
              <label className="settings-wide">
                Sessions path
                <input value={settings.sessions_dir} onChange={(event) => setField("sessions_dir", event.target.value)} />
              </label>
              <label className="settings-wide">
                Reports path
                <input value={settings.reports_dir} onChange={(event) => setField("reports_dir", event.target.value)} />
              </label>
            </div>

            <p className="settings-note">
              Relative paths such as "sessions" and "reports" are resolved from the project root, so they work on another computer too.
              Provider chooses local Ollama or an OpenAI-compatible API. The default API URL is OpenAI, but you can replace it with another
              compatible provider URL. API keys are not stored here; set the real key in your terminal environment.
            </p>
            {status && <p className="settings-status">{status}</p>}
            <div className="settings-actions">
              <button className="btn-secondary" type="button" onClick={onClose}>
                Cancel
              </button>
              <button className="btn-primary" type="submit">
                Save Settings
              </button>
            </div>
          </>
        )}
      </form>
    </div>
  );
}

function ProfileDialog({ onClose }: { onClose: () => void }) {
  const { settings, setField, saveSettings, status } = useSettingsForm();

  async function handleSave(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await saveSettings();
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Personal CBT context">
      <form className="settings-modal profile-modal" onSubmit={handleSave}>
        <div className="settings-head">
          <div>
            <div className="eyebrow">Personal Context</div>
            <h2>Background for guided CBT sessions</h2>
          </div>
          <button className="icon-btn" type="button" aria-label="Close personal context" onClick={onClose}>
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        {!settings ? (
          <p className="muted">{status}</p>
        ) : (
          <>
            <label className="context-field">
              Optional user information
              <textarea
                value={settings.user_context}
                onChange={(event) => setField("user_context", event.target.value)}
                placeholder="Examples: current role or study context, recurring stressors, recurring automatic thoughts, CBT practice goals, preferred response style, or things to avoid. Keep it brief and factual."
              />
            </label>
            <p className="settings-note">
              This is used only as background for new sessions and generated report summaries. The assistant should not diagnose from it
              or override what the user says in the current thought record.
            </p>
            {status && <p className="settings-status">{status}</p>}
            <div className="settings-actions">
              <button className="btn-secondary" type="button" onClick={onClose}>
                Cancel
              </button>
              <button className="btn-primary" type="submit">
                Save Context
              </button>
            </div>
          </>
        )}
      </form>
    </div>
  );
}

function ThoughtRecordConversation({
  sessionId,
  currentStep,
  llm,
  messages,
  draft,
  setDraft,
  isSending,
  isSessionComplete,
  recordUrl,
  error,
  logRef,
  onSend,
  onUndo,
  canUndo,
  isUndoing,
  undoCount,
  undoLimit
}: {
  sessionId: string;
  currentStep: number | null;
  llm?: LlmMetadata | null;
  messages: ChatMessage[];
  draft: string;
  setDraft: (value: string) => void;
  isSending: boolean;
  isSessionComplete: boolean;
  recordUrl: string | null;
  error: string | null;
  logRef: React.RefObject<HTMLDivElement | null>;
  onSend: () => Promise<void>;
  onUndo: () => Promise<void>;
  canUndo: boolean;
  isUndoing: boolean;
  undoCount: number;
  undoLimit: number;
}) {
  const showDistortionGuide = currentStep === 4;
  const lastUserMessageId = [...messages].reverse().find((message) => message.role === "user")?.id;
  const undoTitle = canUndo ? `Undo last input (${undoCount}/${undoLimit})` : "Nothing to undo yet";

  return (
    <AppFrame active="session">
      <div className="conversation-shell">
        <header className="conversation-header">
          <div className="eyebrow">Current Session</div>
          <h1 className="conversation-title">Thought Record Session</h1>
          <p className="conversation-copy">Work through one difficult moment, one step at a time.</p>
          <div className="session-meta-row">
            <div className="session-chip">
              <span className="material-symbols-outlined small-icon">psychology</span>
              <span>
                Session {sessionId} · Step {currentStep}
              </span>
            </div>
            <div className="session-chip">
              <span className="material-symbols-outlined small-icon">receipt_long</span>
              <span>Session data is saved locally</span>
            </div>
            <div className="session-chip">
              <span className="material-symbols-outlined small-icon">memory</span>
              <span>Conversation LLM: {llmLabel(llm)}</span>
            </div>
          </div>
          <div className="conversation-actions">
            <a className="button secondary" href="/sessions">
              <span className="material-symbols-outlined small-icon">arrow_back</span>
              Back to Sessions
            </a>
          </div>
        </header>

        <div className="panel chat-panel-card">
          <div>
            <div className="chat">
              <div className="log" ref={logRef}>
                {messages.map((message) => {
                  const shouldShowGuide =
                    showDistortionGuide && message.role === "assistant" && message.id === messages[messages.length - 1]?.id;
                  const shouldShowUndoSlot = message.role === "user" && message.id === lastUserMessageId;
                  const undoDisabled = !canUndo || isSending || isUndoing;
                  return (
                    <div className={`msg ${message.role}`} key={message.id}>
                    {message.role === "assistant" && (
                      <div className={`avatar ${message.role}`}>
                        <span className="material-symbols-outlined filled">spa</span>
                      </div>
                    )}
                    <div className="bubble-wrap">
                      <div className="bubble">
                        <span>{message.text}</span>
                        {shouldShowGuide && (
                          <DistortionGuide
                            items={DISTORTION_GUIDE_ITEMS}
                          />
                        )}
                      </div>
                      {isSessionComplete && recordUrl && message.role === "assistant" && message.id === messages[messages.length - 1]?.id && (
                        <div className="summary-review-card">
                          <div>
                            <strong>Thought record complete</strong>
                            <span>Review the completed worksheet before starting another session.</span>
                          </div>
                          <a className="btn-primary" href={sessionDetailUrl(sessionId)}>
                            <span className="material-symbols-outlined small-icon">description</span>
                            View Thought Record
                          </a>
                        </div>
                      )}
                      {shouldShowUndoSlot ? (
                        <div className="message-meta-row">
                          <button
                            className="message-undo"
                            type="button"
                            aria-label="Undo last input"
                            title={undoTitle}
                            onClick={() => void onUndo()}
                            disabled={undoDisabled}
                          >
                            <span className="material-symbols-outlined small-icon">undo</span>
                          </button>
                          <div className="timestamp">{formatTime(message.createdAt)}</div>
                        </div>
                      ) : (
                        <div className="timestamp">{formatTime(message.createdAt)}</div>
                      )}
                    </div>
                    {message.role === "user" && (
                      <div className={`avatar ${message.role}`}>
                        <span className="material-symbols-outlined">person</span>
                      </div>
                    )}
                  </div>
                  );
                })}
              </div>
            </div>

            <div className="composer-shell">
              <div className="focus-row">
                <span className="focus-label">Start with:</span>
                <span className="focus-chip">Situation</span>
                <span className="focus-chip">Emotion</span>
                <span className="focus-chip">Automatic Thought</span>
              </div>
              <form
                className="composer"
                onSubmit={(event) => {
                  event.preventDefault();
                  void onSend();
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
              <div className="input-note">This tool supports structured self-reflection and does not replace professional care.</div>
            </div>
          </div>
        </div>

        {error && !messages.some((message) => message.text === error) && <div className="error-banner">{error}</div>}

      </div>
    </AppFrame>
  );
}

function DistortionGuide({ items }: { items: DistortionGuideItem[] }) {
  return (
    <details className="distortion-guide">
      <summary>
        <span className="material-symbols-outlined small-icon">help</span>
        Cognitive distortion guide
        <span className="material-symbols-outlined disclosure-icon">expand_more</span>
      </summary>
      <div className="distortion-guide-grid">
        {items.map((item) => (
          <article className="distortion-guide-item" key={item.label}>
            <strong>{item.label}</strong>
            <p>{item.definition}</p>
            <span>{item.example}</span>
          </article>
        ))}
      </div>
    </details>
  );
}

function HomePage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<number | null>(null);
  const [isSessionComplete, setIsSessionComplete] = useState(false);
  const [isLearnOpen, setIsLearnOpen] = useState(false);
  const [recordUrl, setRecordUrl] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [recentRecords, setRecentRecords] = useState<ReportSession[]>([]);
  const [isStarting, setIsStarting] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isUndoing, setIsUndoing] = useState(false);
  const [canUndo, setCanUndo] = useState(false);
  const [undoCount, setUndoCount] = useState(0);
  const [undoLimit, setUndoLimit] = useState(3);
  const [isLoadingRecords, setIsLoadingRecords] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [conversationLlm, setConversationLlm] = useState<LlmMetadata | null>(null);
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
    setCanUndo(false);
    setUndoCount(0);
    setUndoLimit(3);

    try {
      const data = await startSession();
      const settings = await getSettings();
      setSessionId(data.session_id);
      setCurrentStep(data.current_step);
      setConversationLlm({
        provider: settings.llm_provider,
        model: settings.llm_model,
        url: settings.llm_url,
        api_key_env_var: settings.api_key_env_var
      });
      setCanUndo(false);
      setUndoCount(0);
      setUndoLimit(3);
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
      setCanUndo(Boolean(data.can_undo));
      setUndoCount(data.undo_count ?? 0);
      setUndoLimit(data.undo_limit ?? 3);
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

  async function handleUndo() {
    if (!sessionId || !canUndo || isUndoing || isSending) return;

    setIsUndoing(true);
    setError(null);
    try {
      const data = await undoLastInput(sessionId);
      setCurrentStep(data.current_step);
      setIsSessionComplete(data.session_status !== "in_progress");
      setRecordUrl(null);
      setCanUndo(Boolean(data.can_undo));
      setUndoCount(data.undo_count ?? 0);
      setUndoLimit(data.undo_limit ?? 3);
      setMessages(messagesFromHistory(data.chat_history));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not undo the previous input.");
    } finally {
      setIsUndoing(false);
    }
  }

  if (sessionId) {
    return (
      <ThoughtRecordConversation
        sessionId={sessionId}
        currentStep={currentStep}
        llm={conversationLlm}
        messages={messages}
        draft={draft}
        setDraft={setDraft}
        isSending={isSending}
        isSessionComplete={isSessionComplete}
        recordUrl={recordUrl}
        error={error}
        logRef={logRef}
        onSend={handleSend}
        onUndo={handleUndo}
        canUndo={canUndo}
        isUndoing={isUndoing}
        undoCount={undoCount}
        undoLimit={undoLimit}
      />
    );
  }

  return (
    <AppFrame active="welcome">
      <section className="welcome-hero">
        <div className="eyebrow">CBT Thought Record</div>
        <h1 className="hero-title">
          Examine one difficult
          <br />
          moment step by step.
        </h1>
        <button className="hero-learn-link" type="button" onClick={() => setIsLearnOpen(true)}>
          Learn more about CBT thought records
        </button>
        <p className="hero-copy">
          Choose a recent moment when your mood shifted. The guide will help you record what happened, what you felt,
          what went through your mind, and later develop a more balanced response.
        </p>
        <div className="hero-actions">
          <button className="btn-primary" type="button" disabled={!canStart || isStarting} onClick={handleStartSession}>
            <span className="material-symbols-outlined filled">add_circle</span>
            {isStarting ? "Starting..." : "Start Thought Record"}
          </button>
          <a className="btn-secondary" href="/reports">
            <span className="material-symbols-outlined">description</span>
            View Reports
          </a>
        </div>
        <p className="start-note">
          Pick one specific intense moment. You do not need to know exactly what to write.
        </p>
      </section>
      {isLearnOpen && <LearnThoughtRecordDialog onClose={() => setIsLearnOpen(false)} />}

      <div className="feature-visual">
        <div className="feature-content">
          <p className="feature-kicker">During the session</p>
          <div className="feature-steps" aria-label="Thought record session steps">
            <div className="feature-step">
              <span className="step-icon material-symbols-outlined">edit_note</span>
              <p>Describe the moment</p>
            </div>
            <div className="feature-step">
              <span className="step-icon material-symbols-outlined">mood</span>
              <p>Name the emotion</p>
            </div>
            <div className="feature-step">
              <span className="step-icon material-symbols-outlined">psychology</span>
              <p>Notice the thought</p>
            </div>
            <div className="feature-step">
              <span className="step-icon material-symbols-outlined">balance</span>
              <p>Build a balanced response</p>
            </div>
          </div>
          <div className="feature-line"></div>
        </div>
      </div>

      <section className="records-grid">
        <aside className="records-sidebar">
          <h2>Recent Thought Records</h2>
          <p>
            Review completed sessions, compare intensity changes, and open reports generated from local session data.
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
        <div className="footer-pill">Your session and report files are stored locally in the configured project folders.</div>
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
          <a className={`record-card ${idx === 1 ? "is-highlight" : ""}`} href={sessionDetailUrl(item.session_id)} key={item.session_id}>
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

function SessionsPage() {
  const pageSize = 10;
  const initialSessionId = useMemo(() => new URLSearchParams(window.location.search).get("session_id"), []);
  const [sessions, setSessions] = useState<SessionArchiveItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(initialSessionId);
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [page, setPage] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [activeCurrentStep, setActiveCurrentStep] = useState<number | null>(null);
  const [activeMessages, setActiveMessages] = useState<ChatMessage[]>([]);
  const [activeDraft, setActiveDraft] = useState("");
  const [activeRecordUrl, setActiveRecordUrl] = useState<string | null>(null);
  const [isStartingNew, setIsStartingNew] = useState(false);
  const [isSendingActive, setIsSendingActive] = useState(false);
  const [isUndoingActive, setIsUndoingActive] = useState(false);
  const [canUndoActive, setCanUndoActive] = useState(false);
  const [undoCountActive, setUndoCountActive] = useState(0);
  const [undoLimitActive, setUndoLimitActive] = useState(3);
  const [isActiveComplete, setIsActiveComplete] = useState(false);
  const [activeConversationLlm, setActiveConversationLlm] = useState<LlmMetadata | null>(null);
  const activeLogRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    void refreshSessions();
  }, []);

  useEffect(() => {
    activeLogRef.current?.scrollTo({ top: activeLogRef.current.scrollHeight, behavior: "smooth" });
  }, [activeMessages]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    setIsLoadingDetail(true);
    getSession(selectedId)
      .then((data) => setDetail(data))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load session."))
      .finally(() => setIsLoadingDetail(false));
  }, [selectedId]);

  const record = (detail?.thought_record || {}) as ReportItem;
  const totalPages = Math.max(1, Math.ceil(sessions.length / pageSize));
  const pageItems = sessions.slice(page * pageSize, page * pageSize + pageSize);

  function returnToList() {
    setSelectedId(null);
    setDetail(null);
  }

  async function refreshSessions() {
    setIsLoading(true);
    try {
      const data = await listSessions();
      setSessions(data.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sessions.");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleStartNewSession() {
    if (isStartingNew) return;
    setIsStartingNew(true);
    setError(null);
    setSelectedId(null);
    setDetail(null);
    setActiveSessionId(null);
    setActiveCurrentStep(null);
    setActiveMessages([]);
    setActiveDraft("");
    setActiveRecordUrl(null);
    setIsActiveComplete(false);
    setActiveConversationLlm(null);
    setCanUndoActive(false);
    setUndoCountActive(0);
    setUndoLimitActive(3);

    try {
      const data = await startSession();
      const settings = await getSettings();
      setActiveSessionId(data.session_id);
      setActiveCurrentStep(data.current_step);
      setActiveConversationLlm({
        provider: settings.llm_provider,
        model: settings.llm_model,
        url: settings.llm_url,
        api_key_env_var: settings.api_key_env_var
      });
      setCanUndoActive(false);
      setUndoCountActive(0);
      setUndoLimitActive(3);
      setActiveMessages([makeMessage("assistant", data.message)]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to start session.";
      setError(message);
      setActiveMessages([makeMessage("assistant", message)]);
    } finally {
      setIsStartingNew(false);
    }
  }

  async function handleSendActive() {
    const message = activeDraft.trim();
    if (!message || !activeSessionId || isActiveComplete || isSendingActive) return;

    setActiveDraft("");
    setIsSendingActive(true);
    setError(null);
    setActiveMessages((current) => [...current, makeMessage("user", message)]);

    try {
      const data = await sendMessage(activeSessionId, message);
      setActiveCurrentStep(data.current_step);
      setIsActiveComplete(data.session_completed);
      setActiveRecordUrl(data.record_url);
      setCanUndoActive(Boolean(data.can_undo));
      setUndoCountActive(data.undo_count ?? 0);
      setUndoLimitActive(data.undo_limit ?? 3);
      setActiveMessages((current) => [...current, makeMessage("assistant", data.message)]);
      if (data.session_completed) {
        await refreshSessions();
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Error processing message.";
      setError(message);
      setActiveMessages((current) => [...current, makeMessage("assistant", message)]);
    } finally {
      setIsSendingActive(false);
    }
  }

  async function handleResumeSession(sessionId: string) {
    setError(null);
    setSelectedId(null);
    setDetail(null);
    try {
      const data = await resumeSession(sessionId);
      if (data.session_status !== "in_progress") {
        setActiveSessionId(null);
        setActiveCurrentStep(null);
        setActiveMessages([]);
        setActiveDraft("");
        setActiveRecordUrl(null);
        setIsActiveComplete(true);
        setCanUndoActive(Boolean(data.can_undo));
        setUndoCountActive(data.undo_count ?? 0);
        setUndoLimitActive(data.undo_limit ?? 3);
        await refreshSessions();
        setSelectedId(data.session_id);
        return;
      }
      setActiveSessionId(data.session_id);
      setActiveCurrentStep(data.current_step);
      setActiveConversationLlm(data.conversation_llm || null);
      setIsActiveComplete(false);
      setActiveRecordUrl(null);
      setCanUndoActive(Boolean(data.can_undo));
      setUndoCountActive(data.undo_count ?? 0);
      setUndoLimitActive(data.undo_limit ?? 3);
      setActiveDraft("");
      const restoredMessages = messagesFromHistory(data.chat_history);
      setActiveMessages(
        restoredMessages.length
          ? restoredMessages
          : [makeMessage("assistant", "Welcome back. We can continue this thought record from where you left off.")]
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not resume session.");
    }
  }

  async function handleUndoActive() {
    if (!activeSessionId || !canUndoActive || isUndoingActive || isSendingActive) return;

    setIsUndoingActive(true);
    setError(null);
    try {
      const data = await undoLastInput(activeSessionId);
      setActiveCurrentStep(data.current_step);
      setIsActiveComplete(data.session_status !== "in_progress");
      setActiveRecordUrl(null);
      setCanUndoActive(Boolean(data.can_undo));
      setUndoCountActive(data.undo_count ?? 0);
      setUndoLimitActive(data.undo_limit ?? 3);
      setActiveMessages(messagesFromHistory(data.chat_history));
      await refreshSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not undo the previous input.");
    } finally {
      setIsUndoingActive(false);
    }
  }

  async function handleDeleteSession(sessionId: string) {
    const confirmed = window.confirm("Delete this session? This removes the local session JSON. Saved reports will not be deleted.");
    if (!confirmed) return;
    setError(null);
    try {
      await deleteSession(sessionId);
      setSessions((current) => current.filter((item) => item.session_id !== sessionId));
      if (selectedId === sessionId) {
        setSelectedId(null);
        setDetail(null);
      }
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
        setActiveMessages([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete session.");
    }
  }

  if (activeSessionId) {
    return (
      <ThoughtRecordConversation
        sessionId={activeSessionId}
        currentStep={activeCurrentStep}
        llm={activeConversationLlm}
        messages={activeMessages}
        draft={activeDraft}
        setDraft={setActiveDraft}
        isSending={isSendingActive}
        isSessionComplete={isActiveComplete}
        recordUrl={activeRecordUrl}
        error={error}
        logRef={activeLogRef}
        onSend={handleSendActive}
        onUndo={handleUndoActive}
        canUndo={canUndoActive}
        isUndoing={isUndoingActive}
        undoCount={undoCountActive}
        undoLimit={undoLimitActive}
      />
    );
  }

  return (
    <AppFrame active="session">
      <section className="hero report-hero">
        <div>
          <div className="eyebrow">Session Archive</div>
          <h1 className="title">Past Sessions</h1>
          <div className="meta-head">Review completed thought records, resume in-progress sessions, or remove local session files.</div>
        </div>
        <button className="status-pill" type="button" onClick={handleStartNewSession} disabled={isStartingNew}>
          <span className="material-symbols-outlined small-icon">add_circle</span>
          <span>{isStartingNew ? "Starting..." : "New Session"}</span>
        </button>
      </section>

      <div className="session-archive-detail">
        {!selectedId && (
          <section className="session-picker-panel">
            <div className="session-picker-head">
              <div>
                <div className="eyebrow">Local Sessions</div>
                <h2>Choose a Session</h2>
              </div>
              <span>{sessions.length} sessions</span>
            </div>
            <div className="session-picker-list">
              {error && <div className="empty">{error}</div>}
              {isLoading && <div className="empty">Loading sessions...</div>}
              {!isLoading && !sessions.length && <div className="empty">No saved sessions yet.</div>}
              {pageItems.map((item) => (
                <div
                  className="session-picker-row"
                  key={item.session_id}
                  role="button"
                  tabIndex={0}
                  onClick={() => {
                    if (item.session_status === "in_progress") {
                      void handleResumeSession(item.session_id);
                    } else {
                      setSelectedId(item.session_id);
                    }
                  }}
                  onKeyDown={(event) => {
                    if (event.key !== "Enter" && event.key !== " ") return;
                    event.preventDefault();
                    if (item.session_status === "in_progress") {
                      void handleResumeSession(item.session_id);
                    } else {
                      setSelectedId(item.session_id);
                    }
                  }}
                >
                  <div className="session-picker-main">
                    <strong>{buildTitle(item)}</strong>
                    <span>{item.situation || item.automatic_thought || buildSummary(item)}</span>
                  </div>
                  <div className="session-picker-meta">
                    <span>{item.date || item.last_updated || item.session_id}</span>
                    <em>
                      {item.session_status === "in_progress"
                        ? `In progress · Step ${item.current_step ?? "N/A"}`
                        : item.session_status === "stopped"
                          ? "Stopped"
                          : item.intensity_before != null && item.intensity_after != null
                        ? `${item.intensity_before} -> ${item.intensity_after}`
                            : "Completed"}
                    </em>
                  </div>
                  <button
                    className="session-delete-mini"
                    type="button"
                    aria-label={`Delete session ${item.session_id}`}
                    onClick={(event) => {
                      event.stopPropagation();
                      void handleDeleteSession(item.session_id);
                    }}
                  >
                    <span className="material-symbols-outlined small-icon">delete</span>
                  </button>
                  <span className="material-symbols-outlined">chevron_right</span>
                </div>
              ))}
            </div>
            {sessions.length > pageSize && (
              <div className="session-pagination">
                <button
                  type="button"
                  className="button secondary"
                  disabled={page === 0}
                  onClick={() => setPage((current) => Math.max(0, current - 1))}
                >
                  Previous
                </button>
                <span>
                  Page {page + 1} of {totalPages}
                </span>
                <button
                  type="button"
                  className="button secondary"
                  disabled={page >= totalPages - 1}
                  onClick={() => setPage((current) => Math.min(totalPages - 1, current + 1))}
                >
                  Next
                </button>
              </div>
            )}
          </section>
        )}

        {selectedId && (
          <section className="session-record-view">
            {error && <div className="empty">{error}</div>}
            {isLoadingDetail && <div className="empty">Loading session content...</div>}
            {!isLoadingDetail && !detail && <div className="empty">Select a session to review.</div>}
            {detail && (
              <>
                <div className="session-detail-head">
                  <div>
                    <div className="eyebrow">Session {detail.session_id}</div>
                    <h2>{record.emotion || "Thought Record"}</h2>
                    <p>{record.date || detail.last_updated || "Date unavailable"}</p>
                    <p>Conversation LLM: {llmLabel(detail.conversation_llm)}</p>
                  </div>
                  <div className="session-detail-actions">
                    <button className="button secondary" type="button" onClick={returnToList}>
                      Back to Sessions
                    </button>
                    {detail.session_status === "in_progress" && (
                      <button className="button primary" type="button" onClick={() => void handleResumeSession(detail.session_id)}>
                        Resume Session
                      </button>
                    )}
                    {detail.session_status === "completed" && (
                      <a className="button primary" href={`/reports/session/${detail.session_id}`}>
                        Generate Report
                      </a>
                    )}
                    <button className="button danger" type="button" onClick={() => void handleDeleteSession(detail.session_id)}>
                      Delete Session
                    </button>
                  </div>
                </div>

                <div className="stitch-two-col">
                  <StitchInsightCard icon="event_note" title="Situation" body={String(record.situation || "No situation recorded.")} />
                  <StitchInsightCard icon="psychology" title="Automatic Thought" body={String(record.automatic_thought || "No automatic thought recorded.")} tone="soft" />
                </div>
                <div className="stitch-two-col">
                  <StitchListCard icon="checklist" title="Evidence For" items={(record.evidence_for as string[]) || []} />
                  <StitchListCard icon="fact_check" title="Evidence Against" items={(record.evidence_against as string[]) || []} />
                </div>
                <div className="stitch-two-col">
                  <StitchListCard icon="scatter_plot" title="Distortions" items={(record.distortions as string[]) || []} emptyText="None recorded" />
                  <StitchInsightCard icon="balance" title="Balanced Thought" body={String(record.balanced_thought || "No balanced thought recorded.")} tone="filled" />
                </div>
                <StitchInsightCard icon="notes" title="Session Summary" body={String(record.summary || "No session summary recorded.")} />
              </>
            )}
          </section>
        )}
      </div>
    </AppFrame>
  );
}

function ReportsHomePage() {
  const [sessions, setSessions] = useState<ReportSession[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [recentLimit, setRecentLimit] = useState(3);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadReportData() {
      try {
        const sessionData = await listReportSessions();
        setSessions(sessionData.items || []);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to load report data.";
        setError(message);
      } finally {
        setIsLoading(false);
      }
    }

    void loadReportData();
  }, []);

  const rankedDistortions = useMemo(() => distortionStats(sessions), [sessions]);
  const maxDistortionCount = rankedDistortions[0]?.count || 0;

  function toggleSession(sessionId: string) {
    setSelectedIds((current) => (current.includes(sessionId) ? current.filter((id) => id !== sessionId) : [...current, sessionId]));
  }

  return (
    <AppFrame active="reports">
      <section className="hero report-hero">
        <div>
          <div className="eyebrow">Session Archives</div>
          <h1 className="title">Thought Record Reports</h1>
          <div className="meta-head">
            Generate a single-session report or combine completed thought records into a broader summary. Reports are generated from local
            session files.
          </div>
        </div>
        <a className="status-pill" href="/reports/saved">
          <span className="material-symbols-outlined small-icon">folder</span>
          <span>Saved Reports</span>
        </a>
      </section>

      <div className="reports-grid">
        <div className="stack">
          <div className="report-panel">
            <div className="section-title">Recent Report</div>
            <div className="hint">Generate a report for the most recent completed sessions.</div>
            <div className="controls">
              <input
                type="number"
                min="1"
                max="50"
                value={recentLimit}
                onChange={(event) => setRecentLimit(Math.max(1, Math.min(50, Number(event.target.value) || 1)))}
              />
              <a className="button primary" href={`/reports/multi?mode=recent&limit=${recentLimit}`}>
                Generate Report
              </a>
            </div>
          </div>

          <div className="report-panel">
            <div className="section-title">Custom Report</div>
            <div className="hint">Select one or more completed sessions, then generate a combined report.</div>
            <div className="controls">
              <a
                className={`button primary ${selectedIds.length ? "" : "is-disabled"}`}
                href={selectedIds.length ? `/reports/multi?mode=custom&session_ids=${encodeURIComponent(selectedIds.join(","))}` : "#"}
                onClick={(event) => {
                  if (!selectedIds.length) event.preventDefault();
                }}
              >
                {selectedIds.length ? `Generate Report (${selectedIds.length})` : "Generate Report"}
              </a>
            </div>
          </div>

          <div className="report-panel distortion-overview-panel">
            <div className="section-title">Distortion Overview</div>
            <div className="hint">Counts across completed sessions. Only recorded labels are shown.</div>
            {isLoading && <div className="empty">Loading distortion overview...</div>}
            {!isLoading && !rankedDistortions.length && <div className="empty">No recorded distortions yet.</div>}
            {!!rankedDistortions.length && (
              <div className="distortion-ranking">
                {rankedDistortions.map((item, idx) => (
                  <div className="distortion-rank-row" key={item.label}>
                    <span className="distortion-rank-index">{idx + 1}</span>
                    <div className="distortion-rank-main">
                      <div className="distortion-rank-top">
                        <strong>{item.label}</strong>
                        <em>{item.count}</em>
                      </div>
                      <div className="distortion-rank-bar" aria-hidden="true">
                        <span style={{ width: `${Math.max(8, (item.count / maxDistortionCount) * 100)}%` }}></span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
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
                    Generate Report
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

function SavedReportsPage() {
  const [reports, setReports] = useState<SavedReportSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteStatus, setDeleteStatus] = useState("");

  useEffect(() => {
    listSavedReports()
      .then((data) => setReports(data.items || []))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load saved reports."))
      .finally(() => setIsLoading(false));
  }, []);

  async function handleDeleteReport(reportId?: string) {
    if (!reportId) return;
    const confirmed = window.confirm("Delete this saved report? The original session will stay unchanged.");
    if (!confirmed) return;
    setDeleteStatus("Deleting report...");
    try {
      await deleteSavedReport(reportId);
      setReports((current) => current.filter((item) => item.report_id !== reportId));
      setDeleteStatus("Report deleted. The source session was not changed.");
    } catch (err) {
      setDeleteStatus(err instanceof Error ? err.message : "Could not delete report.");
    }
  }

  return (
    <AppFrame active="reports">
      <section className="hero report-hero">
        <div>
          <div className="eyebrow">Local Archive</div>
          <h1 className="title">Saved Reports</h1>
          <div className="meta-head">Reports listed here are loaded from local JSON files and do not regenerate the LLM synthesis.</div>
        </div>
        <a className="status-pill" href="/reports">
          <span className="material-symbols-outlined small-icon">arrow_back</span>
          <span>Back to Reports</span>
        </a>
      </section>

      <div className="saved-report-page-list">
        {error && <div className="empty">{error}</div>}
        {deleteStatus && <div className="empty">{deleteStatus}</div>}
        {isLoading && <div className="empty">Loading saved reports...</div>}
        {!isLoading && !reports.length && <div className="empty">No saved reports yet. Generate a report, then use Save Report.</div>}
        {reports.map((item) => (
          <div className="saved-report-card" key={item.report_id}>
            <a className="saved-report-card-main" href={`/reports/${item.report_id}`}>
              <div className="eyebrow">{item.generated_at || "Saved report"}</div>
              <h2>{savedReportTitle(item)}</h2>
              <p>{savedReportSummary(item)}</p>
            </a>
            <div className="saved-report-card-actions">
              <div className="record-tags">
                <span className="tag tag-emotion">{item.scope?.report_type === "single_session" ? "Single" : "Progress"}</span>
                <span className="tag tag-metric">{item.has_llm_summary ? "Synthesis saved" : "No synthesis"}</span>
              </div>
              <button className="button danger" type="button" onClick={() => handleDeleteReport(item.report_id)}>
                <span className="material-symbols-outlined small-icon">delete</span>
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>
    </AppFrame>
  );
}

function ReportPage({ loader, canSave = true, canDelete = false }: { loader: () => Promise<Report>; canSave?: boolean; canDelete?: boolean }) {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isSaved, setIsSaved] = useState(!canSave);
  const [savedReportId, setSavedReportId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    let isMounted = true;
    loader()
      .then((data) => {
        if (isMounted) {
          setReport(data);
          setSavedReportId(canSave ? null : data.report_id);
        }
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

  async function handleSaveReport() {
    if (!report || isSaving || isSaved) return;
    setIsSaving(true);
    setSaveStatus("Saving report...");
    try {
      const saved = await saveGeneratedReport(report);
      setReport(saved);
      setIsSaved(true);
      setSavedReportId(saved.report_id);
      setSaveStatus(`Saved report ${saved.report_id}. You can reopen it from Saved Reports.`);
    } catch (err) {
      setSaveStatus(err instanceof Error ? err.message : "Could not save report.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDeleteReport() {
    if (!report || isDeleting) return;
    const confirmed = window.confirm("Delete this saved report? The original session will stay unchanged.");
    if (!confirmed) return;
    setIsDeleting(true);
    setSaveStatus("Deleting saved report...");
    try {
      await deleteSavedReport(report.report_id);
      window.location.assign("/reports/saved");
    } catch (err) {
      setSaveStatus(err instanceof Error ? err.message : "Could not delete report.");
      setIsDeleting(false);
    }
  }

  const saveControl = (
    <ReportSaveBar
      canSave={canSave}
      isSaved={isSaved}
      savedReportId={savedReportId}
      onSave={canSave ? handleSaveReport : undefined}
      onDelete={canDelete ? handleDeleteReport : undefined}
      isSaving={isSaving}
      isDeleting={isDeleting}
      status={saveStatus}
    />
  );

  return report.scope.report_type === "single_session" ? (
    <StitchSingleReportPage report={report} saveControl={saveControl} />
  ) : (
    <StitchMultiReportPage report={report} saveControl={saveControl} />
  );
}

function ReportSaveBar({
  canSave,
  isSaved,
  savedReportId,
  onSave,
  onDelete,
  isSaving = false,
  isDeleting = false,
  status = ""
}: {
  canSave: boolean;
  isSaved: boolean;
  savedReportId?: string | null;
  onSave?: () => void;
  onDelete?: () => void;
  isSaving?: boolean;
  isDeleting?: boolean;
  status?: string;
}) {
  const message = status || (canSave ? "This generated report is not saved yet." : "This report was loaded from saved reports. Deleting it will not change the original session.");
  return (
    <div className="report-save-bar">
      <div>
        <strong>{canSave ? "Generated Report Preview" : "Saved Report"}</strong>
        <span>{message}</span>
      </div>
      <div className="report-save-actions">
        <a className="button" href="/reports">
          <span className="material-symbols-outlined small-icon">arrow_back</span>
          Back to Reports
        </a>
        {isSaved && savedReportId && canSave && (
          <a className="button" href={`/reports/${savedReportId}`}>
            <span className="material-symbols-outlined small-icon">folder_open</span>
            View Saved
          </a>
        )}
        {onSave && (
          <button className="button primary" type="button" onClick={onSave} disabled={isSaving || isSaved}>
            <span className="material-symbols-outlined small-icon">{isSaved ? "check_circle" : "save"}</span>
            {isSaved ? "Saved" : isSaving ? "Saving" : "Save Report"}
          </button>
        )}
        {onDelete && (
          <button className="button danger" type="button" onClick={onDelete} disabled={isDeleting}>
            <span className="material-symbols-outlined small-icon">delete</span>
            {isDeleting ? "Deleting" : "Delete Report"}
          </button>
        )}
      </div>
    </div>
  );
}

function StitchSingleReportPage({ report, saveControl }: { report: Report; saveControl: React.ReactNode }) {
  const item = report.sessions[0] || {};
  const before = report.metrics.intensity_before ?? item.intensity_before ?? null;
  const after = report.metrics.intensity_after ?? item.intensity_after ?? null;
  const generatedSummary = generatedReportText(report);
  const actionItems = reportActionItems(report);
  const reportLlm = llmLabel(report.report_llm);

  return (
    <AppFrame active="reports">
      <StitchReportHeader
        eyebrow="Session Archive"
        title="Session Reflection Report"
        subtitle={`Session ${item.session_id || ""} · Generated at ${report.generated_at} · Report LLM: ${reportLlm}`}
        status="Single Session"
      />
      {saveControl}

      <section className="stitch-bento-grid">
        <StitchReframePathCard item={item} before={before} after={after} />
        <div className="stitch-summary-column">
          <StitchSynthesisCard body={generatedSummary} />
          <StitchActionItems items={actionItems} />
        </div>
      </section>

      <section className="stitch-detail-section">
        <div className="stitch-section-heading">
          <div>
            <div className="eyebrow">Thought Record</div>
            <h2>Session Details</h2>
          </div>
        </div>
        <div className="stitch-two-col">
          <StitchInsightCard icon="event_note" title="Situation" body={item.situation || "No situation text was recorded."} />
          <StitchInsightCard icon="psychology" title="Automatic Thought" body={item.automatic_thought || "No automatic thought was recorded."} tone="soft" />
        </div>
        <div className="stitch-two-col">
          <StitchListCard icon="checklist" title="Evidence For" items={item.evidence_for || []} />
          <StitchListCard icon="fact_check" title="Evidence Against" items={item.evidence_against || []} />
        </div>
        <div className="stitch-two-col">
          <StitchListCard icon="scatter_plot" title="Distortions" items={item.distortions || []} emptyText="None recorded" />
          <StitchInsightCard icon="balance" title="Balanced Thought" body={item.balanced_thought || "No balanced thought was recorded."} tone="filled" />
        </div>
        <StitchInsightCard icon="notes" title="Session Summary" body={item.summary || "No session summary was recorded."} />
      </section>
    </AppFrame>
  );
}

function StitchMultiReportPage({ report, saveControl }: { report: Report; saveControl: React.ReactNode }) {
  const scope = report.scope || {};
  const metrics = report.metrics || {};
  const sessionCount = metrics.total_sessions_in_scope ?? report.sessions.length;
  const generatedSummary = generatedReportText(report);
  const actionItems = reportActionItems(report);
  const reportLlm = llmLabel(report.report_llm);

  return (
    <AppFrame active="reports">
      <StitchReportHeader
        eyebrow="Session Archives"
        title="Pattern Insight Report"
        subtitle={`Report ID ${report.report_id} · Generated at ${report.generated_at} · Report LLM: ${reportLlm}`}
        status={`${sessionCount} Sessions`}
      />
      {saveControl}

      <section className="stitch-bento-grid">
        <StitchProgressOverviewCard report={report} />
        <div className="stitch-summary-column">
          <StitchSynthesisCard body={generatedSummary} />
          <StitchActionItems items={actionItems} />
        </div>
      </section>

      <section className="stitch-detail-section">
        <div className="stitch-section-heading">
          <div>
            <div className="eyebrow">Report Data</div>
            <h2>Patterns and Records</h2>
          </div>
          <div className="stitch-scope-box compact">
            <div className="label">Date Range</div>
            <p>{scope.date_range?.start || "N/A"} to {scope.date_range?.end || "N/A"}</p>
          </div>
        </div>
        <div className="stitch-two-col">
          <StitchDistributionCard title="Common Distortions" items={metrics.top_distortions || []} />
          <StitchDistributionCard title="Common Emotions" items={metrics.top_emotions || []} />
        </div>
        <div className="stitch-session-list">
          {newestFirst(report.sessions).map((item, idx) => (
            <StitchSessionCard item={item} key={item.session_id} index={idx} />
          ))}
        </div>
      </section>
    </AppFrame>
  );
}

function StitchReportHeader({ eyebrow, title, subtitle, status }: { eyebrow: string; title: string; subtitle: string; status: string }) {
  return (
    <section className="stitch-report-hero">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      <div className="stitch-status-pill">
        <span className="material-symbols-outlined small-icon">verified</span>
        {status}
      </div>
    </section>
  );
}

function StitchReframePathCard({ item, before, after }: { item: ReportItem; before: number | null; after: number | null }) {
  const delta = item.intensity_delta ?? (before != null && after != null ? after - before : null);
  const pathItems = [
    { icon: "event_note", label: "Situation", body: item.situation || "No situation text was recorded." },
    { icon: "psychology", label: "Automatic Thought", body: item.automatic_thought || "No automatic thought was recorded." },
    { icon: "scatter_plot", label: "Distortion Focus", body: (item.distortions || []).join(", ") || "No distortion was recorded." },
    { icon: "balance", label: "Balanced Thought", body: item.balanced_thought || "No balanced thought was recorded." }
  ];

  return (
    <article className="stitch-reframe-card">
      <div className="stitch-reframe-head">
        <div>
          <h3>Thought Reframe Path</h3>
          <p>The core CBT movement from the original situation and thought toward a more balanced response.</p>
        </div>
        <div className="stitch-shift-pill">
          <span>{before != null && after != null ? `${before} -> ${after}` : "Recorded"}</span>
          <strong>{changeText(delta)}</strong>
        </div>
      </div>
      <div className="stitch-reframe-path">
        {pathItems.map((pathItem, idx) => (
          <div className="stitch-path-item" key={pathItem.label}>
            <div className="stitch-path-icon">
              <span className="material-symbols-outlined">{pathItem.icon}</span>
            </div>
            <div>
              <div className="detail-title">{pathItem.label}</div>
              <p>{pathItem.body}</p>
            </div>
            {idx < pathItems.length - 1 && <div className="stitch-path-line"></div>}
          </div>
        ))}
      </div>
      <div className="stitch-chip-cloud">
        {[item.emotion || "Reflection", ...(item.distortions || [])].filter(Boolean).map((chip, idx) => (
          <span key={`${chip}-${idx}`}>{chip}</span>
        ))}
      </div>
    </article>
  );
}

function StitchProgressOverviewCard({ report }: { report: Report }) {
  const metrics = report.metrics || {};
  const sessions = newestFirst(report.sessions).slice(0, 6);
  const sessionCount = metrics.total_sessions_in_scope ?? report.sessions.length;

  return (
    <article className="stitch-progress-overview-card">
      <div className="stitch-reframe-head">
        <div>
          <h3>Progress Overview</h3>
          <p>A clearer view of emotional movement and repeated patterns across the selected thought records.</p>
        </div>
      </div>
      <div className="stitch-overview-stats">
        <div>
          <span className="label">Sessions</span>
          <strong>{sessionCount}</strong>
        </div>
        <div>
          <span className="label">Improved</span>
          <strong>{metrics.improved_sessions ?? 0}</strong>
        </div>
        <div>
          <span className="label">Average Change</span>
          <strong>{changeText(metrics.average_intensity_delta)}</strong>
        </div>
      </div>
      <div className="stitch-mini-trend">
        {sessions.map((item) => {
          const before = item.intensity_before ?? 0;
          const after = item.intensity_after ?? 0;
          return (
            <a className="stitch-trend-row" href={sessionDetailUrl(item.session_id)} key={item.session_id}>
              <div>
                <strong>{item.emotion || "Reflection"}</strong>
                <span>{formatDate(item.date)}</span>
              </div>
              <div className="stitch-trend-bars" aria-label={`Intensity ${before} to ${after}`}>
                <span style={{ width: `${Math.max(3, Math.min(100, before))}%` }}></span>
                <span style={{ width: `${Math.max(3, Math.min(100, after))}%` }}></span>
              </div>
              <em>{before} to {after}</em>
            </a>
          );
        })}
      </div>
      <div className="stitch-chip-cloud">
        {(metrics.top_distortions || []).slice(0, 4).map((item, idx) => (
          <span key={`${item.label}-${idx}`}>{item.label || "Distortion"} · {item.count ?? 0}</span>
        ))}
      </div>
    </article>
  );
}

function StitchSynthesisCard({ body }: { body: string }) {
  return (
    <article className="stitch-synthesis-card">
      <div className="stitch-card-title-row">
        <span className="material-symbols-outlined">auto_awesome</span>
        <h3>Synthesis</h3>
      </div>
      <p>{body}</p>
    </article>
  );
}

function StitchActionItems({ items }: { items: string[] }) {
  return (
    <article className="stitch-action-card">
      <h4>Key Practice Items</h4>
      <ul>
        {items.map((item, idx) => (
          <li key={`${item}-${idx}`}>
            <span className="stitch-check">
              <span className="material-symbols-outlined">check</span>
            </span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </article>
  );
}

function StitchMetricPanel({ title, metric, detail }: { title: string; metric: string; detail: string }) {
  return (
    <div className="stitch-metric-panel">
      <div className="label">{title}</div>
      <div className="stitch-metric-value">{metric}</div>
      <p>{detail}</p>
    </div>
  );
}

function StitchProgress({ label, value }: { label: string; value: number | null }) {
  const normalized = value == null ? 0 : Math.max(0, Math.min(100, value * 10));
  return (
    <div className="stitch-progress">
      <div className="stitch-progress-row">
        <span>{label}</span>
        <strong>{value ?? "N/A"}</strong>
      </div>
      <div className="streak-track">
        <div className="streak-fill" style={{ width: `${normalized}%` }}></div>
      </div>
    </div>
  );
}

function StitchInsightCard({ icon, title, body, tone = "plain" }: { icon: string; title: string; body: string; tone?: "plain" | "soft" | "filled" }) {
  return (
    <article className={`stitch-insight-card ${tone}`}>
      <div className="stitch-card-icon">
        <span className="material-symbols-outlined">{icon}</span>
      </div>
      <div>
        <div className="detail-title">{title}</div>
        <p>{body}</p>
      </div>
    </article>
  );
}

function StitchListCard({ icon, title, items, emptyText = "None" }: { icon: string; title: string; items: string[]; emptyText?: string }) {
  return (
    <article className="stitch-insight-card">
      <div className="stitch-card-icon">
        <span className="material-symbols-outlined">{icon}</span>
      </div>
      <div>
        <div className="detail-title">{title}</div>
        <ul>{items.length ? items.map((item, idx) => <li key={`${item}-${idx}`}>{item}</li>) : <li>{emptyText}</li>}</ul>
      </div>
    </article>
  );
}

function StitchDistributionCard({ title, items }: { title: string; items: { label?: string; count?: number; percentage?: number }[] }) {
  return (
    <article className="stitch-distribution-card">
      <div className="detail-title">{title}</div>
      <div className="stitch-chip-cloud">
        {items.length ? (
          items.map((item, idx) => (
            <span key={`${title}-${item.label}-${idx}`}>
              {item.label || "Unknown"} · {item.count ?? 0}
            </span>
          ))
        ) : (
          <span>None recorded</span>
        )}
      </div>
    </article>
  );
}

function StitchSessionCard({ item, index }: { item: ReportItem; index: number }) {
  return (
    <a className={`stitch-session-card ${index === 1 ? "is-highlight" : ""}`} href={sessionDetailUrl(item.session_id)}>
      <div className="record-icon">
        <span className="material-symbols-outlined">{index === 1 ? "spa" : index === 2 ? "edit_note" : "cloud_queue"}</span>
      </div>
      <div className="record-body">
        <div className="record-top">
          <span className="record-date">{formatDate(item.date)}</span>
          <div className="record-tags">
            <span className="tag tag-emotion">{item.emotion || "Reflection"}</span>
            <span className="tag tag-metric">
              {item.intensity_before != null && item.intensity_after != null ? `${item.intensity_before} -> ${item.intensity_after}` : "Completed"}
            </span>
          </div>
        </div>
        <h3 className="record-title">{buildTitle(item)}</h3>
        <p className="record-copy">{item.balanced_thought || buildSummary(item)}</p>
      </div>
      <div className="record-arrow">
        <span className="material-symbols-outlined">arrow_forward_ios</span>
      </div>
    </a>
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
    <a className="session-card" href={sessionDetailUrl(item.session_id)}>
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
        View session <span className="material-symbols-outlined small-icon">arrow_forward</span>
      </div>
    </a>
  );
}

export default function App() {
  const path = window.location.pathname;
  const search = new URLSearchParams(window.location.search);

  if (path === "/sessions") {
    return <SessionsPage />;
  }

  if (path === "/reports") {
    return <ReportsHomePage />;
  }

  if (path === "/reports/saved") {
    return <SavedReportsPage />;
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
    return <ReportPage loader={() => getSavedReport(reportId)} canSave={false} canDelete />;
  }

  return <HomePage />;
}
