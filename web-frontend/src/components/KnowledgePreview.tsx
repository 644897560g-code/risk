import React, { useEffect, useState } from 'react';
import { Drawer, Spin, Typography, Tag, Empty, Alert } from 'antd';
import { fetchKnowledgePreview } from '@/services/api';

const { Text } = Typography;

interface Props {
  filename: string | null;
  open: boolean;
  onClose: () => void;
}

const KnowledgePreview: React.FC<Props> = ({ filename, open, onClose }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ content: string; total_lines: number } | null>(null);

  useEffect(() => {
    if (!open || !filename) return;

    setLoading(true);
    setError(null);
    setPreview(null);

    fetchKnowledgePreview(filename)
      .then((data) => setPreview(data))
      .catch((e) => setError(e?.response?.data?.detail || e?.message || '预览加载失败'))
      .finally(() => setLoading(false));
  }, [filename, open]);

  const ext = filename?.split('.').pop()?.toLowerCase() || '';

  return (
    <Drawer
      title={
        <span>
          {filename}
          {ext && <Tag style={{ marginLeft: 8 }}>{ext.toUpperCase()}</Tag>}
        </span>
      }
      open={open}
      onClose={onClose}
      width={720}
    >
      {loading && (
        <div style={{ textAlign: 'center', padding: 40 }}><Spin /><p style={{ marginTop: 8, color: 'rgba(226,232,240,0.58)' }}>加载中...</p></div>
      )}
      {error && (
        <Alert type="error" message="预览失败" description={error} showIcon closable onClose={() => setError(null)} />
      )}
      {preview && (
        <div>
          {preview.total_lines > 100 && (
            <Text type="secondary" style={{ display: 'block', marginBottom: 8, fontSize: 12 }}>
              显示前 100 行（共 {preview.total_lines} 行）
            </Text>
          )}
          <pre style={{
            background: '#1e1e1e', color: '#d4d4d4', padding: 16, borderRadius: 6,
            fontSize: 13, lineHeight: 1.6, overflow: 'auto', maxHeight: 600,
            whiteSpace: 'pre-wrap', wordBreak: 'break-all', margin: 0,
          }}>
            {preview.content || <span style={{ color: 'rgba(226,232,240,0.58)' }}>（空文件）</span>}
          </pre>
        </div>
      )}
      {!loading && !error && !preview && <Empty description="无法预览该文件" />}
    </Drawer>
  );
};

export default KnowledgePreview;
