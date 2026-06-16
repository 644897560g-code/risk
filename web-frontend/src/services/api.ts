import axios from 'axios';
import type { Task, TaskListResponse, TaskResultResponse, CreateTaskRequest } from '@/types/task';
import type { FeatureVersion, FeatureMetric, TopFeature } from '@/types/feature';
import type { SystemHealth, OrchestratorStatus, PendingTemplate, FeatureReviewResult } from '@/types/agent';
import type { KnowledgeStats, KnowledgePreview } from '@/types/knowledge';
import type { CreateProjectRequest, Project, ProjectListResponse, ProjectTemplate } from '@/types/project';
import {
  demoFeatureMetrics,
  demoFeatureVersions,
  demoPendingTemplates,
  demoProjectListResponse,
  demoProjects,
  demoProjectTemplates,
  demoTaskListResponse,
  demoTaskResult,
  demoTasks,
  demoTemplates,
  demoTopFeatures,
} from '@/services/mockData';

const api = axios.create({
  baseURL: '/api',
  timeout: 3000,
  headers: {
    'Content-Type': 'application/json',
  },
});

const FRONTEND_DEMO_MODE = import.meta.env.VITE_FRONTEND_DEMO !== 'false';

// Request interceptor: attach JWT token from localStorage
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    return Promise.reject(error);
  }
);

// ---- Tasks ----

export async function fetchTasks(skip = 0, limit = 50, projectId?: number): Promise<TaskListResponse> {
  if (FRONTEND_DEMO_MODE) {
    const items = projectId ? demoTasks.filter((task) => task.project_id === projectId) : demoTasks;
    return { items: items.slice(skip, skip + limit), total: items.length };
  }
  try {
    const { data } = await api.get('/tasks', { params: { skip, limit, project_id: projectId } });
    return data;
  } catch {
    const items = projectId ? demoTasks.filter((task) => task.project_id === projectId) : demoTasks;
    return { items: items.slice(skip, skip + limit), total: items.length };
  }
}

export async function fetchTask(id: number): Promise<Task> {
  if (FRONTEND_DEMO_MODE) {
    return demoTasks.find((task) => task.id === id) || demoTasks[0];
  }
  try {
    const { data } = await api.get(`/tasks/${id}`);
    return data;
  } catch {
    return demoTasks.find((task) => task.id === id) || demoTasks[0];
  }
}

export async function fetchTaskResult(id: number): Promise<TaskResultResponse> {
  if (FRONTEND_DEMO_MODE) {
    return { ...demoTaskResult, task: demoTasks.find((task) => task.id === id) || demoTaskResult.task };
  }
  try {
    const { data } = await api.get(`/tasks/${id}/result`);
    return data;
  } catch {
    return { ...demoTaskResult, task: demoTasks.find((task) => task.id === id) || demoTaskResult.task };
  }
}

