# Web开发计划

> **开始时间**: 2026-04-25
> **目标**: 6周内完成前后端分离的Web应用开发

---

## 技术栈

### 前端
- React 18 + TypeScript
- Ant Design (UI组件)
- ECharts (数据可视化)
- Axios (HTTP请求)
- React Router (路由)
- Zustand (状态管理)

### 后端
- FastAPI (API框架)
- SQLite (任务状态存储)
- Celery (异步任务)
- Redis (缓存)
- qwen3.6-plus (LLM)

---

## 第一阶段：FastAPI后端基础（Week 1）

**状态**: ⏳ 待开始

### 1.1 项目结构

- [ ] `backend/`
  - [ ] `app/`
    - [ ] `__init__.py` - 应用工厂
    - [ ] `main.py` - FastAPI入口
    - [ ] `config.py` - 配置管理
    - [ ] `database.py` - 数据库连接
  - [ ] `routers/`
    - [ ] `__init__.py`
    - [ ] `tasks.py` - 任务API
    - [ ] `agents.py` - Agent API
    - [ ] `data.py` - 数据API
  - [ ] `models/`
    - [ ] `__init__.py`
    - [ ] `task.py` - 任务模型
    - [ ] `feature.py` - 特征模型
  - [ ] `schemas/`
    - [ ] `__init__.py`
    - [ ] `task.py` - Pydantic Schema
    - [ ] `agent.py`
  - [ ] `services/`
    - [ ] `__init__.py`
    - [ ] `task_service.py` - 任务服务
    - [ ] `agent_service.py` - Agent服务
  - [ ] `celery_tasks/`
    - [ ] `__init__.py`
    - [ ] `celery_app.py` - Celery配置
    - [ ] `agent_tasks.py` - Agent异步任务
  - [ ] `utils/`
    - [ ] `__init__.py`
    - [ ] `file_utils.py` - 文件工具
    - [ ] `json_utils.py` - JSON工具

### 1.2 数据库设计

- [ ] SQLite初始化
- [ ] 创建tasks表
- [ ] 创建feature_metrics表
- [ ] 创建索引

### 1.3 核心API开发

- [ ] POST /api/tasks - 创建任务
- [ ] GET /api/tasks - 任务列表
- [ ] GET /api/tasks/{id} - 任务详情
- [ ] GET /api/tasks/{id}/result - 任务结果
- [ ] POST /api/tasks/{id}/cancel - 取消任务
- [ ] POST /api/tasks/{id}/retry - 重试任务
- [ ] GET /api/agents/status - Agent状态

### 1.4 Celery集成

- [ ] Redis配置
- [ ] Celery Worker设置
- [ ] run_data_analysis_task任务
- [ ] run_feature_design_task任务
- [ ] 任务状态更新机制

**交付物**:
- `backend/` 完整项目结构
- FastAPI应用可运行
- API文档（/docs）
- SQLite数据库

---

## 第二阶段：React前端基础（Week 2）

**状态**: ⏳ 待开始

### 2.1 项目初始化

- [ ] 使用Vite创建React项目
- [ ] TypeScript配置
- [ ] ESLint + Prettier
- [ ] Tailwind CSS配置

### 2.2 项目结构

- [ ] `web-frontend/`
  - [ ] `src/`
    - [ ] `components/` - 可复用组件
    - [ ] `pages/` - 页面组件
    - [ ] `services/` - API服务
    - [ ] `hooks/` - 自定义Hooks
    - [ ] `store/` - 状态管理
    - [ ] `types/` - TypeScript类型
    - [ ] `styles/` - 全局样式
    - [ ] `App.tsx`
    - [ ] `main.tsx`
  - [ ] `public/`
  - [ ] `package.json`

### 2.3 核心组件开发

- [ ] Layout组件（顶部导航 + 侧边栏）
- [ ] AgentCard组件（Agent状态卡片）
- [ ] TaskTable组件（任务列表）
- [ ] ProgressBar组件（进度条）
- [ ] JsonViewer组件（JSON查看器）
- [ ] StatusTag组件（状态标签）

### 2.4 路由配置

- [ ] React Router配置
- [ ] /dashboard - Dashboard首页
- [ ] /tasks - 任务管理
- [ ] /agent/data-analysis - 数据分析Agent
- [ ] /agent/feature-design - 特征设计Agent
- [ ] /agent/feature-evaluation - 特征评估

### 2.5 API服务封装

- [ ] Axios配置
- [ ] Task API服务
- [ ] Agent API服务
- [ ] 错误处理
- [ ] 请求拦截器

**交付物**:
- `web-frontend/` 可运行项目
- 基础页面布局
- 路由切换正常

---

## 第三阶段：Dashboard和任务管理（Week 3）

**状态**: ⏳ 待开始

### 3.1 Dashboard页面

- [ ] Agent状态卡片网格（2x3）
- [ ] 实时任务状态（轮询或WebSocket）
- [ ] 最近任务列表
- [ ] 任务趋势图表（ECharts）
- [ ] Agent使用分布饼图

