import React from 'react';
import { Alert, Typography } from 'antd';
import { UserOutlined, RobotOutlined } from '@ant-design/icons';
import type { ChatMessage as ChatMessageType } from '@/types/agent';

const { Text, Paragraph } = Typography;

interface Props {
  message: ChatMessageType;
}

const toolCallColors: Record<string, string> = {
  success: '#52c41a',
  error: '#ff4d4f',
  pending: '#faad14',
};

const ChatMessage: React.FC<Props> = ({ message }) => {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: isUser ? 'row-reverse' : 'row',
        alignItems: 'flex-start',
        gap: 10,
        marginBottom: 16,
      }}
    >
      {/* Avatar */}
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          background: isUser ? '#1677ff' : isSystem ? '#722ed1' : '#f0f0f0',
          color: isUser || isSystem ? '#fff' : '#333',
          fontSize: 16,
        }}
      >
        {isUser ? <UserOutlined /> : isSystem ? 'S' : <RobotOutlined />}
      </div>

      {/* Bubble */}
      <div
        style={{
          maxWidth: '75%',
          padding: '10px 14px',
          borderRadius: 12,
          background: isUser ? '#1677ff' : isSystem ? '#f9f0ff' : '#fff',
          color: isUser ? '#fff' : '#333',
          border: isUser ? 'none' : '1px solid #e8e8e8',
          fontSize: 14,
          lineHeight: 1.6,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        <Paragraph style={{ margin: 0, color: 'inherit', whiteSpace: 'pre-wrap' }}>
          {message.content}
        </Paragraph>

        {/* Tool call info */}
        {message.tool_call && (
          <Alert
            type={message.tool_call.status === 'success' ? 'success' : 'error'}
            message={
              <span>
                <Text strong style={{ fontSize: 12 }}>
                  {message.tool_call.tool === 'trigger_channel2' ? '触发通道2模板创建' : message.tool_call.tool}
                </Text>
                <br />
                <Text style={{ fontSize: 12 }}>{message.tool_call.detail}</Text>
              </span>
            }
            style={{ marginTop: 8, borderRadius: 6 }}
            showIcon
          />
        )}
      </div>
    </div>
  );
};

/** Loading indicator (typing animation) */
export const ChatLoading: React.FC = () => (
  <div
    style={{
      display: 'flex',
      flexDirection: 'row',
      alignItems: 'center',
      gap: 10,
      marginBottom: 16,
    }}
  >
    <div
      style={{
        width: 32, height: 32, borderRadius: '50%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: '#f0f0f0', fontSize: 16,
      }}
    >
      <RobotOutlined />
    </div>
    <div
      style={{
        padding: '10px 16px',
        borderRadius: 12,
        background: '#fff',
        border: '1px solid #e8e8e8',
      }}
    >
      <span style={{ fontSize: 20, lineHeight: 1, color: '#999' }}>
        <span style={{ animation: 'pulse 1.4s infinite' }}>.</span>
        <span style={{ animation: 'pulse 1.4s infinite 0.2s' }}>.</span>
        <span style={{ animation: 'pulse 1.4s infinite 0.4s' }}>.</span>
      </span>
    </div>
  </div>
);

/** Error banner with retry button */
export const ChatError: React.FC<{ message: string; onRetry?: () => void }> = ({ message, onRetry }) => (
  <Alert
    type="error"
    message="发送失败"
    description={message}
    showIcon
    closable
    style={{ marginBottom: 16 }}
    action={
      onRetry ? (
        <span
          onClick={onRetry}
          style={{ cursor: 'pointer', textDecoration: 'underline', fontSize: 12 }}
        >
          重试
        </span>
      ) : undefined
    }
  />
);

/** Welcome message (empty state) */
export const ChatWelcome: React.FC = () => (
  <div style={{ textAlign: 'center', padding: '60px 20px', color: '#999' }}>
    <RobotOutlined style={{ fontSize: 48, color: '#d9d9d9', marginBottom: 16 }} />
    <h3 style={{ color: '#666', marginBottom: 8 }}>Agent Chat</h3>
    <p style={{ fontSize: 13, lineHeight: 1.8 }}>
      向 AI 助手咨询特征设计问题，或直接要求创建新特征模板。
      <br />
      系统已内置 15 个通道1模板作为参考上下文。
    </p>
  </div>
);

export default ChatMessage;
