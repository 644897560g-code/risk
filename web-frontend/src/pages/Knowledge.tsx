import React, { useEffect, useState, useCallback } from 'react';
import {
  Table, Button, Upload, message, Typography, Space, Tag, Popconfirm, Input, Select,
  Card, Row, Col, Statistic,
} from 'antd';
import {
  UploadOutlined, DeleteOutlined, FileTextOutlined, SearchOutlined,
  EyeOutlined,
} from '@ant-design/icons';
import type { UploadFile } from 'antd/es/upload/interface';
import {
  fetchKnowledgeList,
  uploadKnowledge,
  deleteKnowledge,
  fetchKnowledgeStats,
  updateKnowledgeTags,
  type KnowledgeItem,
} from '@/services/api';
import type { KnowledgeStats as KnowledgeStatsType } from '@/types/knowledge';
import KnowledgePreview from '@/components/KnowledgePreview';

const { Title } = Typography;

const categoryConfig: Record<string, { label: string; color: string }> = {
  doc: { label: '文档', color: 'blue' },
  excel: { label: '表格', color: 'green' },
  code: { label: '代码', color: 'purple' },
  other: { label: '其他', color: 'default' },
};

const formatSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const Knowledge: React.FC = () => {
  const [items, setItems] = useState<KnowledgeItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>(undefined);
  const [stats, setStats] = useState<KnowledgeStatsType | null>(null);

  // Preview state
  const [previewFilename, setPreviewFilename] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);

  const loadList = useCallback(async () => {
    setLoading(true);
    try {
      const list = await fetchKnowledgeList(categoryFilter);
      setItems(list);
    } catch {
      message.error('加载知识列表失败');
    } finally {
      setLoading(false);
    }
  }, [categoryFilter]);

  const loadStats = useCallback(async () => {
    try {
      setStats(await fetchKnowledgeStats());
    } catch {
      // silent
    }
  }, []);

  useEffect(() => {
    loadList();
    loadStats();
  }, [loadList, loadStats]);

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      await uploadKnowledge(file);
      message.success(`文件 ${file.name} 上传成功`);
      await loadList();
      await loadStats();
    } catch {
      message.error('上传失败');
    } finally {
      setUploading(false);
    }
    return false;
  };

  const handleDelete = async (filename: string) => {
    try {
      await deleteKnowledge(filename);
      message.success(`已删除 ${filename}`);
      await loadList();
      await loadStats();
    } catch {
      message.error('删除失败');
    }
  };

  const handlePreview = (filename: string) => {
    setPreviewFilename(filename);
    setPreviewOpen(true);
  };

  const handleAddTag = async (filename: string, tag: string) => {
    const item = items.find((i) => i.filename === filename);
    if (!item) return;
    const currentTags = item.tags || [];
    if (currentTags.includes(tag)) return;
    try {
      await updateKnowledgeTags(filename, [...currentTags, tag]);
      await loadList();
    } catch {
      message.error('添加标签失败');
    }
  };

  const handleRemoveTag = async (filename: string, tag: string) => {
    const item = items.find((i) => i.filename === filename);
    if (!item) return;
    const currentTags = item.tags || [];
    try {
      await updateKnowledgeTags(filename, currentTags.filter((t) => t !== tag));
      await loadList();
    } catch {
      message.error('删除标签失败');
    }
  };

  // Filter by search text client-side (already filtered by category on server)
  const filteredItems = searchText
    ? items.filter((item) => item.filename.toLowerCase().includes(searchText.toLowerCase()))
    : items;

  const columns = [
    {
      title: '文件名',
      dataIndex: 'filename',
      key: 'filename',
      render: (name: string) => (
        <Button type="link" style={{ padding: 0 }} onClick={() => handlePreview(name)}>
          <Space>
            <FileTextOutlined />
            {name}
          </Space>
        </Button>
      ),
    },
    {
      title: '类型',
      dataIndex: 'category',
      key: 'category',
      width: 80,
      render: (cat: string) => {
        const info = categoryConfig[cat] || categoryConfig.other;
        return <Tag color={info.color}>{info.label}</Tag>;
      },
    },
    {
      title: '预览',
      key: 'preview',
      width: 80,
      render: (_: unknown, record: KnowledgeItem) => (
        <Button type="link" size="small" icon={<EyeOutlined />}
          onClick={() => handlePreview(record.filename)}>
          预览
        </Button>
      ),
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      width: 200,
      render: (tags: string[] | undefined, record: KnowledgeItem) => (
        <Space wrap size={4}>
          {(tags || []).map((tag) => (
            <Tag
              key={tag}
              closable
              onClose={() => handleRemoveTag(record.filename, tag)}
              style={{ margin: 0 }}
            >
              {tag}
            </Tag>
          ))}
          <Tag
            style={{ background: '#fff', borderStyle: 'dashed', cursor: 'pointer', margin: 0 }}
            onClick={() => {
              const tag = prompt('输入标签名称:');
              if (tag?.trim()) handleAddTag(record.filename, tag.trim());
            }}
          >
            + 标签
          </Tag>
        </Space>
      ),
    },
    {
      title: '大小',
      dataIndex: 'size',
      key: 'size',
      width: 100,
      render: (size: number) => formatSize(size),
    },
    {
      title: '上传时间',
      dataIndex: 'uploaded_at',
      key: 'uploaded_at',
      width: 180,
      render: (t: string) => (t ? new Date(t).toLocaleString('zh-CN') : '-'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 80,
      render: (_: unknown, record: KnowledgeItem) => (
        <Popconfirm
          title={`确认删除 ${record.filename}？`}
          onConfirm={() => handleDelete(record.filename)}
        >
          <Button type="link" danger icon={<DeleteOutlined />} size="small" />
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      {/* Stats cards */}
      {stats && (
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Card size="small">
              <Statistic title="文件总数" value={stats.total_files} suffix="个" />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <Statistic title="总大小" value={formatSize(stats.total_size)} />
            </Card>
          </Col>
          {Object.entries(stats.by_category).map(([cat, info]) => (
            <Col span={4} key={cat}>
              <Card size="small">
                <Statistic
                  title={(categoryConfig[cat] || categoryConfig.other).label}
                  value={info.count}
                  suffix="个"
                />
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {/* Search + Filter + Upload bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
          gap: 12,
        }}
      >
        <Space>
          <Input.Search
            placeholder="搜索文件名..."
            allowClear
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            onSearch={(v) => setSearchText(v)}
            style={{ width: 240 }}
            prefix={<SearchOutlined />}
          />
          <Select
            placeholder="分类筛选"
            allowClear
            style={{ width: 130 }}
            value={categoryFilter}
            onChange={(v) => setCategoryFilter(v)}
            options={[
              { value: 'doc', label: '文档' },
              { value: 'excel', label: '表格' },
              { value: 'code', label: '代码' },
              { value: 'other', label: '其他' },
            ]}
          />
        </Space>
        <Upload
          beforeUpload={handleUpload}
          showUploadList={false}
          accept=".txt,.md,.json,.csv,.xlsx,.xls,.py,.sql,.yaml,.yml,.pdf,.doc,.docx"
        >
          <Button type="primary" icon={<UploadOutlined />} loading={uploading}>
            上传文件
          </Button>
        </Upload>
      </div>

      {/* File table */}
      <Table
        dataSource={filteredItems}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 20, showSizeChanger: false }}
        locale={{ emptyText: '暂无知识文件' }}
      />

      {/* Preview drawer */}
      <KnowledgePreview
        filename={previewFilename}
        open={previewOpen}
        onClose={() => { setPreviewOpen(false); setPreviewFilename(null); }}
      />
    </div>
  );
};

export default Knowledge;
