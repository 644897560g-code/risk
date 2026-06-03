import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Form, Input, Button, Typography, message } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useAuthStore } from '@/store/authStore';

const { Text } = Typography;

const RiskForgeLogo: React.FC<{ size?: number }> = ({ size = 64 }) => (
  <div style={{ textAlign: 'center' }}>
    <img
      src="/logo.png"
      alt="云雁九辰"
      style={{
        width: size * 3,
        height: size,
        objectFit: 'contain',
        display: 'block',
        margin: '0 auto',
      }}
    />
    <div style={{ marginTop: 12 }}>
      <div
        style={{
          color: '#ffffff',
          fontSize: 22,
          fontWeight: 700,
          letterSpacing: '1px',
          fontFamily: "'Inter', -apple-system, sans-serif",
        }}
      >
        RiskForge AI
      </div>
      <div
        style={{
          color: 'rgba(255,255,255,0.4)',
          fontSize: 11,
          letterSpacing: '2px',
          textTransform: 'uppercase',
          marginTop: 4,
        }}
      >
        智能特征挖掘引擎
      </div>
    </div>
  </div>
);

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const login = useAuthStore((s) => s.login);
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      await login(values.username, values.password);
      message.success('登录成功');
      navigate('/agent', { replace: true });
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '登录失败，请检查用户名和密码');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        background: 'linear-gradient(135deg, #0a1628 0%, #132044 50%, #1a2a4a 100%)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Decorative gradient orbs */}
      <div
        style={{
          position: 'absolute',
          top: '-20%',
          right: '-10%',
          width: 400,
          height: 400,
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(0, 210, 255, 0.08) 0%, transparent 70%)',
          pointerEvents: 'none',
        }}
      />
      <div
        style={{
          position: 'absolute',
          bottom: '-20%',
          left: '-10%',
          width: 500,
          height: 500,
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(225, 0, 255, 0.06) 0%, transparent 70%)',
          pointerEvents: 'none',
        }}
      />

      {/* Login card */}
      <div
        style={{
          width: 400,
          padding: '40px 36px 32px',
          background: 'rgba(255, 255, 255, 0.04)',
          borderRadius: 16,
          border: '1px solid rgba(255, 255, 255, 0.08)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          animation: 'fadeInUp 0.5s ease',
        }}
      >
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <RiskForgeLogo size={72} />
        </div>

        {/* Login form */}
        <Form
          form={form}
          layout="vertical"
          onFinish={onFinish}
          size="large"
          requiredMark={false}
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input
              prefix={<UserOutlined style={{ color: 'rgba(255,255,255,0.3)' }} />}
              placeholder="用户名"
              style={{
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: 8,
                color: '#ffffff',
                height: 44,
              }}
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password
              prefix={<LockOutlined style={{ color: 'rgba(255,255,255,0.3)' }} />}
              placeholder="密码"
              style={{
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: 8,
                color: '#ffffff',
                height: 44,
              }}
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0 }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              style={{
                height: 44,
                borderRadius: 8,
                fontSize: 15,
                fontWeight: 600,
                background: 'linear-gradient(135deg, #3a7bd5 0%, #00d2ff 100%)',
                border: 'none',
                boxShadow: '0 4px 12px rgba(58, 123, 213, 0.35)',
              }}
            >
              登录
            </Button>
          </Form.Item>
        </Form>
      </div>
    </div>
  );
};

export default LoginPage;
