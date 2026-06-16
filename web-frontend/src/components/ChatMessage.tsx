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
  const roleClass = isUser ? 'user' : isSystem ? 'system' : 'assistant';

  return (
    <div className={`chat-message-row ${roleClass}`}>
      {/* Avatar */}
      <div className="chat-avatar">
        {isUser ? <UserOutlined /> : isSystem ? 'S' : <RobotOutlined />}
      </div>

      {/* Bubble */}
      <div className="chat-bubble">
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
  <div className="chat-message-row assistant">
    <div className="chat-avatar">
      <RobotOutlined />
    </div>
    <div className="chat-bubble">
      <span style={{ fontSize: 20, lineHeight: 1, color: 'rgba(226,232,240,0.58)' }}>
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
  <div className="chat-welcome">
    <div className="chat-welcome-core"><RobotOutlined /></div>
    <h3>RiskForge Copilot</h3>
    <p>围绕项目、模板、任务和评估结果进行对话式分析，也可以直接发起模板评审建议。</p>
    <div className="chat-prompt-grid">
      <span>解释一个特征为什么通过</span>
      <span>检查模板是否有业务含义污染</span>
      <span>总结本轮任务失败原因</span>
    </div>
  </div>
);

export default ChatMessage;
