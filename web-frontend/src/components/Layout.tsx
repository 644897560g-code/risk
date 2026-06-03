import React from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Typography, Button, theme } from 'antd';
import {
  MessageOutlined,
  DatabaseOutlined,
  OrderedListOutlined,
  UserOutlined,
  LogoutOutlined,
} from '@ant-design/icons';
import { useAuthStore } from '@/store/authStore';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

const menuItems = [
  { key: '/agent', icon: <MessageOutlined />, label: 'Agent' },
  { key: '/knowledge', icon: <DatabaseOutlined />, label: '知识' },
  { key: '/tasks', icon: <OrderedListOutlined />, label: '任务' },
];

const AppLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { token } = theme.useToken();
  const authLogout = useAuthStore((s) => s.logout);
  const authUsername = useAuthStore((s) => s.username);

  const selectedKey = '/' + location.pathname.split('/')[1];

  const handleLogout = () => {
    authLogout();
    navigate('/login', { replace: true });
  };

  return (
    <Layout style={{ minHeight: '100vh', background: token.colorBgLayout }}>
      {/* Sidebar */}
      <Sider
        width={220}
        style={{
          background: 'linear-gradient(180deg, #0a1628 0%, #132044 100%)',
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
              特征挖掘引擎
            </span>
          </div>
        </div>

        {/* Navigation */}
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems.map((item) => ({
            ...item,
            style: {
              borderRadius: 8,
              margin: '4px 8px',
              color: 'rgba(255,255,255,0.65)',
            },
          }))}
          onClick={({ key }) => navigate(key)}
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
          style={{
            background: '#ffffff',
            padding: '0 28px',
            borderBottom: '1px solid #e8ecf1',
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
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Typography.Title level={4} style={{ margin: 0, fontWeight: 600 }}>
              {menuItems.find((m) => m.key === selectedKey)?.label || '特征挖掘系统'}
            </Typography.Title>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <Text style={{ color: '#5a6070', fontSize: 14 }}>
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
              退出
            </Button>
          </div>
        </Header>

        {/* Content */}
        <Content
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
