# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 常用命令

### 环境准备
```bash
# 创建虚拟环境并安装依赖
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 启动 MySQL + Redis（Docker）
docker compose up -d

# 初始化数据库和种子数据
python scripts/env_check.py
python scripts/init_db.py
python scripts/seed_categories.py
python scripts/seed_products.py
python scripts/seed_market_templates.py
python scripts/seed_feature_flags.py

# 构建 FAISS 索引（仅首次或知识库更新后）
python scripts/build_faiss_index.py
```

### 启动服务
```bash
# API 服务（开发模式，热重载）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Worker（消费 Redis 仿真任务队列）
python engine/worker.py

# Monitor（心跳监控、超时处理、自定义竞品回填）
python engine/monitor.py

# 前端开发服务器
cd frontend && npm run dev
```

### 测试
```bash
# 运行全部测试
pytest

# 运行单个测试文件
pytest tests/test_worker_flow.py

# 运行特定标记的测试
pytest -m "not no_db"

# 带覆盖率
pytest --cov=app --cov=engine --cov-report=term-missing
```

### 检查与调试
```bash
python scripts/check_services.py     # 检查 MySQL / Redis 连通性
python scripts/check_faiss_rag.py    # 检查 RAG 检索可用性
python scripts/v24_preflight.py      # v2.4 预检
```

### 前端构建
```bash
cd frontend
npm run build       # 生产构建到 frontend/dist/
npm run preview     # 预览生产构建
```

## 核心架构

### 数据流主线

```
前端 (React/Vite) → FastAPI → MySQL (草稿/快照/结果)
                         ↘ Redis 队列 → Worker → LLM + FAISS RAG → 报告写入 MySQL
```

关键链路：`product_definition → market_config → config_snapshot → Redis task → Worker simulation → result_data`

### 三层职责分离

| 层 | 目录 | 职责 |
|---|---|---|
| API 层 | `app/` | 路由、认证、草稿管理、快照生成、任务入队、报告查询 |
| 仿真引擎 | `engine/` | Worker 消费队列，执行 RAG → Agent 生成 → 决策 → 社交传播 → 聚合 → 报告 |
| 知识库 | `knowledge_model/` | FAISS 向量检索、RAG 服务封装、产品证据查询 |

**前端不直接调用 RAG、LLM 或 Agent。** 所有模型调用发生在 Worker 内部。

### 仿真项目的生命周期

```
draft → submitted → queued → running → report_waiting → completed
  ↓                                              ↓
  └── 用户编辑草稿                         failed / cancelled
```

- **draft**：Step1（产品定义）和 Step2（市场配置）仅写 MySQL，不触及 Redis。
- **submitted**：配置冻结为 `config_snapshot`（SHA256 哈希），生成三类 RAG 查询文本。
- **running**：Worker 只读快照，不读实时草稿 — 用户编辑不影响运行中任务。
- **report_waiting**：报告数据已生成但故意延迟展示，前端显示"报告生成中"，由 `runtime_status.py` 控制目标时长后自动转为 completed。

### 多级 Redis 队列

```
simulation:queue         — 兼容旧任务的默认队列
simulation:queue:basic   — 普通版用户
simulation:queue:pro     — 专业版用户
simulation:queue:exports — 导出任务（PDF/Excel）
```

Worker 按 pro → basic → default 优先级 BLPOP。Monitor 管理心跳、超时，仅在全部空闲时处理自定义竞品回填（只操作 MySQL，不调 RAG/LLM/FAISS）。

### Worker 仿真流水线

```
start → RAG 检索（三类 query） → 公开资料补充 → Agent 生成
  → 购买决策（LLM 采样 + MAUT 评分） → 社交传播（小世界网络，多轮）
  → 蒸馏校验（可选） → 指标聚合 → 报告组装 → report_waiting 阶段
```

每个阶段通过 `update_progress()` 写入 Redis `simulation:progress:{task_id}`，前端轮询 `/api/simulations/{id}/progress` 获取。

### 决策模型的混合架构

`engine/decision_model.py` 采用 **规则 fallback + LLM 采样增强**：
1. 先用确定性的价格匹配 + 特征匹配为所有 Agent 计算基线分数
2. 对少数代表 Agent（`social_llm_sample_size`，默认 12）调用 LLM 生成推理理由
3. LLM 失败时自动回退到规则基线，不阻断仿真

### 社交传播

`engine/social_simulation.py` 构建 Watts-Strogatz 小世界网络，实际节点数由 `representative_agent_count()` 限制在 60-300（由环境变量 `SOCIAL_REPRESENTATIVE_*` 控制）。每轮传播后可选调用蒸馏校验，最终 `final_decisions` 写回结果。

## 关键设计模式

