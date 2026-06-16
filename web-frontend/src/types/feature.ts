/** Feature types — matching backend schemas */

export interface FeatureVersion {
  id: number;
  version: string;
  task_id: number;
  total_features: number;
  passed_features: number;
  created_at: string;
}

export interface FeatureMetric {
  id: number;
  version: string;
  task_id: number;
  feature_name: string;
  feature_logic?: string;
  template_type?: string;
  source_fields?: string[];
  iv: number;
  psi: number;
  coverage: number;
  is_passed: boolean;
}

export interface TopFeature {
  feature_name: string;
  iv: number;
  psi: number;
  coverage: number;
  version: string;
}
