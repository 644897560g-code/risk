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
const CandidateFeatures = React.lazy(() => import('@/pages/CandidateFeatures'));

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
        <Route index element={<Navigate to="/home" replace />} />
        <Route path="home" element={
          <Suspense fallback={<PageLoading />}><Dashboard /></Suspense>
        } />
        <Route path="dashboard" element={<Navigate to="/home" replace />} />
        <Route path="projects" element={
          <Suspense fallback={<PageLoading />}><Projects /></Suspense>
        } />
        <Route path="assets/knowledge" element={
          <Suspense fallback={<PageLoading />}><Knowledge /></Suspense>
        } />
        <Route path="knowledge" element={<Navigate to="/assets/knowledge" replace />} />
        <Route path="assets/data" element={
          <Suspense fallback={<PageLoading />}><DataSources /></Suspense>
        } />
        <Route path="data-sources" element={<Navigate to="/assets/data" replace />} />
        <Route path="assets/templates" element={
          <Suspense fallback={<PageLoading />}><Templates /></Suspense>
        } />
        <Route path="templates" element={<Navigate to="/assets/templates" replace />} />
        <Route path="mine/experiments" element={
          <Suspense fallback={<PageLoading />}><Tasks /></Suspense>
        } />
        <Route path="tasks" element={<Navigate to="/mine/experiments" replace />} />
        <Route path="mine/report" element={
          <Suspense fallback={<PageLoading />}><Evaluation /></Suspense>
        } />
        <Route path="evaluation" element={<Navigate to="/mine/report" replace />} />
        <Route path="ship/candidates" element={
          <Suspense fallback={<PageLoading />}><CandidateFeatures /></Suspense>
        } />
        <Route path="ship/versions" element={
          <Suspense fallback={<PageLoading />}><Deployment /></Suspense>
        } />
        <Route path="deployment" element={<Navigate to="/ship/versions" replace />} />
        <Route path="copilot" element={
          <Suspense fallback={<PageLoading />}><AgentChat /></Suspense>
        } />
        <Route path="agent" element={<Navigate to="/copilot" replace />} />
      </Route>

      {/* Catch-all redirect */}
      <Route path="*" element={<Navigate to="/home" replace />} />
    </Routes>
  );
};

export default App;
