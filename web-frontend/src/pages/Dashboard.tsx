import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Col, Empty, Progress, Row, Space, Steps, Table, Tag, Typography, message } from 'antd';
import {
  BarChartOutlined,
  CheckCircleOutlined,
  CloudUploadOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  FileTextOutlined,
  FolderOpenOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import ReactEChartsCore from 'echarts-for-react';
import { useNavigate } from 'react-router-dom';
import {
  fetchChannel1Templates,
  fetchFeatureStats,
  fetchProjects,
  fetchTasks,
  type Channel1Template,
} from '@/services/api';
import type { Task } from '@/types/task';
import { useProjectStore } from '@/store/projectStore';

const { Text, Title } = Typography;

const statusColor: Record<string, string> = {
  pending: 'default',
  running: 'processing',
  completed: 'success',
  failed: 'error',
  cancelled: 'warning',
};

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const currentProject = useProjectStore((s) => s.currentProject);
  const [loading, setLoading] = useState(false);
  const [projectTotal, setProjectTotal] = useState(0);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [templates, setTemplates] = useState<Channel1Template[]>([]);
  const [featureStats, setFeatureStats] = useState({
    current_total: 0,
    current_passed: 0,
    accumulated_passed: 0,
    latest_version: '',
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [projectRes, taskRes, tmplRes, statsRes] = await Promise.allSettled([
        fetchProjects(),
        fetchTasks(0, 8, currentProject?.id),
        fetchChannel1Templates(),
        fetchFeatureStats(),
      ]);
      if (projectRes.status === 'fulfilled') setProjectTotal(projectRes.value.total || 0);
      if (taskRes.status === 'fulfilled') setTasks(taskRes.value.items || []);
      if (tmplRes.status === 'fulfilled') setTemplates(tmplRes.value || []);
      if (statsRes.status === 'fulfilled') setFeatureStats(statsRes.value);
    } catch {
      message.error('工作台数据加载失败');
    } finally {
      setLoading(false);
    }
  }, [currentProject?.id]);

  useEffect(() => {
    load();
  }, [load]);

  const runningTask = tasks.find((task) => task.status === 'running' || task.status === 'pending');
  const latestTask = tasks[0];
  const completedTasks = tasks.filter((task) => task.status === 'completed').length;
  const failedTasks = tasks.filter((task) => task.status === 'failed').length;
  const latestCompletedTask = tasks.find((task) => task.status === 'completed' && task.mode !== 'template_task');
  const hasProject = Boolean(currentProject);
  const hasProjectDataSource = hasProject;
  const hasKnowledgeBasis = hasProject;
  const hasTemplates = templates.length > 0;
  const hasProductionTask = tasks.some((task) => task.mode !== 'template_task');
  const hasEvaluation = featureStats.current_total > 0;
  const hasDeployment = Boolean(featureStats.latest_version);
  const lifecycleCurrent = !hasProject ? 0
    : !hasProjectDataSource ? 1
      : !hasKnowledgeBasis ? 2
        : !hasTemplates ? 3
          : !hasProductionTask ? 4
            : runningTask ? 4
              : !hasEvaluation ? 5
                : !hasDeployment ? 5
                  : 5;
  const passRate = featureStats.current_total
    ? Math.round((featureStats.current_passed / featureStats.current_total) * 100)
    : 0;
  const nextActions = [
    !hasProject && { title: '先创建业务项目', desc: '明确国家、产品、客户范围和评估阈值。', action: '去项目列表', path: '/projects' },
    hasProject && !hasProductionTask && { title: '确认项目数据源', desc: '任务启动前先选择或生成项目级数据快照。', action: '去数据源', path: '/data-sources' },
    hasProject && !hasTemplates && { title: '选择可用模板', desc: '确认平台模板库中有哪些加工方式可用于生产。', action: '去模板库', path: '/templates' },
    hasProject && hasTemplates && !hasProductionTask && { title: '发起首轮生产', desc: '绑定数据快照和模板范围，生成候选特征并进入评估。', action: '发起生产', path: '/tasks' },
    runningTask && { title: '跟踪运行任务', desc: `${runningTask.name} 正在执行，优先查看步骤状态。`, action: '查看任务', path: '/tasks' },
    hasEvaluation && !hasDeployment && { title: '确认评估结论', desc: '判断本轮特征是否足够稳定，是否可进入部署。', action: '查看评估', path: '/evaluation' },
    hasDeployment && { title: '进入版本与交付', desc: `最新版本 ${featureStats.latest_version} 已生成，等待业务确认和交付。`, action: '查看交付版本', path: '/deployment' },
  ].filter(Boolean) as Array<{ title: string; desc: string; action: string; path: string }>;

  const taskChartOption = useMemo(() => ({
    tooltip: {
      trigger: 'item' as const,
      backgroundColor: 'rgba(8, 13, 21, 0.94)',
      borderColor: 'rgba(55, 231, 255, 0.26)',
      textStyle: { color: '#e5f6ff' },
    },
    legend: { bottom: 0, textStyle: { color: '#cbd5e1' } },
    series: [{
      type: 'pie',
      radius: ['48%', '70%'],
      center: ['50%', '44%'],
      data: [
        { name: '已完成', value: completedTasks, itemStyle: { color: '#00b383' } },
        { name: '运行中', value: tasks.filter((task) => task.status === 'running').length, itemStyle: { color: '#2b5fd9' } },
        { name: '失败', value: failedTasks, itemStyle: { color: '#e8453c' } },
        { name: '等待', value: tasks.filter((task) => task.status === 'pending').length, itemStyle: { color: '#8c93a3' } },
      ].filter((item) => item.value > 0),
      label: { formatter: '{b}\n{d}%', color: '#cbd5e1' },
    }],
  }), [completedTasks, failedTasks, tasks]);

  return (
    <div className="page-enter">
      <div className="page-header">
        <div>
          <Title level={3} style={{ margin: 0 }}>项目概览</Title>
          <Text type="secondary">
            {currentProject?.name ? `当前项目：${currentProject.name}。` : '当前项目未选择。'}
            本页只展示当前项目的数据与产物。
          </Text>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>刷新</Button>
          <Button type="primary" icon={<PlayCircleOutlined />} onClick={() => navigate('/tasks')}>创建任务</Button>
        </Space>
      </div>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card className="metric-card compact">
            <DatabaseOutlined className="metric-icon blue" />
            <div className="metric-value">{hasProjectDataSource ? '已就绪' : '待配置'}</div>
            <div className="metric-label">数据是否就绪</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="metric-card compact">
            <ExperimentOutlined className="metric-icon teal" />
            <div className="metric-value">{hasTemplates ? templates.length : '待确认'}</div>
            <div className="metric-label">模板是否可用</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="metric-card compact">
            <PlayCircleOutlined className="metric-icon green" />
            <div className="metric-value">{runningTask ? '运行中' : latestTask ? statusColor[latestTask.status] === 'success' ? '已完成' : '待处理' : '无任务'}</div>
            <div className="metric-label">最近任务状态</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="metric-card compact">
            <CloudUploadOutlined className="metric-icon orange" />
            <div className="metric-value">{featureStats.latest_version || '-'}</div>
            <div className="metric-label">最新交付版本</div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={16}>
          <Card
            title="核心流程闭环"
            extra={<Button type="link" onClick={() => navigate('/tasks')}>查看任务中心</Button>}
          >
            <Steps
              current={lifecycleCurrent}
              items={[
                { title: '项目', description: '确认业务范围', icon: <FolderOpenOutlined /> },
                { title: '数据源', description: '生成可复现快照', icon: <DatabaseOutlined /> },
                { title: '知识', description: '确认业务口径', icon: <FileTextOutlined /> },
                { title: '模板', description: '选择加工方式', icon: <ExperimentOutlined /> },
                { title: '任务', description: '绑定快照并生产', icon: <PlayCircleOutlined /> },
                { title: '版本与交付', description: '评估、部署与追溯', icon: <CloudUploadOutlined /> },
              ]}
            />
            <div className="process-summary">
              {runningTask ? (
                <>
                  <Text strong>当前运行：</Text>
                  <Text>{runningTask.name}</Text>
                  <Progress percent={Math.round(runningTask.progress || 0)} size="small" style={{ marginTop: 10 }} />
                </>
              ) : (
                <Text type="secondary">
                  {hasDeployment
                    ? `当前闭环已走到部署交付，最新版本为 ${featureStats.latest_version}。`
                    : '当前闭环尚未完成，请按右侧建议推进下一步。'}
                </Text>
              )}
            </div>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="下一步建议">
            {nextActions.length > 0 ? (
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                {nextActions.slice(0, 3).map((item) => (
                  <Alert
                    key={item.title}
                    type={runningTask ? 'info' : hasDeployment ? 'success' : 'warning'}
                    showIcon
                    message={item.title}
                    description={(
                      <Space direction="vertical" size={8}>
                        <span>{item.desc}</span>
                        <Button size="small" type="primary" onClick={() => navigate(item.path)}>{item.action}</Button>
                      </Space>
                    )}
                  />
                ))}
              </Space>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无待办" />
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card className="metric-card compact">
            <FolderOpenOutlined className="metric-icon blue" />
            <div className="metric-value">{projectTotal}</div>
            <div className="metric-label">平台项目总数</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="metric-card compact">
            <ExperimentOutlined className="metric-icon teal" />
            <div className="metric-value">{templates.length}</div>
            <div className="metric-label">平台可用模板</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="metric-card compact">
            <CheckCircleOutlined className="metric-icon green" />
            <div className="metric-value">{featureStats.accumulated_passed}</div>
            <div className="metric-label">累计通过特征</div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="metric-card compact">
            <CloudUploadOutlined className="metric-icon orange" />
            <div className="metric-value">{featureStats.latest_version || '-'}</div>
            <div className="metric-label">最新部署版本</div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={9}>
          <Card title="本轮评估概览" extra={<Button type="link" onClick={() => navigate('/evaluation')}>查看报告</Button>}>
            <div className="pass-rate-block">
              <Progress type="dashboard" percent={passRate} strokeColor={passRate >= 50 ? '#00b383' : '#f5a623'} />
              <div>
                <div className="pass-rate-title">{featureStats.current_passed}/{featureStats.current_total}</div>
                <Text type="secondary">通过阈值的特征数</Text>
                <div style={{ marginTop: 12 }}>
                  <Tag color="green">IV &gt;= 0.02</Tag>
                  <Tag color="blue">PSI &lt;= 0.25</Tag>
                  <Tag color="gold">覆盖率 &gt; 5%</Tag>
                </div>
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} lg={7}>
          <Card title="最近任务状态">
            {tasks.length > 0 ? (
              <ReactEChartsCore option={taskChartOption} style={{ height: 245 }} notMerge />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无任务" />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="最新产出">
            {latestCompletedTask ? (
              <Space direction="vertical" size={10} style={{ width: '100%' }}>
                <Text strong>{latestCompletedTask.name}</Text>
                <Text type="secondary">
                  已通过 {latestCompletedTask.passed_features || 0}/{latestCompletedTask.total_features || 0} 个特征。
                </Text>
                <Space wrap>
                  {latestCompletedTask.deployed_version && <Tag color="blue">版本 {latestCompletedTask.deployed_version}</Tag>}
                  <Tag color={passRate >= 50 ? 'success' : 'warning'}>通过率 {passRate}%</Tag>
                </Space>
                <Space>
                  <Button size="small" onClick={() => navigate(`/evaluation?taskId=${latestCompletedTask.id}`)}>评估决策</Button>
                  <Button size="small" type="primary" onClick={() => navigate(`/deployment?taskId=${latestCompletedTask.id}`)}>版本与交付</Button>
                </Space>
              </Space>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无完成任务" />
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24}>
          <Card title="最近生产任务">
            <Table
              rowKey="id"
              size="small"
              dataSource={tasks}
              pagination={false}
              columns={[
                { title: '任务', dataIndex: 'name', ellipsis: true },
                {
                  title: '状态',
                  dataIndex: 'status',
                  width: 100,
                  render: (status: string) => <Tag color={statusColor[status] || 'default'}>{status}</Tag>,
                },
                {
                  title: '通过/总数',
                  width: 110,
                  render: (_, row: Task) => row.total_features != null ? `${row.passed_features}/${row.total_features}` : '-',
                },
                {
                  title: '版本',
                  dataIndex: 'deployed_version',
                  width: 100,
                  render: (version: string) => version ? <Tag color="blue">{version}</Tag> : '-',
                },
              ]}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;
