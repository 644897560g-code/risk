import React, { Suspense, useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Spin } from 'antd';
import AppLayout from '@/components/Layout';
import { useAuthStore } from '@/store/authStore';

const Login = React.lazy(() => import('@/pages/Login'));
const Dashboard = React.lazy(() => import('@/pages/Dashboard'));
const AgentChat = React.lazy(() => import('@/pages/AgentChat'));
const DataSources = React.lazy(() => import('@/pages/DataSources'));
const Knowledge = React.lazy(() => import('@/pages/Knowledge'));
const Projects = React.lazy(() => import('@/pages/Projects'));
const Tasks = React.lazy(() => import('@/pages/Tasks'));
const Templates = React.lazy(() => import('@/pages/Templates'));
const Evaluation = React.lazy(() => import('@/pages/Evaluation'));
const Deployment = React.lazy(() => import('@/pages/Deployment'));

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
      <Route path="/login" element={
        <Navigate to="/dashboard" replace />
      } />

      <Route path="/" element={
        <AppLayout />
      }>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={
          <Suspense fallback={<PageLoading />}><Dashboard /></Suspense>
        } />
        <Route path="projects" element={
          <Suspense fallback={<PageLoading />}><Projects /></Suspense>
        } />
        <Route path="knowledge" element={
          <Suspense fallback={<PageLoading />}><Knowledge /></Suspense>
        } />
        <Route path="data-sources" element={
          <Suspense fallback={<PageLoading />}><DataSources /></Suspense>
        } />
        <Route path="templates" element={
          <Suspense fallback={<PageLoading />}><Templates /></Suspense>
        } />
        <Route path="tasks" element={
          <Suspense fallback={<PageLoading />}><Tasks /></Suspense>
        } />
        <Route path="evaluation" element={
          <Suspense fallback={<PageLoading />}><Evaluation /></Suspense>
        } />
        <Route path="deployment" element={
          <Suspense fallback={<PageLoading />}><Deployment /></Suspense>
        } />
        <Route path="agent" element={
          <Suspense fallback={<PageLoading />}><AgentChat /></Suspense>
        } />
      </Route>

      {/* Catch-all redirect */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
};

export default App;
