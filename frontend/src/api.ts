import type {
  AppSettings,
  DeleteReportResponse,
  DeleteSessionResponse,
  MessageResponse,
  Report,
  ReportSessionsResponse,
  ResumeSessionResponse,
  SavedReportsResponse,
  SessionArchiveResponse,
  SessionDetail,
  StartResponse
} from "./types";

async function requestJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers
    },
    ...options
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      const text = await response.text();
      message = text || message;
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export function startSession(): Promise<StartResponse> {
  return requestJson<StartResponse>("/api/start", { method: "POST" });
}

export function sendMessage(sessionId: string, message: string): Promise<MessageResponse> {
  return requestJson<MessageResponse>("/api/message", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      message
    })
  });
}

export function listReportSessions(): Promise<ReportSessionsResponse> {
  return requestJson<ReportSessionsResponse>("/api/report-sessions");
}

export function listSessions(): Promise<SessionArchiveResponse> {
  return requestJson<SessionArchiveResponse>("/api/sessions");
}

export function getSession(sessionId: string): Promise<SessionDetail> {
  return requestJson<SessionDetail>(`/api/sessions/${encodeURIComponent(sessionId)}`);
}

export function resumeSession(sessionId: string): Promise<ResumeSessionResponse> {
  return requestJson<ResumeSessionResponse>(`/api/sessions/${encodeURIComponent(sessionId)}/resume`, {
    method: "POST"
  });
}

export function deleteSession(sessionId: string): Promise<DeleteSessionResponse> {
  return requestJson<DeleteSessionResponse>(`/api/sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE"
  });
}

export function getSingleSessionReport(sessionId: string): Promise<Report> {
  return requestJson<Report>(`/api/reports/session/${encodeURIComponent(sessionId)}`);
}

export function getMultiSessionReport(mode: string, limit: number, sessionIds: string[]): Promise<Report> {
  const params = new URLSearchParams({ mode, limit: String(limit) });
  if (mode === "custom") {
    params.set("session_ids", sessionIds.join(","));
  }
  return requestJson<Report>(`/api/reports/multi?${params.toString()}`);
}

export function getSavedReport(reportId: string): Promise<Report> {
  return requestJson<Report>(`/api/reports/${encodeURIComponent(reportId)}`);
}

export function listSavedReports(): Promise<SavedReportsResponse> {
  return requestJson<SavedReportsResponse>("/api/reports");
}

export function saveGeneratedReport(report: Report): Promise<Report> {
  return requestJson<Report>("/api/reports/save", {
    method: "POST",
    body: JSON.stringify(report)
  });
}

export function deleteSavedReport(reportId: string): Promise<DeleteReportResponse> {
  return requestJson<DeleteReportResponse>(`/api/reports/${encodeURIComponent(reportId)}`, {
    method: "DELETE"
  });
}

export function getSettings(): Promise<AppSettings> {
  return requestJson<AppSettings>("/api/settings");
}

export function updateSettings(settings: AppSettings): Promise<AppSettings> {
  return requestJson<AppSettings>("/api/settings", {
    method: "PUT",
    body: JSON.stringify(settings)
  });
}
