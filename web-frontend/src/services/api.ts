import axios from 'axios';
import type { Task, TaskListResponse, TaskResultResponse, CreateTaskRequest } from '@/types/task';
import type { FeatureVersion, FeatureMetric, TopFeature } from '@/types/feature';
import type { SystemHealth, OrchestratorStatus, PendingTemplate, FeatureReviewResult } from '@/types/agent';
import type { KnowledgeStats, KnowledgePreview } from '@/types/knowledge';

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: attach JWT token from localStorage
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: handle 401 — redirect to login
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_username');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ---- Tasks ----

export async function fetchTasks(skip = 0, limit = 50): Promise<TaskListResponse> {
  const { data } = await api.get('/tasks', { params: { skip, limit } });
  return data;
}

export async function fetchTask(id: number): Promise<Task> {
  const { data } = await api.get(`/tasks/${id}`);
  return data;
}

export async function fetchTaskResult(id: number): Promise<TaskResultResponse> {
  const { data } = await api.get(`/tasks/${id}/result`);
  return data;
}

export async function fetchTaskSamples(id: number, limit = 5): Promise<{ items: any[]; total: number }> {
  const { data } = await api.get(`/tasks/${id}/samples`, { params: { limit } });
  return data;
}

export async function downloadTaskDeployment(id: number): Promise<Blob> {
  const { data } = await api.get(`/tasks/${id}/deployment`, {
    responseType: 'blob',
  });
  return data;
}

export async function downloadTaskResultCsv(id: number): Promise<Blob> {
  const { data } = await api.get(`/tasks/${id}/result/csv`, {
    responseType: 'blob',
  });
  return data;
}

export async function downloadTaskResultReport(id: number): Promise<Blob> {
  const { data } = await api.get(`/tasks/${id}/result/report`, {
    responseType: 'blob',
  });
  return data;
}

