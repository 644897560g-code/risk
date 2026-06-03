import { create } from 'zustand';
import type { Task } from '@/types/task';
import type { OrchestratorStatus } from '@/types/agent';
import type { FeatureVersion, FeatureMetric } from '@/types/feature';

interface AppState {
  // Tasks
  tasks: Task[];
  currentTask: Task | null;
  loading: boolean;
  setTasks: (tasks: Task[]) => void;
  setCurrentTask: (task: Task | null) => void;
  setLoading: (loading: boolean) => void;

  // Orchestrator
  orchStatus: OrchestratorStatus | null;
  setOrchStatus: (status: OrchestratorStatus | null) => void;

  // Features
  versions: FeatureVersion[];
  currentMetrics: FeatureMetric[];
  setVersions: (versions: FeatureVersion[]) => void;
  setCurrentMetrics: (metrics: FeatureMetric[]) => void;
}

export const useStore = create<AppState>((set) => ({
  tasks: [],
  currentTask: null,
  loading: false,
  setTasks: (tasks) => set({ tasks }),
  setCurrentTask: (currentTask) => set({ currentTask }),
  setLoading: (loading) => set({ loading }),

  orchStatus: null,
  setOrchStatus: (orchStatus) => set({ orchStatus }),

  versions: [],
  currentMetrics: [],
  setVersions: (versions) => set({ versions }),
  setCurrentMetrics: (currentMetrics) => set({ currentMetrics }),
}));
