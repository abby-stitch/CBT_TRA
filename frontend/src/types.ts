export type ThoughtRecord = Record<string, unknown>;

export type ChatRole = "assistant" | "user";

export type ChatMessage = {
  id: string;
  role: ChatRole;
  text: string;
  createdAt: string;
};

export type StartResponse = {
  session_id: string;
  message: string;
  current_step: number;
  thought_record: ThoughtRecord;
};

export type MessageResponse = {
  session_id: string;
  message: string;
  current_step: number;
  step_completed: boolean;
  session_completed: boolean;
  record_url: string | null;
  thought_record: ThoughtRecord;
};

export type ReportSession = {
  session_id: string;
  date?: string;
  emotion?: string;
  intensity_before?: number | null;
  intensity_after?: number | null;
  intensity_delta?: number | null;
  distortions?: string[];
  balanced_thought?: string;
};

export type ReportSessionsResponse = {
  items: ReportSession[];
  total: number;
};

export type ReportScope = {
  mode?: string;
  requested_limit?: number | null;
  session_ids?: string[];
  report_type?: "single_session" | "multi_session";
  date_range?: {
    start?: string;
    end?: string;
  };
};

export type DistributionItem = {
  label?: string;
  count?: number;
  percentage?: number;
};

export type ReportMetrics = {
  intensity_before?: number | null;
  intensity_after?: number | null;
  intensity_delta?: number | null;
  total_sessions_in_scope?: number;
  improved_sessions?: number;
  average_intensity_delta?: number | null;
  top_distortions?: DistributionItem[];
  top_emotions?: DistributionItem[];
};

export type ReportItem = ReportSession & {
  situation?: string;
  automatic_thought?: string;
  evidence_for?: string[];
  evidence_against?: string[];
  summary?: string;
  session_report_url?: string;
};

export type Report = {
  report_id: string;
  generated_at: string;
  scope: ReportScope;
  metrics: ReportMetrics;
  sessions: ReportItem[];
  llm_summary: string | null;
  llm_error: string | null;
};
