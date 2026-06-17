import React, { useEffect } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Breadcrumb, Layout, Menu, Typography, Button, theme, Select, message } from 'antd';
import {
  MessageOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  FolderOpenOutlined,
  UserOutlined,
  LogoutOutlined,
  RocketOutlined,
  ExperimentOutlined,
  CloudUploadOutlined,
  HomeOutlined,
  BulbOutlined,
  CheckSquareOutlined,
} from '@ant-design/icons';
import { useAuthStore } from '@/store/authStore';
import { useProjectStore } from '@/store/projectStore';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

const menuItems = [
  { key: '/home', icon: <HomeOutlined />, label: '工作台' },
  {
    key: 'platform',
    label: '平台',
    children: [
      { key: 'projects', icon: <FolderOpenOutlined />, label: '项目列表' },
      { key: '/assets/templates', icon: <ExperimentOutlined />, label: '模板库' },
    ],
  },
  {
    key: 'mine',
    label: '探索',
    children: [
      { key: '/mine/experiments', icon: <RocketOutlined />, label: '实验列表' },
      { key: '/mine/report', icon: <FileTextOutlined />, label: '评估报告' },
    ],
  },
  {
    key: 'assets',
    label: '资产',
    children: [
      { key: '/assets/data', icon: <DatabaseOutlined />, label: '数据版本' },
      { key: '/assets/knowledge', icon: <BulbOutlined />, label: '知识库' },
    ],
  },
  {
    key: 'ship',
    label: '交付',
    children: [
      { key: '/ship/candidates', icon: <CheckSquareOutlined />, label: '候选特征集' },
      { key: '/ship/versions', icon: <CloudUploadOutlined />, label: '版本管理' },
    ],
  },
  { key: '/copilot', icon: <MessageOutlined />, label: '助手' },
];

const AppLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { token } = theme.useToken();
  const authLogout = useAuthStore((s) => s.logout);
  const authUsername = useAuthStore((s) => s.username);
  const { projects, currentProject, isLoading, loadProjects, selectProject } = useProjectStore();

  const pathname = location.pathname;
  const selectedKey = (() => {
    if (pathname.startsWith('/projects')) return 'projects';
    if (pathname.startsWith('/mine/report')) return '/mine/report';
    if (pathname.startsWith('/mine/experiments')) return '/mine/experiments';
    if (pathname.startsWith('/assets/data')) return '/assets/data';
    if (pathname.startsWith('/assets/templates')) return '/assets/templates';
    if (pathname.startsWith('/assets/knowledge')) return '/assets/knowledge';
    if (pathname.startsWith('/ship/candidates')) return '/ship/candidates';
    if (pathname.startsWith('/ship/versions')) return '/ship/versions';
    if (pathname.startsWith('/copilot')) return '/copilot';
    return '/home';
  })();
  const isProjectListPage = selectedKey === 'projects';
  const projectName = currentProject?.name || '当前项目';
  const routeContext = (() => {
    switch (selectedKey) {
      case 'projects':
        return { title: '项目列表', breadcrumb: ['平台', '项目列表'] };
      case '/home':
        return { title: '工作台', breadcrumb: ['工作台'] };
      case '/mine/experiments':
        return { title: '实验列表', breadcrumb: ['探索', projectName, '实验列表'] };
      case '/mine/report':
        return { title: '评估报告', breadcrumb: ['探索', projectName, '评估报告'] };
      case '/assets/data':
        return { title: '数据版本', breadcrumb: ['资产', projectName, '数据版本'] };
      case '/assets/templates':
        return { title: '模板库', breadcrumb: ['平台', '模板库'] };
      case '/assets/knowledge':
        return { title: '知识库', breadcrumb: ['资产', projectName, '知识库'] };
      case '/ship/candidates':
        return { title: '候选特征集', breadcrumb: ['交付', projectName, '候选特征集'] };
      case '/ship/versions':
        return { title: '版本管理', breadcrumb: ['交付', projectName, '版本管理'] };
      case '/copilot':
        return { title: '助手', breadcrumb: ['助手'] };
      default:
        return { title: '工作台', breadcrumb: ['工作台'] };
    }
  })();

  const handleLogout = () => {
    authLogout();
    message.info('当前为前端产品原型模式，无需登录');
    navigate('/home', { replace: true });
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
          defaultOpenKeys={['platform', 'mine', 'assets', 'ship']}
          items={menuItems}
          onClick={({ key }) => {
            if (key === 'projects') {
              navigate('/projects');
            } else if (String(key).startsWith('/')) {
              navigate(key);
            }
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
              style={{ width: isProjectListPage ? 260 : 220 }}
              placeholder={isProjectListPage ? '当前项目，可在列表中管理' : '选择项目'}
              options={projects.map((p) => ({
                value: p.id,
                label: p.is_default
                  ? `${p.name}（默认）`
                  : isProjectListPage && p.id === currentProject?.id
                    ? `${p.name}（当前）`
                    : p.name,
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
