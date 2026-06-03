import { create } from 'zustand';
import { login as apiLogin, fetchMe } from '@/services/api';

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
  token: localStorage.getItem('auth_token'),
  username: localStorage.getItem('auth_username'),
  isAuthenticated: !!localStorage.getItem('auth_token'),
  isLoading: !!localStorage.getItem('auth_token'),

  login: async (username: string, password: string) => {
    const res = await apiLogin(username, password);
    localStorage.setItem('auth_token', res.access_token);
    localStorage.setItem('auth_username', res.username);
    set({
      token: res.access_token,
      username: res.username,
      isAuthenticated: true,
      isLoading: false,
    });
  },

  logout: () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_username');
    set({ token: null, username: null, isAuthenticated: false, isLoading: false });
  },

  validateToken: async () => {
    const token = localStorage.getItem('auth_token');
    if (!token) {
      set({ isLoading: false, isAuthenticated: false });
      return;
    }
    try {
      const user = await fetchMe();
      set({ username: user.username, isAuthenticated: true, isLoading: false });
    } catch {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_username');
      set({ token: null, username: null, isAuthenticated: false, isLoading: false });
    }
  },
}));
