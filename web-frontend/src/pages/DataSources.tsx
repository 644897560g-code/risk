import React, { useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Input,
  Modal,
  Progress,
  Radio,
  Row,
  Select,
  Space,
  Steps,
  Table,
  Tag,
  Typography,
  Upload,
  message,
} from 'antd';
import {
  CheckCircleOutlined,
  DatabaseOutlined,
  ExclamationCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useProjectStore } from '@/store/projectStore';

const { Text, Title } = Typography;

interface DataSourceRow {
  id: string;
  name: string;
  type: 'file' | 'database';
  status: 'ready' | 'pending';
  snapshot: string;
  sampleCount: number;
  labelCoverage: number;
  timeRange: string;
  agentStatus: string;
}

interface SnapshotRow {
  id: string;
  source: string;
  createdAt: string;
  sampleCount: number;
  labelCoverage: number;
  qualityStatus: string;
  task: string;
}

const dataSources: DataSourceRow[] = [
  {
    id: 'ds_file_0421',
    name: '0421首贷样本文件源',
    type: 'file',
    status: 'ready',
    snapshot: 'snapshot_20260615_001',
    sampleCount: 2272,
    labelCoverage: 100,
    timeRange: '2026-04-01 至 2026-04-21',
    agentStatus: '字段识别完成，业务口径已确认',
  },
  {
    id: 'ds_fdc_db',
    name: '印尼FDC数据库连接',
    type: 'database',
    status: 'pending',
    snapshot: '待生成',
    sampleCount: 0,
    labelCoverage: 0,
    timeRange: '待配置',
    agentStatus: '待接入数据库后识别',
  },
];

const snapshots: SnapshotRow[] = [
  {
    id: 'snapshot_20260615_001',
    source: '0421首贷样本文件源',
    createdAt: '2026-06-15 14:20',
    sampleCount: 2272,
    labelCoverage: 100,
    qualityStatus: '通过',
    task: '#108 印尼首贷6月批量特征生产',
  },
  {
    id: 'snapshot_20260612_001',
    source: '0421首贷样本文件源',
    createdAt: '2026-06-12 09:00',
    sampleCount: 2272,
    labelCoverage: 100,
    qualityStatus: '通过',
    task: '#106 5月首贷样本复盘',
  },
];

const previewRows = [
  { orderId: 'id002luzt202603090951432723072', applyTime: '2026-04-21 09:51', label: '逾期', appCount: 47, fdcRecords: 23 },
  { orderId: 'id002demo202604210000000001', applyTime: '2026-04-21 10:12', label: '正常', appCount: 39, fdcRecords: 8 },
  { orderId: 'id002demo202604210000000002', applyTime: '2026-04-21 10:45', label: '逾期', appCount: 61, fdcRecords: 15 },
];

const sourceColumns: ColumnsType<DataSourceRow> = [
  {
    title: '数据源',
    dataIndex: 'name',
    render: (name: string, row) => (
      <Space direction="vertical" size={2}>
        <Text strong>{name}</Text>
        <Text type="secondary">{row.type === 'file' ? '文件上传' : '数据库连接'}</Text>
      </Space>
    ),
  },
  {
    title: '状态',
    dataIndex: 'status',
    width: 110,
    render: (status: DataSourceRow['status']) => (
      status === 'ready' ? <Tag color="success">可用于任务</Tag> : <Tag color="warning">待配置</Tag>
    ),
  },
  { title: '最近快照', dataIndex: 'snapshot', width: 190 },
  { title: '样本量', dataIndex: 'sampleCount', width: 90 },
  {
    title: '标签覆盖',
    dataIndex: 'labelCoverage',
    width: 110,
    render: (value: number) => value ? `${value}%` : '-',
  },
  { title: '时间范围', dataIndex: 'timeRange', width: 210 },
  { title: 'Agent解析状态', dataIndex: 'agentStatus', ellipsis: true },
];

const snapshotColumns: ColumnsType<SnapshotRow> = [
  { title: '快照ID', dataIndex: 'id', width: 190, render: (id: string) => <Tag color="blue">{id}</Tag> },
  { title: '来源数据源', dataIndex: 'source', ellipsis: true },
  { title: '生成时间', dataIndex: 'createdAt', width: 160 },
  { title: '样本量', dataIndex: 'sampleCount', width: 90 },
  { title: '标签覆盖', dataIndex: 'labelCoverage', width: 100, render: (value: number) => `${value}%` },
  { title: '质量检查', dataIndex: 'qualityStatus', width: 100, render: (value: string) => <Tag color="success">{value}</Tag> },
  { title: '最近任务', dataIndex: 'task', ellipsis: true },
];

