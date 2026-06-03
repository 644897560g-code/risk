# Web应用详细开发计划

**日期**: 2026-05-04
**总工期**: 6周（42天）
**目标**: 完成前后端分离的Web应用，实现完整的Agent流程可视化

---

## 阶段一：FastAPI后端基础（Week 1，第1-7天）

### 任务清单

#### Day 1: 项目初始化
- [ ] 创建后端项目结构
- [ ] 安装FastAPI依赖
- [ ] 配置项目基础设置
- [ ] 编写Hello World接口

**交付物**:
```
backend/
├── app/
│   ├── __init__.py
│   └── main.py          # FastAPI入口
├── requirements.txt
└── README.md
```

#### Day 2: 数据库设计
- [ ] 设计SQLite数据库表（任务、Agent执行记录）
- [ ] 创建ORM模型（SQLAlchemy）
- [ ] 数据库迁移脚本

**数据库表设计**:
```sql
-- 任务表
tasks (
    id INTEGER PK,
    name TEXT,
    status TEXT,              -- pending/running/completed/failed
    feature_count INTEGER,    -- 目标特征数量
    short_url_file TEXT,      -- 短链文件路径
    labels_file TEXT,         -- Label文件路径
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)

-- Agent执行记录表
agent_executions (
    id INTEGER PK,
    task_id INTEGER FK,
    agent_name TEXT,          -- data_analysis/design/engineering/review/evaluation/deployment
    status TEXT,              -- pending/running/completed/failed
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    output_file TEXT,         -- 输出文件路径
    error_message TEXT,
    step_order INTEGER        -- 执行顺序
)
```

#### Day 3: Pydantic Schema定义
- [ ] 定义任务相关的请求/响应Schema
- [ ] 定义Agent执行记录Schema
- [ ] 定义错误响应Schema

**关键Schema**:
```python
# 创建任务请求
class CreateTaskRequest(BaseModel):
    feature_count: int = 20
    oot_ratio: float = 0.2
    enable_human_review: bool = True

# 上传数据请求
class UploadDataRequest(BaseModel):
    short_url_file: UploadFile
    labels_file: UploadFile

# 任务响应
class TaskResponse(BaseModel):
    id: int
    name: str
    status: str
    feature_count: int
    created_at: datetime

# 进度响应
class ProgressResponse(BaseModel):
    task_id: int
    current_step: str
    progress: float  # 0-100
    status: str
```

#### Day 4-5: 任务管理API
- [ ] 创建任务API（POST /api/v1/tasks）
- [ ] 查询任务列表API（GET /api/v1/tasks）
- [ ] 查询任务详情API（GET /api/v1/tasks/{id}）
- [ ] 删除任务API（DELETE /api/v1/tasks/{id}）
- [ ] 停止任务API（POST /api/v1/tasks/{id}/stop）
- [ ] 查询进度API（GET /api/v1/tasks/{id}/progress）

**实现要点**:
- 任务状态机管理
- 统一的响应格式
- 错误处理中间件

#### Day 6: 数据上传API
- [ ] 上传短链文件API（POST /api/v1/data/short-urls）
- [ ] 上传Label Excel API（POST /api/v1/data/labels）
- [ ] 获取数据格式指南API（GET /api/v1/data/format-guide）

**实现要点**:
- 文件验证（格式、大小）
- 保存到指定目录
- 返回文件路径

#### Day 7: 集成现有Agent系统
- [ ] 创建Agent Worker封装类
- [ ] 实现异步任务执行（Celery/Thread）
- [ ] 实现进度更新机制

**关键实现**:
```python
class AgentExecutor:
    def execute_task(self, task_id: int):
        """执行完整Agent流程"""
        # 1. 加载数据
        # 2. 依次调用6个Agent
        # 3. 更新数据库状态
        # 4. 保存结果
```

**Week 1 交付物**:
- ✅ 完整的FastAPI项目结构
- ✅ SQLite数据库
- ✅ 8个核心API端点
- ✅ 任务执行框架

---

## 阶段二：React前端基础（Week 2，第8-14天）

### 任务清单

#### Day 8: 项目初始化
- [ ] 使用Vite创建React + TypeScript项目
- [ ] 安装依赖（Ant Design、Router、Axios等）
- [ ] 配置TypeScript（tsconfig.json）
- [ ] 配置Vite（vite.config.ts）

**依赖安装**:
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install antd @ant-design/icons
npm install react-router-dom
npm install axios
npm install zustand
npm install echarts @ant-design/plots
```

#### Day 9: 项目结构设计
- [ ] 创建目录结构（components/pages/hooks/store/api）
- [ ] 配置路由（App.tsx）
- [ ] 创建布局组件
- [ ] 配置全局样式

**目录结构**:
```
frontend/src/
├── components/        # 公共组件
├── pages/            # 页面组件
├── hooks/            # 自定义Hooks
├── store/            # Zustand状态
├── api/              # API调用
├── styles/           # 全局样式
└── App.tsx
```

#### Day 10: API客户端封装
- [ ] 封装Axios实例
- [ ] 实现请求/响应拦截器
- [ ] 封装所有API调用函数
- [ ] 实现错误处理统一逻辑

**关键代码**:
```typescript
// api/client.ts
import axios from 'axios'