### 配置系统
`app/config.py` 使用 `pydantic-settings`，从项目根目录 `.env` 读取所有环境变量。`resolve_path()` 方法将相对路径转为基于 `ROOT_DIR`（`app/` 的父目录）的绝对路径。设置通过 `settings` 单例全局访问。

### API 响应包装
所有 JSON 响应被中间件 `wrap_json_response` 自动包装为 `{code, message, data}` 结构。只跳过 `/docs`、`/redoc`、`/openapi.json` 和非 2xx 响应。任何返回的 dict 如果已含这三个 key 则不再重复包装。

### 草稿版本冲突检测
前端保存草稿时携带 `draft_version`，后端通过 `ensure_draft_version()` 比较。不匹配返回 409 `DRAFT_CONFLICT`，前端提示用户刷新。

### 报告数据自动修复
`repair_project_report_data()` 在每次查询报告时运行。如果历史项目的 `result_data` 缺少新版本才有的图表字段（如 `market_share_scope`、`propagation_funnel`），会从快照和决策数据重新计算并回填。这是只读修复，不改变仿真结果。

### 普通版 vs 专业版限制
- 普通版：≤3 个产品参数、≤1 个竞品、≤3 类客群、样本量 1000、配额扣减
- 专业版：无上述限制、样本量 10000、多方案对比（最多 5 个）
- 限制在 `validate_version_limits()` 中集中校验
- 普通版配额在任务入队时扣减，失败或取消时回滚

### 重试与错误处理
Worker 的 `process_task()` 对可重试异常（TimeoutError、ConnectionError 等）自动重新入队，最多 `max_retry` 次（默认 2）。非可重试异常标记 `failed` 并回滚配额。`check_cancel()` 在每个阶段检查 Redis 取消标记。

### 数据库访问
- `SessionLocal`（SQLAlchemy sessionmaker）用于 Worker 和脚本
- API 通过 FastAPI 依赖注入 `get_db` → `DbSession`
- 列表查询用 `defer()` 延迟加载大字段（`config_snapshot`、`result_data`）
- ORM 模型统一使用 `JsonColumn = MySQLJSON` 类型存储 JSON 字段

## 前端结构

前端是单文件 `App.tsx`（~6000+ 行），使用 React Router v7 管理所有路由：
- `/login`、`/register` — 认证
- `/dashboard` — 项目列表
- `/projects/:id` — 仿真向导（Step1-4 的 Tab 切换）
- `/share/:token` — 公开分享报告

UI 组件库：Ant Design 6 + `@ant-design/icons`。图表：ECharts 6（`echarts-for-react`）。

API 封装在 `frontend/src/api.ts`，所有请求自动携带 JWT token，响应解包 `{code, message, data}` 结构。

## 测试结构

测试在 `tests/` 目录，使用 pytest。`conftest.py` 提供 fixtures（数据库 session、测试客户端、Redis mock）。测试标记：
- `no_db`：不需要 MySQL/Redis 清理 fixtures

关键测试文件：
- `test_worker_flow.py` — Worker 完整仿真流程
- `test_api_basic.py` — API 端点和认证
- `test_formal_engine.py` — 正式仿真场景
- `test_crowd_segments.py` — 人群分段校验
- `test_social_simulation.py` — 社交传播逻辑
- `test_chart_data.py` — 图表数据构建

## 部署与发布红线（禁止再犯）

### 1. Docker 部署：禁止只覆盖宿主机源码就重启容器

**错误做法**：修改宿主机源码 → `docker compose up -d --force-recreate`。
**为什么错**：生产 Compose 不 bind-mount `app/`/`engine/` 到容器。容器从 `agentsim-backend-core:prod` **镜像**读取代码，重建容器用的还是旧镜像。

**唯一正确流程**：
```bash
# 1. 先给旧镜像打回滚标签
docker tag agentsim-backend-core:prod agentsim-backend-core:rollback-YYYYMMDD
docker tag agentsim-frontend:prod agentsim-frontend:rollback-YYYYMMDD

# 2. 基于旧镜像构建增量候选镜像（--network none 禁止网络下载）
docker build --network none --build-arg BASE_IMAGE=agentsim-backend-core:rollback-YYYYMMDD \
  -f deploy/Dockerfile.backend-incremental -t agentsim-backend-core:candidate .

# 3. 验证候选镜像
docker run --rm --network none --entrypoint python agentsim-backend-core:candidate \
  -m compileall -q app engine
docker run -d --name api-candidate --network agentsim_default --env-file .env.production \
  agentsim-backend-core:candidate
curl -fsS http://127.0.0.1:8000/health && docker rm -f api-candidate

# 4. 切换镜像标签
docker tag agentsim-backend-core:candidate agentsim-backend-core:prod

# 5. 重建容器（此时才能读到新代码）
docker compose up -d --no-deps --force-recreate api
```

