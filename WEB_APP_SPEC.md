# Web应用Spec文档

**项目名称**: 印尼风险特征挖掘Agent系统 - Web应用
**版本**: 1.0
**日期**: 2026-05-04
**目标**: 6周内完成前后端分离的Web应用，实现Agent流程的可视化控制和结果展示

---

## 一、核心目标

### 1.1 业务目标
- 用户可以通过Web界面**配置参数、触发Agent流程**
- 实时**监控Agent执行进度**
- **可视化展示**各Agent的输出结果
- 支持**多任务管理**和历史记录查看

### 1.2 技术目标
- **前后端分离**: React 18 + FastAPI
- **RESTful API**: 标准化接口设计
- **实时通信**: WebSocket推送进度和日志
- **任务隔离**: 支持多用户并发使用
- **可扩展性**: 预留商业化功能接口

---

## 二、功能需求

### 2.1 用户角色

| 角色 | 权限 | 使用场景 |
|------|------|----------|
| **管理员** | 全部功能 | 风控团队内部使用，配置系统、创建任务 |
| **普通用户** | 只读+创建任务 | 查看结果、触发新特征挖掘 |

### 2.2 核心功能模块

#### 模块A: 主Agent控制面板（核心入口）

**功能描述**:
用户与系统的主要交互界面，通过对话式UI引导用户完成特征挖掘流程

**用户流程**:
```
1. 用户访问首页
   ↓
2. 系统展示对话界面和参数配置
   ↓
3. 用户输入："我要生成新的风控特征"
   ↓
4. 系统回复数据格式要求（展示样例）
   ↓
5. 用户上传文件：
   - 短链数据文件（TXT格式）
   - Label数据Excel（XLSX格式）
   ↓
6. 用户配置参数：
   - 目标特征数量（默认20，可修改）
   - OOT比例（默认0.2）
   - 是否启用审核人工确认
   ↓
7. 点击"开始执行"
   ↓
8. 系统实时显示进度和日志
   ↓
9. 完成后展示结果报告和特征列表
```

**前端组件**:
- 对话式UI（类似聊天界面）
- 文件上传组件（支持拖拽）
- 参数配置表单
- 进度条和日志展示
- 结果报告卡片

**后端API**:
```
POST   /api/v1/tasks              # 创建任务
POST   /api/v1/tasks/{id}/start   # 启动执行
GET    /api/v1/tasks/{id}/progress # 查询进度
WS     /api/v1/tasks/{id}/logs    # 实时日志流
```

---

#### 模块B: 数据分析Agent可视化

**功能描述**:
展示数据分析Agent的输出结果，包括样本统计、APP类别分布、FDC数据概览

**展示内容**:
- **统计卡片**:
  - 总样本数
  - 好客户数 / 坏客户数
  - 总APP数 / 未知APP数
  - FDC信贷记录总数

- **图表**:
  - APP类别分布（饼图/柱状图）
  - 高风险APP分类（柱状图）
  - 样本逾期率（环形图）
  - FDC数据覆盖情况（表格）

- **交互**:
  - 点击类别查看该类别下的APP列表
  - 导出统计报告

**前端组件**:
- Ant Design Statistic Cards
- ECharts饼图/柱状图
- Data Table（可搜索、过滤）

**后端API**:
```
GET /api/v1/tasks/{id}/analysis/summary    # 统计摘要
GET /api/v1/tasks/{id}/analysis/apps       # APP分类数据
GET /api/v1/tasks/{id}/analysis/fdc        # FDC数据概况
```

---

#### 模块C: 特征设计Agent可视化

**功能描述**:
展示特征设计Agent输出的特征列表，支持搜索、筛选和交互

**展示内容**:
- **特征列表表格**:
  | 列 | 说明 |
  |----|------|
  | 特征名称 | 可点击展开详情 |
  | 业务类别 | 赌博/借贷/安装列表等 |
  | 数据来源 | Base/FDC/Applist/AI生成 |
  | 业务解释 | 简要说明 |
  | 操作 | 查看详情、导出 |

- **特征详情面板**（点击展开）:
  - 完整业务解释
  - 设计理由
  - 计算公式（伪代码）
  - 相关APP/字段列表

- **统计图表**:
  - 特征类别分布（饼图）
  - 数据来源分布（柱状图）

**交互功能**:
- 搜索特征（按名称/解释）
- 筛选类别
- 导出特征设计文档（Excel/CSV）
- 手动调整特征列表（添加/删除）

**前端组件**:
- Ant Design Table（支持展开、搜索）
- 模态框（详情展示）
- ECharts饼图/柱状图

