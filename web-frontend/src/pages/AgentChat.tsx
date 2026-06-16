import React, { useReducer, useCallback, useRef, useEffect, useState } from 'react';
import { Card, message as antMessage, Button, Tabs, List, Popconfirm, Empty, Tooltip, Space, Tag, Segmented } from 'antd';
import {
  ApiOutlined,
  FullscreenOutlined,
  FullscreenExitOutlined,
  PlusOutlined,
  DeleteOutlined,
  HistoryOutlined,
  RobotOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import ChatMessage, { ChatLoading, ChatError, ChatWelcome } from '@/components/ChatMessage';
import ChatInput from '@/components/ChatInput';
import TemplateSidebar from '@/components/TemplateSidebar';
import { sendChatMessageStream, fetchChatSessions, fetchChatSessionMessages, deleteChatSession, clearChatSessions } from '@/services/api';
import type { ChatMessage as ChatMessageType, ChatSessionSummary } from '@/types/agent';
import { useProjectStore } from '@/store/projectStore';

// ========== State ==========

interface ChatState {
  messages: ChatMessageType[];
  loading: boolean;
  streamingContent: string;
  error: string | null;
  conversationId: string | null;
}

type ChatAction =
  | { type: 'SET_MESSAGES'; messages: ChatMessageType[] }
  | { type: 'ADD_MESSAGE'; message: ChatMessageType }
  | { type: 'SET_STREAMING'; content: string }
  | { type: 'COMMIT_STREAMING' }
  | { type: 'SET_TOOL_CALL'; tool: string; status: string; detail: string }
  | { type: 'SET_LOADING'; loading: boolean }
  | { type: 'SET_ERROR'; error: string }
  | { type: 'CLEAR_ERROR' }
  | { type: 'SET_CONVERSATION_ID'; id: string }
  | { type: 'RESET' };

const initialChatState: ChatState = {
  messages: [],
  loading: false,
  streamingContent: '',
  error: null,
  conversationId: null,
};

function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'SET_MESSAGES':
      return { ...state, messages: action.messages, streamingContent: '' };
    case 'ADD_MESSAGE':
      return { ...state, messages: [...state.messages, action.message] };
    case 'SET_STREAMING':
      return { ...state, streamingContent: action.content };
    case 'COMMIT_STREAMING': {
      const content = state.streamingContent;
      if (!content) return state;
      return {
        ...state,
        messages: [...state.messages, { role: 'assistant', content, timestamp: new Date().toISOString() }],
        streamingContent: '',
      };
    }
    case 'SET_TOOL_CALL': {
      const msgs = [...state.messages];
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === 'assistant') {
          msgs[i] = { ...msgs[i], tool_call: { tool: action.tool, status: action.status, detail: action.detail } };
          break;
        }
      }
      return { ...state, messages: msgs };
    }
    case 'SET_LOADING':
      return { ...state, loading: action.loading };
    case 'SET_ERROR':
      return { ...state, error: action.error };
    case 'CLEAR_ERROR':
      return { ...state, error: null };
    case 'SET_CONVERSATION_ID':
      return { ...state, conversationId: action.id };
    case 'RESET':
      return { ...initialChatState };
    default:
      return state;
  }
}

// ========== Component ==========