export async function createTask(req: CreateTaskRequest): Promise<Task> {
  const form = new FormData();
  if (req.name) form.append('name', req.name);
  if (req.mode) form.append('mode', req.mode);
  if (req.scheduled_at) form.append('scheduled_at', req.scheduled_at);
  if (req.recurring_cron) form.append('recurring_cron', req.recurring_cron);
  if (req.url_file) form.append('url_file', req.url_file);
  if (req.label_file) form.append('label_file', req.label_file);
  if (req.url_path) form.append('url_path', req.url_path);
  if (req.label_path) form.append('label_path', req.label_path);
  const { data } = await api.post('/tasks', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export interface TaskStep {
  name: string;
  label: string;
  status: 'wait' | 'process' | 'finish' | 'error';
  message: string;
}

export async function fetchTaskSteps(taskId: number): Promise<{ steps: TaskStep[]; task_status: string }> {
  const { data } = await api.get(`/tasks/${taskId}/steps`);
  return data;
}

export async function cancelTask(taskId: number): Promise<{ status: string; task_id: number }> {
  const { data } = await api.post(`/tasks/${taskId}/cancel`);
  return data;
}

export async function resumeTask(taskId: number): Promise<{ status: string; task_id: number }> {
  const { data } = await api.post(`/tasks/${taskId}/resume`);
  return data;
}

export async function rerunTask(taskId: number): Promise<{ status: string; task_id: number }> {
  const { data } = await api.post(`/tasks/${taskId}/rerun`);
  return data;
}

export async function runOrchestrator(): Promise<{ task_id: number; status: string }> {
  const { data } = await api.post('/agents/orchestrator/run');
  return data;
}

export async function fetchOrchestratorStatus(): Promise<OrchestratorStatus> {
  const { data } = await api.get('/agents/orchestrator/status');
  return data;
}

export async function fetchOrchestratorLogs(lines = 50): Promise<string[]> {
  const { data } = await api.get('/agents/orchestrator/logs', { params: { lines } });
  return data.lines;
}

// ---- Reviews: Channel 2 templates ----

export async function fetchPendingChannel2Templates(): Promise<PendingTemplate[]> {
  const { data } = await api.get('/agents/reviews/channel2-pending');
  return data.items;
}

export async function approveChannel2Template(templateId: string): Promise<void> {
  await api.post(`/agents/reviews/channel2-pending/${templateId}/approve`);
}

export async function rejectChannel2Template(templateId: string, reason = ''): Promise<void> {
  await api.post(`/agents/reviews/channel2-pending/${templateId}/reject`, { reason });
}

// ---- Reviews: Feature review ----

export async function fetchFeatureReview(): Promise<{ exists: boolean; review: FeatureReviewResult | null }> {
  const { data } = await api.get('/agents/reviews/feature-review');
  return data;
}

export async function confirmFeatureReview(): Promise<void> {
  await api.post('/agents/reviews/feature-review/confirm');
}

export async function rejectFeatureReview(reason = ''): Promise<void> {
  await api.post('/agents/reviews/feature-review/reject', { reason });
}

// ---- Features ----

export async function fetchFeatureVersions(): Promise<FeatureVersion[]> {
  const { data } = await api.get('/features/versions');
  return data.items || [];
}

export async function fetchFeatureMetrics(version: string): Promise<FeatureMetric[]> {
  const { data } = await api.get(`/features/versions/${version}`);
  return data.items || [];
}

export async function fetchFeatureReportUrl(version: string): Promise<string> {
  const { data } = await api.get(`/features/versions/${version}/report`);
  return data.report_url;
}

export async function fetchTopFeatures(): Promise<TopFeature[]> {
  const { data } = await api.get('/features/top');
  return data.items || [];
}

export async function fetchFeatureStats(): Promise<{
  current_total: number;
  current_passed: number;
  accumulated_passed: number;
  latest_version: string;
}> {
  const { data } = await api.get('/features/stats');
  return data;
}

// ---- Feature Compute ----

export interface ComputeResult {
  order_id: string;
  features: Record<string, number>;
  processing_time_ms: number;
  error?: string;
}

export interface ComputeResponse {
  total: number;
  results: ComputeResult[];
}

export async function computeFeatures(samples: Record<string, unknown>[]): Promise<ComputeResponse> {
  const { data } = await api.post('/features/compute', { samples });
  return data;
}

// ---- Health ----

export async function fetchHealth(): Promise<SystemHealth> {
  const { data } = await api.get('/health');
  return data;
}

// ---- Knowledge ----

export interface KnowledgeItem {
  id: string;
  filename: string;
  size: number;
  uploaded_at: string;
  category: string;
  tags?: string[];
}

export async function fetchKnowledgeList(category?: string): Promise<KnowledgeItem[]> {
  const { data } = await api.get('/knowledge', { params: { category } });
  return data.items || [];
}

export async function uploadKnowledge(file: File): Promise<{ status: string; item: KnowledgeItem }> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post('/knowledge/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function deleteKnowledge(filename: string): Promise<void> {
  await api.delete(`/knowledge/${encodeURIComponent(filename)}`);
}

export async function fetchKnowledgeStats(): Promise<KnowledgeStats> {
  const { data } = await api.get('/knowledge/stats');
  return data;
}

export async function fetchKnowledgePreview(filename: string, lines = 100): Promise<KnowledgePreview> {
  const { data } = await api.get(`/knowledge/${encodeURIComponent(filename)}/preview`, { params: { lines } });
  return data;
}

export async function updateKnowledgeTags(filename: string, tags: string[]): Promise<void> {
  await api.post(`/knowledge/${encodeURIComponent(filename)}/tags`, { tags });
}


// ---- Templates ----

export interface Channel1Template {
  template_id: string;
  template_name?: string;
  dimension: string;
  description: string;
  dsl: string;
  python_function: string;
  python_code?: string;
  /** @deprecated use template_name */
  name?: string;
}

export interface PendingTemplateItem {
  template_id: string;
  template_name?: string;
  dimension: string;
  description: string;
  iv?: number;
  psi?: number;
  coverage?: number;
  dsl?: string;
  python_function?: string;
  python_code?: string;
  created_at?: string;
  source?: string;
  /** @deprecated use template_name */
  name?: string;
}

export async function fetchChannel1Templates(): Promise<Channel1Template[]> {
  const { data } = await api.get('/templates/channel1');
  return data.items || [];
}

export async function fetchChannel2PendingTemplates(): Promise<PendingTemplateItem[]> {
  const { data } = await api.get('/templates/channel2-pending');
  return data.items || [];
}

export async function fetchChannel1TemplateCode(templateId: string): Promise<string> {
  const { data } = await api.get(`/templates/channel1/${templateId}/code`);
  return data.code || '';
}

export async function clearAllTasks(): Promise<{ status: string; deleted: number }> {
  const { data } = await api.delete('/tasks');
  return data;
}

export default api;

// ---- Auth ----

export interface LoginResponse {
  access_token: string;
  token_type: string;
  username: string;
}

export interface UserInfo {
  id: number;
  username: string;
  is_active: boolean;
  created_at: string | null;
  last_login_at: string | null;
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const { data } = await api.post('/auth/login', { username, password });
  return data;
}

export async function register(username: string, password: string): Promise<UserInfo> {
  const { data } = await api.post('/auth/register', { username, password });
  return data;
}

export async function fetchMe(): Promise<UserInfo> {
  const { data } = await api.get('/auth/me');
  return data;
}

// ---- Agent Chat ----

export interface ChatResponse {
  reply: string;
  tool_call: { tool: string; status: string; detail: string } | null;
  conversation_id: string;
}

export async function sendChatMessage(message: string, conversationId?: string): Promise<ChatResponse> {
  const { data } = await api.post('/agents/chat', { message, conversation_id: conversationId });
  return data;
}

/** SSE stream callback types */
export interface StreamEvents {
  onMeta?: (conversationId: string) => void;
  onChunk: (text: string) => void;
  onToolCall: (tool: string, status: string, detail: string) => void;
  onDone: (fullText: string) => void;
  onError: (error: string) => void;
}

/**
 * Send chat message via SSE streaming.
 * Returns the conversation_id once connected.
 */
export function sendChatMessageStream(
  message: string,
  events: StreamEvents,
  conversationId?: string,
): AbortController {
  const controller = new AbortController();
  const token = localStorage.getItem('auth_token');

  fetch('/api/agents/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message, conversation_id: conversationId }),
    signal: controller.signal,
  }).then(async (response) => {
    if (!response.ok) {
      events.onError(`请求失败 (${response.status})`);
      return;
    }
    const reader = response.body?.getReader();
    if (!reader) {
      events.onError('无法读取响应流');
      return;
    }

    const decoder = new TextDecoder();
    const buffer: string[] = [];
    let convId: string | undefined;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const text = decoder.decode(value, { stream: true });
      // SSE format: "data: {...}\n\n"
      for (const line of text.split('\n')) {
        const trimmed = line.trim();
        if (!trimmed.startsWith('data: ')) continue;
        try {
          const payload = JSON.parse(trimmed.slice(6));
          switch (payload.type) {
            case 'meta':
              convId = payload.conversation_id;
              events.onMeta?.(convId!);
              break;
            case 'chunk':
              buffer.push(payload.content);
              events.onChunk(payload.content);
              break;
            case 'tool_call':
              events.onToolCall(payload.tool, payload.status, payload.detail);
              break;
            case 'error':
              events.onError(payload.detail);
              break;
            case 'done':
              events.onDone(buffer.join(''));
              break;
          }
        } catch {
          // skip non-JSON SSE lines
        }
      }
    }
  }).catch((err) => {
    if (err.name !== 'AbortError') {
      events.onError(err.message || '请求异常');
    }
  });

  return controller;
}

// ---- Chat Sessions ----

export async function fetchChatSessions(): Promise<import('@/types/agent').ChatSessionSummary[]> {
  const { data } = await api.get('/agents/chat/sessions');
  return data;
}

export async function fetchChatSessionMessages(id: string): Promise<import('@/types/agent').ChatSessionDetail> {
  const { data } = await api.get(`/agents/chat/sessions/${id}`);
  return data;
}

export async function deleteChatSession(id: string): Promise<void> {
  await api.delete(`/agents/chat/sessions/${id}`);
}

export async function clearChatSessions(): Promise<void> {
  await api.delete('/agents/chat/sessions');
}
