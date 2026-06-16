import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Col, Empty, Input, Progress, Row, Segmented, Space, Tag, Typography, message } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, CloudUploadOutlined, EyeOutlined, ReloadOutlined, WarningOutlined } from '@ant-design/icons';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { fetchFeatureMetrics, fetchFeatureVersions } from '@/services/api';
import type { FeatureMetric, FeatureVersion } from '@/types/feature';
import { useProjectStore } from '@/store/projectStore';

const { Text, Title } = Typography;

type CandidateStatus = 'pending' | 'confirmed' | 'excluded';

interface CandidateFeature extends FeatureMetric {
  businessName: string;
  note: string;
  status: CandidateStatus;
  riskFlag?: string;
}

const statusMeta: Record<CandidateStatus, { label: string; color: string }> = {
  pending: { label: '待确认', color: 'warning' },
  confirmed: { label: '已确认', color: 'success' },
  excluded: { label: '已排除', color: 'default' },
};

const businessNameMap: Record<string, string> = {
  ratio_applist_highrisk_apps_all: '高风险APP占比',
  cnt_fdc_query_7d_platforms: '近7天征信查询平台数',
  flag_app_cashloan_recent_install: '近期新装借贷APP标记',
  cross_age_marital_gambling: '年龄婚姻与赌博APP组合风险',
  ratio_bank_app_to_loan_app: '银行APP与借贷APP比例',
};