### 2. manifest.sha256 规范

- **不要将 `manifest.sha256` 自身列入校验**：检查时自身哈希必然不匹配
- **路径统一使用 Linux 正斜杠**：`./project_overlay/engine/maut_model.py`，禁止 `.\project_overlay\engine\maut_model.py`
- **构建后必须验证**：在真正的 Linux 环境执行 `sha256sum -c manifest.sha256` 确保全部通过
- **`manifest.json` 的 `entry_count` 必须等于 ZIP 实际条目数**

### 3. 前端回滚必须先保存旧镜像

**错误做法**：只备份 `frontend_dist/` 目录。
**为什么错**：前端是 Docker 镜像，回滚时只恢复目录文件不恢复镜像标签，容器启动的还是新镜像。

**正确做法**：
```bash
# 部署前先打标签
docker tag agentsim-frontend:prod agentsim-frontend:rollback-YYYYMMDD
# 回滚时恢复标签
docker tag agentsim-frontend:rollback-YYYYMMDD agentsim-frontend:prod
docker compose up -d --no-deps --force-recreate frontend
```

### 4. 停止/恢复服务必须成对

`docker compose stop worker monitor export-worker` 之后，恢复时**必须三项全部恢复**。不允许忘记 `export-worker` 或其他被停止的服务。建议在部署文档中用一个变量统一管理待恢复服务列表。

### 5. 禁止使用 Python `hash()` 生成仿真确定性数据

Python 内置 `hash()` 默认 PYTHONHASHSEED 随机化，**同一输入跨进程产出不同哈希值**。仿真中任何需要"基于 agent_id 产生稳定差异"的场景，必须使用：
```python
import hashlib
hashlib.sha256(agent_id.encode()).hexdigest()  # 确定性
# 或
int(hashlib.md5(agent_id.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF  # 确定性浮点
```

验收标准：同一 snapshot、同一配置运行两次，结果完全一致。

### 6. 分数→阈值→标签的计算顺序不可颠倒

**错误顺序**：先用原始分数算阈值 → 用新 MAUT 分数覆盖 → 仍用旧阈值分类。
**正确顺序**：先计算全部最终分数 → 基于**最终分数**确定阈值 → 再分类。

涉及 `enrich_decisions_with_maut()` 和 `adaptive_thresholds()` 的调用关系。

### 7. 舆情/决策标签不要完全依赖分位数切分

`buy/consider/not_buy` 标签如果完全用当轮样本的 p33/p67 切分，会把"消费者绝对态度变化"变成"相对排名变化"。应保留业务意义的绝对阈值（如 0.45/0.68），仅在数据分布极端窄时做有限自适应校准，不能每轮独立分位数切分。

### 8. 更新包必备检查清单

打包前逐一确认：
- [ ] `apply-files.txt` 列出所有将被覆盖/新增的文件
- [ ] `manifest.sha256` 不包含自身，路径用 `/`
- [ ] `manifest.json` 的 `entry_count` 与实际 ZIP 条目一致
- [ ] `RELEASE_NOTES.txt` 内容完整、可审计，不只一行
- [ ] 外层 `.sha256` 正确
- [ ] ZIP 无 Windows 反斜杠、无绝对路径、无 `..` 穿越
- [ ] 没有 `.env.production`、数据库文件、FAISS 索引、种子数据
- [ ] 包内源码与本地文件一致（`diff -r`）
- [ ] `frontend_dist/` 与本地 `npm run build` 产出一致
- [ ] 所有 Python 文件通过 `compileall` 语法检查
- [ ] **部署文档声明依赖的前置包**：如果不是独立包，必须写明"需先部署 XXXX 包"
- [ ] **绝对不把任何账号密码打进前端 JS**：演示账号/共享账号一律通过数据库种子脚本创建

### 9. 仪表盘数据刷新

仪表盘汇总（项目计数等）只在 `useEffect([], [])` 挂载时请求一次。如果用户在同一会话中新建/删除项目后回到仪表盘，数字是旧值。需要：
- 在路由切换回仪表盘时重新请求，或
- 提供手动刷新按钮，或
- 监听项目列表变更事件

### 10. 声明连续化修改时必须验证

声称"从离散改为连续"的修改，提交前必须用实际数据跑一遍，打印 min/max/unique_values 验证输出分布：
```python
values = [func(x) for x in test_inputs]
print(f"unique={len(set(round(v, 3) for v in values))}, min={min(values):.3f}, max={max(values):.3f}")
```
如果 `len(set(...))` ≤ 10，说明"连续化"没有实际生效。
