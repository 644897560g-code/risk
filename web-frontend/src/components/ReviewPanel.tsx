import React, { useEffect, useState, useCallback } from 'react';
import {
  Button, Tag, Space, Table, Modal, Input, Descriptions, Empty, message,
} from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { fetchPendingChannel2Templates, approveChannel2Template, rejectChannel2Template } from '@/services/api';
import type { PendingTemplate } from '@/types/agent';

const { TextArea } = Input;

const ReviewPanel: React.FC = () => {
  const [pendingTemplates, setPendingTemplates] = useState<PendingTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [rejectTargetId, setRejectTargetId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('');

  const loadTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const templates = await fetchPendingChannel2Templates();
      setPendingTemplates(templates);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTemplates();
    const interval = setInterval(loadTemplates, 5000);
    return () => clearInterval(interval);
  }, [loadTemplates]);

  const handleApprove = async (templateId: string) => {
    try {
      await approveChannel2Template(templateId);
      message.success(`模板 ${templateId} 已审批通过`);
      loadTemplates();
    } catch (e: any) {
      message.error('审批失败: ' + (e?.message || ''));
    }
  };

  const handleReject = async () => {
    if (!rejectTargetId) return;
    try {
      await rejectChannel2Template(rejectTargetId, rejectReason);
      message.success(`模板 ${rejectTargetId} 已拒绝`);
      setRejectModalOpen(false);
      setRejectReason('');
      setRejectTargetId(null);
      loadTemplates();
    } catch (e: any) {
      message.error('操作失败: ' + (e?.message || ''));
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'template_id', key: 'template_id', width: 80 },
    { title: '名称', dataIndex: 'template_name', key: 'template_name', ellipsis: true },
    { title: '维度', dataIndex: 'dimension', key: 'dimension', width: 70 },
    {
      title: '操作', key: 'actions', width: 150,
      render: (_: any, r: PendingTemplate) => (
        <Space>
          <Button type="primary" size="small" icon={<CheckCircleOutlined />}
            onClick={() => handleApprove(r.template_id)}>通过</Button>
          <Button danger size="small" icon={<CloseCircleOutlined />}
            onClick={() => { setRejectTargetId(r.template_id); setRejectReason(''); setRejectModalOpen(true); }}>拒绝</Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      {pendingTemplates.length > 0 ? (
        <Table
          dataSource={pendingTemplates}
          columns={columns}
          rowKey="template_id"
          size="small"
          pagination={false}
          expandable={{
            expandedRowRender: (record: PendingTemplate) => (
              <div style={{ padding: 8 }}>
                <Descriptions size="small" column={1} bordered>
                  <Descriptions.Item label="DSL">{record.dsl}</Descriptions.Item>
                  <Descriptions.Item label="函数">{record.python_function}</Descriptions.Item>
                  {record.python_code && (
                    <Descriptions.Item label="代码">
                      <pre style={{ margin: 0, fontSize: 11, maxHeight: 150, overflow: 'auto' }}>
                        {record.python_code}
                      </pre>
                    </Descriptions.Item>
                  )}
                </Descriptions>
              </div>
            ),
          }}
        />
      ) : (
        <Empty description="暂无待审批的通道2模板" />
      )}

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

export default ReviewPanel;