const CandidateFeatures: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const currentProject = useProjectStore((s) => s.currentProject);
  const taskIdParam = Number(searchParams.get('taskId')) || undefined;
  const [versions, setVersions] = useState<FeatureVersion[]>([]);
  const [candidates, setCandidates] = useState<CandidateFeature[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<CandidateStatus | 'all'>('all');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const versionItems = await fetchFeatureVersions(currentProject?.id);
      setVersions(versionItems);
      const scopedVersion = taskIdParam
        ? versionItems.find((item) => item.task_id === taskIdParam)?.version
        : versionItems[0]?.version;
      const metrics = scopedVersion ? await fetchFeatureMetrics(scopedVersion, currentProject?.id) : [];
      const rows = metrics
        .filter((item) => item.is_passed)
        .map((item, index) => ({
          ...item,
          businessName: businessNameMap[item.feature_name] || '待上线风控特征',
          note: index === 1 ? 'PSI略高，建议先小流量观察。' : '指标表现稳定，可进入上线确认。',
          status: index < 3 ? 'pending' as const : index === 3 ? 'confirmed' as const : 'excluded' as const,
          riskFlag: index === 2 ? '与长窗口版本可能共线' : undefined,
        }));
      setCandidates(rows);
    } catch {
      message.error('候选特征加载失败');
      setCandidates([]);
    } finally {
      setLoading(false);
    }
  }, [currentProject?.id, taskIdParam]);

  useEffect(() => {
    load();
  }, [load]);

  const visibleCandidates = useMemo(() => (
    statusFilter === 'all' ? candidates : candidates.filter((item) => item.status === statusFilter)
  ), [candidates, statusFilter]);

  const counts = useMemo(() => ({
    pending: candidates.filter((item) => item.status === 'pending').length,
    confirmed: candidates.filter((item) => item.status === 'confirmed').length,
    excluded: candidates.filter((item) => item.status === 'excluded').length,
  }), [candidates]);

  const updateStatus = (featureName: string, status: CandidateStatus) => {
    setCandidates((prev) => prev.map((item) => (
      item.feature_name === featureName ? { ...item, status } : item
    )));
    message.success(status === 'confirmed' ? '已确认上线' : status === 'excluded' ? '已排除' : '已改为待确认');
  };

  const currentVersion = taskIdParam
    ? versions.find((item) => item.task_id === taskIdParam)
    : versions[0];

  return (
    <div className="page-enter">
      <div className="page-header">
        <div>
          <Title level={3} style={{ margin: 0 }}>候选特征集</Title>
          <Text type="secondary">
            {currentProject?.name ? `当前项目：${currentProject.name}。` : ''}
            这里承接评估报告中可上线的特征，人工确认后再生成交付版本。
          </Text>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} loading={loading} onClick={load}>刷新</Button>
          <Button type="primary" icon={<CloudUploadOutlined />} disabled={!counts.confirmed} onClick={() => navigate('/ship/versions')}>
            生成部署版本
          </Button>
        </Space>
      </div>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message={currentVersion ? `来自实验 #${currentVersion.task_id}，版本 ${currentVersion.version}` : '暂无来源版本'}
        description="候选集是评估到交付之间的人工确认区。建议先确认业务解释、稳定性和共线性，再生成版本。"
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={8}>
          <Card className="metric-card compact">
            <div className="metric-value">{counts.pending}</div>
            <div className="metric-label">待确认</div>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card className="metric-card compact">
            <div className="metric-value">{counts.confirmed}</div>
            <div className="metric-label">已确认</div>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card className="metric-card compact">
            <div className="metric-value">{counts.excluded}</div>
            <div className="metric-label">已排除</div>
          </Card>
        </Col>
      </Row>

      <Card
        title="待上线特征"
        style={{ marginTop: 16 }}
        extra={(
          <Segmented
            value={statusFilter}
            onChange={(value) => setStatusFilter(value as CandidateStatus | 'all')}
            options={[
              { label: `全部 ${candidates.length}`, value: 'all' },
              { label: `待确认 ${counts.pending}`, value: 'pending' },
              { label: `已确认 ${counts.confirmed}`, value: 'confirmed' },
              { label: `已排除 ${counts.excluded}`, value: 'excluded' },
            ]}
          />
        )}
      >
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          {visibleCandidates.map((item) => (
            <Card key={item.feature_name} size="small" className="candidate-card">
              <Row gutter={[16, 12]} align="middle">
                <Col xs={24} lg={15}>
                  <Space direction="vertical" size={8}>
                    <Space wrap>
                      <Text strong>{item.feature_name}</Text>
                      <Tag color={statusMeta[item.status].color}>{statusMeta[item.status].label}</Tag>
                      {item.riskFlag && <Tag color="warning" icon={<WarningOutlined />}>{item.riskFlag}</Tag>}
                    </Space>
                    <Title level={5} style={{ margin: 0 }}>{item.businessName}</Title>
                    <Text type="secondary">{item.feature_logic || '暂无业务解释'}</Text>
                    <Input.TextArea
                      rows={2}
                      defaultValue={item.note}
                      placeholder="填写业务备注或主管批注"
                    />
                  </Space>
                </Col>
                <Col xs={24} lg={5}>
                  <Space direction="vertical" size={6} style={{ width: '100%' }}>
                    <div className="dimension-row"><span>预测力</span><Tag>{item.iv.toFixed(3)}</Tag></div>
                    <div className="dimension-row"><span>稳定性</span><Tag>{item.psi.toFixed(3)}</Tag></div>
                    <Progress percent={Math.round(item.coverage * 100)} size="small" />
                  </Space>
                </Col>
                <Col xs={24} lg={4} style={{ textAlign: 'right' }}>
                  <Space direction="vertical">
                    <Button icon={<CheckCircleOutlined />} type="primary" disabled={item.status === 'confirmed'} onClick={() => updateStatus(item.feature_name, 'confirmed')}>
                      确认
                    </Button>
                    <Button icon={<CloseCircleOutlined />} danger disabled={item.status === 'excluded'} onClick={() => updateStatus(item.feature_name, 'excluded')}>
                      排除
                    </Button>
                    <Button icon={<EyeOutlined />} onClick={() => message.info('样本对比为原型占位，后续接入单特征样本剖析。')}>
                      查看样本
                    </Button>
                  </Space>
                </Col>
              </Row>
            </Card>
          ))}
          {!visibleCandidates.length && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无候选特征" />}
        </Space>
      </Card>
    </div>
  );
};

export default CandidateFeatures;
