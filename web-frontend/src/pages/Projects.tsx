import React, { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Card,
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
  fetchProjects,
  updateProject,
} from '@/services/api';
import type { Project } from '@/types/project';
import { useProjectStore } from '@/store/projectStore';

const Projects: React.FC = () => {
  const [items, setItems] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Project | null>(null);
  const [form] = Form.useForm();
  const { currentProject, loadProjects } = useProjectStore();

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

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    setModalOpen(true);
  };

  const openEdit = (project: Project) => {
    setEditing(project);
    form.setFieldsValue({
      name: project.name,
      business_line: project.business_line,
      country: project.country,
      product: project.product,
      description: project.description,
    });
    setModalOpen(true);
  };

  const handleSubmit = async (values: any) => {
    try {
      const payload = {
        name: values.name,
        business_line: values.business_line || '',
        country: values.country || '',
        product: values.product || '',
        description: values.description || '',
        config: editing?.config || {},
      };

      if (editing) {
        await updateProject(editing.id, payload);
        message.success('项目已更新');
      } else {
        await createProject(payload);
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
    { title: '国家/地区', dataIndex: 'country', width: 110 },
    { title: '产品', dataIndex: 'product', width: 150 },
    { title: '业务线', dataIndex: 'business_line', width: 150 },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (status: string) => <Tag color={status === 'active' ? 'success' : 'default'}>{status}</Tag>,
    },
    {
      title: '任务数',
      width: 90,
      render: (_, row) => row.id === currentProject?.id ? <Tag color="blue">3</Tag> : <Tag>1</Tag>,
    },
    {
      title: '最新版本',
      width: 110,
      render: (_, row) => row.id === currentProject?.id ? <Tag color="geekblue">v14</Tag> : '-',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 170,
      render: (time: string) => time ? new Date(time).toLocaleString('zh-CN') : '-',
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
        title="项目列表"
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
        </Form>
      </Modal>
    </>
  );
};

export default Projects;
