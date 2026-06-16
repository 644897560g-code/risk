import React, { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Card,
  Checkbox,
  Form,
  Input,
  Modal,
  Popconfirm,
  Space,
  Table,
  Tag,
  message,
} from 'antd';
import { DeleteOutlined, EditOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  createProject,
  deleteProject,
  fetchChannel1Templates,
  fetchProjectTemplates,
  fetchProjects,
  setProjectTemplateSelection,
  updateProject,
  type Channel1Template,
} from '@/services/api';
import type { Project } from '@/types/project';
import { useProjectStore } from '@/store/projectStore';

const parseConfig = (raw?: string): Record<string, unknown> => {
  if (!raw || !raw.trim()) return {};
  const parsed = JSON.parse(raw);
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('配置必须是 JSON 对象');
  }
  return parsed as Record<string, unknown>;
};

const Projects: React.FC = () => {
  const [items, setItems] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Project | null>(null);
  const [activeTemplates, setActiveTemplates] = useState<Channel1Template[]>([]);
  const [templateLoading, setTemplateLoading] = useState(false);
  const [selectedTemplateIds, setSelectedTemplateIds] = useState<string[]>([]);
  const [form] = Form.useForm();
  const { currentProject, loadProjects } = useProjectStore();
  const activeTemplateIds = activeTemplates.map((tmpl) => tmpl.template_id);
  const selectedActiveTemplateCount = selectedTemplateIds.filter((id) => activeTemplateIds.includes(id)).length;
  const allTemplatesSelected = activeTemplateIds.length > 0 && selectedActiveTemplateCount === activeTemplateIds.length;
  const templatesPartiallySelected = selectedActiveTemplateCount > 0 && selectedActiveTemplateCount < activeTemplateIds.length;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchProjects();
      setItems(res.items || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const loadTemplateOptions = useCallback(async () => {
    setTemplateLoading(true);
    try {
      const templates = await fetchChannel1Templates();
      setActiveTemplates(templates);
      return templates;
    } finally {
      setTemplateLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTemplateOptions().catch(() => message.error('模板列表加载失败'));
  }, [loadTemplateOptions]);

  const openCreate = async () => {
    setEditing(null);
    form.resetFields();
    form.setFieldValue('config_json', '{\n  \n}');
    const templates = activeTemplates.length > 0 ? activeTemplates : await loadTemplateOptions();
    setSelectedTemplateIds(templates.map((t) => t.template_id));
    setModalOpen(true);
  };

  const openEdit = async (project: Project) => {
    setEditing(project);
    if (activeTemplates.length === 0) {
      await loadTemplateOptions();
    }
    const selected = await fetchProjectTemplates(project.id, true);
    setSelectedTemplateIds(selected.map((t) => t.template_id).filter(Boolean));
    form.setFieldsValue({
      name: project.name,
      business_line: project.business_line,
      country: project.country,
      product: project.product,
      description: project.description,
      config_json: JSON.stringify(project.config || {}, null, 2),
    });
    setModalOpen(true);
  };

  const handleSubmit = async (values: any) => {
    try {
      const config = parseConfig(values.config_json);
      const payload = {
        name: values.name,
        business_line: values.business_line || '',
        country: values.country || '',
        product: values.product || '',
        description: values.description || '',
        config,
      };

      if (editing) {
        await updateProject(editing.id, payload);
        await setProjectTemplateSelection(editing.id, selectedTemplateIds);
        message.success('项目已更新');
      } else {
        await createProject({ ...payload, template_ids: selectedTemplateIds });
        message.success('项目已创建');
      }

      setModalOpen(false);
      form.resetFields();
      await load();
      await loadProjects();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '保存失败');
    }
  };

  const handleDelete = async (project: Project) => {
    try {
      await deleteProject(project.id);
      message.success('项目已标记删除');
      await load();
      await loadProjects();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '删除失败');
    }
  };

  const columns: ColumnsType<Project> = [
    {
      title: '项目',
      dataIndex: 'name',
      render: (name: string, row) => (
        <Space size={6}>
          <span>{name}</span>
          {row.is_default && <Tag color="blue">默认</Tag>}
          {currentProject?.id === row.id && <Tag color="green">当前</Tag>}
        </Space>
      ),
    },
    { title: '业务线', dataIndex: 'business_line', width: 150 },
    { title: '国家/地区', dataIndex: 'country', width: 110 },
    { title: '产品', dataIndex: 'product', width: 150 },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (status: string) => <Tag color={status === 'active' ? 'success' : 'default'}>{status}</Tag>,
    },
    {
      title: '配置',
      dataIndex: 'config',
      width: 120,
      render: (config: Record<string, unknown>) => {
        const count = config ? Object.keys(config).length : 0;
        return count > 0 ? <Tag>{count} 项</Tag> : '-';
      },
    },
    {
      title: '操作',
      width: 150,
      render: (_, row) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(row)} />
          <Popconfirm
            title="标记删除项目"
            description={row.is_default ? '默认项目不能删除' : `确认将「${row.name}」标记为删除？`}
            okText="删除"
            cancelText="取消"
            disabled={row.is_default}
            onConfirm={() => handleDelete(row)}
          >
            <Button size="small" danger disabled={row.is_default} icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Card
        title="项目管理"
        extra={(
          <Space>
            <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建项目</Button>
          </Space>
        )}
      >
        <Table
          rowKey="id"
          size="small"
          loading={loading}
          columns={columns}
          dataSource={items}
          pagination={false}
        />
      </Card>

      <Modal
        title={editing ? '编辑项目' : '新建项目'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        okText="保存"
        cancelText="取消"
        width={720}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="name" label="项目名称" rules={[{ required: true, message: '请输入项目名称' }]}>
            <Input />
          </Form.Item>
          <Space style={{ display: 'flex' }} align="start">
            <Form.Item name="business_line" label="业务线" style={{ width: 210 }}>
              <Input placeholder="印尼现金贷" />
            </Form.Item>
            <Form.Item name="country" label="国家/地区" style={{ width: 160 }}>
              <Input placeholder="INDO" />
            </Form.Item>
            <Form.Item name="product" label="产品" style={{ width: 210 }}>
              <Input placeholder="短期现金贷" />
            </Form.Item>
          </Space>
          <Form.Item name="description" label="说明">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item
            name="config_json"
            label="业务策略配置"
            extra="用于记录项目级策略参数，例如首贷客群、评估阈值、样本范围等。"
          >
            <Input.TextArea rows={8} spellCheck={false} style={{ fontFamily: 'Menlo, Consolas, monospace' }} />
          </Form.Item>
          <Form.Item
            label={(
              <Space>
                <span>启用模板</span>
                <Checkbox
                  checked={allTemplatesSelected}
                  indeterminate={templatesPartiallySelected}
                  disabled={templateLoading || activeTemplateIds.length === 0}
                  onChange={(event) => {
                    setSelectedTemplateIds(event.target.checked ? activeTemplateIds : []);
                  }}
                >
                  全选
                </Checkbox>
              </Space>
            )}
            extra="选择当前项目允许使用的数据加工模板，决定生产任务可调用哪些加工方式。"
          >
            <Checkbox.Group
              value={selectedTemplateIds}
              onChange={(values) => setSelectedTemplateIds(values.map(String))}
              style={{ width: '100%' }}
              disabled={templateLoading}
            >
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 8 }}>
                {activeTemplates.map((tmpl) => (
                  <Checkbox key={tmpl.template_id} value={tmpl.template_id}>
                    {tmpl.template_id} {tmpl.template_name_cn || tmpl.template_name}
                  </Checkbox>
                ))}
              </div>
            </Checkbox.Group>
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

export default Projects;