const DataSources: React.FC = () => {
  const currentProject = useProjectStore((s) => s.currentProject);
  const readySource = dataSources.find((item) => item.status === 'ready');
  const [uploadOpen, setUploadOpen] = useState(false);
  const [databaseOpen, setDatabaseOpen] = useState(false);
  const [snapshotOpen, setSnapshotOpen] = useState(false);
  const [snapshotSource, setSnapshotSource] = useState<DataSourceRow | null>(null);
  const [uploadForm] = Form.useForm();
  const [databaseForm] = Form.useForm();
  const [snapshotForm] = Form.useForm();

  const openSnapshot = (source?: DataSourceRow) => {
    setSnapshotSource(source || readySource || dataSources[0]);
    snapshotForm.setFieldsValue({
      snapshot_name: `snapshot_${new Date().toISOString().slice(0, 10).replace(/-/g, '')}_new`,
      sample_scope: '首贷客户',
      label_meaning: '标签1表示逾期，标签0表示正常',
      time_policy: '以申请时间向前回溯，禁止使用申请后数据',
    });
    setSnapshotOpen(true);
  };

  const handleUploadSubmit = async () => {
    await uploadForm.validateFields();
    message.success('文件数据源已创建，Agent将继续识别数据结构并生成质量检查结果');
    setUploadOpen(false);
    uploadForm.resetFields();
  };

  const handleDatabaseSubmit = async () => {
    await databaseForm.validateFields();
    message.success('数据库连接已提交，连通性检查和Agent识别将在后台执行');
    setDatabaseOpen(false);
    databaseForm.resetFields();
  };

  const handleSnapshotSubmit = async () => {
    await snapshotForm.validateFields();
    message.success('数据快照生成任务已提交');
    setSnapshotOpen(false);
  };

  const columns: ColumnsType<DataSourceRow> = [
    ...sourceColumns,
    {
      title: '操作',
      width: 110,
      render: (_, row) => (
        <Button size="small" disabled={row.status !== 'ready'} onClick={() => openSnapshot(row)}>
          生成快照
        </Button>
      ),
    },
  ];

  return (
    <div className="page-enter">
      <div className="page-header">
        <div>
          <Title level={3} style={{ margin: 0 }}>数据源</Title>
          <Text type="secondary">
            {currentProject?.name ? `当前项目：${currentProject.name}。` : ''}
            本页数据仅属于当前项目；任务不直接消费临时数据，而是绑定数据快照执行。
          </Text>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />}>刷新</Button>
          <Button icon={<UploadOutlined />} onClick={() => setUploadOpen(true)}>上传文件源</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setDatabaseOpen(true)}>新增数据库连接</Button>
        </Space>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={8}>
          <Card title="项目数据可用性">
            <Space direction="vertical" size={14} style={{ width: '100%' }}>
              <div>
                <Text type="secondary">最近可用快照</Text>
                <div style={{ marginTop: 6 }}><Tag color="blue">{readySource?.snapshot || '暂无'}</Tag></div>
              </div>
              <div>
                <Text type="secondary">基础质量检查</Text>
                <Progress percent={92} strokeColor="#34d399" style={{ marginTop: 6 }} />
              </div>
              <Descriptions column={1} size="small">
                <Descriptions.Item label="可用数据源">1 个</Descriptions.Item>
                <Descriptions.Item label="任务绑定方式">选择快照 / 生成新快照</Descriptions.Item>
                <Descriptions.Item label="项目隔离"><Tag color="success">已按项目隔离</Tag></Descriptions.Item>
              </Descriptions>
            </Space>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="Agent数据识别">
            <Space direction="vertical" size={10} style={{ width: '100%' }}>
              <div className="dimension-row"><span>订单号</span><Tag color="success">已识别</Tag></div>
              <div className="dimension-row"><span>申请时间</span><Tag color="success">已识别</Tag></div>
              <div className="dimension-row"><span>好坏标签</span><Tag color="success">已识别</Tag></div>
              <div className="dimension-row"><span>APP列表</span><Tag color="success">已识别</Tag></div>
              <div className="dimension-row"><span>FDC报告</span><Tag color="success">已识别</Tag></div>
            </Space>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="业务口径确认">
            <Space direction="vertical" size={10} style={{ width: '100%' }}>
              <div className="dimension-row">
                <span>当前状态</span>
                <Tag color="success">可启动任务</Tag>
              </div>
              <Text type="secondary">标签1表示逾期，样本范围为首贷客户，时间口径以申请时间向前回溯。</Text>
              <Space wrap>
                <Tag color="success" icon={<CheckCircleOutlined />}>首贷范围</Tag>
                <Tag color="success" icon={<CheckCircleOutlined />}>标签含义</Tag>
                <Tag color="success" icon={<CheckCircleOutlined />}>防穿越口径</Tag>
              </Space>
            </Space>
          </Card>
        </Col>
      </Row>

      <Card title="数据源列表" style={{ marginTop: 16 }}>
        <Table
          rowKey="id"
          size="small"
          columns={columns}
          dataSource={dataSources}
          pagination={false}
        />
      </Card>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={14}>
          <Card title="数据预览">
            <Table
              rowKey="orderId"
              size="small"
              dataSource={previewRows}
              pagination={false}
              columns={[
                { title: '订单号', dataIndex: 'orderId', ellipsis: true },
                { title: '申请时间', dataIndex: 'applyTime', width: 160 },
                { title: '标签', dataIndex: 'label', width: 80, render: (value: string) => <Tag color={value === '逾期' ? 'error' : 'success'}>{value}</Tag> },
                { title: 'APP数', dataIndex: 'appCount', width: 80 },
                { title: 'FDC记录', dataIndex: 'fdcRecords', width: 90 },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="基础质量检查">
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <div className="dimension-row"><span>样本量满足评估要求</span><Tag color="success">通过</Tag></div>
              <div className="dimension-row"><span>标签覆盖率</span><Tag color="success">100%</Tag></div>
              <div className="dimension-row"><span>申请时间完整性</span><Tag color="success">通过</Tag></div>
              <div className="dimension-row"><span>APP/FDC结构可解析</span><Tag color="success">通过</Tag></div>
              <div className="dimension-row"><span>数据库连接</span><Tag color="warning" icon={<ExclamationCircleOutlined />}>待接入</Tag></div>
            </Space>
          </Card>
        </Col>
      </Row>

      <Card title="数据快照" style={{ marginTop: 16 }}>
        <div style={{ marginBottom: 12, textAlign: 'right' }}>
          <Button type="primary" onClick={() => openSnapshot()} disabled={!readySource}>生成新快照</Button>
        </div>
        <Table
          rowKey="id"
          size="small"
          columns={snapshotColumns}
          dataSource={snapshots}
          pagination={false}
        />
      </Card>

      <Modal
        title="上传文件数据源"
        open={uploadOpen}
        onCancel={() => setUploadOpen(false)}
        onOk={handleUploadSubmit}
        okText="创建数据源"
        cancelText="取消"
        width={760}
      >
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="上传文件会先进入项目级数据源"
          description="本次上传不会直接绑定任务。系统会先完成Agent数据识别、业务口径确认和质量检查，然后生成可被任务引用的数据快照。"
        />
        <Steps
          size="small"
          current={0}
          style={{ marginBottom: 20 }}
          items={[
            { title: '上传文件' },
            { title: 'Agent识别' },
            { title: '质量检查' },
            { title: '生成快照' },
          ]}
        />
        <Form form={uploadForm} layout="vertical">
          <Form.Item name="source_name" label="数据源名称" rules={[{ required: true, message: '请输入数据源名称' }]}>
            <Input placeholder="例如：0421印尼首贷样本文件源" />
          </Form.Item>
          <Form.Item label="客户申请短链文件（.txt）" required>
            <Upload accept=".txt" maxCount={1} beforeUpload={() => false}>
              <Button icon={<UploadOutlined />}>选择短链文件</Button>
            </Upload>
          </Form.Item>
          <Form.Item label="好坏标签文件（.xlsx / .csv）" required>
            <Upload accept=".xlsx,.xls,.csv" maxCount={1} beforeUpload={() => false}>
              <Button icon={<UploadOutlined />}>选择标签文件</Button>
            </Upload>
          </Form.Item>
          <Row gutter={12}>
            <Col xs={24} md={12}>
              <Form.Item name="sample_scope" label="样本范围" initialValue="first_loan">
                <Select
                  options={[
                    { value: 'first_loan', label: '首贷客户' },
                    { value: 'repeat_loan', label: '复贷客户' },
                    { value: 'mixed', label: '混合样本' },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item name="label_meaning" label="标签含义" initialValue="1_overdue">
                <Radio.Group>
                  <Radio value="1_overdue">1=逾期，0=正常</Radio>
                  <Radio value="1_normal">1=正常，0=逾期</Radio>
                </Radio.Group>
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="business_note" label="业务口径补充">
            <Input.TextArea rows={3} placeholder="例如：仅包含印尼短期现金贷首贷客户；申请时间作为所有时间窗口的截止点。" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="新增数据库连接"
        open={databaseOpen}
        onCancel={() => setDatabaseOpen(false)}
        onOk={handleDatabaseSubmit}
        okText="提交连接配置"
        cancelText="取消"
        width={760}
      >
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="当前为前端原型配置"
          description="这里定义项目级数据库数据源。后续真实接入时，账号密钥应由后端密钥管理，不在前端明文保存。"
        />
        <Form form={databaseForm} layout="vertical">
          <Form.Item name="connection_name" label="连接名称" rules={[{ required: true, message: '请输入连接名称' }]}>
            <Input placeholder="例如：印尼FDC生产只读库" />
          </Form.Item>
          <Row gutter={12}>
            <Col xs={24} md={8}>
              <Form.Item name="db_type" label="数据库类型" initialValue="postgresql">
                <Select
                  options={[
                    { value: 'postgresql', label: 'PostgreSQL' },
                    { value: 'mysql', label: 'MySQL' },
                    { value: 'hive', label: 'Hive / 数仓' },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={10}>
              <Form.Item name="host" label="主机地址" rules={[{ required: true, message: '请输入主机地址' }]}>
                <Input placeholder="db.internal.company" />
              </Form.Item>
            </Col>
            <Col xs={24} md={6}>
              <Form.Item name="port" label="端口" initialValue="5432">
                <Input />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col xs={24} md={12}>
              <Form.Item name="database" label="库/Schema" rules={[{ required: true, message: '请输入库或Schema' }]}>
                <Input placeholder="risk_feature" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item name="table_view" label="数据表或视图" rules={[{ required: true, message: '请输入数据表或视图' }]}>
                <Input placeholder="loan_application_feature_view" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="extract_policy" label="抽取范围">
            <Input.TextArea rows={3} placeholder="例如：按申请时间抽取首贷客户；任务启动前生成固定快照；禁止读取申请后信息。" />
          </Form.Item>
          <Form.Item name="refresh_mode" label="快照生成方式" initialValue="manual">
            <Radio.Group>
              <Radio value="manual">任务启动前手动生成</Radio>
              <Radio value="scheduled">定期生成</Radio>
              <Radio value="on_task">任务启动时自动生成</Radio>
            </Radio.Group>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="生成数据快照"
        open={snapshotOpen}
        onCancel={() => setSnapshotOpen(false)}
        onOk={handleSnapshotSubmit}
        okText="生成快照"
        cancelText="取消"
        width={720}
      >
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="任务只绑定快照执行"
          description="快照生成后，后续任务、评估、部署版本和交付包都会记录该快照ID，确保结果可复现、交付可追溯。"
        />
        <Descriptions column={1} size="small" bordered style={{ marginBottom: 16 }}>
          <Descriptions.Item label="来源数据源">{snapshotSource?.name || '-'}</Descriptions.Item>
          <Descriptions.Item label="数据源类型">{snapshotSource?.type === 'database' ? '数据库连接' : '文件上传'}</Descriptions.Item>
          <Descriptions.Item label="Agent解析状态">{snapshotSource?.agentStatus || '-'}</Descriptions.Item>
        </Descriptions>
        <Form form={snapshotForm} layout="vertical">
          <Form.Item name="snapshot_name" label="快照名称" rules={[{ required: true, message: '请输入快照名称' }]}>
            <Input />
          </Form.Item>
          <Row gutter={12}>
            <Col xs={24} md={12}>
              <Form.Item name="sample_scope" label="样本范围">
                <Input />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item name="label_meaning" label="标签含义">
                <Input />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="time_policy" label="时间口径">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default DataSources;
