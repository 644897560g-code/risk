# 风险特征挖掘系统 - Web架构设计

## 技术栈

### 前端
- **React 18** + TypeScript
- **Ant Design** - UI组件库
- **ECharts** - 数据可视化
- **Axios** - HTTP请求
- **React Router** - 路由管理
- **Zustand** - 状态管理

### 后端
- **FastAPI** - Python API框架
- **SQLite/PostgreSQL** - 任务状态存储
- **Celery** - 异步任务队列
- **Redis** - 缓存和消息队列
- **Pydantic** - 数据验证

### LLM集成
- **qwen3.6-plus** - 通过OpenAI兼容API调用

---

## 系统架构

```
┌──────────────────────────────────────────────────────────┐
│                        前端 (React)                       │
│  Dashboard | 任务管理 | Agent监控 | 结果查看 | 系统设置    │
└───────────────────────┬──────────────────────────────────┘
                        │ REST API (HTTP/WebSocket)
┌───────────────────────┴──────────────────────────────────┐
│                      后端 (FastAPI)                       │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐ │
│  │                   API Layer                         │ │
│  │  /api/tasks, /api/agents, /api/data, /api/results  │ │
│  └─────────────────────────────────────────────────────┘ │
│                           │                               │
│  ┌─────────────────────────────────────────────────────┐ │
│  │                 Service Layer                       │ │
│  │  DataAnalysisService, FeatureDesignService, etc.   │ │
│  └─────────────────────────────────────────────────────┘ │
│                           │                               │
│  ┌─────────────────────────────────────────────────────┐ │
│  │                  Task Queue (Celery)                 │ │
│  │  analyze_data_task, design_features_task, etc.      │ │
│  └─────────────────────────────────────────────────────┘ │
│                           │                               │
│  ┌─────────────────────────────────────────────────────┐ │
│  │               Agent Execution Layer                 │ │
│  │  DataAnalysisAgent, FeatureDesignAgent, etc.        │ │
│  └─────────────────────────────────────────────────────┘ │
│                           │                               │
│  ┌─────────────────────────────────────────────────────┐ │
│  │                 External Services                   │ │
│  │  qwen3.6-plus API, Short Links, File System         │ │
│  └─────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

---

## 页面设计

### 1. 首页 - Dashboard

```
┌─────────────────────────────────────────────────────────┐
│  🏠 风险特征挖掘系统 - Dashboard                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Agent状态卡片（2x3网格）                                │
│  ┌──────────────┬──────────────┬──────────────┐         │
│  │ 📊 数据分析   │ 🎨 特征设计   │ 🔧 特征工程   │         │
│  │ 🟢 空闲       │ 🟢 空闲       │ 🟢 空闲       │         │
│  │ 今日任务: 5   │ 今日任务: 3   │ 今日任务: 4   │         │
│  │ [查看详情]    │ [查看详情]    │ [查看详情]    │         │
│  ├──────────────┼──────────────┼──────────────┤         │
│  │ ✅ 特征审核   │ 📈 特征评估   │ 📦 特征部署   │         │
│  │ 🟢 空闲       │ 🟢 空闲       │ 🟢 空闲       │         │
│  │ 今日任务: 4   │ 今日任务: 3   │ 今日任务: 2   │         │
│  │ [查看详情]    │ [查看详情]    │ [查看详情]    │         │
│  └──────────────┴──────────────┴──────────────┘         │
│                                                         │
│  最近任务（表格）                                         │
│  ┌────────┬────────┬────────┬────────┬────────┐         │
│  │ 任务ID  │ Agent  │ 状态    │ 进度    │ 操作    │         │
│  ├────────┼────────┼────────┼────────┼────────┤         │
│  │ t_001  │ 数据分析 │ 🔄运行  │ ███▒░ 60%│ [查看] │         │
│  │ t_002  │ 特征设计 │ ⏸等待   │ ░░░░░  0%│ [启动] │         │
│  │ t_003  │ 特征评估 │ ✅完成  │ █████ 100%│ [查看] │         │
│  └────────┴────────┴────────┴────────┴────────┘         │
│                                                         │
│  统计图表（ECharts）                                      │
│  ┌─────────────────────┬─────────────────────┐          │
│  │  今日任务趋势（折线图）│  Agent使用分布（饼图）│          │
│  │                     │                     │          │
│  └─────────────────────┴─────────────────────┘          │
└─────────────────────────────────────────────────────────┘
```

### 2. 数据分析Agent页面

```
┌─────────────────────────────────────────────────────────┐
│  📊 数据分析Agent                                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  [开始分析] 按钮                                         │
│                                                         │
│  配置项:                                                 │
│  ┌───────────────────────────────────────────────────┐  │
│  │ 样本数量: [100 ▼] 条                              │  │
│  │ 短链文件: 0421全样本短链.txt (2915条)              │  │
│  │ 标签文件: 印尼模型分_*.xlsx (2272条)               │  │
│  │ LLM模型: qwen3.6-plus                             │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  执行进度:                                               │
│  ┌───────────────────────────────────────────────────┐  │
│  │ ████████████████████▒▒▒▒▒▒▒▒░░░░░░░  65%         │  │
│  │ 当前步骤: 调用qwen3.6-plus分析FDC数据...           │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  步骤状态:                                               │
│  ┌──────────┬──────────┬──────────┬──────────┐         │
│  │ ✅ 加载   │ ✅ 统计   │ 🔄 分析  │ ⏸ 生成   │         │
│  │ 短链数据  │ 样本数据  │ LLM处理  │ 知识库   │         │
│  └──────────┴──────────┴──────────┴──────────┘         │
│                                                         │
│  分析结果预览:                                           │
│  ┌───────────────────────────────────────────────────┐  │
│  │ {                                                 │  │
│  │   "summary": {                                    │  │
│  │     "total_samples": 100,                         │  │
│  │     "overdue_rate": 0.7245,                       │  │
│  │     ...                                           │  │
│  │   },                                              │  │
│  │   "base_analysis": {...},                         │  │
│  │   "app_analysis": {...},                          │  │
│  │   "fdc_analysis": {...}                           │  │
│  │ }                                                 │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  [下载JSON] [查看可视化] [下一步: 特征设计]              │
└─────────────────────────────────────────────────────────┘
```

### 3. 特征设计Agent页面

```
┌─────────────────────────────────────────────────────────┐
│  🎨 特征设计Agent                                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  [开始设计] 按钮                                         │
│                                                         │
│  输入:                                                   │
│  - 知识库文件: knowledge_base.json [浏览]               │
│  - FDC变量清单: FDC4710变量.xlsx [浏览]                 │
│                                                         │
│  执行进度:                                               │
│  ┌───────────────────────────────────────────────────┐  │
│  │ ███████████████████████████████░░  90%            │  │
│  │ 当前: 检查特征去重...                              │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  设计结果（表格展示）:                                    │
│  ┌────┬──────────────────┬──────┬──────────┬────────┐  │
│  │ #  │ 特征名            │ 类型 │ 风险等级 │ 操作    │  │
│  ├────┼──────────────────┼──────┼──────────┼────────┤  │
│  │ 1  │ app_loan_cnt_7d  │ 计数 │ 高       │ [详情] │  │
│  │ 2  │ fdc_query_freq_3 │ 比例 │ 中       │ [详情] │  │
│  │ 3  │ salary_loan_ratio│ 交叉 │ 高       │ [详情] │  │
│  └────┴──────────────────┴──────┴──────────┴────────┘  │
│                                                         │
│  特征详情弹窗:                                           │
│  ┌───────────────────────────────────────────────────┐  │
│  │ 特征名: app_loan_cnt_7d                           │  │
│  │ 业务解释: 近7天新增借贷类APP数量                    │  │
│  │ 设计理由: 短期频繁安装借贷APP说明资金需求强烈...    │  │
│  │ 预期IV: 0.035                                      │  │
│  │ 预期覆盖率: 95%                                    │  │
│  │ [关闭]                                             │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  [下载设计文档] [下一步: 特征工程]                       │
└─────────────────────────────────────────────────────────┘
```

### 4. 任务管理页面

```
┌─────────────────────────────────────────────────────────┐
│  📋 任务管理                                             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  筛选器:                                                 │
│  [全部 Agent ▼]  [全部状态 ▼]  [日期选择器]  [搜索...]  │
│                                                         │
│  任务列表:                                               │
│  ┌────────┬────────┬────────┬────────┬────────┐         │
│  │ 任务ID  │ Agent  │ 状态    │ 耗时    │ 操作    │         │
│  ├────────┼────────┼────────┼────────┼────────┤         │
│  │ t_042  │ 数据分析 │ ✅完成  │ 12m 30s │ [详情] │         │
│  │ t_041  │ 数据分析 │ ✅完成  │ 15m 12s │ [详情] │         │
│  │ t_040  │ 特征设计 │ ✅完成  │ 8m 45s  │ [详情] │         │
│  │ t_039  │ 特征审核 │ ❌失败  │ 3m 20s  │ [重试] │         │
│  │ t_038  │ 特征评估 │ ✅完成  │ 25m 8s  │ [详情] │         │
│  └────────┴────────┴────────┴────────┴────────┘         │
│                                                         │
│  分页: < 1 2 3 4 5 ... 10 >  共96条                     │
│                                                         │
│  任务详情弹窗:                                           │
│  ┌───────────────────────────────────────────────────┐  │
│  │ 任务ID: t_042                                     │  │
│  │ Agent: 数据分析Agent                               │  │
│  │ 状态: ✅ 完成                                      │  │
│  │ 开始: 2026-04-25 14:30:00                         │  │
│  │ 结束: 2026-04-25 14:42:30                         │  │
│  │ 耗时: 12分30秒                                     │  │
│  │                                                   │  │
│  │ 日志输出:                                          │  │
│  │ ┌───────────────────────────────────────────────┐ │  │
│  │ │ 14:30:00 开始加载短链数据...                  │ │  │
│  │ │ 14:30:05 成功加载100条样本                    │ │  │
│  │ │ 14:31:00 调用qwen3.6-plus分析...              │ │  │
│  │ │ 14:42:00 分析完成，保存知识库                 │ │  │
│  │ └───────────────────────────────────────────────┘ │  │
│  │                                                   │  │
│  │ 结果文件:                                          │  │
│  │ 📄 knowledge_base.json (25KB) [下载]             │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 5. 特征评估报告页面

