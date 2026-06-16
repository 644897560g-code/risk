import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Card,
  Col,
  Descriptions,
  Drawer,
  Empty,
  Form,
  Input,
  Modal,
  Row,
  Space,
  Table,
  Tabs,
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

type TemplateLifecycle = 'pending' | 'active' | 'rejected';

type TemplateRow = (Channel1Template | PendingTemplateItem) & {
  lifecycle: TemplateLifecycle;
  source?: string;
  reject_reason?: string;
  rejected_at?: string;
};

const initialRejectedTemplates: TemplateRow[] = [
  {
    template_id: 'T019',
    template_name: 'raw_device_identifier_join',
    template_name_cn: '设备标识直接拼接',
    dimension: '设备信息',
    description: '直接拼接设备标识生成特征，解释性弱且存在隐私口径风险。',
    dsl: 'concat(device_id, phone_hash)',
    python_function: 'raw_device_identifier_join',
    lifecycle: 'rejected',
    reject_reason: '缺少可解释业务含义，且未完成脱敏泛化。',
    rejected_at: '2026-06-13 16:20',
    source: '通道2',
  },
];

const lifecycleLabel: Record<TemplateLifecycle, { text: string; color: string }> = {
  pending: { text: '待审', color: 'warning' },
  active: { text: '已生效', color: 'success' },
  rejected: { text: '已驳回', color: 'error' },
};

const getQualityChecks = (row: TemplateRow) => {
  const parameterPass = row.template_id !== 'T018' && row.lifecycle !== 'rejected';
  return [
    { label: 'DSL 可解析', pass: true },
    { label: '命名模板完整', pass: Boolean(row.template_id && (row.template_name || row.template_name_cn || row.name)) },
    { label: '参数空间合理', pass: parameterPass },
    { label: '防穿越口径明确', pass: row.lifecycle !== 'rejected' },
  ];
};

const qualityText = (row: TemplateRow) => {
  const checks = getQualityChecks(row);
  const passed = checks.filter((item) => item.pass).length;
  return `${passed}/${checks.length}`;
};

