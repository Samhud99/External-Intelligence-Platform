export interface Job {
  id: string;
  name: string;
  target_url: string;
  schedule: string;
  status: string;
  created_at: string;
  consecutive_failures?: number;
}

export interface ExtractionConfig {
  job_id: string;
  strategy: string;
  tier?: string;
  selectors: Record<string, string>;
  base_url: string;
  playwright_actions?: Record<string, unknown>[];
}

export interface JobDetail {
  job: Job;
  config: ExtractionConfig | null;
}

export interface RunResult {
  run_id: string;
  job_id: string;
  ran_at: string;
  runner_type: string;
  items: ResultItem[];
  items_total: number;
  items_new: number;
  success: boolean;
}

export interface ResultItem {
  title?: string;
  url?: string;
  is_new?: boolean;
  [key: string]: unknown;
}

export interface CreateSessionResponse {
  session_id: string;
}

export interface NextStep {
  type: string;
  label: string;
}

export interface AgentEvent {
  type: string;
  message?: string;
  url?: string;
  title?: string;
  content_length?: number;
  selectors?: Record<string, string>;
  sample_items?: Record<string, unknown>[];
  count?: number;
  job?: Record<string, unknown>;
  config?: Record<string, unknown>;
  sample_data?: Record<string, unknown>[];
  status?: string;
  current_tier?: string;
  proposed_tier?: string;
  failure_code?: string;
  user_message?: string;
  next_steps?: NextStep[];
  technical_details?: Record<string, unknown>;
}
