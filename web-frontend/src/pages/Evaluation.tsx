import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Col, Descriptions, Drawer, Empty, Row, Select, Space, Table, Tag, Typography, message } from 'antd';
import { CodeOutlined, DownloadOutlined, EyeOutlined, ReloadOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useNavigate, useSearchParams } from 'react-router-dom';
import FeatureCharts from '@/components/FeatureCharts';
import {
  fetchFeatureMetrics,
  fetchFeatureReportUrl,
  fetchFeatureVersions,
} from '@/services/api';
import type { FeatureMetric, FeatureVersion } from '@/types/feature';
import { useProjectStore } from '@/store/projectStore';

const { Text, Title } = Typography;

const Evaluation: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const currentProject = useProjectStore((s) => s.currentProject);
  const taskIdParam = Number(searchParams.get('taskId')) || undefined;
  const [versions, setVersions] = useState<FeatureVersion[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<string>();
  const [metrics, setMetrics] = useState<FeatureMetric[]>([]);
  const [logicDetail, setLogicDetail] = useState<FeatureMetric | null>(null);
  const [loading, setLoading] = useState(false);
  const [metricLoading, setMetricLoading] = useState(false);

  const loadVersions = useCallback(async () => {
    setLoading(true);
    try {
      const items = await fetchFeatureVersions(currentProject?.id);
      setVersions(items);
      const taskVersion = taskIdParam ? items.find((item) => item.task_id === taskIdParam) : undefined;
      setSelectedVersion((prev) => taskVersion?.version || prev || items[0]?.version);
    } catch {
      message.error('评估版本加载失败');
    } finally {
      setLoading(false);
    }
  }, [currentProject?.id, taskIdParam]);

  const loadMetrics = useCallback(async (version?: string) => {
    if (!version) {
      setMetrics([]);
      return;
    }
    setMetricLoading(true);
    try {
      setMetrics(await fetchFeatureMetrics(version, currentProject?.id));
    } catch {
      setMetrics([]);
    } finally {
      setMetricLoading(false);
    }
  }, [currentProject?.id]);

  useEffect(() => {
    loadVersions();
  }, [loadVersions]);

  useEffect(() => {
    loadMetrics(selectedVersion);
  }, [selectedVersion, loadMetrics]);

  const selected = versions.find((item) => item.version === selectedVersion);
  const passed = metrics.filter((item) => item.is_passed).length;
  const failed = metrics.length - passed;
  const avgIv = metrics.length ? metrics.reduce((sum, item) => sum + item.iv, 0) / metrics.length : 0;
  const decisionTotal = selected?.total_features || metrics.length;
  const decisionPassed = selected?.passed_features ?? passed;
  const decisionPassRate = decisionTotal ? Math.round((decisionPassed / decisionTotal) * 100) : 0;
  const recommended = metrics.filter((item) => item.is_passed);
  const watchList = metrics.filter((item) => !item.is_passed && item.iv >= 0.02 && (item.psi > 0.25 || item.coverage <= 0.05));
  const notRecommended = metrics.filter((item) => !item.is_passed && item.iv < 0.02);
  const lowIvCount = metrics.filter((item) => item.iv < 0.02).length;
  const highPsiCount = metrics.filter((item) => item.psi > 0.25).length;
  const lowCoverageCount = metrics.filter((item) => item.coverage <= 0.05).length;
  const decisionReady = decisionPassed > 0 && decisionPassRate >= 40;
  const decisionMessage = metrics.length === 0
    ? '暂无可判断的评估数据'
    : decisionReady
      ? '建议进入部署确认'
      : '建议补充验证后再进入部署';
  const decisionDescription = metrics.length === 0
    ? '请先完成特征生产任务，生成 IV、PSI、覆盖率等评估指标。'
    : decisionReady
      ? `当前版本 ${selectedVersion || '-'} 有 ${decisionPassed} 个特征通过阈值，可进入业务确认和部署交付。`
      : `当前通过率为 ${decisionPassRate}%，建议先复盘淘汰原因，再决定是否重新生产。`;

  const chartFeatures = useMemo(() => metrics.map((item) => ({
    feature_name: item.feature_name,
    iv: item.iv,
    psi: item.psi,
    coverage: item.coverage,
    status: item.is_passed ? 'passed' : 'failed',
  })), [metrics]);

  const openReport = async () => {
    if (!selectedVersion) return;
    try {
      const url = await fetchFeatureReportUrl(selectedVersion);
      window.open(url, '_blank');
    } catch {
      message.error('报告地址获取失败');
    }
  };

  const columns: ColumnsType<FeatureMetric> = [
    {
      title: '特征',
      dataIndex: 'feature_name',
      width: 270,
      render: (name: string, row) => (
        <div>
          <Text strong>{name}</Text>
          <div style={{ marginTop: 5 }}>
            <Tag color="cyan">{row.template_type || '加工模板'}</Tag>
          </div>
        </div>
      ),
    },
    {
      title: '特征逻辑',
      dataIndex: 'feature_logic',
      ellipsis: true,
      render: (logic: string, row) => (
        <div className="feature-logic-cell">
          <Text>{logic || '暂无加工逻辑说明'}</Text>
          <Button type="link" size="small" icon={<CodeOutlined />} onClick={() => setLogicDetail(row)}>
            查看口径
          </Button>
        </div>
      ),
    },
    {
      title: '结果',
      dataIndex: 'is_passed',
      width: 90,
      render: (pass: boolean) => <Tag color={pass ? 'success' : 'error'}>{pass ? '通过' : '未通过'}</Tag>,
    },
    {
      title: '上线建议',
      width: 110,
      render: (_, row) => {
        if (row.is_passed) return <Tag color="success">推荐上线</Tag>;
        if (row.iv >= 0.02 && (row.psi > 0.25 || row.coverage <= 0.05)) return <Tag color="warning">谨慎观察</Tag>;
        return <Tag color="default">不建议</Tag>;
      },
    },
    {
      title: 'IV',
      dataIndex: 'iv',
      width: 100,
      sorter: (a, b) => a.iv - b.iv,
      render: (v: number) => <Text type={v >= 0.02 ? undefined : 'danger'}>{v.toFixed(4)}</Text>,
    },
    {
      title: 'PSI',
      dataIndex: 'psi',
      width: 100,
      sorter: (a, b) => a.psi - b.psi,
      render: (v: number) => <Text type={v <= 0.25 ? undefined : 'danger'}>{v.toFixed(4)}</Text>,
    },
    {
      title: '覆盖率',
      dataIndex: 'coverage',
      width: 100,
      sorter: (a, b) => a.coverage - b.coverage,
      render: (v: number) => <Text type={v > 0.05 ? undefined : 'danger'}>{(v * 100).toFixed(1)}%</Text>,
    },
  ];

  return (
    <div className="page-enter">
      <div className="page-header">
        <div>
          <Title level={3} style={{ margin: 0 }}>结果库 / 评估报告</Title>
          <Text type="secondary">
            {currentProject?.name ? `当前项目：${currentProject.name}。` : ''}
            按项目下的任务版本查看特征 IV、PSI、覆盖率及上线判断
          </Text>
        </div>
        <Space>
          <Select
            value={selectedVersion}
            onChange={setSelectedVersion}
            style={{ width: 220 }}
            placeholder="选择版本"
            options={versions.map((item) => ({
              label: `${item.version}（${item.passed_features}/${item.total_features}）`,
              value: item.version,
            }))}
          />
          <Button icon={<ReloadOutlined />} loading={loading || metricLoading} onClick={loadVersions}>刷新</Button>
          <Button icon={<EyeOutlined />} onClick={openReport} disabled={!selectedVersion}>打开HTML报告</Button>
        </Space>
      </div>

      <Card style={{ marginBottom: 16 }}>
        <Descriptions column={{ xs: 1, sm: 2, lg: 5 }} size="small">
          <Descriptions.Item label="所属平台">RiskForge AI</Descriptions.Item>
          <Descriptions.Item label="所属项目">{currentProject?.name || '-'}</Descriptions.Item>
          <Descriptions.Item label="来源任务">{selected?.task_id ? `#${selected.task_id}` : taskIdParam ? `#${taskIdParam}` : '请选择版本'}</Descriptions.Item>
          <Descriptions.Item label="来源快照">{selected?.task_id ? `snapshot_task_${selected.task_id}` : taskIdParam ? `snapshot_task_${taskIdParam}` : '-'}</Descriptions.Item>
          <Descriptions.Item label="结果类型">评估报告</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card style={{ marginBottom: 16 }}>
        <Alert
          type={metrics.length === 0 ? 'info' : decisionReady ? 'success' : 'warning'}
          showIcon
          message={decisionMessage}
          description={(
            <Space direction="vertical" size={10}>
              <span>{decisionDescription}</span>
              <Space wrap>
                <Button type="primary" disabled={!decisionReady} onClick={() => navigate(selected?.task_id ? `/deployment?taskId=${selected.task_id}` : '/deployment')}>进入该任务部署确认</Button>
                <Button onClick={() => navigate('/tasks')}>返回项目任务</Button>
                <Button icon={<EyeOutlined />} onClick={openReport} disabled={!selectedVersion}>打开HTML报告</Button>
              </Space>
            </Space>
          )}
        />
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card className="metric-card compact">
            <div className="metric-value">{decisionTotal}</div>
            <div className="metric-label">评估特征数</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="metric-card compact">
            <div className="metric-value">{decisionPassed}</div>
            <div className="metric-label">推荐上线特征</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="metric-card compact">
            <div className="metric-value">{watchList.length}</div>
            <div className="metric-label">谨慎观察特征</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="metric-card compact">
            <div className="metric-value">{notRecommended.length || failed}</div>
            <div className="metric-label">不建议上线特征</div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={8}>
          <Card title="上线分层">
            <Space direction="vertical" size={10} style={{ width: '100%' }}>
              <div className="dimension-row"><span>推荐上线</span><Tag color="success">{recommended.length}</Tag></div>
              <div className="dimension-row"><span>谨慎观察</span><Tag color="warning">{watchList.length}</Tag></div>
              <div className="dimension-row"><span>不建议上线</span><Tag>{notRecommended.length || failed}</Tag></div>
            </Space>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="淘汰原因">
            <Space direction="vertical" size={10} style={{ width: '100%' }}>
              <div className="dimension-row"><span>IV低于阈值</span><Tag color={lowIvCount ? 'error' : 'success'}>{lowIvCount}</Tag></div>
              <div className="dimension-row"><span>PSI稳定性不足</span><Tag color={highPsiCount ? 'warning' : 'success'}>{highPsiCount}</Tag></div>
              <div className="dimension-row"><span>覆盖率不足</span><Tag color={lowCoverageCount ? 'warning' : 'success'}>{lowCoverageCount}</Tag></div>
            </Space>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="版本结论">
            <Space direction="vertical" size={10}>
              <Text>平均 IV：{avgIv.toFixed(3)}</Text>
              <Text>通过率：{decisionPassRate}%</Text>
              <Text type="secondary">结论以 IV、PSI、覆盖率共同判断，部署前仍需业务确认。</Text>
            </Space>
          </Card>
        </Col>
      </Row>

      <Card title="指标分布" style={{ marginTop: 16 }}>
        {metrics.length ? (
          <FeatureCharts
            totalFeatures={selected?.total_features || metrics.length}
            passedFeatures={selected?.passed_features ?? passed}
            features={chartFeatures}
            loading={metricLoading}
          />
        ) : (
          <Empty description="暂无评估数据" />
        )}
      </Card>

      <Card
        title="特征明细"
        style={{ marginTop: 16 }}
        extra={<Button icon={<DownloadOutlined />} disabled>导出明细</Button>}
      >
        <Table
          rowKey={(row) => `${row.version}-${row.feature_name}`}
          loading={metricLoading}
          columns={columns}
          dataSource={metrics}
          pagination={{ pageSize: 12, showTotal: (total) => `共 ${total} 个特征` }}
        />
      </Card>

      <Drawer
        title={logicDetail ? `${logicDetail.feature_name} · 特征逻辑` : '特征逻辑'}
        open={!!logicDetail}
        onClose={() => setLogicDetail(null)}
        width={620}
      >
        {logicDetail && (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Card size="small" title="加工口径">
              <Text>{logicDetail.feature_logic || '暂无加工逻辑说明'}</Text>
            </Card>
            <Card size="small" title="输入字段">
              <Space wrap>
                {(logicDetail.source_fields || []).map((field) => <Tag key={field}>{field}</Tag>)}
                {(!logicDetail.source_fields || logicDetail.source_fields.length === 0) && <Text type="secondary">暂无字段说明</Text>}
              </Space>
            </Card>
            <Card size="small" title="评估结果">
              <Space wrap>
                <Tag color={logicDetail.is_passed ? 'success' : 'error'}>{logicDetail.is_passed ? '通过' : '未通过'}</Tag>
                <Tag>IV {logicDetail.iv.toFixed(4)}</Tag>
                <Tag>PSI {logicDetail.psi.toFixed(4)}</Tag>
                <Tag>覆盖率 {(logicDetail.coverage * 100).toFixed(1)}%</Tag>
              </Space>
            </Card>
          </Space>
        )}
      </Drawer>
    </div>
  );
};

export default Evaluation;
