/** Task types — matching backend schemas */

export interface Task {
  id: number;
  name: string;
  mode: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  linked_task_id?: number;
  total_features?: number;
  passed_features?: number;
  deployed_version?: string;
  error_message?: string;
  config?: Record<string, string>;
  scheduled_at?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  logs?: TaskLog[];
}

export interface TaskLog {
  id: number;
  task_id: number;
  level: string;
  message: string;
  timestamp: string;
}

export interface CreateTaskRequest {
  name?: string;
  mode?: 'normal' | 'template_task';
  url_file?: File;
  label_file?: File;
  url_path?: string;
  label_path?: string;
  scheduled_at?: string;
  recurring_cron?: string;
}

export interface TaskListResponse {
  items: Task[];
  total: number;
}

export interface TaskResultResponse {
  task: Task;
  logs: TaskLog[];
  result?: Record<string, unknown>;
}
