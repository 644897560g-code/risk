import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Col, Empty, List, Progress, Row, Space, Statistic, Tag, Typography, message } from 'antd';
import {
  CloudUploadOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  FileTextOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  RocketOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
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

const taskStatusText: Record<string, { text: string; color: string }> = {
  pending: { text: '待启动', color: 'default' },
  running: { text: '运行中', color: 'processing' },
  completed: { text: '评估完成', color: 'success' },
  failed: { text: '运行失败', color: 'error' },
  cancelled: { text: '已归档', color: 'warning' },
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

  const runningExperiment = tasks.find((task) => task.status === 'running' || task.status === 'pending');
  const completedExperiment = tasks.find((task) => task.status === 'completed' && task.mode !== 'template_task');
  const failedExperiment = tasks.find((task) => task.status === 'failed');
  const passRate = featureStats.current_total
    ? Math.round((featureStats.current_passed / featureStats.current_total) * 100)
    : 0;
  const todoCount = [
    completedExperiment,
    featureStats.current_passed > 0 ? 'candidate' : null,
    featureStats.latest_version ? 'ship' : null,
  ].filter(Boolean).length;

  const recentActivities = useMemo(() => {
    const items = tasks.slice(0, 4).map((task) => {
      const status = taskStatusText[task.status] || { text: task.status, color: 'default' };
      if (task.status === 'completed') {
        return {
          id: task.id,
          title: `实验 #${task.id} 评估完成`,
          desc: `${task.passed_features || 0} 个特征可进入候选集`,
          tag: status,
          actions: [
            { label: '查看报告', path: `/mine/report?taskId=${task.id}`, primary: true },
            { label: '加入候选集', path: `/ship/candidates?taskId=${task.id}` },
          ],
        };
      }
      if (task.status === 'failed') {
        return {
          id: task.id,
          title: `实验 #${task.id} 运行失败`,
          desc: task.error_message || '建议查看失败原因后调整数据或策略重试',
          tag: status,
          actions: [
            { label: '查看原因', path: '/mine/experiments', primary: true },
            { label: '调整后重试', path: '/mine/experiments?create=factory' },
          ],
        };
      }
      return {
        id: task.id,
        title: `实验 #${task.id} ${status.text}`,
        desc: task.status === 'running' ? `当前进度 ${Math.round(task.progress || 0)}%` : task.name,
        tag: status,
        actions: [{ label: '查看进度', path: '/mine/experiments', primary: task.status === 'running' }],
      };
    });
    return items;
  }, [tasks]);

  return (
    <div className="page-enter">
      <div className="page-header">
        <div>
          <Title level={3} style={{ margin: 0 }}>工作台</Title>
          <Text type="secondary">
            {currentProject?.name ? `当前项目：${currentProject.name}。` : '当前未选择项目。'}
            这里聚合今天最该推进的实验、评估和交付动作。
          </Text>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>刷新</Button>
          <Button type="primary" icon={<RocketOutlined />} onClick={() => navigate('/mine/experiments?create=factory')}>
            创建实验
          </Button>
        </Space>
      </div>

      <Alert
        type={todoCount ? 'warning' : 'success'}
        showIcon
        style={{ marginBottom: 16 }}
        message={todoCount ? `待办：${completedExperiment ? '1个实验待评估，' : ''}${featureStats.current_passed ? `${featureStats.current_passed}个特征待确认，` : ''}${featureStats.latest_version ? '1个版本待交付' : ''}` : '当前没有阻塞待办'}
        description="优先处理评估完成、候选确认和版本交付，确保每次实验都有明确下一步。"
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card className="action-card" hoverable>
            <Space direction="vertical" size={14} style={{ width: '100%' }}>
              <Space align="start">
                <ExperimentOutlined className="metric-icon blue" />
                <div>
                  <Title level={4} style={{ margin: 0 }}>发起探索</Title>
                  <Text type="secondary">适合新场景分析、异常样本诊断和新模板创新。</Text>
                </div>
              </Space>
              <Text>AI 会根据业务问题和样本表现推荐特征方向，预计产出 20-30 个精选特征。</Text>
              <Button type="primary" icon={<ThunderboltOutlined />} onClick={() => navigate('/mine/experiments?create=explore')}>
                发起探索
              </Button>
            </Space>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card className="action-card" hoverable>
            <Space direction="vertical" size={14} style={{ width: '100%' }}>
              <Space align="start">
                <RocketOutlined className="metric-icon teal" />
                <div>
                  <Title level={4} style={{ margin: 0 }}>启动特征工厂</Title>
                  <Text type="secondary">适合已知场景快速扩量，基于模板库批量生成组合。</Text>
                </div>
              </Space>
              <Text>系统推荐高通过率模板组合，预计 15-30 分钟产出 200-500 个候选特征。</Text>
              <Button type="primary" icon={<PlayCircleOutlined />} onClick={() => navigate('/mine/experiments?create=factory')}>
                快速启动
              </Button>
            </Space>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card className="metric-card compact">
            <Statistic title="平台项目" value={projectTotal} suffix="个" />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="metric-card compact">
            <Statistic title="可用加工方式" value={templates.length} suffix="个" />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="metric-card compact">
            <Statistic title="本轮通过率" value={passRate} suffix="%" />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="metric-card compact">
            <Statistic title="最新版本" value={featureStats.latest_version || '-'} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={15}>
          <Card title="最近动态">
            {recentActivities.length ? (
              <List
                dataSource={recentActivities}
                renderItem={(item) => (
                  <List.Item
                    actions={item.actions.map((action) => (
                      <Button
                        key={action.label}
                        size="small"
                        type={action.primary ? 'primary' : 'default'}
                        onClick={() => navigate(action.path)}
                      >
                        {action.label}
                      </Button>
                    ))}
                  >
                    <List.Item.Meta
                      title={<Space><span>{item.title}</span><Tag color={item.tag.color}>{item.tag.text}</Tag></Space>}
                      description={item.desc}
                    />
                  </List.Item>
                )}
              />
            ) : (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="暂无实验动态"
              >
                <Button type="primary" onClick={() => navigate('/mine/experiments?create=factory')}>启动第一次实验</Button>
              </Empty>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={9}>
          <Card title="平台洞察">
            <Space direction="vertical" size={14} style={{ width: '100%' }}>
              <div>
                <div className="dimension-row">
                  <span>历史平均通过率</span>
                  <Tag color="success">68%</Tag>
                </div>
                <Progress percent={68} strokeColor="#34d399" />
              </div>
              <Alert
                type="info"
                showIcon
                message="建议优先使用占比类加工方式"
                description="APP高风险类别占比在当前项目中表现稳定，适合作为快速上手策略的核心组合。"
              />
              <Space wrap>
                <Button size="small" icon={<DatabaseOutlined />} onClick={() => navigate('/assets/data')}>查看数据版本</Button>
                <Button size="small" icon={<FileTextOutlined />} onClick={() => navigate('/assets/knowledge')}>查看知识库</Button>
                <Button size="small" icon={<CloudUploadOutlined />} onClick={() => navigate('/ship/versions')}>查看交付</Button>
              </Space>
            </Space>
          </Card>
        </Col>
      </Row>

      {runningExperiment && (
        <Card title="正在运行的实验" style={{ marginTop: 16 }}>
          <Space direction="vertical" size={10} style={{ width: '100%' }}>
            <Space>
              <Tag color="processing">运行中</Tag>
              <Text strong>{runningExperiment.name}</Text>
            </Space>
            <Progress percent={Math.round(runningExperiment.progress || 0)} />
            <Space>
              <Button type="primary" onClick={() => navigate('/mine/experiments')}>查看实时进度</Button>
              <Button onClick={() => navigate('/copilot')}>让助手诊断实验</Button>
            </Space>
          </Space>
        </Card>
      )}

      {!currentProject && (
        <Card style={{ marginTop: 16 }}>
          <Empty description="欢迎来到 RiskForge AI">
            <Space direction="vertical">
              <Text>3步开始挖掘风控特征：创建项目、准备数据版本、启动第一次实验。</Text>
              <Button type="primary" onClick={() => navigate('/projects')}>开始设置</Button>
            </Space>
          </Empty>
        </Card>
      )}
    </div>
  );
};

export default Dashboard;