**后端API**:
```
GET /api/v1/tasks/{id}/design/features      # 特征列表
GET /api/v1/tasks/{id}/design/stats         # 统计信息
GET /api/v1/tasks/{id}/design/export        # 导出文档
```

---

#### 模块D: 特征工程Agent可视化

**功能描述**:
展示特征工程Agent生成的代码，提供代码预览和统计信息

**展示内容**:
- **代码预览**:
  - 语法高亮（Python）
  - 行号显示
  - 可滚动/缩放
  - 关键函数折叠/展开

- **代码统计**:
  - 总行数
  - 特征计算方法数
  - 依赖库列表
  - 代码复杂度（可选）

- **逻辑可视化**（可选）:
  - 流程图（简化版）
  - 函数调用关系图

- **交互**:
  - 下载代码文件
  - 查看代码差异（迭代时）
  - 手动编辑（高级用户，可选）

**前端组件**:
- Monaco Editor / React-CodeMirror（代码编辑器）
- Ant Design Card（统计卡片）

**后端API**:
```
GET /api/v1/tasks/{id}/engineering/code      # 获取代码
GET /api/v1/tasks/{id}/engineering/stats     # 代码统计
GET /api/v1/tasks/{id}/engineering/download  # 下载
```

---

#### 模块E: 特征审核Agent可视化

**功能描述**:
展示特征审核Agent的审核结果，需要人工确认

**展示内容**:
- **审核报告卡片**:
  - ✅ 语法检查通过
  - ✅ 逻辑检查通过
  - ✅ 防穿越检查通过
  - ⚠️ 发现的问题

- **审核意见文本**:
  显示审核Agent的详细意见

- **操作按钮**（需人工确认时）:
  - [ 确认通过 ] - 继续执行
  - [ 打回修改 ] - 触发重试（最多3次）

- **审核历史**（多次迭代）:
  - 第1次审核: 未通过 - 发现2个问题
  - 第2次审核: 通过 - 人工确认

**前端组件**:
- Ant Design Result Component
- Timeline（审核历史）
- Button Group（操作按钮）

**后端API**:
```
GET    /api/v1/tasks/{id}/review/result    # 获取审核结果
POST   /api/v1/tasks/{id}/review/approve   # 确认通过
POST   /api/v1/tasks/{id}/review/reject    # 打回修改
GET    /api/v1/tasks/{id}/review/history   # 审核历史
```

---

#### 模块F: 特征评估Agent可视化 ⭐ 重点

**功能描述**:
展示特征评估Agent的输出结果，包括IV/PSI等指标和HTML报告

**展示内容**:
- **关键指标卡片**:
  - IV分布（直方图，标注 >= 0.02的特征数）
  - PSI稳定性（散点图，标注 <= 0.25的特征数）
  - 覆盖率（饼图，标注 > 5%的特征数）
  - 总特征数 / 通过筛选数 / 通过率

- **特征排行榜表格**:
  | 列 | 说明 |
  |----|------|
  | 特征名称 | 可点击查看详情 |
  | IV值 | 排序（降序）|
  | PSI | 颜色标识（红/绿）|
  | 覆盖率 | 百分比 |
  | 状态 | ✅ 通过 / ❌ 未通过 |
  | 操作 | 查看指标详情 |

- **HTML报告嵌入**:
  直接嵌入Agent生成的HTML报告（使用iframe）

- **交互**:
  - 点击特征查看详细指标
  - 导出评估报告（HTML/PDF）
  - 筛选通过/未通过的特征
  - 下载通过筛选的特征列表

**前端组件**:
- ECharts直方图/散点图/饼图
- Ant Design Table（排序、筛选）
- iframe（HTML报告嵌入）

**后端API**:
```
GET /api/v1/tasks/{id}/evaluation/metrics     # 关键指标
GET /api/v1/tasks/{id}/evaluation/features    # 特征列表
GET /api/v1/tasks/{id}/evaluation/report      # HTML报告
GET /api/v1/tasks/{id}/evaluation/export      # 导出
```

---

#### 模块G: 特征部署Agent可视化

**功能描述**:
展示特征部署Agent的部署包信息，支持部署管理和API测试

**展示内容**:
- **版本列表表格**:
  | 列 | 说明 |
  |----|------|
  | 版本号 | v1, v2, v3... |
  | 创建时间 | ISO格式 |
  | 特征数量 | 点击查看详情 |
  | 状态 | 当前 / 历史 |
  | 操作 | 部署、回滚、查看 |

- **API文档预览**:
  - 单样本计算API
  - 批量计算API
  - 请求/响应示例

- **快速测试工具**:
  类似Postman的简单测试界面
  - 输入测试数据
  - 发送请求
  - 查看响应

