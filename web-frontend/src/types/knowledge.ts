/** Knowledge management types */

export interface KnowledgeStats {
  total_files: number;
  total_size: number;
  by_category: Record<string, { count: number; size: number }>;
}

export interface KnowledgePreview {
  filename: string;
  total_lines: number;
  preview_lines: number;
  content: string;
}