```
┌─────────────────────────────────────────────────────────┐
│  📈 特征评估报告                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  评估概况:                                               │
│  ┌──────────────┬──────────────┬──────────────┐         │
│  │ 总特征数      │ 通过筛选      │ 淘汰率        │         │
│  │    150       │     42       │   72%        │         │
│  └──────────────┴──────────────┴──────────────┘         │
│                                                         │
│  筛选条件:                                               │
│  ✅ IV >= 0.02  ✅ PSI <= 0.25  ✅ 覆盖率 > 5%          │
│                                                         │
│  IV分布（柱状图）:                                       │
│  ┌───────────────────────────────────────────────────┐  │
│  │     ██                                            │  │
│  │     ██    ███                                     │  │
│  │ █   ██    ███    █                                │  │
│  │ █   ██    ███    █   █                            │  │
│  │─┴───┴─────┴─────┴───┴─                           │  │
│  │ <0.02  0.02  0.05  0.1  >0.2                     │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  PSI分布（热力图）:                                       │
│  ┌───────────────────────────────────────────────────┐  │
│  │                                                   │  │
│  │  (颜色渐变表示分布稳定性)                           │  │
│  │                                                   │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  通过特征列表（可排序表格）:                              │
│  ┌────┬──────────────────┬──────┬──────┬──────┬────────┐│
│  │ #  │ 特征名            │ IV   │ PSI  │ 覆盖率│ 状态   ││
│  ├────┼──────────────────┼──────┼──────┼──────┼────────┤│
│  │ 1  │ fdc_dpd_max_90d  │ 0.125│ 0.08 │ 98%  │ ✅通过 ││
│  │ 2  │ app_loan_finance │ 0.098│ 0.12 │ 92%  │ ✅通过 ││
│  │ 3  │ salary_loan_ratio│ 0.087│ 0.15 │ 85%  │ ✅通过 ││
│  └────┴──────────────────┴──────┴──────┴──────┴────────┘│
│                                                         │
│  [下载报告HTML] [下载报告PDF] [部署通过的特征]            │
└─────────────────────────────────────────────────────────┘
```