export const apiClient = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

// api/tasks.ts
export const taskAPI = {
  list: () => apiClient.get('/tasks'),
  create: (data: CreateTaskRequest) => apiClient.post('/tasks', data),
  get: (id: number) => apiClient.get(`/tasks/${id}`),
  delete: (id: number) => apiClient.delete(`/tasks/${id}`),
  // ...
}
```

#### Day 11: 状态管理（Zustand）
- [ ] 设计全局状态Store
- [ ] 实现任务列表状态
- [ ] 实现当前任务状态
- [ ] 实现用户状态（可选）

**Store设计**:
```typescript
// store/taskStore.ts
import create from 'zustand'

interface TaskStore {
  tasks: Task[]
  currentTask: Task | null
  setTasks: (tasks: Task[]) => void
  addTask: (task: Task) => void
  updateTask: (id: number, updates: Partial<Task>) => void
  removeTask: (id: number) => void
}

export const useTaskStore = create<TaskStore>((set) => ({
  tasks: [],
  currentTask: null,
  setTasks: (tasks) => set({ tasks }),
  addTask: (task) => set((state) => ({ tasks: [...state.tasks, task] })),
  // ...
}))
```

#### Day 12: 布局组件
- [ ] 创建主布局（Header + Sider + Content）
- [ ] 创建导航菜单
- [ ] 实现路由切换
- [ ] 添加面包屑

#### Day 13: 任务列表页面
- [ ] 实现任务列表页面
- [ ] 实现任务卡片组件
- [ ] 实现筛选/搜索功能
- [ ] 实现创建任务模态框

**页面功能**:
- 任务列表展示
- 按状态筛选
- 搜索任务
- 创建新任务

#### Day 14: 任务详情页面（基础）
- [ ] 实现任务详情页面框架
- [ ] 实现Tab切换（6个Agent）
- [ ] 实现进度条组件
- [ ] 实现日志显示组件

**Week 2 交付物**:
- ✅ React项目结构
- ✅ 路由配置
- ✅ API封装
- ✅ 状态管理
- ✅ 基础页面

---

## 阶段三：主Agent控制面板（Week 3，第15-21天）

### 任务清单

#### Day 15: 对话式UI设计
- [ ] 设计对话界面布局
- [ ] 实现消息列表组件
- [ ] 实现用户输入组件
- [ ] 实现滚动自动滚动手势

**界面设计**:
```
┌──────────────────────────────────┐
│  系统: 请上传数据文件              │
│  用户: [短链文件.xlsx]            │
│  系统: 请配置参数                  │
│  用户: [特征数量: 20] [开始执行]   │
└──────────────────────────────────┘
```

#### Day 16: 文件上传组件
- [ ] 实现拖拽上传组件
- [ ] 实现文件验证（格式、大小）
- [ ] 实现上传进度条
- [ ] 实现文件预览

**关键功能**:
- 拖拽上传
- 文件类型验证
- 大小限制（< 100MB）
- 上传状态显示

#### Day 17: 参数配置表单
- [ ] 实现参数配置表单组件
- [ ] 实现表单验证
- [ ] 实现参数持久化（localStorage）

**表单字段**:
- 特征数量（InputNumber）
- OOT比例（InputNumber）
- 是否启用审核（Switch）

#### Day 18: 任务创建逻辑
- [ ] 实现"开始执行"按钮逻辑
- [ ] 实现API调用顺序（上传数据 → 创建任务 → 启动）
- [ ] 实现错误处理
- [ ] 实现成功提示

#### Day 19: 实时进度显示
- [ ] 实现进度条组件
- [ ] 实现轮询查询进度（setInterval）
- [ ] 实现进度更新动画
- [ ] 实现步骤指示器

**进度显示**:
```
步骤 3/6: 特征工程Agent 🔄 进行中
[████████░░░░░░░░░░] 50%
```

#### Day 20: 实时日志（Polling）
- [ ] 实现日志显示组件
- [ ] 实现轮询获取日志
- [ ] 实现日志自动滚动
- [ ] 实现日志过滤/高亮

#### Day 21: WebSocket实时日志（进阶）
- [ ] 实现WebSocket连接
- [ ] 实现日志实时推送
- [ ] 实现断线重连
- [ ] 降级方案（WebSocket失败时用Polling）

**Week 3 交付物**:
- ✅ 主Agent控制面板完整功能
- ✅ 文件上传
- ✅ 参数配置
- ✅ 任务创建
- ✅ 实时进度和日志

---

## 阶段四：Agent结果可视化（Week 4-5，第22-35天）

### 任务清单

#### Day 22-23: 数据分析Agent可视化
- [ ] 实现统计卡片组件
- [ ] 实现APP类别分布饼图（ECharts）
- [ ] 实现样本分布柱状图
- [ ] 实现FDC数据表格

**关键图表**:
- APP类别分布（饼图）
- 高风险类别（柱状图）
- 逾期率（环形图）

#### Day 24-25: 特征设计Agent可视化
- [ ] 实现特征列表表格（可展开详情）
- [ ] 实现特征详情模态框
- [ ] 实现搜索/筛选功能
- [ ] 实现特征类别饼图

**表格功能**:
- 可展开显示详情
- 按类别筛选
- 搜索功能
- 导出CSV

#### Day 26-27: 特征工程Agent可视化
- [ ] 集成Monaco Editor代码查看器
- [ ] 实现代码高亮
- [ ] 实现代码统计卡片
- [ ] 实现下载功能

#### Day 28-29: 特征审核Agent可视化
- [ ] 实现审核报告卡片
- [ ] 实现人工确认按钮组
- [ ] 实现审核历史时间线
- [ ] 实现审核结果API调用

**交互流程**:
```
用户点击"确认通过" → API调用 → 更新状态 → 继续下一步
```

#### Day 30-33: 特征评估Agent可视化 ⭐ 重点
- [ ] 实现IV分布直方图
- [ ] 实现PSI稳定性散点图
- [ ] 实现覆盖率饼图
- [ ] 实现特征排行榜表格
- [ ] 嵌入HTML报告（iframe）
- [ ] 实现特征详情模态框

**关键指标卡片**:
- IV >= 0.02 的特征数
- PSI <= 0.25 的特征数
- 覆盖率 > 5% 的特征数
- 总通过率

#### Day 34-35: 特征部署Agent可视化
- [ ] 实现版本列表表格
- [ ] 实现部署按钮
- [ ] 实现回滚功能
- [ ] 实现API文档折叠面板
- [ ] 实现API测试工具

**Week 4-5 交付物**:
- ✅ 6个Agent结果可视化
- ✅ ECharts图表集成
- ✅ 代码查看器
- ✅ HTML报告嵌入
- ✅ 部署管理

---

## 阶段五：实时交互优化（Week 6，第36-40天）

### 任务清单

#### Day 36: WebSocket优化
- [ ] 实现WebSocket连接池
- [ ] 实现心跳检测
- [ ] 实现消息队列
- [ ] 实现优雅关闭

#### Day 37: 错误处理
- [ ] 实现统一错误处理
- [ ] 实现错误提示组件
- [ ] 实现重试机制
- [ ] 实现错误日志上报

#### Day 38:  Loading状态
- [ ] 实现全局Loading状态
- [ ] 实现骨架屏
- [ ] 实现加载进度提示

#### Day 39: 动画优化
- [ ] 实现页面切换动画
- [ ] 实现列表项动画
- [ ] 实现图表加载动画

#### Day 40: 性能优化
- [ ] 实现组件懒加载
- [ ] 实现图表懒加载
- [ ] 实现虚拟列表（长列表）
- [ ] 实现防抖/节流

**Week 6 交付物**:
- ✅ 实时交互完善
- ✅ 错误处理
- ✅ 性能优化

---

## 阶段六：测试和优化（Week 7，第41-42天+）

### 任务清单

#### Day 41: 端到端测试
- [ ] 编写E2E测试用例
- [ ] 执行完整流程测试
- [ ] 修复发现的问题
- [ ] 性能测试

**测试场景**:
1. 创建任务 → 上传数据 → 执行 → 查看结果
2. 中断恢复
3. 错误处理

#### Day 42+: 优化和文档
- [ ] 代码审查和优化
- [ ] 编写使用文档
- [ ] 编写部署文档
- [ ] 编写维护手册

**Week 7+ 交付物**:
- ✅ 完整测试
- ✅ 文档
- ✅ 优化后的代码

---

## 总交付时间表

| 周 | 主要交付物 | 里程碑 |
|----|-----------|--------|
| Week 1 | FastAPI后端基础 | M1: 后端API可用 |
| Week 2 | React前端基础 | M2: 前端框架就绪 |
| Week 3 | 主Agent控制面板 | M3: 核心功能可用 |
| Week 4-5 | Agent结果可视化 | M4: 结果可视化完成 |
| Week 6 | 实时交互优化 | - |
| Week 7 | 测试和优化 | M5: 完整流程可用 |

---

## 立即开始：第1天任务

### Backend Day 1 任务详情

**目标**: 创建后端项目结构并运行第一个API

**步骤**:

1. **创建项目目录**
```bash
cd /Users/apple/Desktop/agents/risk-agent-cc-indo
mkdir -p backend/app
touch backend/app/__init__.py
touch backend/app/main.py
```

2. **创建requirements.txt**
```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
```

3. **编写第一个API**
```python
# backend/app/main.py
from fastapi import FastAPI

app = FastAPI(title="Risk Agent Web App")

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/health")
async def health():
    return {"status": "ok"}
```

4. **安装依赖并运行**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

5. **验证**
```bash
curl http://localhost:8000/
curl http://localhost:8000/health
```

**验收标准**:
- ✅ 项目结构创建
- ✅ 依赖安装成功
- ✅ API可访问
- ✅ /health返回{"status": "ok"}

---

你觉得这个计划如何？需要立即开始第1天的任务吗？还是有其他需要调整的地方？