export async function fetchTaskSamples(id: number, limit = 5): Promise<{ items: any[]; total: number }> {
  if (FRONTEND_DEMO_MODE) {
    return {
      total: 1,
      items: [{
        country: 'INDO',
        orderId: 'demo_order_001',
        applyTime: 1743482879000,
        params: { base: { salary: 12000000, job: '12', gender: 0 }, appList: [] },
        FDC: { pinjaman: [] },
      }],
    };
  }
  try {
    const { data } = await api.get(`/tasks/${id}/samples`, { params: { limit } });
    return data;
  } catch {
    return {
      total: 1,
      items: [{
        country: 'INDO',
        orderId: 'demo_order_001',
        applyTime: 1743482879000,
        params: { base: { salary: 12000000, job: '12', gender: 0 }, appList: [] },
        FDC: { pinjaman: [] },
      }],
    };
  }
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
  if (FRONTEND_DEMO_MODE) {
    return {
      id: Date.now(),
      name: req.name || '演示特征生产任务',
      mode: req.mode || 'normal',
      status: 'pending',
      progress: 0,
      project_id: req.project_id || 1,
      created_at: new Date().toISOString(),
    };
  }
  const form = new FormData();
  if (req.name) form.append('name', req.name);
  if (req.mode) form.append('mode', req.mode);
  if (req.scheduled_at) form.append('scheduled_at', req.scheduled_at);
  if (req.recurring_cron) form.append('recurring_cron', req.recurring_cron);
  if (req.url_file) form.append('url_file', req.url_file);
  if (req.label_file) form.append('label_file', req.label_file);
  if (req.url_path) form.append('url_path', req.url_path);
  if (req.label_path) form.append('label_path', req.label_path);
  if (req.project_id) form.append('project_id', String(req.project_id));
  try {
    const { data } = await api.post('/tasks', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  } catch {
    return {
      id: Date.now(),
      name: req.name || '演示特征生产任务',
      mode: req.mode || 'normal',
      status: 'pending',
      progress: 0,
      project_id: req.project_id || 1,
      created_at: new Date().toISOString(),
    };
  }
}

export interface TaskStep {
  name: string;
  label: string;
  status: 'wait' | 'process' | 'finish' | 'error';
  message: string;
}

export async function fetchTaskSteps(taskId: number): Promise<{ steps: TaskStep[]; task_status: string }> {
  if (FRONTEND_DEMO_MODE) {
    return {
      task_status: 'completed',
      steps: [
        { name: 'data_download', label: '数据准备', status: 'finish', message: '样本与标签已就绪' },
        { name: 'mass_production', label: '特征生产', status: 'finish', message: '已生成候选特征' },
        { name: 'feature_evaluation', label: '特征评估', status: 'finish', message: 'IV/PSI/覆盖率已计算' },
        { name: 'feature_deployment', label: '部署包', status: 'finish', message: '部署版本已生成' },
        { name: 'feedback_aggregation', label: '反馈沉淀', status: 'finish', message: '已沉淀本轮结果' },
      ],
    };
  }
  try {
    const { data } = await api.get(`/tasks/${taskId}/steps`);
    return data;
  } catch {
    return {
      task_status: 'completed',
      steps: [
        { name: 'data_download', label: '数据准备', status: 'finish', message: '样本与标签已就绪' },
        { name: 'mass_production', label: '特征生产', status: 'finish', message: '已生成候选特征' },
        { name: 'feature_evaluation', label: '特征评估', status: 'finish', message: 'IV/PSI/覆盖率已计算' },
        { name: 'feature_deployment', label: '部署包', status: 'finish', message: '部署版本已生成' },
        { name: 'feedback_aggregation', label: '反馈沉淀', status: 'finish', message: '已沉淀本轮结果' },
      ],
    };
  }
}

export async function cancelTask(taskId: number): Promise<{ status: string; task_id: number }> {
  if (FRONTEND_DEMO_MODE) return { status: 'cancelled', task_id: taskId };
  try {
    const { data } = await api.post(`/tasks/${taskId}/cancel`);
    return data;
  } catch {
    return { status: 'cancelled', task_id: taskId };
  }
}

export async function resumeTask(taskId: number): Promise<{ status: string; task_id: number }> {
  if (FRONTEND_DEMO_MODE) return { status: 'running', task_id: taskId };
  try {
    const { data } = await api.post(`/tasks/${taskId}/resume`);
    return data;
  } catch {
    return { status: 'running', task_id: taskId };
  }
}

export async function rerunTask(taskId: number): Promise<{ status: string; task_id: number }> {
  if (FRONTEND_DEMO_MODE) return { status: 'running', task_id: taskId };
  try {
    const { data } = await api.post(`/tasks/${taskId}/rerun`);
    return data;
  } catch {
    return { status: 'running', task_id: taskId };
  }
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
  if (FRONTEND_DEMO_MODE) return;
  try {
    await api.post(`/agents/reviews/channel2-pending/${templateId}/approve`);
  } catch {
    return;
  }
}

export async function rejectChannel2Template(templateId: string, reason = ''): Promise<void> {
  if (FRONTEND_DEMO_MODE) return;
  try {
    await api.post(`/agents/reviews/channel2-pending/${templateId}/reject`, { reason });
  } catch {
    return;
  }
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

export async function fetchFeatureVersions(projectId?: number): Promise<FeatureVersion[]> {
  if (FRONTEND_DEMO_MODE) return demoFeatureVersions;
  try {
    const { data } = await api.get('/features/versions', { params: { project_id: projectId } });
    return data.items || [];
  } catch {
    return demoFeatureVersions;
  }
}

export async function fetchFeatureMetrics(version: string, projectId?: number): Promise<FeatureMetric[]> {
  if (FRONTEND_DEMO_MODE) return demoFeatureMetrics.map((item) => ({ ...item, version }));
  try {
    const { data } = await api.get(`/features/versions/${version}`, { params: { project_id: projectId } });
    return data.items || [];
  } catch {
    return demoFeatureMetrics.map((item) => ({ ...item, version }));
  }
}

export async function fetchFeatureReportUrl(version: string): Promise<string> {
  if (FRONTEND_DEMO_MODE) return '#';
  try {
    const { data } = await api.get(`/features/versions/${version}/report`);
    return data.report_url;
  } catch {
    return '#';
  }
}

export async function fetchTopFeatures(projectId?: number): Promise<TopFeature[]> {
  if (FRONTEND_DEMO_MODE) return demoTopFeatures;
  try {
    const { data } = await api.get('/features/top', { params: { project_id: projectId } });
    return data.items || [];
  } catch {
    return demoTopFeatures;
  }
}

export async function fetchFeatureStats(): Promise<{
  current_total: number;
  current_passed: number;
  accumulated_passed: number;
  latest_version: string;
}> {
  if (FRONTEND_DEMO_MODE) {
    return {
      current_total: demoFeatureVersions[0].total_features,
      current_passed: demoFeatureVersions[0].passed_features,
      accumulated_passed: 147,
      latest_version: demoFeatureVersions[0].version,
    };
  }
  try {
    const { data } = await api.get('/features/stats');
    return data;
  } catch {
    return {
      current_total: demoFeatureVersions[0].total_features,
      current_passed: demoFeatureVersions[0].passed_features,
      accumulated_passed: 147,
      latest_version: demoFeatureVersions[0].version,
    };
  }
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
  if (FRONTEND_DEMO_MODE) {
    return {
      total: samples.length,
      results: samples.map((sample, index) => ({
        order_id: String(sample.orderId || `demo_order_${index + 1}`),
        processing_time_ms: 12,
        features: {
          ratio_applist_highrisk_apps_all: 0.18,
          cnt_fdc_query_7d_platforms: 3,
          flag_app_cashloan_recent_install: 1,
        },
      })),
    };
  }
  try {
    const { data } = await api.post('/features/compute', { samples });
    return data;
  } catch {
    return {
      total: samples.length,
      results: samples.map((sample, index) => ({
        order_id: String(sample.orderId || `demo_order_${index + 1}`),
        processing_time_ms: 12,
        features: {
          ratio_applist_highrisk_apps_all: 0.18,
          cnt_fdc_query_7d_platforms: 3,
          flag_app_cashloan_recent_install: 1,
        },
      })),
    };
  }
}

// ---- Health ----

export async function fetchHealth(): Promise<SystemHealth> {
  const { data } = await api.get('/health');
  return data;
}

// ---- Projects ----

export async function fetchProjects(): Promise<ProjectListResponse> {
  if (FRONTEND_DEMO_MODE) return demoProjectListResponse;
  try {
    const { data } = await api.get('/projects');
    return data;
  } catch {
    return demoProjectListResponse;
  }
}

export async function fetchDefaultProject(): Promise<Project> {
  if (FRONTEND_DEMO_MODE) return demoProjects[0];
  try {
    const { data } = await api.get('/projects/default');
    return data;
  } catch {
    return demoProjects[0];
  }
}

export async function createProject(req: CreateProjectRequest): Promise<Project> {
  if (FRONTEND_DEMO_MODE) {
    return {
      id: Date.now(),
      name: req.name,
      business_line: req.business_line || '',
      country: req.country || '',
      product: req.product || '',
      description: req.description || '',
      config: req.config,
      status: 'active',
      is_default: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
  }
  try {
    const { data } = await api.post('/projects', req);
    return data;
  } catch {
    return {
      id: Date.now(),
      name: req.name,
      business_line: req.business_line || '',
      country: req.country || '',
      product: req.product || '',
      description: req.description || '',
      config: req.config,
      status: 'active',
      is_default: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
  }
}

export async function updateProject(projectId: number, req: Partial<CreateProjectRequest> & { status?: string }): Promise<Project> {
  if (FRONTEND_DEMO_MODE) {
    const old = demoProjects.find((item) => item.id === projectId) || demoProjects[0];
    return { ...old, ...req, updated_at: new Date().toISOString() };
  }
  try {
    const { data } = await api.patch(`/projects/${projectId}`, req);
    return data;
  } catch {
    const old = demoProjects.find((item) => item.id === projectId) || demoProjects[0];
    return { ...old, ...req, updated_at: new Date().toISOString() };
  }
}

export async function deleteProject(projectId: number): Promise<Project> {
  if (FRONTEND_DEMO_MODE) {
    const old = demoProjects.find((item) => item.id === projectId) || demoProjects[0];
    return { ...old, status: 'deleted' };
  }
  try {
    const { data } = await api.delete(`/projects/${projectId}`);
    return data;
  } catch {
    const old = demoProjects.find((item) => item.id === projectId) || demoProjects[0];
    return { ...old, status: 'deleted' };
  }
}

export async function fetchProjectTemplates(projectId: number, enabled?: boolean): Promise<ProjectTemplate[]> {
  if (FRONTEND_DEMO_MODE) {
    return enabled === undefined ? demoProjectTemplates : demoProjectTemplates.filter((item) => item.enabled === enabled);
  }
  try {
    const { data } = await api.get(`/projects/${projectId}/templates`, { params: { enabled } });
    return data.items || [];
  } catch {
    return enabled === undefined ? demoProjectTemplates : demoProjectTemplates.filter((item) => item.enabled === enabled);
  }
}

export async function setProjectTemplateSelection(projectId: number, templateIds: string[]): Promise<ProjectTemplate[]> {
  if (FRONTEND_DEMO_MODE) {
    return demoProjectTemplates.filter((item) => templateIds.includes(item.template_id));
  }
  try {
    const { data } = await api.put(`/projects/${projectId}/templates`, { template_ids: templateIds });
    return data.items || [];
  } catch {
    return demoProjectTemplates.filter((item) => templateIds.includes(item.template_id));
  }
}

export async function setProjectTemplateEnabled(
  projectId: number,
  templateId: string,
  enabled: boolean,
): Promise<ProjectTemplate> {
  if (FRONTEND_DEMO_MODE) {
    return { ...demoProjectTemplates[0], project_id: projectId, template_id: templateId, enabled };
  }
  try {
    const { data } = await api.post(`/projects/${projectId}/templates/${templateId}`, { enabled });
    return data;
  } catch {
    return { ...demoProjectTemplates[0], project_id: projectId, template_id: templateId, enabled };
  }
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
  template_name_cn?: string;
  dimension: string;
  description: string;
  dsl: string;
  python_function: string;
  python_code?: string;
  created_at?: string;
  /** @deprecated use template_name */
  name?: string;
}

export interface PendingTemplateItem {
  template_id: string;
  template_name?: string;
  template_name_cn?: string;
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

function sortTemplatesByCreatedAt<T extends { created_at?: string; template_id?: string }>(items: T[]): T[] {
  return [...items].sort((a, b) => {
    const aCreatedAt = a.created_at ? new Date(a.created_at).getTime() : 0;
    const bCreatedAt = b.created_at ? new Date(b.created_at).getTime() : 0;
    if (aCreatedAt !== bCreatedAt) return aCreatedAt - bCreatedAt;
    return (a.template_id || '').localeCompare(b.template_id || '', undefined, { numeric: true });
  });
}

export async function fetchChannel1Templates(): Promise<Channel1Template[]> {
  if (FRONTEND_DEMO_MODE) return sortTemplatesByCreatedAt(demoTemplates);
  try {
    const { data } = await api.get('/templates/channel1');
    return sortTemplatesByCreatedAt(data.items || []);
  } catch {
    return sortTemplatesByCreatedAt(demoTemplates);
  }
}

export async function fetchChannel2PendingTemplates(): Promise<PendingTemplateItem[]> {
  if (FRONTEND_DEMO_MODE) return sortTemplatesByCreatedAt(demoPendingTemplates);
  try {
    const { data } = await api.get('/templates/channel2-pending');
    return sortTemplatesByCreatedAt(data.items || []);
  } catch {
    return sortTemplatesByCreatedAt(demoPendingTemplates);
  }
}

export async function fetchChannel1TemplateCode(templateId: string): Promise<string> {
  if (FRONTEND_DEMO_MODE) {
    return `def ${templateId.toLowerCase()}_calculator(sample):\n    \"\"\"演示模板代码：生产模式下展示真实模板代码。\"\"\"\n    return 0`;
  }
  try {
    const { data } = await api.get(`/templates/channel1/${templateId}/code`);
    return data.code || '';
  } catch {
    return `def ${templateId.toLowerCase()}_calculator(sample):\n    \"\"\"演示模板代码：生产模式下展示真实模板代码。\"\"\"\n    return 0`;
  }
}

export async function clearAllTasks(projectId?: number): Promise<{ status: string; deleted: number }> {
  if (FRONTEND_DEMO_MODE) return { status: 'ok', deleted: 0 };
  try {
    const { data } = await api.delete('/tasks', { params: { project_id: projectId } });
    return data;
  } catch {
    return { status: 'ok', deleted: 0 };
  }
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