- **统计信息**:
  - 部署次数
  - API调用次数（如有监控）
  - 当前版本

**交互**:
- [ 部署新版本 ] - 触发部署
- [ 回滚 ] - 回滚到指定版本
- [ 测试API ] - 打开测试工具

**前端组件**:
- Ant Design Table
- Collapse（API文档折叠）
- Form（测试工具）

**后端API**:
```
GET    /api/v1/tasks/{id}/deployment/versions  # 版本列表
POST   /api/v1/tasks/{id}/deployment/deploy    # 部署
POST   /api/v1/tasks/{id}/deployment/rollback  # 回滚
GET    /api/v1/tasks/{id}/deployment/api-docs  # API文档
POST   /api/v1/tasks/{id}/deployment/test      # API测试
```

---

#### 模块H: 任务管理面板

**功能描述**:
管理多次特征挖掘任务，查看历史和状态

**展示内容**:
- **任务列表**:
  | 列 | 说明 |
  |----|------|
  | 任务ID | 可点击查看详情 |
  | 任务名称 | 用户自定义 |
  | 状态 | 待执行/进行中/已完成/失败 |
  | 特征数 | 完成后的特征数量 |
  | 创建时间 | 相对时间（2小时前）|
  | 操作 | 查看/停止/删除 |

- **筛选/搜索**:
  - 按状态筛选
  - 按时间范围筛选
  - 按任务名称搜索

- **批量操作**:
  - 批量删除
  - 批量导出

**前端组件**:
- Ant Design Table
- Search / Filter组件
- Modal（任务详情）

**后端API**:
```
GET    /api/v1/tasks              # 任务列表
GET    /api/v1/tasks/{id}         # 任务详情
DELETE /api/v1/tasks/{id}         # 删除任务
POST   /api/v1/tasks/{id}/stop    # 停止任务
```

---

## 三、技术架构

### 3.1 前端技术栈

```json
{
  "框架": "React 18.2+",
  "语言": "TypeScript 5.0+",
  "UI组件": "Ant Design 5.0+",
  "图表": "ECharts 5.4+ + @ant-design/plots",
  "状态管理": "Zustand 4.4+",
  "路由": "React Router 6.0+",
  "HTTP请求": "Axios 1.4+",
  "WebSocket": "react-use-websocket 4.0+",
  "代码编辑器": "@monaco-editor/react",
  "构建工具": "Vite 4.4+"
}
```

### 3.2 后端技术栈

```python
# 核心框架
FastAPI 0.100+         # API框架
Pydantic 2.0+           # 数据验证
SQLAlchemy 2.0+         # ORM（可选）

# 异步任务
Celery 5.3+             # 任务队列
Redis 4.6+              # 消息代理

# 数据库
SQLite3                 # 任务状态存储
# 或 PostgreSQL 15+     # 生产环境推荐

# WebSocket
websockets 11.0+        # WebSocket支持

# 文件处理
python-multipart        # 文件上传
openpyxl 3.1+           # Excel处理
```

### 3.3 项目结构

```
web-app/
├── frontend/                # React前端
│   ├── src/
│   │   ├── components/      # 公共组件
│   │   │   ├── Layout/      # 布局组件
│   │   │   ├── FileUpload/  # 文件上传
│   │   │   ├── CodeViewer/  # 代码查看
│   │   │   └── TaskCard/    # 任务卡片
│   │   ├── pages/           # 页面组件
│   │   │   ├── Home/        # 首页（主Agent面板）
│   │   │   ├── TaskList/    # 任务列表
│   │   │   ├── TaskDetail/  # 任务详情
│   │   │   └── Settings/    # 设置
│   │   ├── hooks/           # 自定义Hooks
│   │   ├── store/           # Zustand状态
│   │   ├── api/             # API调用封装
│   │   ├── styles/          # 全局样式
│   │   └── App.tsx          # 根组件
│   ├── public/
│   ├── package.json
│   └── vite.config.ts
│
├── backend/                 # FastAPI后端
│   ├── app/
│   │   ├── api/             # API路由
│   │   │   ├── tasks.py     # 任务API
│   │   │   ├── agents.py    # Agent API
│   │   │   └── data.py      # 数据API
│   │   ├── models/          # 数据模型
│   │   │   ├── task.py      # 任务模型
│   │   │   └── agent.py     # Agent模型
│   │   ├── schemas/         # Pydantic Schema
│   │   │   ├── task.py      # 任务Schema
│   │   │   └── agent.py     # Agent Schema
│   │   ├── services/        # 业务逻辑
│   │   │   ├── task_service.py    # 任务服务
│   │   │   └── agent_service.py   # Agent服务
│   │   ├── workers/         # Celery任务
│   │   │   └── agent_worker.py    # Agent执行Worker
│   │   ├── websocket/       # WebSocket
│   │   │   └── logs.py      # 日志WebSocket
│   │   ├── database.py      # 数据库连接
│   │   ├── config.py        # 配置管理
│   │   └── main.py          # FastAPI入口
│   ├── requirements.txt
│   └── tests/               # 测试
│
└── README.md
```

