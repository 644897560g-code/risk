export interface Project {
  id: number;
  name: string;
  business_line: string;
  country: string;
  product: string;
  description: string;
  config?: Record<string, unknown>;
  owner_user_id?: number | null;
  status: string;
  is_default: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ProjectTemplate {
  id: number;
  project_id: number;
  template_db_id: number;
  template_id: string;
  template_name: string;
  template_name_cn?: string;
  dimension?: string;
  enabled: boolean;
  selected_by?: number | null;
  selected_at?: string | null;
  config_override?: Record<string, unknown> | null;
}

export interface ProjectListResponse {
  items: Project[];
  total: number;
}

export interface CreateProjectRequest {
  name: string;
  business_line?: string;
  country?: string;
  product?: string;
  description?: string;
  config?: Record<string, unknown>;
  template_ids?: string[];
}
