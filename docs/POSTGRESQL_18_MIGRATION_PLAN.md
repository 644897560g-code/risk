# PostgreSQL 18 迁移计划

> 日期: 2026-06-09
> 适用范围: 本机测试环境使用 Docker PostgreSQL 18，生产环境预期使用阿里云 RDS PostgreSQL。

## 1. 迁移目标

当前后端默认使用 SQLite:

- 配置入口: `backend/app/config.py`
- 数据库初始化: `backend/app/database.py`
- 默认连接串: `sqlite:///./data/feature_mining.db`
- 表结构创建方式: `Base.metadata.create_all(bind=engine)` 加少量手写 `ALTER TABLE`

本次迁移目标:

1. 将 Web 后端主数据库从 SQLite 完全切换为 PostgreSQL 18。
2. 引入正式迁移工具 Alembic，替代启动时手写 `ALTER TABLE`。
3. 移除 SQLite 兼容分支和 `data/feature_mining.db` 运行依赖。
4. 为后续“统一模板库”和“项目 / 任务 / 版本产物隔离”提供可靠关系型数据底座。
5. 生产环境连接方式兼容阿里云 RDS PostgreSQL。

## 2. PostgreSQL 18 版本选择建议

测试环境可以使用 PostgreSQL 18，和你当前本机 Docker 镜像保持一致。

生产环境上阿里云 RDS 是否直接使用 18，要以正式上线时阿里云控制台可选版本和稳定性策略为准:

- 如果阿里云 RDS PostgreSQL 18 已经 GA 且团队接受新版本，生产可以直接用 18。
- 如果阿里云当时仍以 17/16 为主推稳定版本，应用层应保持兼容 PostgreSQL 16+，生产先用阿里云推荐稳定版本。
- 本工程不要依赖 PostgreSQL 18 独有语法，避免将来生产版本低一档时迁移困难。

## 3. 本机测试环境

启动命令:

```bash
docker run -d \
  --name pg18 \
  -e POSTGRES_USER=riskforge \
  -e POSTGRES_PASSWORD=123456 \
  -e POSTGRES_DB=riskforge_ai \
  -p 5432:5432 \
  -v pg18_data:/var/lib/postgresql \
  postgres:18
```

```bash
DATABASE_URL=postgresql+psycopg://riskforge:123456@127.0.0.1:5432/riskforge_ai
```

## 4. 迁移策略调整: 不做 SQLite 数据迁移

当前 SQLite 中只有少量用户数据，可以重新创建，因此本轮不做 SQLite 历史数据搬迁。

新的策略:

1. PostgreSQL 作为唯一运行数据库。
2. 删除或忽略应用侧 `data/feature_mining.db`、`data/feature_mining.db-wal`、`data/feature_mining.db-shm`。
3. PostgreSQL 初始化后重新注册用户。
4. 不保留 SQLite fallback，避免后续开发时误连回本地 `.db` 文件。
5. 后续如确实需要迁移历史业务数据，再单独写一次性脚本，不纳入本轮主线。

## 5. 需要改造的代码点

### 5.1 依赖

修改 `backend/requirements.txt`:

```text
psycopg[binary]>=3.2.0
alembic>=1.13.0
```

说明:

- 推荐 `psycopg` v3，而不是旧的 `psycopg2`。
- SQLAlchemy 2.x 支持 `postgresql+psycopg://...`。

### 5.2 配置

修改 `backend/app/config.py`:

- 保留 `database_url` 字段，并要求必须通过 `DATABASE_URL` 环境变量或 `.env` 提供。
- 代码中不保留本机 PostgreSQL 账号密码默认值。
- 不再使用 `sqlite:///./data/feature_mining.db` 作为默认值。
- `.env.example` 增加 PostgreSQL 示例。

建议 `.env.example` 增加:

```bash
DATABASE_URL=postgresql+psycopg://riskforge:123456@127.0.0.1:5432/riskforge_ai
```

### 5.3 数据库初始化

当前 `backend/app/database.py` 存在 SQLite 专用逻辑:

- `os.makedirs(os.path.dirname(settings.database_url.replace("sqlite:///", "")), exist_ok=True)`
- `connect_args={"check_same_thread": False}`
- `PRAGMA journal_mode=WAL`
- `PRAGMA foreign_keys=ON`
- 启动时手写 `ALTER TABLE`

改造目标:

1. 移除 SQLite 路径创建逻辑。
2. 移除 `connect_args={"check_same_thread": False}`。
3. 移除 SQLite PRAGMA event listener。
4. `init_db()` 不再负责业务迁移，迁移交给 Alembic。
5. 后端启动前必须执行 `alembic upgrade head`。

