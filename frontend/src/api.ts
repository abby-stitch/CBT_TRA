import type { MessageResponse, Report, ReportSessionsResponse, StartResponse } from "./types";

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
