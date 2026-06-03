import React, { useEffect, useState, useCallback } from 'react';
import {
  Table, Tag, Button, Modal, Form, Input, Space, Card,
  Drawer, Spin, Descriptions, Timeline, Tabs, message, Upload, Radio,
  Empty, DatePicker, Steps, Collapse,
} from 'antd';
import {
  PlusOutlined, ReloadOutlined, UploadOutlined, DownloadOutlined,
  CheckCircleOutlined, CloseCircleOutlined, SyncOutlined, ClockCircleOutlined,
  LinkOutlined, DeleteOutlined, FullscreenOutlined, FullscreenExitOutlined,
} from '@ant-design/icons';
import { fetchTasks, fetchTask, createTask, computeFeatures, fetchTaskResult, resumeTask, fetchTaskSamples, downloadTaskDeployment, downloadTaskResultCsv, downloadTaskResultReport, fetchTaskSteps, cancelTask, rerunTask, clearAllTasks, type ComputeResult } from '@/services/api';
import { FRAMEWORK_DESCRIPTION, TEMPLATE_DEFINITIONS } from '@/constants/featureDesignFramework';
import type { Task, TaskLog } from '@/types';
import FeatureCharts from '@/components/FeatureCharts';
import dayjs from 'dayjs';

const { TextArea } = Input;

const taskStatusMap: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
  pending: { color: 'default', icon: <ClockCircleOutlined />, label: '等待中' },
  running: { color: 'processing', icon: <SyncOutlined spin />, label: '运行中' },
  completed: { color: 'success', icon: <CheckCircleOutlined />, label: '完成' },
  failed: { color: 'error', icon: <CloseCircleOutlined />, label: '失败' },
  cancelled: { color: 'warning', icon: <CloseCircleOutlined />, label: '已终止' },
};