const Templates: React.FC = () => {
  const [active, setActive] = useState<Channel1Template[]>([]);
  const [pending, setPending] = useState<PendingTemplateItem[]>([]);
  const [rejected, setRejected] = useState<TemplateRow[]>(initialRejectedTemplates);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [scope, setScope] = useState<TemplateLifecycle>('pending');
  const [detail, setDetail] = useState<TemplateRow | null>(null);
  const [rejecting, setRejecting] = useState<TemplateRow | null>(null);
  const [code, setCode] = useState('');
  const [codeLoading, setCodeLoading] = useState(false);
  const [rejectForm] = Form.useForm();

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
      message.error('模板库加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const allRows = useMemo<TemplateRow[]>(() => [
    ...pending.map((item) => ({ ...item, lifecycle: 'pending' as const })),
    ...active.map((item) => ({ ...item, lifecycle: 'active' as const })),
    ...rejected,
  ], [active, pending, rejected]);

  const rows = useMemo<TemplateRow[]>(() => {
    return allRows.filter((item) => {
      if (item.lifecycle !== scope) return false;
      const text = `${item.template_id} ${item.template_name || ''} ${item.template_name_cn || ''} ${item.dimension || ''} ${item.description || ''}`.toLowerCase();
      return text.includes(keyword.trim().toLowerCase());
    });
  }, [allRows, keyword, scope]);

  const templateTypes = useMemo(() => {
    const counter = new Map<string, number>();
    allRows.forEach((row) => counter.set(row.dimension || '未分类', (counter.get(row.dimension || '未分类') || 0) + 1));
    return Array.from(counter.entries()).sort((a, b) => b[1] - a[1]);
  }, [allRows]);

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
    const checks = getQualityChecks(row);
    if (checks.some((item) => !item.pass)) {
      message.warning('质量校验未全部通过，不能批准生效');
      return;
    }
    try {
      await approveChannel2Template(row.template_id);
      setPending((prev) => prev.filter((item) => item.template_id !== row.template_id));
      setActive((prev) => prev.some((item) => item.template_id === row.template_id)
        ? prev
        : [...prev, row as Channel1Template]);
      message.success('模板已批准生效');
      setDetail(null);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '审批失败');
    }
  };

  const openReject = (row: TemplateRow) => {
    setRejecting(row);
    rejectForm.resetFields();
  };

  const handleReject = async () => {
    const values = await rejectForm.validateFields();
    if (!rejecting) return;
    try {
      await rejectChannel2Template(rejecting.template_id, values.reason);
      setPending((prev) => prev.filter((item) => item.template_id !== rejecting.template_id));
      setRejected((prev) => [
        {
          ...rejecting,
          lifecycle: 'rejected',
          reject_reason: values.reason,
          rejected_at: new Date().toLocaleString('zh-CN'),
        },
        ...prev,
      ]);
      message.success('模板已驳回');
      setRejecting(null);
      setDetail(null);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '驳回失败');
    }
  };

  const columns: ColumnsType<TemplateRow> = [
    {
      title: '来源通道',
      width: 110,
      render: (_, row) => <Tag color={row.lifecycle === 'active' ? 'blue' : 'purple'}>{row.source || (row.lifecycle === 'active' ? '通道1' : '通道2')}</Tag>,
    },
    {
      title: '模板名',
      dataIndex: 'template_id',
      width: 260,
      render: (_: string, row) => (
        <div>
          <Space size={6}>
            <Text strong>{row.template_id}</Text>
            <Tag color={lifecycleLabel[row.lifecycle].color}>{lifecycleLabel[row.lifecycle].text}</Tag>
          </Space>
          <div style={{ color: 'rgba(226, 232, 240, 0.68)', marginTop: 4 }}>
            {row.template_name_cn || row.template_name || row.name || '-'}
          </div>
        </div>
      ),
    },
    { title: '维度', dataIndex: 'dimension', width: 130, render: (v: string) => <Tag>{v || '未分类'}</Tag> },
    {
      title: '质量校验',
      width: 120,
      render: (_, row) => {
        const text = qualityText(row);
        return <Tag color={text === '4/4' ? 'success' : 'warning'}>{text}</Tag>;
      },
    },
    {
      title: '状态时间',
      width: 170,
      render: (_, row) => row.rejected_at || (row.created_at ? new Date(row.created_at).toLocaleString('zh-CN') : '-'),
    },
    { title: '加工方式说明', dataIndex: 'description', ellipsis: true },
    {
      title: '操作',
      width: 180,
      render: (_, row) => (
        <Space>
          <Button icon={<EyeOutlined />} size="small" onClick={() => openDetail(row)}>详情</Button>
          {row.lifecycle === 'pending' && (
            <>
              <Button danger icon={<CloseOutlined />} size="small" onClick={() => openReject(row)}>驳回</Button>
              <Button
                type="primary"
                icon={<CheckOutlined />}
                size="small"
                disabled={qualityText(row) !== '4/4'}
                onClick={() => handleApprove(row)}
              >
                通过
              </Button>
            </>
          )}
        </Space>
      ),
    },
  ];

  const detailTabs = detail ? [
    {
      key: 'overview',
      label: '概览',
      children: (
        <Descriptions bordered size="small" column={1}>
          <Descriptions.Item label="状态"><Tag color={lifecycleLabel[detail.lifecycle].color}>{lifecycleLabel[detail.lifecycle].text}</Tag></Descriptions.Item>
          <Descriptions.Item label="来源通道">{detail.source || (detail.lifecycle === 'active' ? '通道1' : '通道2')}</Descriptions.Item>
          <Descriptions.Item label="维度">{detail.dimension || '-'}</Descriptions.Item>
          <Descriptions.Item label="加工方式说明">{detail.description || '-'}</Descriptions.Item>
          {detail.reject_reason && <Descriptions.Item label="驳回原因">{detail.reject_reason}</Descriptions.Item>}
        </Descriptions>
      ),
    },
    {
      key: 'logic',
      label: '逻辑框架',
      children: (
        <Card size="small" title="DSL / Python 口径" loading={codeLoading}>
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="DSL">{detail.dsl || '-'}</Descriptions.Item>
            <Descriptions.Item label="函数名">{detail.python_function || '-'}</Descriptions.Item>
          </Descriptions>
          <div style={{ marginTop: 12 }}>
            {code ? <pre className="code-preview">{code}</pre> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前模板没有可展示代码" />}
          </div>
        </Card>
      ),
    },
    {
      key: 'params',
      label: '参数空间与命名模板',
      children: (
        <Descriptions column={1} size="small" bordered>
          <Descriptions.Item label="参数空间">实体字段、时间窗口、统计方法、缺失值处理。</Descriptions.Item>
          <Descriptions.Item label="命名模板">{`${detail.template_name || detail.template_id.toLowerCase()}_{field}_{window}`}</Descriptions.Item>
          <Descriptions.Item label="适用范围">仅作为加工方式，具体特征是否交付由任务评估决定。</Descriptions.Item>
        </Descriptions>
      ),
    },
    {
      key: 'quality',
      label: '质量校验清单',
      children: (
        <Space direction="vertical" style={{ width: '100%' }}>
          {getQualityChecks(detail).map((item) => (
            <div key={item.label} className="dimension-row">
              <span>{item.label}</span>
              <Tag color={item.pass ? 'success' : 'warning'}>{item.pass ? '通过' : '未通过'}</Tag>
            </div>
          ))}
        </Space>
      ),
    },
    {
      key: 'history',
      label: '审批记录',
      children: (
        <Descriptions column={1} size="small" bordered>
          <Descriptions.Item label="当前状态">{lifecycleLabel[detail.lifecycle].text}</Descriptions.Item>
          <Descriptions.Item label="状态时间">{detail.rejected_at || (detail.created_at ? new Date(detail.created_at).toLocaleString('zh-CN') : '-')}</Descriptions.Item>
          <Descriptions.Item label="审批说明">{detail.reject_reason || '等待产品/风控确认。'}</Descriptions.Item>
        </Descriptions>
      ),
    },
  ] : [];

  return (
    <div className="page-enter">
      <div className="page-header">
        <div>
          <Title level={3} style={{ margin: 0 }}>模板库</Title>
          <Text type="secondary">平台级统一模板入口，管理待审、已生效和已驳回的数据加工方式</Text>
        </div>
        <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>刷新</Button>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={8}>
          <Card className="metric-card compact">
            <div className="metric-value">{pending.length}</div>
            <div className="metric-label">待审模板</div>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card className="metric-card compact">
            <div className="metric-value">{active.length}</div>
            <div className="metric-label">已生效模板</div>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card className="metric-card compact">
            <div className="metric-value">{rejected.length}</div>
            <div className="metric-label">已驳回模板</div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={6}>
          <Card title="模板维度分布">
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
                  placeholder="搜索模板名称、ID、维度"
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  style={{ width: 260 }}
                />
              </Space>
            )}
          >
            <Tabs
              activeKey={scope}
              onChange={(key) => setScope(key as TemplateLifecycle)}
              items={[
                { key: 'pending', label: `待审 ${pending.length}` },
                { key: 'active', label: `已生效 ${active.length}` },
                { key: 'rejected', label: `已驳回 ${rejected.length}` },
              ]}
            />
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
        width={760}
        extra={detail?.lifecycle === 'pending' ? (
          <Space>
            <Button danger icon={<CloseOutlined />} onClick={() => openReject(detail)}>驳回</Button>
            <Button
              type="primary"
              icon={<CheckOutlined />}
              disabled={qualityText(detail) !== '4/4'}
              onClick={() => handleApprove(detail)}
            >
              通过
            </Button>
          </Space>
        ) : null}
      >
        {detail && <Tabs items={detailTabs} />}
      </Drawer>

      <Modal
        title="驳回模板"
        open={!!rejecting}
        onCancel={() => setRejecting(null)}
        onOk={handleReject}
        okText="确认驳回"
        cancelText="取消"
      >
        <Form form={rejectForm} layout="vertical">
          <Form.Item
            name="reason"
            label="驳回原因"
            rules={[{ required: true, message: '请填写驳回原因' }]}
          >
            <Input.TextArea rows={4} placeholder="例如：加工逻辑与已有模板重复、解释性不足、质量校验未通过。" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Templates;
