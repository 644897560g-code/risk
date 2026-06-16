import React, { useEffect } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Breadcrumb, Layout, Menu, Typography, Button, theme, Select, message } from 'antd';
import {
  AppstoreOutlined,
  MessageOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  OrderedListOutlined,
  UserOutlined,
  LogoutOutlined,
  FolderOpenOutlined,
  ExperimentOutlined,
  CloudUploadOutlined,
} from '@ant-design/icons';
import { useAuthStore } from '@/store/authStore';
import { useProjectStore } from '@/store/projectStore';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

const menuItems = [
  {
    key: 'platform',
    label: '平台',
    children: [
      { key: '/projects', icon: <FolderOpenOutlined />, label: '项目列表' },
      { key: '/templates', icon: <ExperimentOutlined />, label: '模板库' },
    ],
  },
  {
    key: 'project',
    label: '当前项目',
    children: [
      { key: '/dashboard', icon: <AppstoreOutlined />, label: '项目概览' },
      { key: '/data-sources', icon: <DatabaseOutlined />, label: '数据源' },
      { key: '/knowledge', icon: <FileTextOutlined />, label: '知识' },
      { key: '/tasks', icon: <OrderedListOutlined />, label: '任务' },
      { key: '/deployment', icon: <CloudUploadOutlined />, label: '版本与交付' },
    ],
  },
  {
    key: 'support',
    label: '辅助工具',
    children: [
      { key: '/agent', icon: <MessageOutlined />, label: '智能助理' },
    ],
  },
];

const AppLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { token } = theme.useToken();
  const authLogout = useAuthStore((s) => s.logout);
  const authUsername = useAuthStore((s) => s.username);
  const { projects, currentProject, isLoading, loadProjects, selectProject } = useProjectStore();

  const routeRoot = '/' + location.pathname.split('/')[1];
  const selectedKey = routeRoot === '/evaluation' ? '/tasks' : routeRoot;
  const projectName = currentProject?.name || '当前项目';
  const routeContext = (() => {
    switch (routeRoot) {
      case '/projects':
        return { title: '项目列表', breadcrumb: ['平台', '项目列表'] };
      case '/templates':
        return { title: '模板库', breadcrumb: ['平台', '模板库'] };
      case '/dashboard':
        return { title: '项目概览', breadcrumb: ['平台', projectName, '项目概览'] };
      case '/data-sources':
        return { title: '数据源', breadcrumb: ['平台', projectName, '数据源'] };
      case '/knowledge':
        return { title: '知识', breadcrumb: ['平台', projectName, '知识'] };
      case '/tasks':
        return { title: '任务', breadcrumb: ['平台', projectName, '任务'] };
      case '/evaluation':
        return { title: '任务结果 / 评估报告', breadcrumb: ['平台', projectName, '任务', '评估报告'] };
      case '/deployment':
        return { title: '版本与交付', breadcrumb: ['平台', projectName, '版本与交付'] };
      case '/agent':
        return { title: '智能助理', breadcrumb: ['辅助工具', '智能助理'] };
      default:
        return { title: '特征生产平台', breadcrumb: ['平台'] };
    }
  })();

  const handleLogout = () => {
    authLogout();
    message.info('当前为前端产品原型模式，无需登录');
    navigate('/dashboard', { replace: true });
  };

  useEffect(() => {
    loadProjects().catch(() => {
      message.error('项目列表加载失败');
    });
  }, [loadProjects]);

  return (
    <Layout className="tech-shell" style={{ minHeight: '100vh', background: token.colorBgLayout }}>
      {/* Sidebar */}
      <Sider
        className="tech-sider"
        width={220}
        style={{
          borderRight: 'none',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 100,
          overflow: 'auto',
        }}
      >
        {/* Logo & Brand */}
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            padding: '0 16px',
            gap: 12,
            borderBottom: '1px solid rgba(255,255,255,0.06)',
          }}
        >
          <img
            src="/logo.png"
            alt="云雁九辰"
            style={{
              height: 36,
              objectFit: 'contain',
              display: 'block',
            }}
          />
          <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.2 }}>
            <span
              style={{
                color: '#ffffff',
                fontSize: 15,
                fontWeight: 700,
                letterSpacing: '0.3px',
                fontFamily: "'Inter', -apple-system, sans-serif",
              }}
            >
              RiskForge AI
            </span>
            <span
              style={{
                color: 'rgba(255,255,255,0.35)',
                fontSize: 9,
                letterSpacing: '0.5px',
                textTransform: 'uppercase' as const,
              }}
            >
              特征生产平台
            </span>
          </div>
        </div>

        {/* Navigation */}
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          defaultOpenKeys={['platform', 'project', 'support']}
          items={menuItems}
          onClick={({ key }) => {
            if (String(key).startsWith('/')) navigate(key);
          }}
          style={{
            background: 'transparent',
            borderRight: 0,
            marginTop: 8,
          }}
          theme="dark"
        />

        {/* Bottom branding */}
        <div
          style={{
            position: 'absolute',
            bottom: 16,
            left: 0,
            right: 0,
            textAlign: 'center',
            padding: '0 16px',
          }}
        >
          <Text
            style={{
              color: 'rgba(255,255,255,0.2)',
              fontSize: 10,
              letterSpacing: '0.5px',
            }}
          >
            v1.0 · AI Powered
          </Text>
        </div>
      </Sider>

      <Layout style={{ marginLeft: 220 }}>
        {/* Header */}
        <Header
          className="tech-header"
          style={{
            padding: '0 28px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            height: 64,
            position: 'sticky',
            top: 0,
            zIndex: 99,
            backdropFilter: 'blur(8px)',
            WebkitBackdropFilter: 'blur(8px)',
            backgroundClip: 'padding-box',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Breadcrumb
              className="app-breadcrumb"
              items={routeContext.breadcrumb.map((title) => ({ title }))}
            />
            <Typography.Title level={4} style={{ margin: 0, fontWeight: 600, lineHeight: 1.2 }}>
              {routeContext.title}
            </Typography.Title>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Select
              value={currentProject?.id}
              loading={isLoading}
              style={{ width: 220 }}
              placeholder="选择项目"
              options={projects.map((p) => ({
                value: p.id,
                label: p.is_default ? `${p.name}（默认）` : p.name,
              }))}
              onChange={selectProject}
            />
            <Text style={{ color: 'rgba(226,232,240,0.72)', fontSize: 14 }}>
              <UserOutlined style={{ marginRight: 6 }} />
              {authUsername || '用户'}
            </Text>
            <Button
              type="text"
              size="small"
              icon={<LogoutOutlined />}
              onClick={handleLogout}
              style={{ color: '#ff4d4f' }}
            >
              演示模式
            </Button>
          </div>
        </Header>

        {/* Content */}
        <Content
          className="tech-content"
          style={{
            padding: 24,
            minHeight: 'calc(100vh - 64px)',
            background: 'transparent',
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
