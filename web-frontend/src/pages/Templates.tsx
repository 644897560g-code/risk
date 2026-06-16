import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Card,
  Col,
  Descriptions,
  Drawer,
  Empty,
  Alert,
  Input,
  Row,
  Segmented,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import { CheckOutlined, CloseOutlined, EyeOutlined, ReloadOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  approveChannel2Template,
  fetchChannel1TemplateCode,
  fetchChannel1Templates,
  fetchChannel2PendingTemplates,
  rejectChannel2Template,
  type Channel1Template,
  type PendingTemplateItem,
} from '@/services/api';

const { Text, Title } = Typography;

type TemplateRow = (Channel1Template | PendingTemplateItem) & {
  lifecycle: 'active' | 'pending';
};

const Templates: React.FC = () => {
  const [active, setActive] = useState<Channel1Template[]>([]);
  const [pending, setPending] = useState<PendingTemplateItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [scope, setScope] = useState<'all' | 'active' | 'pending'>('all');
  const [detail, setDetail] = useState<TemplateRow | null>(null);
  const [code, setCode] = useState('');
  const [codeLoading, setCodeLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [activeRes, pendingRes] = await Promise.all([
        fetchChannel1Templates(),
        fetchChannel2PendingTemplates(),
      ]);
      setActive(activeRes);
      setPending(pendingRes);
    } catch {
      message.error('模板资产加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const rows = useMemo<TemplateRow[]>(() => {
    const merged: TemplateRow[] = [
      ...active.map((item) => ({ ...item, lifecycle: 'active' as const })),
      ...pending.map((item) => ({ ...item, lifecycle: 'pending' as const })),
    ];
    return merged.filter((item) => {
      if (scope !== 'all' && item.lifecycle !== scope) return false;
      const text = `${item.template_id} ${item.template_name || ''} ${item.template_name_cn || ''} ${item.dimension || ''} ${item.description || ''}`.toLowerCase();
      return text.includes(keyword.trim().toLowerCase());
    });
  }, [active, pending, keyword, scope]);

  const templateTypes = useMemo(() => {
    const counter = new Map<string, number>();
    rows.forEach((row) => counter.set(row.dimension || '未分类', (counter.get(row.dimension || '未分类') || 0) + 1));
    return Array.from(counter.entries()).sort((a, b) => b[1] - a[1]);
  }, [rows]);

  const openDetail = async (row: TemplateRow) => {
    setDetail(row);
    setCode(row.python_code || '');
    if (row.lifecycle === 'active' && !row.python_code) {
      setCodeLoading(true);
      try {
        setCode(await fetchChannel1TemplateCode(row.template_id));
      } catch {
        setCode('');
      } finally {
        setCodeLoading(false);
      }
    }
  };

  const handleApprove = async (row: TemplateRow) => {
    try {
      await approveChannel2Template(row.template_id);
      message.success('模板已批准启用');
      await load();
      setDetail(null);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '审批失败');
    }
  };

  const handleReject = async (row: TemplateRow) => {
    try {
      await rejectChannel2Template(row.template_id, '产品评审未通过');
      message.success('模板已拒绝');
      await load();
      setDetail(null);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '拒绝失败');
    }
  };

  const columns: ColumnsType<TemplateRow> = [
    {
      title: '模板',
      dataIndex: 'template_id',
      width: 260,
      render: (_: string, row) => (
        <div>
          <Space size={6}>
            <Text strong>{row.template_id}</Text>
            <Tag color={row.lifecycle === 'active' ? 'success' : 'processing'}>
              {row.lifecycle === 'active' ? '已启用' : '待审批'}
            </Tag>
          </Space>
          <div style={{ color: 'rgba(226, 232, 240, 0.68)', marginTop: 4 }}>
            {row.template_name_cn || row.template_name || row.name || '-'}
          </div>
        </div>
      ),
    },
    { title: '模板类型', dataIndex: 'dimension', width: 140, render: (v: string) => <Tag>{v || '未分类'}</Tag> },
    { title: '加工方式说明', dataIndex: 'description', ellipsis: true },
    {
      title: '产品判断',
      width: 130,
      render: (_, row) => row.lifecycle === 'active'
        ? <Tag color="success">可用于生产</Tag>
        : <Tag color="warning">需评审</Tag>,
    },
    {
      title: '操作',
      width: 110,
      render: (_, row) => <Button icon={<EyeOutlined />} size="small" onClick={() => openDetail(row)}>详情</Button>,
    },
  ];

  return (
    <div className="page-enter">
      <div className="page-header">
        <div>
          <Title level={3} style={{ margin: 0 }}>模板资产</Title>
          <Text type="secondary">管理可复用的数据加工方式；特征是否上线由后续任务评估判断</Text>
        </div>
        <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>刷新</Button>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={8}>
          <Card className="metric-card compact">
            <div className="metric-value">{active.length}</div>
            <div className="metric-label">已启用模板</div>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card className="metric-card compact">
            <div className="metric-value">{pending.length}</div>
            <div className="metric-label">待审批模板</div>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card className="metric-card compact">
            <div className="metric-value">{templateTypes.length}</div>
            <div className="metric-label">模板类型</div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={6}>
          <Card title="模板类型分布">
            {templateTypes.length ? templateTypes.map(([dimension, count]) => (
              <div key={dimension} className="dimension-row">
                <span>{dimension}</span>
                <Tag>{count}</Tag>
              </div>
            )) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />}
          </Card>
        </Col>
        <Col xs={24} lg={18}>
          <Card
            title="模板清单"
            extra={(
              <Space>
                <Input.Search
                  allowClear
                  placeholder="搜索模板名称、ID、加工方式"
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  style={{ width: 260 }}
                />
                <Segmented
                  value={scope}
                  onChange={(value) => setScope(value as typeof scope)}
                  options={[
                    { label: '全部', value: 'all' },
                    { label: '已启用', value: 'active' },
                    { label: '待审批', value: 'pending' },
                  ]}
                />
              </Space>
            )}
          >
            <Table
              rowKey={(row) => `${row.lifecycle}-${row.template_id}`}
              loading={loading}
              columns={columns}
              dataSource={rows}
              pagination={{ pageSize: 10, showTotal: (total) => `共 ${total} 个模板` }}
            />
          </Card>
        </Col>
      </Row>

      <Drawer
        title={detail ? `${detail.template_id} · ${detail.template_name_cn || detail.template_name || detail.name || '模板详情'}` : '模板详情'}
        open={!!detail}
        onClose={() => setDetail(null)}
        width={720}
        extra={detail?.lifecycle === 'pending' ? (
          <Space>
            <Button danger icon={<CloseOutlined />} onClick={() => handleReject(detail)}>拒绝</Button>
            <Button type="primary" icon={<CheckOutlined />} onClick={() => handleApprove(detail)}>批准启用</Button>
          </Space>
        ) : null}
      >
        {detail && (
          <>
            <Alert
              type={detail.lifecycle === 'active' ? 'success' : 'warning'}
              showIcon
              style={{ marginBottom: 16 }}
              message={detail.lifecycle === 'active' ? '该模板已可用于生产任务' : '该模板仍需产品/风控评审'}
              description="评审重点是加工方式是否合理、是否可解释、是否与已有模板重复；特征效果由后续生产任务评估。"
            />
            <Descriptions bordered size="small" column={1}>
              <Descriptions.Item label="状态">
                <Tag color={detail.lifecycle === 'active' ? 'success' : 'processing'}>
                  {detail.lifecycle === 'active' ? '已启用' : '待审批'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="模板类型">{detail.dimension || '-'}</Descriptions.Item>
              <Descriptions.Item label="加工方式说明">{detail.description || '-'}</Descriptions.Item>
              <Descriptions.Item label="DSL">{detail.dsl || '-'}</Descriptions.Item>
              <Descriptions.Item label="函数名">{detail.python_function || '-'}</Descriptions.Item>
            </Descriptions>
            <Card title="模板代码/口径" size="small" style={{ marginTop: 16 }} loading={codeLoading}>
              {code ? (
                <pre className="code-preview">{code}</pre>
              ) : (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前模板没有可展示代码" />
              )}
            </Card>
          </>
        )}
      </Drawer>
    </div>
  );
};

export default Templates;
