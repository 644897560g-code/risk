import React, { useState, useRef, useEffect } from 'react';
import { Input, Button } from 'antd';
import { SendOutlined } from '@ant-design/icons';

const { TextArea } = Input;

interface Props {
  onSend: (message: string) => void;
  loading?: boolean;
  disabled?: boolean;
}

const ChatInput: React.FC<Props> = ({ onSend, loading = false, disabled = false }) => {
  const [value, setValue] = useState('');
  const textAreaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!loading && !disabled) {
      textAreaRef.current?.focus();
    }
  }, [loading, disabled]);

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || loading || disabled) return;
    onSend(trimmed);
    setValue('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div
      className="chat-input-bar"
    >
      <TextArea
        ref={textAreaRef as any}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={loading ? '等待回复中...' : disabled ? '系统繁忙，请稍后再试' : '输入消息，Enter发送，Shift+Enter换行'}
        rows={2}
        disabled={loading || disabled}
        style={{ flex: 1, resize: 'none' }}
      />
      <Button
        type="primary"
        icon={<SendOutlined />}
        onClick={handleSend}
        loading={loading}
        disabled={!value.trim() || disabled}
        style={{ alignSelf: 'flex-end' }}
      >
        发送
      </Button>
    </div>
  );
};

export default ChatInput;