---

## API接口设计

```python
# fastapi_app/routers/tasks.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter()

# 创建任务
@router.post("/api/tasks")
def create_task(request: CreateTaskRequest):
    """创建新的分析任务"""
    # 验证参数
    # 生成任务ID
    # 存入数据库
    # 触发Celery异步任务
    return {"task_id": "t_043", "status": "pending"}

# 获取任务列表
@router.get("/api/tasks")
def list_tasks(
    agent: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
):
    """获取任务列表，支持筛选和分页"""
    return {
        "tasks": [...],
        "total": 96,
        "page": 1,
        "page_size": 20
    }

# 获取任务详情
@router.get("/api/tasks/{task_id}")
def get_task(task_id: str):
    """获取单个任务的详细信息"""
    return {
        "task_id": task_id,
        "agent": "data_analysis",
        "status": "running",
        "progress": 65,
        "current_step": "调用qwen3.6-plus分析FDC数据",
        "started_at": "2026-04-25T14:30:00",
        "logs": [...]
    }

# 获取任务结果
@router.get("/api/tasks/{task_id}/result")
def get_task_result(task_id: str):
    """获取任务执行结果（JSON或文件URL）"""
    return {
        "task_id": task_id,
        "result_type": "json",
        "result": {...},
        "download_url": "/downloads/knowledge_base.json"
    }

# 取消任务
@router.post("/api/tasks/{task_id}/cancel")
def cancel_task(task_id: str):
    """取消正在运行的任务"""
    return {"status": "cancelled"}

# 重试任务
@router.post("/api/tasks/{task_id}/retry")
def retry_task(task_id: str):
    """重新运行失败的任务"""
    return {"task_id": "t_044", "status": "pending"}


# 请求/响应模型
class CreateTaskRequest(BaseModel):
    agent: str  # data_analysis, feature_design, etc.
    params: dict
    sample_size: int = 100

class TaskResponse(BaseModel):
    task_id: str
    agent: str
    status: str  # pending, running, completed, failed, cancelled
    progress: int
    current_step: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    result: Optional[dict]
    error: Optional[str]
```

