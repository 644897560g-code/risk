import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Col, Descriptions, Drawer, Empty, Progress, Row, Select, Space, Tabs, Tag, Typography, message } from 'antd';
import { CodeOutlined, DownloadOutlined, EyeOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons';
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

type DecisionLevel = 'recommend' | 'watch' | 'reject';

const businessNames: Record<string, string> = {
  ratio_applist_highrisk_apps_all: '高风险APP占比',
  cnt_fdc_query_7d_platforms: '近7天征信查询平台数',
  flag_app_cashloan_recent_install: '近期新装借贷APP标记',
  cross_age_marital_gambling: '年龄婚姻与赌博APP组合风险',
  ratio_bank_app_to_loan_app: '银行APP与借贷APP比例',
  cnt_unknown_apps_30d: '近30天未知APP数量',
  fdc_active_platform_shift: '活跃平台分布偏移',
  low_coverage_installment_signal: '分期消费APP低覆盖信号',
};

const decisionMeta: Record<DecisionLevel, { label: string; color: string; description: string }> = {
  recommend: { label: '推荐上线', color: 'success', description: '预测力、稳定性和完整度都较好，可优先加入候选集。' },
  watch: { label: '谨慎观察', color: 'warning', description: '已具备一定价值，但需要人工复核稳定性、覆盖或共线性。' },
  reject: { label: '不建议上线', color: 'error', description: '当前指标不足，建议归档原因或调整参数后重新评估。' },
};

const getDecisionLevel = (item: FeatureMetric): DecisionLevel => {
  if (item.is_passed && item.iv >= 0.05 && item.psi <= 0.1 && item.coverage >= 0.8) return 'recommend';
  if (item.is_passed || (item.iv >= 0.02 && item.psi <= 0.25 && item.coverage > 0.05)) return 'watch';
  return 'reject';
};

const getIvText = (iv: number) => {
  if (iv >= 0.05) return '预测力较强';
  if (iv >= 0.02) return '中等预测力';
  return '预测力不足';
};

const getPsiText = (psi: number) => {
  if (psi <= 0.1) return '稳定性良好';
  if (psi <= 0.25) return '稳定性可接受';
  return '稳定性不足';
};

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
  const recommended = metrics.filter((item) => getDecisionLevel(item) === 'recommend');
  const watchList = metrics.filter((item) => getDecisionLevel(item) === 'watch');
  const notRecommended = metrics.filter((item) => getDecisionLevel(item) === 'reject');
  const lowIvCount = metrics.filter((item) => item.iv < 0.02).length;
  const highPsiCount = metrics.filter((item) => item.psi > 0.25).length;
  const lowCoverageCount = metrics.filter((item) => item.coverage <= 0.05).length;
  const decisionReady = decisionPassed > 0 && decisionPassRate >= 40;
  const decisionMessage = metrics.length === 0
    ? '暂无可判断的评估数据'
    : decisionReady
      ? '建议进入候选集'
      : '建议补充验证后再进入部署';
  const decisionDescription = metrics.length === 0
    ? '请先完成特征生产任务，生成 IV、PSI、覆盖率等评估指标。'
    : decisionReady
      ? `当前版本 ${selectedVersion || '-'} 有 ${recommended.length} 个推荐上线特征，可先加入候选集确认。`
      : `当前通过率为 ${decisionPassRate}%，建议先复盘淘汰原因，再决定是否重新生产。`;
  const featureBuckets: Record<DecisionLevel, FeatureMetric[]> = {
    recommend: recommended,
    watch: watchList,
    reject: notRecommended,
  };

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

  return (
    <div className="page-enter">
      <div className="page-header">
        <div>
          <Title level={3} style={{ margin: 0 }}>评估报告</Title>
          <Text type="secondary">
            {currentProject?.name ? `当前项目：${currentProject.name}。` : ''}
            按推荐上线、谨慎观察和不建议上线分层，帮助快速完成上线判断。
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
          <Descriptions.Item label="来源实验">{selected?.task_id ? `#${selected.task_id}` : taskIdParam ? `#${taskIdParam}` : '请选择版本'}</Descriptions.Item>
          <Descriptions.Item label="数据版本">{selected?.task_id ? `V_task_${selected.task_id}` : taskIdParam ? `V_task_${taskIdParam}` : '-'}</Descriptions.Item>
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
                <Button type="primary" disabled={!decisionReady} onClick={() => navigate(selected?.task_id ? `/ship/candidates?taskId=${selected.task_id}` : '/ship/candidates')}>进入候选集</Button>
                <Button onClick={() => navigate('/mine/experiments')}>返回实验列表</Button>
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
        title="特征决策卡片"
        style={{ marginTop: 16 }}
        extra={<Button icon={<DownloadOutlined />} disabled>下载清单</Button>}
      >
        {metrics.length ? (
          <Tabs
            items={(Object.keys(featureBuckets) as DecisionLevel[]).map((level) => ({
              key: level,
              label: `${decisionMeta[level].label} ${featureBuckets[level].length}`,
              children: (
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  <Alert
                    type={level === 'recommend' ? 'success' : level === 'watch' ? 'warning' : 'error'}
                    showIcon
                    message={decisionMeta[level].label}
                    description={decisionMeta[level].description}
                  />
                  {featureBuckets[level].map((item) => (
                    <Card
                      key={`${item.version}-${item.feature_name}`}
                      size="small"
                      className="feature-decision-card"
                    >
                      <Row gutter={[16, 12]} align="middle">
                        <Col xs={24} lg={15}>
                          <Space direction="vertical" size={8} style={{ width: '100%' }}>
                            <Space wrap>
                              <Text strong>{item.feature_name}</Text>
                              <Tag color={decisionMeta[getDecisionLevel(item)].color}>{decisionMeta[getDecisionLevel(item)].label}</Tag>
                              <Tag>{item.template_type || '特征加工方式'}</Tag>
                            </Space>
                            <Title level={5} style={{ margin: 0 }}>{businessNames[item.feature_name] || '业务特征'}</Title>
                            <Text type="secondary">{item.feature_logic || '暂无业务解释。'}</Text>
                            <Space wrap>
                              <Tag color={item.iv >= 0.02 ? 'green' : 'red'}>预测力：{getIvText(item.iv)}</Tag>
                              <Tag color={item.psi <= 0.25 ? 'blue' : 'orange'}>稳定性：{getPsiText(item.psi)}</Tag>
                              <Tag color={item.coverage > 0.05 ? 'cyan' : 'orange'}>数据完整度：{(item.coverage * 100).toFixed(1)}%</Tag>
                            </Space>
                            {level === 'recommend' && (
                              <Text type="secondary">下一步建议：加入候选集，和相似时间窗口特征做二选一确认。</Text>
                            )}
                            {level === 'watch' && (
                              <Text type="secondary">下一步建议：检查样本分布和业务解释，通过后再加入候选集。</Text>
                            )}
                            {level === 'reject' && (
                              <Text type="secondary">下一步建议：记录淘汰原因，必要时调整窗口或阈值后重新评估。</Text>
                            )}
                          </Space>
                        </Col>
                        <Col xs={24} lg={5}>
                          <Space direction="vertical" size={6} style={{ width: '100%' }}>
                            <div className="dimension-row"><span>IV</span><Tag>{item.iv.toFixed(3)}</Tag></div>
                            <div className="dimension-row"><span>PSI</span><Tag>{item.psi.toFixed(3)}</Tag></div>
                            <div>
                              <Text type="secondary">覆盖率</Text>
                              <Progress percent={Math.round(item.coverage * 100)} size="small" />
                            </div>
                          </Space>
                        </Col>
                        <Col xs={24} lg={4} style={{ textAlign: 'right' }}>
                          <Space direction="vertical">
                            <Button type="primary" icon={<PlusOutlined />} disabled={level === 'reject'} onClick={() => navigate(`/ship/candidates?taskId=${item.task_id}`)}>
                              加入候选集
                            </Button>
                            <Button icon={<CodeOutlined />} onClick={() => setLogicDetail(item)}>
                              查看口径
                            </Button>
                          </Space>
                        </Col>
                      </Row>
                    </Card>
                  ))}
                  {featureBuckets[level].length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无特征" />}
                </Space>
              ),
            }))}
          />
        ) : (
          <Empty description="暂无评估数据" />
        )}
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