---

## 四、API设计

### 4.1 通用响应格式

```json
{
  "code": 200,                // 状态码
  "message": "success",       // 消息
  "data": {},                 // 数据
  "timestamp": 1234567890     // 时间戳
}
```

### 4.2 错误响应

```json
{
  "code": 400,
  "message": "参数错误",
  "errors": [
    {
      "field": "feature_count",
      "message": "特征数量必须在1-100之间"
    }
  ]
}
```

### 4.3 主要API端点

已在各模块中列出，此处总结：

| API分类 | 端点数 | 说明 |
|---------|--------|------|
| 任务管理 | 8 | 创建、查询、删除、停止任务 |
| Agent控制 | 6 | 启动、暂停、恢复各Agent |
| 数据上传 | 3 | 上传短链、Label、格式指南 |
| 进度查询 | 2 | 进度、日志（WS）|
| 结果展示 | 18 | 6个Agent的结果API |
| 配置管理 | 2 | 获取、更新配置 |
| 部署管理 | 5 | 部署、回滚、测试 |
| **总计** | **44** | |

---

## 五、非功能需求

### 5.1 性能要求
- API响应时间: < 500ms（95%）
- 页面加载时间: < 3s
- 并发用户: 10人同时使用
- 大数据支持: 支持10000+样本处理

### 5.2 可靠性
- 任务执行失败率: < 5%
- 数据丢失率: 0%
- 自动重试机制: Agent失败自动重试3次

### 5.3 安全性
- 文件上传验证（格式、大小限制）
- SQL注入/XSS防护
- API限流（防止滥用）
- 用户认证（可选，预留）

### 5.4 可扩展性
- 模块化设计，易于添加新Agent
- API版本控制
- 数据库可扩展（SQLite → PostgreSQL）

---

## 六、UI/UX设计原则

### 6.1 设计规范
- 遵循Ant Design设计规范
- 一致的配色方案
- 统一的图标系统（Ant Design Icons）
- 响应式设计（支持1024+屏幕）

### 6.2 交互原则
- 用户操作有明确反馈
- 长耗时任务显示进度
- 错误提示清晰友好
- 减少用户等待时间（异步执行）

### 6.3 可访问性
- 支持键盘操作
- 色盲友好的配色
- 清晰的字体大小
- Alt文本描述

---

## 七、开发计划

详见单独的`WEB_DETAILED_DEV_PLAN.md`，此处概要：

| 阶段 | 时间 | 主要任务 | 交付物 |
|------|------|----------|--------|
| 1 | Week 1 | FastAPI后端基础 | 完整API结构 |
| 2 | Week 2 | React前端基础 | 项目结构 |
| 3 | Week 3 | 主Agent控制面板 | 核心功能 |
| 4 | Week 4 | Agent结果可视化 | 6个Agent展示 |
| 5 | Week 5 | 实时交互优化 | WebSocket |
| 6 | Week 6 | 测试和优化 | 端到端测试 |

---

## 八、里程碑

| 里程碑 | 目标 | 验收标准 |
|--------|------|----------|
| M1: 后端API可用 | Week 2 | 所有API端点可访问 |
| M2: 前端框架就绪 | Week 3 | 页面路由、基本布局 |
| M3: 核心功能可用 | Week 4 | 主Agent面板可创建任务 |
| M4: 结果可视化完成 | Week 5 | 6个Agent结果可展示 |
| M5: 完整流程可用 | Week 6 | 端到端测试通过 |

---

## 九、风险与应对

### 9.1 技术风险
- **WebSocket稳定性**: 备选方案Polling
- **大数据性能**: 分页、懒加载
- **前端复杂度**: 分模块开发，MVP优先

### 9.2 业务风险
- **需求变更**: 预留可扩展性
- **数据格式不一致**: 严格验证+友好提示
- **Agent执行失败**: 错误处理+重试机制

---

## 十、后续规划

### Phase 2（商业化）
- 用户认证和权限管理
- API密钥管理（trial/pro/enterprise）
- 监控和日志
- 多租户支持

### Phase 3（增强）
- 特征市场（分享/下载）
- 自动报告生成
- 高级分析工具

---

**下一步**: 创建详细的`WEB_DETAILED_DEV_PLAN.md`开发计划，按阶段逐步实现。
