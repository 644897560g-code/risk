import { create } from 'zustand';
import { createProject, fetchDefaultProject, fetchProjects } from '@/services/api';
import type { CreateProjectRequest, Project } from '@/types/project';

const PROJECT_STORAGE_KEY = 'current_project_id';

interface ProjectState {
  projects: Project[];
  currentProject: Project | null;
  isLoading: boolean;
  loadProjects: () => Promise<void>;
  selectProject: (projectId: number) => void;
  createAndSelectProject: (payload: CreateProjectRequest) => Promise<Project>;
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  projects: [],
  currentProject: null,
  isLoading: false,

  loadProjects: async () => {
    set({ isLoading: true });
    try {
      const res = await fetchProjects();
      let projects = res.items || [];
      if (projects.length === 0) {
        const defaultProject = await fetchDefaultProject();
        projects = [defaultProject];
      }

      const storedId = Number(localStorage.getItem(PROJECT_STORAGE_KEY));
      const currentProject =
        projects.find((p) => p.id === storedId)
        || projects.find((p) => p.is_default)
        || projects[0]
        || null;

      if (currentProject) {
        localStorage.setItem(PROJECT_STORAGE_KEY, String(currentProject.id));
      }
      set({ projects, currentProject });
    } finally {
      set({ isLoading: false });
    }
  },

  selectProject: (projectId: number) => {
    const currentProject = get().projects.find((p) => p.id === projectId) || null;
    if (currentProject) {
      localStorage.setItem(PROJECT_STORAGE_KEY, String(projectId));
      set({ currentProject });
    }
  },

  createAndSelectProject: async (payload: CreateProjectRequest) => {
    const project = await createProject(payload);
    const projects = [...get().projects.filter((p) => p.id !== project.id), project]
      .sort((a, b) => Number(b.is_default) - Number(a.is_default) || a.id - b.id);
    localStorage.setItem(PROJECT_STORAGE_KEY, String(project.id));
    set({ projects, currentProject: project });
    return project;
  },
}));
