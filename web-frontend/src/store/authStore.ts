import { create } from 'zustand';

interface AuthState {
  token: string | null;
  username: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  validateToken: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: 'frontend-demo-token',
  username: localStorage.getItem('auth_username') || '产品经理',
  isAuthenticated: true,
  isLoading: false,

  login: async (username: string, password: string) => {
    const displayName = username || '产品经理';
    localStorage.setItem('auth_token', 'frontend-demo-token');
    localStorage.setItem('auth_username', displayName);
    set({
      token: 'frontend-demo-token',
      username: displayName,
      isAuthenticated: true,
      isLoading: false,
    });
  },

  logout: () => {
    localStorage.setItem('auth_token', 'frontend-demo-token');
    localStorage.setItem('auth_username', '产品经理');
    set({ token: 'frontend-demo-token', username: '产品经理', isAuthenticated: true, isLoading: false });
  },

  validateToken: async () => {
    const username = localStorage.getItem('auth_username') || '产品经理';
    localStorage.setItem('auth_token', 'frontend-demo-token');
    set({ token: 'frontend-demo-token', username, isAuthenticated: true, isLoading: false });
  },
}));
