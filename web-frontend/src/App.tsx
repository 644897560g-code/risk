import React, { Suspense, useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Spin } from 'antd';
import AppLayout from '@/components/Layout';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useAuthStore } from '@/store/authStore';

const Login = React.lazy(() => import('@/pages/Login'));
const AgentChat = React.lazy(() => import('@/pages/AgentChat'));
const Knowledge = React.lazy(() => import('@/pages/Knowledge'));
const Tasks = React.lazy(() => import('@/pages/Tasks'));

const PageLoading = () => (
  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
    <Spin size="large" />
  </div>
);

const App: React.FC = () => {
  const validateToken = useAuthStore((s) => s.validateToken);

  useEffect(() => {
    validateToken();
  }, [validateToken]);

  return (
    <Routes>
      {/* Public route: login */}
      <Route path="/login" element={
        <Suspense fallback={<PageLoading />}><Login /></Suspense>
      } />

      {/* Protected routes */}
      <Route path="/" element={
        <ProtectedRoute>
          <AppLayout />
        </ProtectedRoute>
      }>
        <Route index element={<Navigate to="/agent" replace />} />
        <Route path="agent" element={
          <Suspense fallback={<PageLoading />}><AgentChat /></Suspense>
        } />
        <Route path="knowledge" element={
          <Suspense fallback={<PageLoading />}><Knowledge /></Suspense>
        } />
        <Route path="tasks" element={
          <Suspense fallback={<PageLoading />}><Tasks /></Suspense>
        } />
      </Route>

      {/* Catch-all redirect */}
      <Route path="*" element={<Navigate to="/agent" replace />} />
    </Routes>
  );
};

export default App;