const Tasks: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailExpanded, setDetailExpanded] = useState(false);
  const [detailTask, setDetailTask] = useState<Task | null>(null);
  const [detailLogs, setDetailLogs] = useState<TaskLog[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [form] = Form.useForm();

  // Task mode for create form
  const [taskMode, setTaskMode] = useState<'normal' | 'template_task'>('normal');
  // Data source type for create form
  const [dataSourceType, setDataSourceType] = useState<'upload' | 'local'>('upload');
  const [urlFile, setUrlFile] = useState<File | null>(null);
  const [labelFile, setLabelFile] = useState<File | null>(null);

  // Feature compute tab state
  const [computeJson, setComputeJson] = useState('');
  const [computeResults, setComputeResults] = useState<ComputeResult[]>([]);
  const [computeLoading, setComputeLoading] = useState(false);

  // Feature charts data
  const [featureData, setFeatureData] = useState<any[] | null>(null);
  const [featureDataLoading, setFeatureDataLoading] = useState(false);

  // Steps state
  const [taskSteps, setTaskSteps] = useState<{ name: string; label: string; status: 'wait' | 'process' | 'finish' | 'error'; message: string }[]>([]);
  const [stepsLoading, setStepsLoading] = useState(false);

  // Resume state
  const [resuming, setResuming] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [rerunning, setRerunning] = useState(false);

  const handleResume = async () => {
    if (!detailTask) return;
    setResuming(true);
    try {
      await resumeTask(detailTask.id);
      message.success('任务已恢复执行');
      loadTasks(page);
    } catch (e: any) {
      message.error('恢复失败: ' + (e?.message || ''));
    } finally {
      setResuming(false);
    }
  };

  const handleRerun = async () => {
    if (!detailTask) return;
    Modal.confirm({
      title: '确认重新执行',
      content: `重新执行将从头开始运行完整流程（重新下载数据、特征生产、评估、部署）。任务的 history 日志会保留。确认重新执行吗？`,
      okText: '确认执行',
      cancelText: '取消',
      onOk: async () => {
        setRerunning(true);
        try {
          await rerunTask(detailTask.id);
          message.success('已触发重新执行');
          loadTasks(page);
        } catch (e: any) {
          message.error('重新执行失败: ' + (e?.message || ''));
        } finally {
          setRerunning(false);
        }
      },
    });
  };

  const handleCancel = async () => {
    if (!detailTask) return;
    Modal.confirm({
      title: '确认终止任务',
      content: `确定要终止任务 "${detailTask.name}" 吗？终止后当前进度不会丢失，但需要手动"继续执行"才能恢复。`,
      okText: '确认终止',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        setCancelling(true);
        try {
          await cancelTask(detailTask.id);
          message.success('任务已终止');
          loadTasks(page);
          loadSteps(detailTask.id);
        } catch (e: any) {
          message.error('终止失败: ' + (e?.message || ''));
        } finally {
          setCancelling(false);
        }
      },
    });
  };

  const handleClearAll = () => {
    Modal.confirm({
      title: '确认清空所有任务',
      content: '确定要清空所有任务记录吗？此操作不可恢复，正在执行的任务将无法清空。',
      okText: '确认清空',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          const res = await clearAllTasks();
          message.success(`已清空 ${res.deleted} 个任务`);
          loadTasks(1);
          setPage(1);
        } catch (e: any) {
          const msg = e?.response?.data?.detail || e?.message || '清空失败';
          message.error(msg);
        }
      },
    });
  };

  const loadTasks = useCallback(async (p: number = 1) => {
    setLoading(true);
    try {
      const data = await fetchTasks((p - 1) * 50, 50);
      setTasks(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTasks(page);
    const interval = setInterval(() => loadTasks(page), 10000);
    return () => clearInterval(interval);
  }, [page, loadTasks]);

  const loadSteps = async (taskId: number) => {
    setStepsLoading(true);
    try {
      const data = await fetchTaskSteps(taskId);
      setTaskSteps(data.steps);
    } catch {
      setTaskSteps([]);
    } finally {
      setStepsLoading(false);
    }
  };

  const openDetail = async (task: Task) => {
    setDetailOpen(true);
    setDetailTask(task);
    setDetailLoading(true);
    setComputeResults([]);
    setComputeJson('');
    setFeatureData(null);
    setFeatureDataLoading(true);
    loadSteps(task.id);
    try {
      const [data, result, samples] = await Promise.allSettled([
        fetchTask(task.id),
        fetchTaskResult(task.id),
        task.mode !== 'template_task' ? fetchTaskSamples(task.id, 5) : Promise.resolve(null),
      ]);
      if (data.status === 'fulfilled') {
        setDetailLogs(data.value.logs || []);
      } else {
        setDetailLogs([]);
      }
      if (result.status === 'fulfilled') {
        const r = result.value as any;
        // Merge passed + failed features so pie chart shows correct pass rate (147/267, not 147/147)
        const passed = r?.passed_features || [];
        const failed = r?.failed_features || [];
        const allFeatures = [...passed, ...failed];
        if (allFeatures.length > 0) {
          setFeatureData(allFeatures);
        } else if (r?.items) {
          setFeatureData(r.items);
        }
      }
      // Auto-fill compute tab with first 5 samples
      if (samples.status === 'fulfilled' && samples.value && samples.value.items && samples.value.items.length > 0) {
        setComputeJson(JSON.stringify(samples.value.items, null, 2));
      }
    } catch {
      setDetailLogs([]);
    } finally {
      setDetailLoading(false);
      setFeatureDataLoading(false);
    }
  };

  const handleCreate = async (values: any) => {
    try {
      const scheduledAt = values.scheduled_at
        ? values.scheduled_at.toISOString()
        : undefined;

      if (taskMode === 'template_task') {
        await createTask({
          name: values.name,
          mode: 'template_task',
          scheduled_at: scheduledAt,
          recurring_cron: values.recurring_cron || undefined,
        });
        message.success('模板生成任务已创建，LLM正在生成模板...');
      } else {
        await createTask({
          name: values.name,
          scheduled_at: scheduledAt,
          ...(dataSourceType === 'upload'
            ? { url_file: urlFile || undefined, label_file: labelFile || undefined }
            : { url_path: values.url_path, label_path: values.label_path }),
        });
        message.success('任务创建成功（系统将自动创建关联的模板任务）');
      }
      setCreateOpen(false);
      setUrlFile(null);
      setLabelFile(null);
      form.resetFields();
      loadTasks(1);
    } catch (e: any) {
      message.error('创建失败: ' + (e?.message || ''));
    }
  };

  const handleComputeTest = async () => {
    if (!computeJson.trim()) {
      message.warning('请输入样本JSON数据');
      return;
    }
    try {
      const samples = JSON.parse(computeJson);
      if (!Array.isArray(samples)) {
        message.error('请输入JSON数组格式');
        return;
      }
      setComputeLoading(true);
      const result = await computeFeatures(samples);
      setComputeResults(result.results);
      message.success(`计算完成，共 ${result.total} 条`);
    } catch (e: any) {
      message.error('计算失败: ' + (e?.message || '请检查JSON格式'));
    } finally {
      setComputeLoading(false);
    }
  };

  const handleDownloadDeployment = async () => {
    if (!detailTask) return;
    try {
      const blob = await downloadTaskDeployment(detailTask.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `deployment_${detailTask.deployed_version}.tar.gz`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      message.success(`正在下载部署包 ${detailTask.deployed_version}`);
    } catch (e: any) {
      message.error('下载失败: ' + (e?.message || ''));
    }
  };

  const handleDownloadCsv = async () => {
    if (!detailTask) return;
    try {
      const blob = await downloadTaskResultCsv(detailTask.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `feature_evaluation_${detailTask.id}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      message.success('特征评估CSV下载完成');
    } catch (e: any) {
      message.error('CSV下载失败: ' + (e?.message || ''));
    }
  };

  const handleDownloadReport = async () => {
    if (!detailTask) return;
    try {
      const blob = await downloadTaskResultReport(detailTask.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `feature_evaluation_report_${detailTask.id}.html`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      message.success('评估报告下载完成');
    } catch (e: any) {
      message.error('报告下载失败: ' + (e?.message || ''));
    }
  };

  // Auto-refresh steps when detail is open and task is active (pending, running, or no final status)
  useEffect(() => {
    if (!detailOpen || !detailTask) return;
    const terminalStates = ['completed', 'failed', 'cancelled'];
    // If terminal state, load steps once (not in interval) but don't poll
    if (terminalStates.includes(detailTask.status)) {
      loadSteps(detailTask.id);
      return;
    }
    // Poll every 5s for non-terminal states
    loadSteps(detailTask.id);
    const interval = setInterval(() => loadSteps(detailTask.id), 5000);
    return () => clearInterval(interval);
  }, [detailOpen, detailTask?.id, detailTask?.status]);

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    {
      title: '类型', dataIndex: 'mode', key: 'mode', width: 90,
      render: (m: string) => m === 'template_task'
        ? <Tag color="purple">模板生成</Tag>
        : <Tag color="blue">特征挖掘</Tag>,
    },
    { title: '名称', dataIndex: 'name', key: 'name', ellipsis: true },
    {
      title: '关联任务', dataIndex: 'linked_task_id', key: 'linked_task_id', width: 90,
      render: (v: number) => v ? `#${v}` : '-',
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 90,
      render: (s: string) => {
        const m = taskStatusMap[s];
        return m ? <Tag color={m.color} icon={m.icon}>{m.label}</Tag> : <Tag>{s}</Tag>;
      },
    },
    {
      title: '进度', dataIndex: 'progress', key: 'progress', width: 70,
      render: (v: number) => `${v?.toFixed(0) || 0}%`,
    },
    {
      title: '通过/总数', key: 'counts', width: 90,
      render: (_: any, r: Task) =>
        r.total_features != null ? `${r.passed_features}/${r.total_features}` : '-',
    },
    {
      title: '版本', dataIndex: 'deployed_version', key: 'deployed_version', width: 70,
      render: (v: string) => v ? <Tag color="blue">{v}</Tag> : '-',
    },
    {
      title: '计划时间', dataIndex: 'scheduled_at', key: 'scheduled_at', width: 160,
      render: (v: string) => v ? new Date(v).toLocaleString() : '-',
    },
    {
      title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170,
      render: (v: string) => v ? new Date(v).toLocaleString() : '-',
    },
    {
      title: '操作', key: 'actions', width: 70,
      render: (_: any, record: Task) => (
        <Button type="link" size="small" onClick={() => openDetail(record)}>详情</Button>
      ),
    },
  ];

  return (
    <div>
      <Card
        title="任务管理"
        extra={
          <Space>
            <Button icon={<DeleteOutlined />} danger onClick={handleClearAll}>清空任务</Button>
            <Button icon={<ReloadOutlined />} onClick={() => loadTasks(page)}>刷新</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>新建任务</Button>
          </Space>
        }
      >
        <Table
          dataSource={tasks}
          columns={columns}
          rowKey="id"
          loading={loading}
          size="small"
          pagination={{
            current: page, total, pageSize: 50,
            onChange: setPage,
            showTotal: (t) => `共 ${t} 条`,
          }}
          onRow={(record) => ({
            onClick: () => openDetail(record),
            style: { cursor: 'pointer' },
          })}
        />
      </Card>

      {/* Create Modal */}
      <Modal
        title="新建任务"
        open={createOpen}
        onCancel={() => { setCreateOpen(false); setUrlFile(null); setLabelFile(null); }}
        onOk={() => form.submit()}
        okText="创建"
        cancelText="取消"
        width={560}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="name" label="任务名称" rules={[{ required: true, message: '请输入任务名称' }]}>
            <Input placeholder={taskMode === 'template_task' ? '例如: 设计GPS防欺诈模板' : '例如: 4月批量特征挖掘'} />
          </Form.Item>

          <Form.Item label="任务类型">
            <Radio.Group
              value={taskMode}
              onChange={(e) => { setTaskMode(e.target.value); form.resetFields(); }}
            >
              <Radio value="normal">特征挖掘</Radio>
              <Radio value="template_task">模板生成</Radio>
            </Radio.Group>
          </Form.Item>

          {taskMode === 'template_task' ? (
            <>
              <Form.Item name="scheduled_at" label="计划执行时间（可选）" extra="设置后系统将在指定时间自动执行">
                <DatePicker
                  showTime
                  format="YYYY-MM-DD HH:mm"
                  style={{ width: '100%' }}
                  placeholder="选择计划执行时间（默认立即执行）"
                />
              </Form.Item>
              <Form.Item name="recurring_cron" label="周期性执行（可选）" extra="设置后系统将按计划反复运行，每次生成的模板自动去重">
                <Input placeholder="例如: 0 2 * * 1（每周一凌晨2点），留空为仅执行一次" />
              </Form.Item>
              <div style={{ padding: '8px 0', color: '#888', fontSize: 13 }}>
                模板生成任务将由LLM自动生成DSL模板和Python计算代码，结果展示在Agent Chat页面的待审核区。无需数据配置。<br />
                <strong>去重机制：</strong>每次运行时LLM会参考已有模板（通道1+通道2待审核），确保不生成重复的 template_name。
              </div>
            </>
          ) : (
            <>
              <Form.Item name="scheduled_at" label="计划执行时间（可选）">
                <DatePicker
                  showTime
                  format="YYYY-MM-DD HH:mm"
                  style={{ width: '100%' }}
                  placeholder="选择计划执行时间（默认立即执行）"
                />
              </Form.Item>

              <Form.Item label="数据配置方式">
                <Radio.Group
                  value={dataSourceType}
                  onChange={(e) => setDataSourceType(e.target.value)}
                >
                  <Radio value="upload">一次性上传</Radio>
                  <Radio value="local">本地路径更新覆盖</Radio>
                </Radio.Group>
              </Form.Item>

              {dataSourceType === 'upload' ? (
                <>
                  <Form.Item label="短链 URL 文件（.txt）" extra="每行一个订单短链地址" required>
                    <Upload
                      accept=".txt"
                      showUploadList={{ showRemoveIcon: true }}
                      maxCount={1}
                      beforeUpload={(file) => { setUrlFile(file); return false; }}
                      onRemove={() => setUrlFile(null)}
                    >
                      <Button icon={<UploadOutlined />}>选择文件</Button>
                    </Upload>
                  </Form.Item>
                  <Form.Item label="好坏标签文件（.xlsx / .csv）" extra="包含订单号与好坏标签列" required>
                    <Upload
                      accept=".xlsx,.xls,.csv"
                      showUploadList={{ showRemoveIcon: true }}
                      maxCount={1}
                      beforeUpload={(file) => { setLabelFile(file); return false; }}
                      onRemove={() => setLabelFile(null)}
                    >
                      <Button icon={<UploadOutlined />}>选择文件</Button>
                    </Upload>
                  </Form.Item>
                </>
              ) : (
                <>
                  <Form.Item name="url_path" label="短链 URL 文件路径" rules={[{ required: true, message: '请输入短链文件路径' }]}>
                    <Input placeholder="例如: /data/0421全样本短链.txt" />
                  </Form.Item>
                  <Form.Item name="label_path" label="好坏标签文件路径" rules={[{ required: true, message: '请输入标签文件路径' }]}>
                    <Input placeholder="例如: /data/印尼模型分_2026_04_21_建模样本aiagent.xlsx" />
                  </Form.Item>
                </>
              )}
            </>
          )}
        </Form>
      </Modal>

      {/* Detail Drawer */}
      <Drawer
        title={
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span>{`任务详情 #${detailTask?.id} ${detailTask?.mode === 'template_task' ? '(模板生成)' : '(特征挖掘)'}`}</span>
            <Button
              type="text"
              size="small"
              icon={detailExpanded ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
              onClick={() => setDetailExpanded(!detailExpanded)}
            />
          </div>
        }
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        width={detailExpanded ? 'calc(100vw - 48px)' : 680}
      >
        {detailLoading ? <Spin /> : (
          <>
            <Descriptions column={2} size="small" bordered style={{ marginBottom: 24 }}>
              <Descriptions.Item label="名称">{detailTask?.name}</Descriptions.Item>
              <Descriptions.Item label="类型">
                {detailTask?.mode === 'template_task'
                  ? <Tag color="purple">模板生成</Tag>
                  : <Tag color="blue">特征挖掘</Tag>}
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                {detailTask && (() => {
                  const m = taskStatusMap[detailTask.status];
                  return m ? <Tag color={m.color} icon={m.icon}>{m.label}</Tag> : detailTask.status;
                })()}
                {detailTask?.status === 'failed' && detailTask?.mode !== 'template_task' && (
                  <Button
                    type="primary"
                    size="small"
                    loading={resuming}
                    onClick={(e) => { e.stopPropagation(); handleResume(); }}
                    style={{ marginLeft: 12 }}
                  >
                    继续执行
                  </Button>
                )}
                {(detailTask?.status === 'running' || detailTask?.status === 'pending') && detailTask?.mode !== 'template_task' && (
                  <Button
                    danger
                    size="small"
                    loading={cancelling}
                    onClick={(e) => { e.stopPropagation(); handleCancel(); }}
                    style={{ marginLeft: 12 }}
                  >
                    终止任务
                  </Button>
                )}
                {detailTask && detailTask.mode !== 'template_task'
                  && detailTask.status !== 'running' && detailTask.status !== 'pending'
                  && detailTask.config?.data_source === 'local'
                  && detailTask.config?.url_path && (
                  <Button
                    type="primary"
                    size="small"
                    loading={rerunning}
                    onClick={(e) => { e.stopPropagation(); handleRerun(); }}
                    style={{ marginLeft: 12 }}
                  >
                    再次运行
                  </Button>
                )}
                {/* 模板任务：失败时可再次执行 */}
                {detailTask?.status === 'failed' && detailTask?.mode === 'template_task' && (
                  <Button
                    type="primary"
                    size="small"
                    loading={rerunning}
                    onClick={(e) => { e.stopPropagation(); handleRerun(); }}
                    style={{ marginLeft: 12 }}
                  >
                    再次执行
                  </Button>
                )}
              </Descriptions.Item>
              <Descriptions.Item label="进度">{detailTask?.progress?.toFixed(0)}%</Descriptions.Item>
              {detailTask?.linked_task_id && (
                <Descriptions.Item label="关联任务" span={2}>#{detailTask.linked_task_id}</Descriptions.Item>
              )}
              {detailTask?.scheduled_at && (
                <Descriptions.Item label="计划执行时间" span={2}>
                  {new Date(detailTask.scheduled_at).toLocaleString()}
                </Descriptions.Item>
              )}
              {detailTask?.total_features != null && (
                <>
                  <Descriptions.Item label="通过/总数">
                    {detailTask.passed_features}/{detailTask.total_features}
                  </Descriptions.Item>
                  <Descriptions.Item label="版本">{detailTask.deployed_version || '-'}</Descriptions.Item>
                </>
              )}
              {detailTask?.error_message && (
                <Descriptions.Item label="错误信息" span={2}>
                  <span style={{ color: '#ff4d4f' }}>{detailTask.error_message}</span>
                </Descriptions.Item>
              )}
            </Descriptions>

            {/* 流程步骤条 */}
            {detailTask && detailTask.mode !== 'template_task' && (
              <Card size="small" style={{ marginBottom: 16, background: '#fafafa' }}>
                <Steps
                  size="small"
                  current={(() => {
                    // current = 已完成的步骤数量（0-based = 已完成数-1）
                    // 如果没有 process 也没有 finish，说明还没开始 → current=0
                    // 如果有 process/finish，current = 已finish的数量
                    const finishCount = taskSteps.filter(s => s.status === 'finish').length;
                    const hasProcess = taskSteps.some(s => s.status === 'process');
                    // 如果有 process，current 指向该步骤的索引
                    const processIdx = taskSteps.findIndex(s => s.status === 'process');
                    if (processIdx >= 0) return processIdx;
                    // 如果没有任何 started，但有一些完成的，current=已完成数
                    if (finishCount > 0) return finishCount;
                    // 如果只有 error
                    if (taskSteps.some(s => s.status === 'error')) {
                      const errorIdx = taskSteps.findIndex(s => s.status === 'error');
                      return errorIdx >= 0 ? errorIdx : 0;
                    }
                    // 全 wait → 还没开始，current=0
                    return 0;
                  })()}
                  status={taskSteps.some(s => s.status === 'error') ? 'error' :
                    taskSteps.some(s => s.status === 'process') ? 'process' : 'wait'}
                  items={taskSteps.map((s, idx) => ({
                    title: s.label,
                    status: s.status,
                    description: s.message || undefined,
                  }))}
                />
                {stepsLoading && (
                  <div style={{ textAlign: 'center', marginTop: 8 }}>
                    <Spin size="small" /> <span style={{ fontSize: 12, color: '#999', marginLeft: 8 }}>正在刷新步骤状态...</span>
                  </div>
                )}
              </Card>
            )}

            {detailTask && (
              <Tabs
                items={[
                  {
                    key: 'logs',
                    label: '执行日志',
                    children: (
                      <Timeline>
                        {detailLogs.map((log) => (
                          <Timeline.Item
                            key={log.id}
                            color={log.level === 'error' ? 'red' : log.level === 'warning' ? 'orange' : 'blue'}
                          >
                            <div style={{ fontSize: 12, color: '#999' }}>
                              {new Date(log.timestamp).toLocaleString()}
                            </div>
                            <div>{log.message}</div>
                          </Timeline.Item>
                        ))}
                        {detailLogs.length === 0 && (
                          <Empty description="暂无日志" />
                        )}
                      </Timeline>
                    ),
                  },
                  ...(detailTask.mode !== 'template_task' ? [
                    {
                      key: 'eval',
                      label: '特征评估',
                      children: detailTask.total_features != null ? (
                        <div>
                          <Collapse
                            ghost
                            expandIconPosition="end"
                            defaultActiveKey={[]}
                            items={[
                              {
                                key: 'framework',
                                label: <span style={{ fontWeight: 600, fontSize: 14 }}>特征设计框架</span>,
                                children: (
                                  <div style={{ padding: '8px 0' }}>
                                    <div style={{
                                      marginBottom: 16, fontSize: 13, lineHeight: 1.8, color: '#555',
                                      padding: '12px 16px', background: '#f9f9f9', borderRadius: 6,
                                    }}>
                                      {FRAMEWORK_DESCRIPTION}
                                    </div>
                                    <Table
                                      dataSource={TEMPLATE_DEFINITIONS}
                                      rowKey="template_id"
                                      size="small"
                                      pagination={false}
                                      scroll={{ x: 'max-content' }}
                                      columns={[
                                        { title: 'ID', dataIndex: 'template_id', key: 'template_id', width: 65 },
                                        { title: '模板名称', dataIndex: 'template_name', key: 'template_name', width: 100 },
                                        { title: '数据维度', dataIndex: 'dimension', key: 'dimension', width: 140 },
                                        { title: '模板描述', dataIndex: 'description', key: 'description', ellipsis: true },
                                        { title: '组合数', dataIndex: 'param_combo_count', key: 'param_combo_count', width: 70, align: 'right' },
                                        { title: '业务含义', dataIndex: 'business_meaning', key: 'business_meaning', width: 260, ellipsis: true },
                                      ]}
                                    />
                                  </div>
                                ),
                              },
                            ]}
                          />
                          <div style={{ marginTop: 16 }}>
                            <FeatureCharts
                              totalFeatures={detailTask.total_features}
                              passedFeatures={detailTask.passed_features}
                              features={featureData || undefined}
                              loading={featureDataLoading}
                            />
                          </div>
                          <div style={{ marginTop: 16, textAlign: 'right', display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                            <Button
                              icon={<DownloadOutlined />}
                              onClick={handleDownloadReport}
                            >
                              下载评估报告
                            </Button>
                            <Button
                              icon={<DownloadOutlined />}
                              onClick={handleDownloadCsv}
                            >
                              下载评估CSV
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <Empty description="暂无评估数据" />
                      ),
                    },
                    {
                      key: 'compute',
                      label: '特征测试',
                      children: (
                        <div>
                          <p style={{ marginBottom: 8, color: '#666' }}>
                            以下为前5个样本数据（可编辑修改），点击"计算测试"运行特征计算：
                          </p>
                          <TextArea
                            rows={8}
                            placeholder='[{"base": {"salary": 5000000}, "appList": []}]'
                            value={computeJson}
                            onChange={(e) => setComputeJson(e.target.value)}
                            style={{ marginBottom: 12, fontFamily: 'monospace', fontSize: 12 }}
                          />
                          <Button
                            type="primary"
                            onClick={handleComputeTest}
                            loading={computeLoading}
                            style={{ marginBottom: 16 }}
                          >
                            计算测试
                          </Button>
                          {computeResults.length > 0 && (
                            <Table
                              dataSource={computeResults.slice(0, 20)}
                              columns={[
                                { title: '订单ID', dataIndex: 'order_id', key: 'order_id', width: 200, ellipsis: true },
                                {
                                  title: '计算结果',
                                  dataIndex: 'features',
                                  key: 'features',
                                  width: 300,
                                  render: (f: Record<string, number>, record: any) => (
                                    <div>
                                      {record.error && (
                                        <div style={{ color: '#ff4d4f', fontSize: 12, marginBottom: 4 }}>
                                          {record.error}
                                        </div>
                                      )}
                                      <pre style={{ fontSize: 12, maxHeight: 200, overflow: 'auto', margin: 0 }}>
                                        {JSON.stringify(f, null, 2)}
                                      </pre>
                                    </div>
                                  ),
                                },
                              ]}
                              rowKey="order_id"
                              size="small"
                              pagination={false}
                            />
                          )}
                          {computeResults.length > 20 && (
                            <div style={{ marginTop: 8, color: '#999' }}>
                              显示前20条，共 {computeResults.length} 条
                            </div>
                          )}
                        </div>
                      ),
                    },
                    {
                      key: 'deploy',
                      label: '特征部署',
                      children: detailTask.deployed_version ? (
                        <div>
                          <Descriptions column={2} size="small" bordered style={{ marginBottom: 16 }}>
                            <Descriptions.Item label="部署版本">{detailTask.deployed_version}</Descriptions.Item>
                            <Descriptions.Item label="状态">
                              <Tag color="success">已部署</Tag>
                            </Descriptions.Item>
                            <Descriptions.Item label="完成时间">
                              {detailTask.completed_at
                                ? new Date(detailTask.completed_at).toLocaleString() : '-'}
                            </Descriptions.Item>
                          </Descriptions>

                          <Card
                            size="small"
                            title={<span style={{ color: '#1890ff' }}>风控团队 — 快速获取特征值</span>}
                            style={{ marginBottom: 16, borderLeft: '3px solid #1890ff' }}
                          >
                            <p style={{ marginBottom: 12, color: '#555' }}>
                              部署包可在公司内任意一台服务器上启动服务。启动后，风控团队通过HTTP API发送
                              样本数据即可获取特征计算结果。以下是一键启动和调用指南：
                            </p>

                            <p><strong>第一步：一键启动服务</strong></p>
                            <pre style={{
                              background: '#f6f8fa', padding: 16, borderRadius: 6,
                              fontSize: 13, lineHeight: 1.6, overflow: 'auto',
                            }}>
{`# 下载部署包 → 上传到服务器 → 解压 → 一键启动
tar -xzf deployment_${detailTask.deployed_version}.tar.gz
cd deployment_${detailTask.deployed_version}

# 一键启动（Docker自动完成端口映射和依赖安装）
docker-compose -f deploy/docker-compose.yml up -d

# 服务运行在 http://服务器IP:8001
# 检查服务状态：
curl http://服务器IP:8001/health`}
                            </pre>

                            <p><strong>第二步：调用服务获取特征值</strong></p>
                            <pre style={{
                              background: '#f6f8fa', padding: 16, borderRadius: 6,
                              fontSize: 13, lineHeight: 1.6, overflow: 'auto',
                            }}>
{`import requests
import json

SERVICE_URL = "http://服务器IP:8001"

# 准备样本（直接使用订单原始JSON数据）
samples = [
    {
        "country": "INDO",
        "orderId": "id002xxxxxxx",
        "applyTime": 1743482879000,
        "params": {
            "base": {"salary": 12000000, "job": "12", "gender": 0},
            "appList": [...],   # 原始appList数据
            "FDC": {...}        # 原始FDC数据
        }
    }
]

# 批量计算特征
resp = requests.post(
    f"{SERVICE_URL}/api/v1/calculate",
    json={"samples": samples},
    timeout=60
)
data = resp.json()

# 输出结果
for r in data["results"]:
    print(f"订单: {r['order_id']}")
    print(f"特征数: {len(r.get('features', {}))}")
    print(f"耗时: {r.get('processing_time_ms')}ms")`}
                            </pre>
                          </Card>

                          <Card
                            size="small"
                            title={<span style={{ color: '#52c41a' }}>IT运维 — 线上部署说明</span>}
                            style={{ marginBottom: 16, borderLeft: '3px solid #52c41a' }}
                          >
                            <p style={{ marginBottom: 12, color: '#555' }}>
                              将特征计算部署为独立微服务，支持Docker和直接运行两种方式。
                            </p>

                            <p><strong>Docker 部署（推荐）</strong></p>
                            <pre style={{
                              background: '#f6f8fa', padding: 16, borderRadius: 6,
                              fontSize: 13, lineHeight: 1.6, overflow: 'auto',
                            }}>
{`# 解压 → 启动 → 完成
tar -xzf deployment_${detailTask.deployed_version}.tar.gz
cd deployment_${detailTask.deployed_version}
docker-compose -f deploy/docker-compose.yml up -d`}
                            </pre>

                            <p><strong>直接运行</strong></p>
                            <pre style={{
                              background: '#f6f8fa', padding: 16, borderRadius: 6,
                              fontSize: 13, lineHeight: 1.6, overflow: 'auto',
                            }}>
{`# 解压 → 装依赖 → 启动
tar -xzf deployment_${detailTask.deployed_version}.tar.gz
cd deployment_${detailTask.deployed_version}
pip install -r requirements.txt
uvicorn api.app:app --host 0.0.0.0 --port 8001`}
                            </pre>

                            <p><strong>API 文档</strong></p>
                            <pre style={{
                              background: '#f6f8fa', padding: 16, borderRadius: 6,
                              fontSize: 13, lineHeight: 1.6, overflow: 'auto',
                            }}>
{`POST /api/v1/calculate  — 批量计算特征值
GET  /health            — 健康检查

请求体: { "samples": [ { 订单JSON }, ... ] }
响应:   { "total": N, "results": [ { order_id, features, ... } ] }`}
                            </pre>
                          </Card>

                          <Button
                            type="primary"
                            icon={<DownloadOutlined />}
                            onClick={handleDownloadDeployment}
                            size="large"
                            block
                            style={{ marginBottom: 16 }}
                          >
                            下载部署包 v{detailTask.deployed_version}
                          </Button>
                        </div>
                      ) : (
                        <Empty description="该任务尚未部署" />
                      ),
                    },
                  ] : []),
                ]}
              />
            )}
          </>
        )}
      </Drawer>
    </div>
  );
};

export default Tasks;
