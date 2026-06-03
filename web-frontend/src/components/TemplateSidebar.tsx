import React, { useEffect, useState, useCallback } from 'react';
import {
  Table, Tabs, Button, Tag, Space, message, Tooltip, Modal,
} from 'antd';
import {
  CheckCircleOutlined, CloseCircleOutlined, CodeOutlined, FileTextOutlined,
} from '@ant-design/icons';
import {
  fetchChannel1Templates,
  fetchChannel2PendingTemplates,
  approveChannel2Template,
  rejectChannel2Template,
  fetchChannel1TemplateCode,
  type Channel1Template,
  type PendingTemplateItem,
} from '@/services/api';
import { Input } from 'antd';

const { TextArea } = Input;

const TemplateSidebar: React.FC = () => {
  const [channel1Items, setChannel1Items] = useState<Channel1Template[]>([]);
  const [channel2Items, setChannel2Items] = useState<PendingTemplateItem[]>([]);
  const [loading1, setLoading1] = useState(false);
  const [loading2, setLoading2] = useState(false);
  const [modalContent, setModalContent] = useState<string | null>(null);
  const [modalTitle, setModalTitle] = useState('');

  // Reject state
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [rejectTargetId, setRejectTargetId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('');

  const loadChannel1 = useCallback(async () => {
    setLoading1(true);
    try {
      setChannel1Items(await fetchChannel1Templates());
    } catch {
      // silent
    } finally {
      setLoading1(false);
    }
  }, []);

  const loadChannel2 = useCallback(async (silent = false) => {
    if (!silent) setLoading2(true);
    try {
      setChannel2Items(await fetchChannel2PendingTemplates());
    } catch {
      // silent
    } finally {
      if (!silent) setLoading2(false);
    }
  }, []);

  useEffect(() => {
    loadChannel1();
    loadChannel2();
    // Silent polling every 5s — does not show spinner
    const interval = setInterval(() => loadChannel2(true), 5000);
    return () => clearInterval(interval);
  }, [loadChannel1, loadChannel2]);

  const handleApprove = async (templateId: string) => {
    try {
      await approveChannel2Template(templateId);
      message.success('模板已通过审批');
      await loadChannel1();
      await loadChannel2();
    } catch {
      message.error('审批操作失败');
    }
  };

  const handleReject = async () => {
    if (!rejectTargetId) return;
    try {
      await rejectChannel2Template(rejectTargetId, rejectReason);
      message.success('模板已拒绝');
      setRejectModalOpen(false);
      setRejectTargetId(null);
      setRejectReason('');
      await loadChannel2();
    } catch {
      message.error('拒绝操作失败');
    }
  };

  const showCode = (title: string, content: string) => {
    setModalTitle(title);
    setModalContent(content);
  };

  const codeLinkColumn = {
    title: '代码', key: 'code',
    render: (_: unknown, record: any) => {
      const handleClick = () => {
        const code = record.python_code || '';
        if (code) {
          showCode(`Python: ${record.template_name || record.name}`, code);
          return;
        }
        // For channel1 templates, python_code is empty — fetch from server
        setModalTitle(`Python: ${record.template_name || record.name}`);
        setModalContent('加载中...');
        fetchChannel1TemplateCode(record.template_id).then(c => {
          setModalContent(c || record.python_function || '// 无代码');
        }).catch(() => {
          setModalContent(record.python_function || '// 无法加载源代码');
        });
      };
      return (
        <Tooltip title="查看DSL对应的Python代码">
          <Button type="link" size="small" icon={<FileTextOutlined />}
            onClick={handleClick}>
            代码
          </Button>
        </Tooltip>
      );
    },
  };

  const channel1Columns = [
    { title: '名称', dataIndex: 'template_name', key: 'template_name', ellipsis: true, render: (v: string, r: Channel1Template) => v || r.name || '-' },
    {
      title: '维度', dataIndex: 'dimension', key: 'dimension',
      render: (d: string) => <Tag style={{ fontSize: 11 }}>{d}</Tag>,
    },
    {
      title: 'DSL', key: 'dsl',
      render: (_: unknown, record: Channel1Template) => (
        <Tooltip title="查看DSL">
          <Button type="link" size="small" icon={<CodeOutlined />}
            onClick={() => showCode(`DSL: ${record.template_name || record.name}`, record.dsl)} />
        </Tooltip>
      ),
    },
    codeLinkColumn,
  ];

  const sourceConfig: Record<string, { label: string; color: string }> = {
    '知识': { label: '知识', color: 'green' },
    '模板生成': { label: '模板生成', color: 'blue' },
    'agent chat': { label: 'agent chat', color: 'orange' },
  };

  const channel2Columns = [
    { title: '名称', dataIndex: 'template_name', key: 'template_name', ellipsis: true, render: (v: string, r: PendingTemplateItem) => v || r.name || '-' },
    {
      title: '维度', dataIndex: 'dimension', key: 'dimension',
      render: (d: string) => <Tag style={{ fontSize: 11 }}>{d}</Tag>,
    },
    {
      title: '来源', dataIndex: 'source', key: 'source', width: 80,
      render: (s: string) => {
        const cfg = sourceConfig[s] || { label: s || '-', color: 'default' };
        return <Tag color={cfg.color} style={{ fontSize: 11 }}>{cfg.label}</Tag>;
      },
    },
    {
      title: 'DSL', dataIndex: 'dsl', key: 'dsl', ellipsis: true,
      render: (dsl: string) => dsl ? (
        <Tooltip title="查看完整DSL">
          <Button type="link" size="small" style={{ padding: 0, fontSize: 12, textAlign: 'left' }}
            onClick={() => showCode('DSL', dsl)}>
            {dsl.length > 18 ? `${dsl.slice(0, 18)}...` : dsl}
          </Button>
        </Tooltip>
      ) : '-',
    },
    codeLinkColumn,
    {
      title: '操作', key: 'actions',
      render: (_: unknown, record: PendingTemplateItem) => (
        <Space size={2}>
          <Button type="primary" size="small" icon={<CheckCircleOutlined />}
            onClick={() => record.template_id && handleApprove(record.template_id)} />
          <Button danger size="small" icon={<CloseCircleOutlined />}
            onClick={() => { setRejectTargetId(record.template_id || ''); setRejectReason(''); setRejectModalOpen(true); }} />
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Tabs
        size="small"
        defaultActiveKey="channel2"
        items={[
          {
            key: 'channel1',
            label: `已生效 (${channel1Items.length})`,
            children: (
              <div style={{ overflowX: 'auto' }}>
                <Table
                  dataSource={channel1Items}
                  columns={channel1Columns}
                  rowKey="template_id"
                  loading={loading1}
                  size="small"
                  pagination={false}
                  locale={{ emptyText: '暂无已生效模板' }}
                />
              </div>
            ),
          },
          {
            key: 'channel2',
            label: `待审核 (${channel2Items.length})`,
            children: (
              <div style={{ overflowX: 'auto' }}>
                <Table
                  dataSource={channel2Items}
                  columns={channel2Columns}
                  rowKey="template_id"
                  loading={loading2}
                  size="small"
                  pagination={false}
                  locale={{ emptyText: '暂无待审核模板' }}
                />
              </div>
            ),
          },
        ]}
      />

      {/* Code viewer modal */}
      <Modal
        title={modalTitle}
        open={!!modalContent}
        onCancel={() => setModalContent(null)}
        footer={null}
        width={600}
      >
        <pre style={{
          background: '#1e1e1e',
          color: '#d4d4d4',
          padding: 16,
          borderRadius: 4,
          fontSize: 12,
          maxHeight: 400,
          overflow: 'auto',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-all',
          margin: 0,
        }}>
          {modalContent}
        </pre>
      </Modal>

      {/* Reject reason modal */}
      <Modal
        title="输入退回原因"
        open={rejectModalOpen}
        onOk={handleReject}
        onCancel={() => { setRejectModalOpen(false); setRejectTargetId(null); }}
        okText="确认退回"
        cancelText="取消"
        okButtonProps={{ danger: true }}
      >
        <TextArea
          rows={3}
          value={rejectReason}
          onChange={(e) => setRejectReason(e.target.value)}
          placeholder="请输入退回原因（可选）"
        />
      </Modal>
    </div>
  );
};

export default TemplateSidebar;