const AgentChat: React.FC = () => {
  const [state, dispatch] = useReducer(chatReducer, initialChatState);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [sidebarTab, setSidebarTab] = useState('sessions');
  const [chatMode, setChatMode] = useState<'project' | 'template'>('project');
  const abortRef = useRef<AbortController | null>(null);
  const convIdRef = useRef<string | null>(null);
  const messagesRef = useRef<ChatMessageType[]>(state.messages);
  const currentProject = useProjectStore((s) => s.currentProject);

  // Session list state
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);

  const loadSessions = useCallback(async () => {
    setSessionsLoading(true);
    try {
      setSessions(await fetchChatSessions());
    } catch {
      // silent
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  // Load sessions on mount
  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [state.messages, state.loading, state.streamingContent]);

  // Keep messagesRef in sync
  useEffect(() => {
    messagesRef.current = state.messages;
  }, [state.messages]);

  const handleSend = useCallback((message: string) => {
    dispatch({
      type: 'ADD_MESSAGE',
      message: { role: 'user', content: message, timestamp: new Date().toISOString() },
    });
    dispatch({ type: 'SET_LOADING', loading: true });
    dispatch({ type: 'SET_STREAMING', content: '' });
    dispatch({ type: 'CLEAR_ERROR' });

    let accumulated = '';

    const controller = sendChatMessageStream(
      message,
      {
        onMeta: (convId) => {
          convIdRef.current = convId;
          dispatch({ type: 'SET_CONVERSATION_ID', id: convId });
        },
        onChunk: (text) => {
          accumulated += text;
          dispatch({ type: 'SET_STREAMING', content: accumulated });
        },
        onToolCall: (tool, status, detail) => {
          dispatch({ type: 'SET_TOOL_CALL', tool, status, detail });
          antMessage.success(detail);
        },
        onDone: () => {
          dispatch({ type: 'COMMIT_STREAMING' });
          dispatch({ type: 'SET_LOADING', loading: false });
          // Refresh session list so new session appears in sidebar
          loadSessions();
        },
        onError: (errMsg) => {
          dispatch({ type: 'SET_STREAMING', content: '' });
          dispatch({ type: 'SET_ERROR', error: errMsg });
          dispatch({ type: 'SET_LOADING', loading: false });
        },
      },
      convIdRef.current || undefined,
    );

    abortRef.current = controller;
  }, [loadSessions]);

  const handleRetry = useCallback(() => {
    const lastUserMsg = [...messagesRef.current].reverse().find(m => m.role === 'user');
    if (lastUserMsg) {
      handleSend(lastUserMsg.content);
    }
  }, [handleSend]);

  const handleNewSession = useCallback(() => {
    abortRef.current?.abort();
    dispatch({ type: 'RESET' });
    convIdRef.current = null;
  }, []);

  const handleSelectSession = useCallback(async (sessionId: string) => {
    abortRef.current?.abort();
    dispatch({ type: 'SET_LOADING', loading: true });
    try {
      const detail = await fetchChatSessionMessages(sessionId);
      const msgs: ChatMessageType[] = detail.messages.map((m) => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
        tool_call: m.tool_call || undefined,
        timestamp: m.created_at,
      }));
      dispatch({ type: 'SET_MESSAGES', messages: msgs });
      convIdRef.current = sessionId;
      dispatch({ type: 'SET_CONVERSATION_ID', id: sessionId });
    } catch {
      antMessage.error('加载会话失败');
    } finally {
      dispatch({ type: 'SET_LOADING', loading: false });
    }
  }, []);

  const handleDeleteSession = useCallback(async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await deleteChatSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      // If deleting the current session, reset
      if (convIdRef.current === sessionId) {
        dispatch({ type: 'RESET' });
        convIdRef.current = null;
      }
    } catch {
      antMessage.error('删除失败');
    }
  }, []);

  const handleClearAll = useCallback(async () => {
    try {
      await clearChatSessions();
      setSessions([]);
      dispatch({ type: 'RESET' });
      convIdRef.current = null;
    } catch {
      antMessage.error('清空失败');
    }
  }, []);

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="agent-console page-enter">
      {/* Left: Chat Panel */}
      <Card
        className="agent-chat-card"
        title={(
          <div className="agent-title">
            <span className="agent-core-icon"><RobotOutlined /></span>
            <div>
              <div className="agent-title-main">智能助理</div>
              <div className="agent-title-sub">
                {chatMode === 'project'
                  ? '当前项目模式：使用项目数据源、项目知识和项目任务上下文'
                  : '平台模板模式：用于讨论公共模板、模板审核和模板优化'}
              </div>
            </div>
          </div>
        )}
        extra={(
          <Space size={8} wrap>
            <Tag color="blue">当前项目：{currentProject?.name || '未选择'}</Tag>
            <Segmented
              size="small"
              value={chatMode}
              onChange={(value) => setChatMode(value as 'project' | 'template')}
              options={[
                { label: '当前项目模式', value: 'project' },
                { label: '平台模板模式', value: 'template' },
              ]}
            />
            <Tag color="cyan" icon={<ThunderboltOutlined />}>实时推理</Tag>
            <Tag color="geekblue" icon={<SafetyCertificateOutlined />}>防穿越校验</Tag>
            <Tag color="purple" icon={<ApiOutlined />}>模板联动</Tag>
          </Space>
        )}
        size="small"
        style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
        styles={{ body: { flex: 1, display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' } }}
      >
        {/* Messages area */}
        <div
          className="agent-message-stream"
        >
          {state.messages.length === 0 && !state.loading && !state.streamingContent && <ChatWelcome />}

          {state.messages.map((msg, i) => (
            <ChatMessage key={i} message={msg} />
          ))}

          {state.loading && state.streamingContent && (
            <ChatMessage message={{ role: 'assistant', content: state.streamingContent }} />
          )}

          {state.loading && !state.streamingContent && <ChatLoading />}

          {state.error && (
            <ChatError message={state.error} onRetry={handleRetry} />
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input area */}
        <ChatInput onSend={handleSend} loading={state.loading} />
      </Card>

      {/* Right: Sessions + Templates sidebar */}
      <div className="agent-side-rail" style={{ width: sidebarExpanded ? 'calc(100vw - 48px)' : 420 }}>
        <Card
          className="agent-side-card"
          size="small"
          styles={{ body: { padding: 0 } }}
          extra={
            <Button
              type="text"
              size="small"
              icon={sidebarExpanded ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
              onClick={() => setSidebarExpanded(!sidebarExpanded)}
            />
          }
        >
          <Tabs
            activeKey={sidebarTab}
            onChange={setSidebarTab}
            style={{ minHeight: 300 }}
            items={[
              {
                key: 'sessions',
                label: <span><HistoryOutlined /> 会话</span>,
                children: (
                  <div style={{ padding: '0 4px' }}>
                    <div className="agent-session-actions">
                      <Button size="small" type="primary" icon={<PlusOutlined />} onClick={handleNewSession}>
                        新建
                      </Button>
                      {sessions.length > 0 && (
                        <Popconfirm title="确定清空所有会话？" onConfirm={handleClearAll} okText="确定" cancelText="取消">
                          <Button size="small" danger icon={<DeleteOutlined />}>
                            清空
                          </Button>
                        </Popconfirm>
                      )}
                    </div>
                    {sessions.length === 0 && !sessionsLoading && (
                      <Empty description="暂无会话" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ margin: '40px 0' }} />
                    )}
                    <List
                      loading={sessionsLoading}
                      dataSource={sessions}
                      renderItem={(s) => (
                        <List.Item
                          key={s.id}
                          onClick={() => handleSelectSession(s.id)}
                          style={{
                            cursor: 'pointer',
                            padding: '10px 12px',
                            borderRadius: 8,
                            margin: '2px 4px',
                            background: convIdRef.current === s.id ? 'rgba(55, 231, 255, 0.14)' : 'transparent',
                            border: convIdRef.current === s.id ? '1px solid rgba(55, 231, 255, 0.28)' : '1px solid transparent',
                          }}
                          onMouseEnter={(e) => {
                            if (convIdRef.current !== s.id) {
                              (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.06)';
                            }
                          }}
                          onMouseLeave={(e) => {
                            if (convIdRef.current !== s.id) {
                              (e.currentTarget as HTMLElement).style.background = 'transparent';
                            }
                          }}
                        >
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontSize: 13, fontWeight: convIdRef.current === s.id ? 600 : 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {s.title}
                            </div>
                            <div style={{ fontSize: 11, color: 'rgba(226, 232, 240, 0.62)', marginTop: 2 }}>
                              {formatTime(s.updated_at)}
                            </div>
                          </div>
                          <Tooltip title="删除">
                            <Button
                              type="text"
                              size="small"
                              danger
                              icon={<DeleteOutlined />}
                              onClick={(e) => handleDeleteSession(s.id, e)}
                              style={{ flexShrink: 0 }}
                            />
                          </Tooltip>
                        </List.Item>
                      )}
                    />
                  </div>
                ),
              },
              {
                key: 'templates',
                label: '模板',
                children: <TemplateSidebar />,
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
};

export default AgentChat;
