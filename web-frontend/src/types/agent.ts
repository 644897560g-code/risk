/** Agent / Orchestrator types */

export interface OrchestratorStatus {
  status: string;
  current_step: string;
  completed_steps: string[];
  start_time?: string;
  end_time?: string;
  error?: string;
  accumulated_passed: number;
  latest_version: string;
}

export interface PendingTemplate {
  template_id: string;
  template_name: string;
  dimension: string;
  dsl: string;
  parameter_space: Record<string, unknown>;
  python_function: string;
  python_code?: string;
  _promotion_status: string;
  [key: string]: unknown;
}

export interface FeatureReviewResult {
  syntax_check?: { passed: boolean; errors: string[] };
  logic_check?: { passed: boolean; errors: string[] };
  llm_review?: { passed: boolean; score: number; issues: string[]; suggestions: string[] };
  overall_passed?: boolean;
  human_confirmed?: boolean | null;
  final_passed?: boolean;
  rejection_reason?: string;
  [key: string]: unknown;
}

/** Chat message type for Agent Chat page */
export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  tool_call?: {
    tool: string;
    status: string;
    detail: string;
  };
  timestamp?: string;
}

/** Chat session summary (from list endpoint) */
export interface ChatSessionSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  last_message?: string;
  last_role?: string;
}

/** Chat session with full messages (from get endpoint) */
export interface ChatSessionDetail extends ChatSessionSummary {
  messages: ChatMessageDB[];
}

/** Raw message from DB */
export interface ChatMessageDB {
  id: number;
  role: string;
  content: string;
  tool_call?: { tool: string; status: string; detail: string } | null;
  created_at: string;
}

export interface SystemHealth {
  status: string;
  database: string;
  celery_available: boolean;
  version: string;
  uptime: string;
}