### 3.2 任务管理页面

- [ ] 任务列表表格
- [ ] 筛选器（Agent、状态、日期）
- [ ] 分页功能
- [ ] 任务详情弹窗
- [ ] 任务日志实时显示
- [ ] 重新运行任务

### 3.3 状态管理

- [ ] Zustand配置
- [ ] TaskStore（任务状态）
- [ ] AgentStore（Agent状态）
- [ ] 持久化策略

### 3.4 实时通信

- [ ] WebSocket连接（可选）
- [ ] 任务进度实时更新
- [ ] Agent状态实时推送

**交付物**:
- Dashboard页面完整
- 任务管理页面完整
- 实时状态更新正常

---

## 第四阶段：Agent页面开发（Week 4-5）

**状态**: ⏳ 待开始

### 4.1 数据分析Agent页面

- [ ] 配置面板（样本数、文件选择）
- [ ] [开始分析]按钮
- [ ] 执行进度条
- [ ] 步骤状态指示器
- [ ] 结果预览（JSON查看器）
- [ ] 结果下载
- [ ] 下一步跳转

### 4.2 特征设计Agent页面

- [ ] 输入文件选择（知识库、FDC清单）
- [ ] [开始设计]按钮
- [ ] 执行进度
- [ ] 设计结果表格
- [ ] 特征详情弹窗
- [ ] 下载设计文档

### 4.3 特征工程Agent页面

- [ ] 输入：特征设计文档
- [ ] 代码生成进度
- [ ] 代码预览
- [ ] 语法检查结果
- [ ] 下载Python代码

### 4.4 特征审核Agent页面

- [ ] 输入：特征代码
- [ ] 审核进度
- [ ] 审核结果（通过/不通过）
- [ ] 错误详情
- [ ] 循环修正按钮

### 4.5 特征评估Agent页面

- [ ] 输入：审核通过的代码 + 样本数据
- [ ] 评估配置（数据集划分比例）
- [ ] 计算进度
- [ ] IV分布图
- [ ] PSI分布图
- [ ] 通过率统计
- [ ] [下载报告]按钮

### 4.6 特征部署Agent页面

- [ ] 输入：通过的特征代码
- [ ] 打包进度
- [ ] 部署包预览
- [ ] 下载部署包
- [ ] 部署说明

**交付物**:
- 6个Agent页面全部完成
- 页面间跳转流畅
- API对接完成

---

## 第五阶段：可视化增强（Week 5）

**状态**: ⏳ 待开始

### 5.1 数据可视化

- [ ] Dashboard图表优化
- [ ] 任务完成度仪表盘
- [ ] Agent性能对比图
- [ ] 历史趋势分析

### 5.2 特征评估可视化

- [ ] IV分布柱状图
- [ ] PSI分布热力图
- [ ] 覆盖率饼图
- [ ] 筛选条件雷达图

### 5.3 知识库可视化

- [ ] 用户画像图表
- [ ] 应用分布图
- [ ] FDC数据统计
- [ ] 风险规则列表

**交付物**:
- ECharts图表集成
- 数据可视化增强
- 交互体验优化

---

## 第六阶段：测试与优化（Week 6）

**状态**: ⏳ 待开始

### 6.1 后端测试

- [ ] API接口单元测试
- [ ] 集成测试
- [ ] 数据库测试
- [ ] Celery任务测试

### 6.2 前端测试

- [ ] 组件单元测试
- [ ] 页面E2E测试
- [ ] API Mock测试

### 6.3 性能优化

- [ ] 后端API响应优化
- [ ] 前端懒加载
- [ ] 缓存策略
- [ ] WebSocket优化

### 6.4 部署配置

- [ ] Docker配置
- [ ] docker-compose.yml
- [ ] 环境变量管理
- [ ] 生产环境配置

**交付物**:
- 测试覆盖率 > 80%
- 性能达标
- Docker镜像

---

## 里程碑汇总

| Week | 阶段 | 状态 | 交付物 |
|------|------|------|--------|
| 1 | FastAPI后端基础 | ⏳ | 后端API + Celery |
| 2 | React前端基础 | ⏳ | React项目框架 |
| 3 | Dashboard+任务管理 | ⏳ | 首页+任务页 |
| 4-5 | Agent页面开发 | ⏳ | 6个Agent页面 |
| 5 | 可视化增强 | ⏳ | ECharts图表 |
| 6 | 测试与优化 | ⏳ | 完整系统 |

---

## 关键约束

1. **前后端分离**: 前端通过REST API与后端通信
2. **异步任务**: 所有Agent任务通过Celery异步执行
3. **实时性**: 任务进度需要实时更新到前端
4. **可扩展**: 支持未来新增Agent
5. **数据安全**: 注意API权限控制

---

## 与Agent开发的协调

- **Agent开发优先**: 确保Agent核心逻辑完成后再开发对应前端
- **API先行**: 先定义好API接口，前后端并行开发
- **Mock数据**: 前端开发时使用Mock数据
- **渐进式集成**: Agent完成一个就集成一个