建议结构:

```python
engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)
```

### 5.4 Alembic

新增:

```text
alembic.ini
backend/migrations/
backend/migrations/env.py
backend/migrations/versions/
```

迁移原则:

- 所有新增表、字段、索引都通过 migration 管理。
- 不再在 `init_db()` 中写 `ALTER TABLE`。
- 首个 migration 应完整覆盖现有模型:
  - `users`
  - `tasks`
  - `task_logs`
  - `feature_versions`
  - `feature_metrics`
  - `chat_sessions`
  - `chat_messages`

## 6. 数据库初始化步骤

### 阶段 A: 创建 PostgreSQL 库

进入本机容器:

```bash
docker exec -it pg18 psql -U postgres
```

创建应用账号和数据库:

```sql
CREATE USER riskforge WITH PASSWORD '123456';
CREATE DATABASE riskforge_ai OWNER riskforge;
GRANT ALL PRIVILEGES ON DATABASE riskforge_ai TO riskforge;
```

### 阶段 B: 结构迁移

1. 安装依赖。
2. 初始化 Alembic。
3. 生成首个 schema migration。
4. 在 PostgreSQL 18 本机库执行:

```bash
alembic upgrade head
```

5. 执行平台初始数据导入:

```bash
python scripts/init_project_data.py
```

6. 启动后端，确认健康检查和登录接口正常。

### 阶段 C: 验证

最小验证清单:

```bash
# 1. PostgreSQL 连接
docker exec -it pg18 psql -U riskforge -d riskforge_ai -c '\dt'

# 2. 后端启动
DATABASE_URL=postgresql+psycopg://riskforge:123456@127.0.0.1:5432/riskforge_ai \
uvicorn backend.app.main:app --reload --port 8000

# 3. 健康检查
curl http://127.0.0.1:8000/api/health

# 4. 重新注册 / 登录
# 通过前端或 API 验证 users 表写入 PostgreSQL

# 5. 创建任务
# 验证 tasks / task_logs 能正常写入
```

## 6.1 平台初始数据导入

表结构由 Alembic 管理，平台基础数据由 seed 初始化脚本管理。不要把 7 个维度和 16 个模板硬编码到 schema migration 中。

统一入口:

```bash
python scripts/init_project_data.py
```

当前包含:

- 从 `outputs/feature_templates/channel1_templates.json` 导入 7 个模板维度。
- 从同一 JSON 导入 16 个 channel1 模板，状态为 `active`。
- 从 `scripts/seeds/fixtures/channel2_pending.seed.json` 导入历史通道2待审批模板，状态为 `pending`。

脚本要求:

- 必须配置 `DATABASE_URL`。
- 所有 seed 必须幂等，重复执行不会插入重复维度或模板。
- 默认只 upsert，不删除数据库中存在但 JSON 中不存在的模板。
- 历史 pending seed 不再放在 `outputs/feature_design/`，避免被误认为运行时审批队列。
- 生产环境和本地测试环境使用同一个初始化入口。

生产初始化顺序:

```bash
export DATABASE_URL="postgresql+psycopg://<user>:<password>@<rds-host>:5432/<db_name>"
alembic upgrade head
python scripts/init_project_data.py
```

## 7. docker-compose 调整

本地开发可以把 PostgreSQL 加进 `docker-compose.yml`:

```yaml
postgres:
  image: postgres:18
  restart: unless-stopped
  ports:
    - "5432:5432"
  environment:
    POSTGRES_USER: riskforge
    POSTGRES_PASSWORD: 123456
    POSTGRES_DB: riskforge_ai
  volumes:
    - pg18_data:/var/lib/postgresql
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U riskforge -d riskforge_ai"]
    interval: 5s
    timeout: 3s
    retries: 20
```

后端环境变量增加:

```yaml
DATABASE_URL: postgresql+psycopg://riskforge:123456@postgres:5432/riskforge_ai
```

volumes 增加:

```yaml
pg18_data:
```

## 8. 阿里云 RDS 生产配置

生产环境建议使用:

```bash
DATABASE_URL=postgresql+psycopg://<user>:<password>@<rds-internal-host>:5432/<db_name>
```

建议配置项:

- 使用 VPC 内网地址，不走公网。
- 开启自动备份和 PITR。
- 独立应用账号，不使用高权限管理员账号。
- 安全组只允许后端 ECS / 容器所在网段访问。
- 连接池先保守配置，避免应用或 Celery 并发打满 RDS 连接数。
- 慢 SQL 日志打开，后续观察任务列表、版本列表、模板库筛选查询。

