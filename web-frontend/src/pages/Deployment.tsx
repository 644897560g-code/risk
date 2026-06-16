import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Button, Card, Col, Descriptions, Empty, Row, Space, Steps, Table, Tag, Typography, message } from 'antd';
import { CloudDownloadOutlined, CloudUploadOutlined, ReloadOutlined, RollbackOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { downloadTaskDeployment, fetchFeatureVersions } from '@/services/api';
import type { FeatureVersion } from '@/types/feature';
import { useProjectStore } from '@/store/projectStore';

const { Text, Title } = Typography;

const Deployment: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const currentProject = useProjectStore((s) => s.currentProject);
  const taskIdParam = Number(searchParams.get('taskId')) || undefined;
  const [versions, setVersions] = useState<FeatureVersion[]>([]);
  const [loading, setLoading] = useState(false);
  const [downloadingId, setDownloadingId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setVersions(await fetchFeatureVersions(currentProject?.id));
    } catch {
      message.error('部署版本加载失败');
    } finally {
      setLoading(false);
    }
  }, [currentProject?.id]);

  useEffect(() => {
    load();
  }, [load]);

  const scopedVersion = taskIdParam ? versions.find((item) => item.task_id === taskIdParam) : undefined;
  const latest = scopedVersion || versions[0];
  const lifecycleItems = [
    { title: '待业务确认', description: '确认评估结论和特征清单' },
    { title: '待技术部署', description: '交付部署包和调用说明' },
    { title: '已发布', description: '线上版本生效' },
    { title: '已回滚/废弃', description: '异常时保留追溯记录' },
  ];

  const download = async (row: FeatureVersion) => {
    setDownloadingId(row.task_id);
    try {
      const blob = await downloadTaskDeployment(row.task_id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `deployment_${row.version}.tar.gz`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      message.success(`正在下载 ${row.version}`);
    } catch (e: any) {
      message.error(e?.message || '下载失败');
    } finally {
      setDownloadingId(null);
    }
  };

  const columns: ColumnsType<FeatureVersion> = [
    {
      title: '版本',
      dataIndex: 'version',
      render: (version: string, row) => (
        <Space>
          <Tag color="blue">{version}</Tag>
          {row.version === latest?.version && <Tag color="success">当前推荐</Tag>}
        </Space>
      ),
    },
    { title: '来源实验', dataIndex: 'task_id', width: 100, render: (id: number) => `#${id}` },
    { title: '数据版本', dataIndex: 'task_id', width: 180, render: (id: number) => <Tag color="blue">{`V_task_${id}`}</Tag> },
    { title: '特征数', dataIndex: 'total_features', width: 100 },
    {
      title: '通过率',
      width: 120,
      render: (_, row) => `${row.passed_features}/${row.total_features}`,
    },
    {
      title: '生成时间',
      dataIndex: 'created_at',
      width: 180,
      render: (v: string) => v ? new Date(v).toLocaleString() : '-',
    },
    {
      title: '状态',
      width: 130,
      render: (_, row) => row.version === latest?.version ? <Tag color="warning">待业务确认</Tag> : <Tag>历史归档</Tag>,
    },
    {
      title: '操作',
      width: 180,
      render: (_, row) => (
        <Space>
          <Button
            size="small"
            icon={<CloudDownloadOutlined />}
            loading={downloadingId === row.task_id}
            onClick={() => download(row)}
          >
            下载
          </Button>
          <Button size="small" icon={<RollbackOutlined />} disabled>回滚</Button>
        </Space>
      ),
    },
  ];

  return (
    <div className="page-enter">
      <div className="page-header">
        <div>
          <Title level={3} style={{ margin: 0 }}>版本管理</Title>
          <Text type="secondary">
            {currentProject?.name ? `当前项目：${currentProject.name}。` : ''}
            管理候选集生成的交付版本，面向模型团队提供技术包、业务说明书和调用说明。
          </Text>
        </div>
        <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>刷新</Button>
      </div>

      <Card style={{ marginBottom: 16 }}>
        <Descriptions column={{ xs: 1, sm: 2, lg: 5 }} size="small">
          <Descriptions.Item label="所属平台">RiskForge AI</Descriptions.Item>
          <Descriptions.Item label="所属项目">{currentProject?.name || '-'}</Descriptions.Item>
          <Descriptions.Item label="来源实验">{latest?.task_id ? `#${latest.task_id}` : taskIdParam ? `#${taskIdParam}` : '请选择版本'}</Descriptions.Item>
          <Descriptions.Item label="数据版本">{latest?.task_id ? `V_task_${latest.task_id}` : taskIdParam ? `V_task_${taskIdParam}` : '-'}</Descriptions.Item>
          <Descriptions.Item label="结果类型">版本交付</Descriptions.Item>
        </Descriptions>
      </Card>

      {latest ? (
        <Card className="release-card">
          <Row gutter={[16, 16]} align="middle">
            <Col xs={24} lg={15}>
              <Space direction="vertical" size={8}>
                <Space>
                  <CloudUploadOutlined style={{ color: '#37e7ff', fontSize: 24 }} />
                  <Title level={4} style={{ margin: 0 }}>当前推荐版本 {latest.version}</Title>
                  <Tag color="warning">待业务确认</Tag>
                </Space>
                <Text type="secondary">
                  来自候选集确认结果，包含 {latest.passed_features} 个待交付特征。当前版本已具备交付条件，但仍需业务确认后再发布。
                </Text>
                <Text>上线建议：特征质量较上一版本提升，建议替换上一版；首次上线特征需重点监控稳定性。</Text>
              </Space>
            </Col>
            <Col xs={24} lg={9} style={{ textAlign: 'right' }}>
              <Space wrap style={{ justifyContent: 'flex-end' }}>
                <Button onClick={() => navigate(`/mine/report?taskId=${latest.task_id}`)}>查看同实验评估</Button>
                <Button onClick={() => navigate(`/ship/candidates?taskId=${latest.task_id}`)}>查看候选集</Button>
                <Button
                  type="primary"
                  icon={<CloudDownloadOutlined />}
                  size="large"
                  loading={downloadingId === latest.task_id}
                  onClick={() => download(latest)}
                >
                  下载部署包
                </Button>
              </Space>
            </Col>
          </Row>
        </Card>
      ) : (
        <Card><Empty description="暂无部署版本" /></Card>
      )}

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24}>
          <Card title="版本生命周期">
            {latest ? (
              <>
                <Alert
                  type="warning"
                  showIcon
                  style={{ marginBottom: 16 }}
                  message="当前停留在业务确认节点"
                  description="产品/风控确认推荐特征、评估报告和部署范围后，再进入技术部署。发布、回滚、废弃都应保留来源任务和评估结论。"
                />
                <Steps current={0} items={lifecycleItems} />
              </>
            ) : (
              <Empty description="暂无可流转版本" />
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={8}>
          <Card title="交付检查">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="特征清单"><Tag color={latest ? 'success' : 'default'}>{latest ? '已生成' : '待生成'}</Tag></Descriptions.Item>
              <Descriptions.Item label="评估报告"><Tag color={latest ? 'success' : 'default'}>{latest ? '已关联' : '待关联'}</Tag></Descriptions.Item>
              <Descriptions.Item label="部署包"><Tag color={latest ? 'success' : 'default'}>{latest ? '可下载' : '待生成'}</Tag></Descriptions.Item>
              <Descriptions.Item label="业务确认"><Tag color="warning">待人工确认</Tag></Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="来源追溯">
            {latest ? (
              <Descriptions column={1} size="small">
                <Descriptions.Item label="来源实验">#{latest.task_id}</Descriptions.Item>
                <Descriptions.Item label="数据版本">{`V_task_${latest.task_id}`}</Descriptions.Item>
                <Descriptions.Item label="评估版本">{latest.version}</Descriptions.Item>
                <Descriptions.Item label="通过特征">{latest.passed_features}/{latest.total_features}</Descriptions.Item>
                <Descriptions.Item label="追溯动作">
                  <Space wrap>
                    <Button size="small" onClick={() => navigate('/mine/experiments')}>查看实验</Button>
                    <Button size="small" onClick={() => navigate(`/mine/report?taskId=${latest.task_id}`)}>查看评估</Button>
                  </Space>
                </Descriptions.Item>
              </Descriptions>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="API 调用信息">
            {latest ? (
              <Space direction="vertical" size={10}>
                <Text>版本号：<Tag color="blue">{latest.version}</Tag></Text>
                <Text type="secondary">调用方应固定传入版本号，确保线上结果与交付包一致。</Text>
                <Text code>{`POST /feature/calculate?version=${latest.version}`}</Text>
                <Tag color="warning">接口信息占位</Tag>
              </Space>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>
      </Row>

      <Card title="交付物" style={{ marginTop: 16 }}>
        <Space wrap>
          <Button
            type="primary"
            icon={<CloudDownloadOutlined />}
            disabled={!latest}
            loading={latest ? downloadingId === latest.task_id : false}
            onClick={() => latest && download(latest)}
          >
            下载技术包
          </Button>
          <Button disabled={!latest} onClick={() => message.info('业务说明书生成为原型占位，后续支持PDF/Excel导出。')}>
            下载业务说明书
          </Button>
          <Button disabled={!latest} onClick={() => message.info('API文档为原型占位，后续展示接口字段和示例请求。')}>
            API文档
          </Button>
          <Button disabled={!latest} onClick={() => message.info('小流量验证能力即将上线。')}>
            小流量验证
          </Button>
          <Button type="primary" disabled={!latest} onClick={() => message.success('已记录业务确认，等待技术部署。')}>
            确认上线
          </Button>
        </Space>
      </Card>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={10}>
          <Card title="版本对比">
            {versions.length >= 2 ? (
              <Descriptions column={1} size="small">
                <Descriptions.Item label="当前版本">{versions[0].version} · {versions[0].passed_features}/{versions[0].total_features}</Descriptions.Item>
                <Descriptions.Item label="对比版本">{versions[1].version} · {versions[1].passed_features}/{versions[1].total_features}</Descriptions.Item>
                <Descriptions.Item label="变化摘要">通过特征增加 {versions[0].passed_features - versions[1].passed_features} 个，发布前需结合评估报告确认。</Descriptions.Item>
              </Descriptions>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无可对比版本" />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={14}>
          <Card title="版本列表">
            <Table
              rowKey="version"
              loading={loading}
              columns={columns}
              dataSource={versions}
              pagination={{ pageSize: 10, showTotal: (total) => `共 ${total} 个版本` }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Deployment;