---

## Celery任务设计

```python
# tasks/agent_tasks.py

from celery import Celery
# 历史示例：旧版分离式Agent已归档到 agents/legacy/
from agents.legacy.data_analysis_agent import DataAnalysisAgent
from agents.legacy.feature_design_agent import FeatureDesignAgent
# 当前主流程请优先使用 agents.feature_orchestrator.FeatureOrchestrator

celery_app = Celery('risk_agent', broker='redis://localhost:6379/0')

@celery_app.task(bind=True)
def run_data_analysis_task(self, task_id: str, params: dict):
    """数据分析异步任务"""
    try:
        # 更新任务状态为运行中
        update_task_status(task_id, 'running', progress=0)

        # 加载数据
        short_links = load_short_links()
        model_samples = load_model_samples()

        # 创建Agent实例
        agent = DataAnalysisAgent()

        # 执行分析
        result = agent.run({
            'short_links': short_links,
            'model_samples': model_samples,
            'sample_size': params.get('sample_size', 100)
        })

        # 保存结果
        save_task_result(task_id, result)
        update_task_status(task_id, 'completed', progress=100)

        return {"status": "success", "task_id": task_id}

    except Exception as e:
        update_task_status(task_id, 'failed', error=str(e))
        return {"status": "failed", "error": str(e)}

@celery_app.task(bind=True)
def run_feature_design_task(self, task_id: str, params: dict):
    """特征设计异步任务"""
    # 类似实现...

# 其他Agent任务...
```

---

## 数据库设计

```sql
-- 任务表
CREATE TABLE tasks (
    task_id VARCHAR(64) PRIMARY KEY,
    agent_name VARCHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    current_step TEXT,
    params JSON,
    result JSON,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- 指标表（特征评估结果）
CREATE TABLE feature_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feature_name VARCHAR(128) NOT NULL,
    iv_score DECIMAL(10, 4),
    psi_score DECIMAL(10, 4),
    coverage_rate DECIMAL(5, 4),
    passed BOOLEAN,
    task_id VARCHAR(64),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- 索引
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_agent ON tasks(agent_name);
CREATE INDEX idx_tasks_created ON tasks(created_at);
```

---

## 前端目录结构

```
web-frontend/
├── src/
│   ├── components/              # 可复用组件
│   │   ├── AgentCard.tsx       # Agent状态卡片
│   │   ├── TaskTable.tsx       # 任务列表表格
│   │   ├── ProgressBar.tsx     # 进度条
│   │   ├── JsonViewer.tsx      # JSON查看器
│   │   └── ...
│   ├── pages/                   # 页面组件
│   │   ├── Dashboard.tsx       # 首页
│   │   ├── TaskList.tsx        # 任务管理
│   │   ├── DataAnalysis.tsx    # 数据分析Agent页面
│   │   ├── FeatureDesign.tsx   # 特征设计Agent页面
│   │   ├── FeatureEvaluation.tsx # 特征评估页面
│   │   └── ...
│   ├── services/                # API服务
│   │   ├── taskApi.ts
│   │   ├── agentApi.ts
│   │   └── ...
│   ├── hooks/                   # 自定义Hooks
│   │   ├── useTaskPolling.ts   # 任务轮询Hook
│   │   └── ...
│   ├── store/                   # 状态管理
│   │   └── taskStore.ts
│   ├── types/                   # TypeScript类型
│   │   └── index.ts
│   └── App.tsx
├── package.json
├── tsconfig.json
└── ...
```

---

## 开发优先级

1. **Phase 1**: Backend API + Task Queue（2周）
   - FastAPI基础框架
   - 任务CRUD接口
   - Celery异步任务集成
   - 数据库模型

2. **Phase 2**: 前端基础架构 + Dashboard（1周）
   - React项目搭建
   - 路由和布局
   - Dashboard首页
   - API对接

3. **Phase 3**: Agent页面开发（2周）
   - 数据分析Agent页面
   - 特征设计Agent页面
   - 特征评估报告页面

4. **Phase 4**: 高级功能（1周）
   - WebSocket实时推送
   - 可视化图表增强
   - 导出功能

---

## 下一步

1. ✅ **已完成**: 数据分析Agent核心逻辑修正
2. 🔄 **进行中**: Web架构设计文档
3. 📋 **待开始**: 实现FastAPI后端 + Celery任务队列