SQLAlchemy 生产建议:

```python
pool_pre_ping=True
pool_size=5
max_overflow=10
pool_recycle=1800
```

后续如果 Web 后端和 Celery worker 都连同一个 RDS，要按进程数重新计算最大连接数。

## 9. 与模板库 PRD 的关系

PostgreSQL 迁移建议先于统一模板库落地，原因:

1. 模板库需要 `pending / active / rejected` 生命周期状态。
2. 审批历史和被拒记忆更适合放 DB，不适合继续写全局 JSON。
3. 项目 / 任务 / 版本隔离需要外键关系和索引。
4. 后续版本对比、模板筛选、审批人筛选，都需要可靠查询能力。

迁移 PostgreSQL 后，下一步可以新增这些表:

- `projects`
- `templates`
- `template_review_histories`
- `template_rejected_memories`
- `delivery_packages`

并给现有表补字段:

- `tasks.project_id`
- `feature_versions.project_id`
- `feature_metrics.project_id`

## 10. 风险点

1. `backend/app/database.py` 当前有 SQLite 专用代码，必须先移除再切 PostgreSQL。
2. 当前没有 Alembic，生产上继续 `create_all` 无法可靠演进表结构。
3. PostgreSQL 的 JSON、DateTime、Boolean 行为需要重点测用户登录、任务日志、任务配置 JSON。
4. 现有全局产物文件仍在 `outputs/`，迁移数据库不会自动解决并发覆盖问题。
5. PostgreSQL 18 在生产上要确认阿里云 RDS 可用性；应用层先按 PostgreSQL 16+ 兼容写法开发。

## 11. 推荐开发任务拆分

### Task 1: 数据库连接完全切换到 PostgreSQL

- 增加 `psycopg[binary]`
- 改造 `backend/app/database.py`
- 移除 SQLite 专用逻辑
- `.env.example` 增加 PostgreSQL 示例
- 本地连接 PostgreSQL 18 验证启动

### Task 2: 引入 Alembic

- 新增 Alembic 配置
- 生成首个 migration
- 移除 `init_db()` 中手写 `ALTER TABLE`
- 验证空 PostgreSQL 库可 `upgrade head`

### Task 3: docker-compose 本地 PostgreSQL

- 增加 postgres 服务
- 后端服务注入 `DATABASE_URL`
- 增加健康检查和依赖顺序

### Task 4: 生产 RDS 配置文档

- 记录阿里云 RDS 参数
- 记录 ECS / 容器环境变量
- 记录备份、连接数、安全组要求

### Task 5: 为统一模板库建表

- 新增 `Template`
- 新增 `TemplateReviewHistory`
- 新增 `TemplateRejectedMemory`
- 后续 API 和前端模板库页面基于这些表实现

## 12. 验收标准

1. 本机 PostgreSQL 18 容器中能创建全部业务表。
2. 后端使用 PostgreSQL 连接串能正常启动。
3. 登录、任务创建、任务日志、特征版本查询能正常读写。
4. 新用户可在 PostgreSQL 中重新创建并登录。
5. 不再依赖 SQLite PRAGMA、SQLite 专用连接参数或 `data/feature_mining.db`。
6. 新增表结构统一通过 Alembic 管理。
7. 生产部署只需替换 `DATABASE_URL` 即可连接阿里云 RDS。

## 13. 2026-06-09 测试环境改造结果

已完成:

- 后端数据库连接已切换为必须从 `DATABASE_URL` 环境变量或 `.env` 读取。
- `backend/app/database.py` 已移除 SQLite 路径、PRAGMA、`check_same_thread` 和手写 `ALTER TABLE`。
- 已新增 Alembic 配置和初始 schema migration。
- 已新增 `psycopg[binary]` 和 `alembic` 依赖。
- Docker 后端启动命令已调整为先执行 `alembic upgrade head`。
- 本地 `pg18` 容器已执行 `alembic upgrade head`。

实测结果:

- PostgreSQL 版本: `PostgreSQL 18.4`
- Alembic 版本表: `20260609_0001`
- 已建表: `users`、`tasks`、`task_logs`、`feature_versions`、`feature_metrics`、`chat_sessions`、`chat_messages`、`alembic_version`
- 临时后端端口 `18000` 健康检查通过。
- 测试用户 `pg_test_user` 注册和登录通过，确认写入 PostgreSQL。

后续:

- 模板库相关新表已放入第二版 migration，应继续通过后续 Alembic migration 迭代。
- 项目 / 任务 / 版本产物隔离同样应单独建模和迁移。
