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

export type SavedReportSummary = {
  report_id?: string;
  generated_at?: string;
  scope?: ReportScope;
  sessions_count?: number;
  has_llm_summary?: boolean;
};

export type SavedReportsResponse = {
  items: SavedReportSummary[];
  total: number;
};

export type DeleteReportResponse = {
  ok: boolean;
  report_id: string;
};

export type LlmMetadata = {
  provider?: string;
  model?: string;
  url?: string;
  api_key_env_var?: string;
};

export type SessionArchiveItem = ReportSession & {
  last_updated?: string;
  current_step?: number;
  session_status?: string;
  situation?: string | null;
  automatic_thought?: string | null;
};

export type SessionArchiveResponse = {
  items: SessionArchiveItem[];
  total: number;
};

export type SessionDetail = {
  session_id: string;
  last_updated?: string;
  current_step?: number;
  session_status?: string;
  conversation_llm?: LlmMetadata;
  thought_record?: ReportItem;
  chat_history?: Array<{ role?: string; content?: string }>;
  turns?: Array<Record<string, unknown>>;
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
  average_intensity_before?: number | null;
  average_intensity_after?: number | null;
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
  llm_action_items?: string[];
  llm_error: string | null;
  profile_context_used?: boolean;
  report_llm?: LlmMetadata;
};

export type AppSettings = {
  llm_provider: string;
  llm_url: string;
  llm_model: string;
  api_key_env_var: string;
  sessions_dir: string;
  reports_dir: string;
  user_context: string;
};
