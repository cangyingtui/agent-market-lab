# Agentsim 产品市场仿真平台

> 基于产品定义、市场配置、RAG 知识库、多 Agent 消费者仿真与结果复核建议的产品市场模拟系统。

本项目用于在产品正式上市前，对目标人群、使用场景、营销策略、竞品环境和产品功能参数进行仿真分析，输出购买意愿、市场份额、竞品对比、参数重要性、价格敏感性、营销渠道效果和报告建议。

---

## 1. 项目定位

Agentsim 是一个面向产品市场验证的仿真平台。用户可以在前端配置待测产品和市场环境，后端将配置冻结为仿真快照，并通过 Redis 队列交给 Worker 执行仿真。Worker 在运行阶段调用本地 FAISS RAG 知识库、多 Agent 消费者模型和大模型 API，最终生成结构化报告、证据引用与结果复核建议。

核心目标：

- 帮助产品团队在早期评估产品市场接受度；
- 支持普通版和专业版两类能力差异；
- 支持竞品库、场景模板、人群模板和营销策略模板；
- 使用 RAG 为仿真推理提供事实依据；
- 使用多 Agent 模拟不同消费者群体的购买决策；
- 轻量辅助模型接口，用于内部一致性检查；
- 通过报告页展示结果、证据与建议。

---

## 2. 当前核心架构

```text
Frontend React / Vite
        │
        ▼
FastAPI Backend
        │
        ├── MySQL：用户、项目、草稿、报告、模板、日志
        ├── Redis：任务队列、运行锁、进度、取消标记、心跳
        ├── Knowledge Base：FAISS 索引与 metadata
        └── Worker Engine：RAG、多 Agent、决策、聚合、报告生成
```

用户使用主流程：

```text
登录 / 进入个人主页
  ↓
创建仿真项目
  ↓
Step1 选择产品并保存 product_definition
  ↓
Step2 配置市场并保存 market_config
  ↓
Step3 提交并运行仿真
  ↓
Redis 入队，Worker 消费任务
  ↓
RAG 检索 + 多 Agent 决策 + 指标聚合 + 报告生成
  ↓
Step4 查看报告 / 导出 / 分享
```

---

## 3. 技术栈

### 后端

- Python
- FastAPI
- SQLAlchemy / PyMySQL
- Redis
- FAISS
- LangChain / OpenAI-compatible client
- Pydantic
- pytest

### 前端

- React
- Vite
- TypeScript
- CSS

### 数据与模型

- MySQL：业务数据持久化
- Redis：异步任务与进度缓存
- FAISS：本地 RAG 向量检索
- 轻量辅助模型服务：HTTP 接口，默认关闭
- 大模型 API：Agent 决策解释与报告总结

---

## 4. 仓库目录概览

> 当前仓库中存在 `.venv/`、`frontend/node_modules/`、`frontend/dist/`、`__pycache__/`、pytest cache、Playwright cache 等运行或依赖生成目录。它们不属于核心源码，通常不应纳入版本管理。

```text
.
├── app/                         # FastAPI 后端主应用
│   ├── main.py                   # API 入口
│   ├── config.py                 # 配置读取
│   ├── database.py               # 数据库连接
│   ├── redis_client.py           # Redis 客户端
│   ├── models.py                 # ORM 模型
│   ├── schemas.py                # Pydantic Schema
│   ├── security.py               # 鉴权与密码处理
│   ├── response.py               # 统一响应结构
│   ├── crowd_profile.py          # 目标人群画像规范化
│   ├── export_service.py         # 报告导出服务
│   ├── share_tokens.py           # 分享 token 逻辑
│   ├── task_keys.py              # Redis key 常量
│   └── time_utils.py             # 时间工具
│
├── engine/                       # 仿真引擎与 Worker 层
│   ├── worker.py                 # Redis 队列消费者
│   ├── monitor.py                # 任务心跳与超时监控
│   ├── agent_generator.py        # 多 Agent 生成
│   ├── decision_model.py         # 消费者决策模型
│   ├── aggregation.py            # 结果聚合
│   ├── report_generator.py       # 报告生成
│   ├── distill_client.py         # 外部辅助模型 HTTP 接口，默认关闭
│   ├── fact_formatter.py         # RAG 证据格式化
│   ├── data_enrichment.py        # 数据增强
│   ├── formal_logger.py          # 正式运行日志
│   ├── maut_model.py             # 多属性效用模型
│   └── chart_data.py             # 图表数据构建
│
├── knowledge_model/              # RAG 与知识库模块
│   ├── rag_service.py            # RAG 检索服务
│   ├── faiss_rag.py              # FAISS 检索封装
│   ├── product_evidence.py       # 产品证据处理
│   ├── data_enrichment.py        # 知识数据增强
│   ├── requirements.txt          # 知识库模块依赖
│   └── knowledge_base/
│       ├── faiss_index           # FAISS 索引
│       ├── faiss_metadata.pkl    # 向量元数据
│       └── faiss_vector_cache/   # 向量缓存
│
├── frontend/                     # React/Vite 前端
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── api.ts                # 前端 API 封装
│       ├── App.tsx               # 应用主组件
│       ├── main.tsx              # 前端入口
│       └── styles.css            # 样式
│
├── data_seed/                    # 初始化与种子数据
│   ├── merged_categories.json
│   ├── market_crowd_templates.json
│   ├── market_scene_templates.json
│   ├── market_strategy_templates.json
│   ├── output_part1.jsonl
│   ├── output_morep1.jsonl
│   ├── output_morep2.jsonl
│   ├── output_morep3.jsonl
│   └── output_morep4.jsonl
│
├── scripts/                      # 初始化、检查、构建、测试脚本
│   ├── env_check.py              # 环境检查
│   ├── init_db.py                # 初始化数据库
│   ├── seed_categories.py        # 导入品类模板
│   ├── seed_products.py          # 导入产品/竞品库
│   ├── seed_market_templates.py  # 导入市场模板
│   ├── seed_feature_flags.py     # 初始化功能开关
│   ├── build_faiss_index.py      # 构建 FAISS 索引
│   ├── check_faiss_rag.py        # 检查 RAG 检索
│   ├── check_services.py         # 检查服务依赖
│   ├── run_frontend_scenarios.py # 前端流程场景测试
│   ├── run_formal_scenarios.py   # 正式仿真场景测试
│   └── cleanup_test_data.py      # 清理测试数据
│
├── docker-compose.yml            # MySQL / Redis 等服务编排
├── requirements.txt              # 后端依赖
├── pytest.ini                    # 测试配置
├── INIT_GUIDE.md                 # 初始化说明
├── README.md                     # 项目说明
├── .env                          # 本地环境变量，不应提交
├── .env.example                  # 环境变量示例
└── .gitignore
```

---

## 5. 核心业务对象

### 5.1 simulation_projects

仿真项目主表，承载项目状态、草稿、快照和结果。

关键字段：

- `product_definition`：Step1 产品定义草稿；
- `market_config`：Step2 市场配置草稿；
- `config_snapshot`：Step3 提交后冻结的运行配置；
- `result_data`：Step4 报告数据；
- `status`：`draft / submitted / running / completed / failed`；
- `task_id`：当前异步任务 ID；
- `error_code` / `error_reason`：失败原因；
- `quota_charged`：普通版配额是否已扣减。

### 5.2 product_definition

用于描述产品本身，包括：

- 产品名称；
- 品类 / 子品类；
- 产品简介；
- 功能参数；
- 专业版多方案 `schemes`；
- 参数权重和启用状态。

### 5.3 market_config

用于描述仿真市场环境，包括：

- 目标人群；
- 结构化人群画像 `crowd_profile`：年龄段、城市层级、收入水平、职业/家庭阶段、价格敏感度、功能偏好、渠道偏好、购买动机、风险顾虑和补充描述；
- 使用场景；
- 样本规模；
- 营销策略；
- 竞品配置；
- 专业版自定义配置。

### 5.4 config_snapshot

用户点击“提交仿真”后生成的冻结配置。Worker 运行时只读取该快照，避免用户后续修改草稿影响当前任务。

建议结构：

```json
{
  "snapshot_id": "snap_123_001",
  "snapshot_hash": "sha256_xxx",
  "project_id": 123,
  "user_id": 1,
  "product_definition": {},
  "market_config": {
    "target_crowd": "高端用户",
    "crowd_profile": {
      "age_range": "28-45",
      "city_tier": "一线/新一线",
      "income_level": "高收入",
      "price_sensitivity": "low",
      "feature_priorities": ["续航", "屏幕", "防水"],
      "channel_preferences": ["品牌旗舰店", "内容种草"],
      "purchase_motivations": ["体验升级", "效率提升"],
      "risk_concerns": ["售后体验", "价格波动"]
    }
  },
  "simulation_params": {
    "simulation_version": "v0.2",
    "sample_size": 10000,
    "random_seed": 123,
    "enable_rag": true,
    "enable_distill_check": true,
    "rag_top_k": 5,
    "distill_sample_size": 100,
    "distill_consistency_threshold": 0.8
  },
  "rag_search_text": "兼容旧逻辑的合并检索文本",
  "rag_search_queries": {
    "product_query": "产品功能、参数、价格检索文本",
    "competitor_query": "竞品对比、价格、规格检索文本",
    "market_query": "人群、场景、渠道、营销检索文本"
  },
  "submitted_at": "2026-05-02T00:00:00Z"
}
```

---

## 6. RAG / 多 Agent / 大模型调用位置

前端不会直接调用 RAG、多 Agent 或大模型 API。

前端只负责：

- 保存产品配置；
- 保存市场配置；
- 触发仿真任务；
- 查询任务进度；
- 展示最终报告。

真正的 RAG、多 Agent、大模型调用发生在 Worker 内部：

```text
POST /api/simulations/{id}/run
  ↓
Redis 入队
  ↓
engine/worker.py 消费任务
  ↓
读取 config_snapshot
  ↓
knowledge_model/rag_service.py 检索 FAISS
  ↓
engine/agent_generator.py 生成消费者 Agent
  ↓
engine/decision_model.py 计算购买意愿
  ↓
engine/aggregation.py 聚合结果
  ↓
engine/distill_client.py 做一致性校验
  ↓
engine/report_generator.py 生成 result_data
```

### 6.1 RAG 查询生成

`rag_search_queries` 在提交阶段由后端根据 `product_definition` 和 `market_config` 生成，包含三类查询；`rag_search_text` 仍保留为旧逻辑兼容字段：

| Query | 作用 |
|---|---|
| `product_query` | 检索产品功能、品类趋势、价格接受度、购买关注点 |
| `competitor_query` | 检索竞品对比、价格差异、参数差异、竞争优势 |
| `market_query` | 检索目标人群、使用场景、营销渠道、转化因素 |

Worker 优先读取快照中的 `rag_search_queries` 执行检索；若旧项目没有该结构，则回退到 `rag_search_text` 动态补齐三类 query。
`crowd_profile` 中的年龄、城市、收入、价格敏感度、功能偏好、渠道偏好和风险顾虑会进入检索文本，因此报告会更清楚地解释“面向谁、为什么这样判断”。

### 6.2 多 Agent 决策

消费者 Agent 通常由以下信息构建：

- 人群模板；
- 城市层级；
- 年龄段；
- 收入水平；
- 价格敏感度；
- 功能偏好；
- 渠道偏好；
- 使用场景。

每个 Agent 对产品输出购买意愿、理由和顾虑，随后聚合为总体购买意愿、市场份额、人群差异和参数重要性。

---

## 7. Redis 的职责

Redis 不保存草稿，也不保存最终报告。Redis 只负责任务运行层：

| Key | 作用 |
|---|---|
| `simulation:queue` | 待执行仿真任务队列 |
| `simulation:project:{project_id}:running` | 防止重复运行同一项目 |
| `simulation:progress:{task_id}` | 任务级实时进度缓存 |
| `simulation:progress:{project_id}` | 项目级进度兼容缓存 |
| `simulation:cancel:{task_id}` | 取消标记 |
| `simulation:heartbeat:{task_id}` | Worker 心跳 |
| `simulation:worker:{worker_id}:heartbeat` | Worker 进程心跳 |

正确理解：

```text
保存草稿 → MySQL
提交快照 → MySQL
开始仿真 → Redis 入队
运行进度 → Redis
最终报告 → MySQL
```

---

## 8. 主要接口

### 8.1 用户与认证

| 方法 | 接口 | 说明 |
|---|---|---|
| POST | `/api/auth/login` | 登录 |
| POST | `/api/auth/register` | 注册 |
| GET | `/api/user/profile` | 获取用户信息 |
| PUT | `/api/user/profile` | 修改用户信息 |
| POST | `/api/user/upgrade` | 升级专业版 |

### 8.2 仿真项目

| 方法 | 接口 | 说明 |
|---|---|---|
| POST | `/api/simulations` | 创建仿真项目 |
| GET | `/api/simulations` | 获取项目列表 |
| DELETE | `/api/simulations/{id}` | 删除项目 |
| GET | `/api/simulations/{id}/draft` | 读取草稿 |
| PUT | `/api/simulations/{id}/draft` | 保存草稿 |
| POST | `/api/simulations/{id}/submit` | 提交配置并生成快照 |
| POST | `/api/simulations/{id}/run` | 启动仿真任务并写入 Redis 队列 |
| GET | `/api/simulations/{id}/progress` | 查询运行进度 |
| DELETE | `/api/simulations/{id}/task` | 取消任务 |
| GET | `/api/simulations/{id}/report` | 获取报告 |

### 8.3 模板与竞品库

| 方法 | 接口 | 说明 |
|---|---|---|
| GET | `/api/categories` | 获取品类列表 |
| GET | `/api/categories/{id}/fields` | 获取子品类字段模板 |
| GET | `/api/products` | 获取产品/竞品列表 |
| GET | `/api/market/crowd-templates` | 获取人群模板 |
| GET | `/api/market/scene-templates` | 获取场景模板 |
| GET | `/api/market/strategy-templates` | 获取策略模板 |

### 8.4 报告、导出与分享

| 方法 | 接口 | 说明 |
|---|---|---|
| POST | `/api/simulations/{id}/export` | 导出报告，建议统一放在导出模块 |
| POST | `/api/simulations/{id}/exports` | 当前前端使用的导出接口，保留兼容 |
| GET | `/api/exports/{export_task_id}` | 查询导出任务 |
| GET | `/api/exports/{export_task_id}/download` | 下载导出文件 |
| POST | `/api/simulations/{id}/share` | 生成分享链接 |
| POST | `/api/simulations/{id}/share-tokens` | 当前前端使用的分享接口，保留兼容 |
| GET | `/api/share/{token}` | 公开访问分享报告 |
| POST | `/api/share/{token}/revoke` | 按 token 撤销分享链接 |

### 8.5 健康检查与调试

| 方法 | 接口 | 说明 |
|---|---|---|
| GET | `/health` | 检查 API、MySQL、Redis、FAISS、小模型 |
| GET | `/api/debug/faiss/status` | 开发环境检查 FAISS |
| GET | `/api/debug/pdf/status` | 开发环境检查 PDF 渲染依赖、前端地址和浏览器内核 |
| POST | `/api/debug/rag/search` | 开发环境测试 RAG |
| POST | `/api/debug/distill/check` | 开发环境测试外部辅助模型一致性接口 |
| GET | `/api/debug/queue/status` | 开发环境检查队列 |

---

## 9. 环境变量

请基于 `.env.example` 创建 `.env`。

示例：

```env
APP_ENV=development
ENABLE_DEBUG_API=true

DATABASE_URL=mysql+pymysql://root:password@127.0.0.1:3306/agentsim
REDIS_URL=redis://127.0.0.1:6379/0

JWT_SECRET_KEY=please_change_me
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

FAISS_INDEX_PATH=knowledge_model/knowledge_base/faiss_index
FAISS_METADATA_PATH=knowledge_model/knowledge_base/faiss_metadata.pkl

LLM_PROVIDER=deepseek
LLM_API_KEY=your_api_key
LLM_MODEL=deepseek-chat
LLM_TIMEOUT_SECONDS=60

ENABLE_RAG=true
ENABLE_DISTILL_CHECK=true
```

---

## 10. 本地启动

### 10.1 启动基础服务

如果使用 Docker：

```bash
docker compose up -d
```

确认 MySQL 和 Redis 已启动。

### 10.2 安装后端依赖

```bash
python -m venv .venv
source .venv/bin/activate  # Windows 可使用 .venv\Scripts\activate
pip install -r requirements.txt
```

### 10.3 初始化数据库与种子数据

```bash
python scripts/env_check.py
python scripts/init_db.py
python scripts/migrate_v24_indexes.py
python scripts/seed_categories.py
python scripts/seed_products.py
python scripts/seed_market_templates.py
python scripts/seed_feature_flags.py
python scripts/check_faiss_rag.py
```

如果需要重建知识库索引：

```bash
python scripts/build_faiss_index.py
```

日常启动不需要每次重建 FAISS。

### 10.4 启动后端 API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

访问：

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/health
```

### 10.5 启动 Worker 与 Monitor

```bash
python engine/worker.py
python engine/monitor.py
```

### 10.6 启动前端

```bash
cd frontend
npm install
npm run dev
```

默认访问：

```text
http://127.0.0.1:5173
```

构建后也可以用项目内的 SPA 静态服务预览：

```bash
cd frontend
npm run build
cd ..
python scripts/serve_frontend.py --host 127.0.0.1 --port 5173 --root frontend/dist
```

---

## 11. 测试与检查

### 11.1 v2.4 预检

```bash
python scripts/v24_preflight.py
```

如果已经启动 API 和前端，可以要求 Web 地址也必须可访问：

```bash
python scripts/v24_preflight.py --require-web
```

### 11.2 单元测试

```bash
pytest
```

### 11.3 服务检查

```bash
python scripts/check_services.py
```

### 11.4 RAG 检查

```bash
python scripts/check_faiss_rag.py
```

### 11.5 前端流程场景测试

```bash
python scripts/run_frontend_scenarios.py --limit 1 --sample-report
python scripts/run_frontend_scenarios.py --limit 1 --run-worker
python scripts/run_frontend_scenarios.py --limit 1 --run-worker --multi-scheme
```

场景脚本会在日志里写入 `acceptance` 和 `v24_contract`，用于检查快照结构、RAG 查询键、报告证据字段、导出、分享脱敏、撤销分享和项目级进度缓存。

### 11.6 正式仿真场景测试

```bash
python scripts/run_formal_scenarios.py
```

### 11.7 长期启动模板

Linux 服务器可参考：

```text
deploy/systemd/agentsim-api.service
deploy/systemd/agentsim-worker.service
deploy/systemd/agentsim-monitor.service
deploy/systemd/agentsim-frontend.service
deploy/nginx/agentsim.conf
```

默认部署目录为 `/opt/agentsim`，运行用户为 `agentsim`。上线时需要先完成 `frontend` 构建，并把 `.env` 中的 `PUBLIC_BASE_URL`、`FRONTEND_BASE_URL`、数据库、Redis、RAG 和蒸馏服务地址改成服务器实际地址。

---

## 12. 任务状态说明

| 状态 | 说明 |
|---|---|
| `draft` | 草稿编辑中 |
| `submitted` | 配置已提交并冻结快照 |
| `running` | Worker 正在执行 |
| `completed` | 仿真完成 |
| `failed` | 失败、取消、超时或 Worker 丢失 |

---

## 13. 普通版与专业版差异

| 功能 | 普通版 | 专业版 |
|---|---|---|
| 产品方案 | 1 个 | 最多 5 个方案对比 |
| 产品参数 | 最多 3 个 | 不限，可自定义 |
| 人群配置 | 使用默认人群 | 可选模板并调整比例 |
| 竞品配置 | 默认/少量竞品 | 多竞品对比 |
| 仿真次数 | 有配额限制 | 理论不限 |
| 报告导出 | 不支持或带限制 | 支持完整导出 |
| 报告分享 | 不支持或受限 | 支持分享链接 |

---

## 14. 开发注意事项

1. 前端不要直接调用 RAG、多 Agent 或大模型 API。
2. Step1 和 Step2 只保存草稿，不进入 Redis 队列。
3. 只有 `/run` 才会创建 Redis 任务。
4. Worker 执行时读取 `config_snapshot`，不要读取实时草稿。
5. RAG 查询文本应在提交阶段生成并写入快照。
6. 竞品选择后建议在 `market_config` 中保存竞品参数快照，避免历史结果受产品库更新影响。
7. 任务进度应同时写 Redis 和持久化日志，避免刷新页面后日志丢失。
8. `.env`、`.venv/`、`node_modules/`、`dist/`、`__pycache__/` 不应提交到 Git。

---

## 15. 后续优化方向

### 市场可信度扩展

- 报告同时输出“仿真环境份额”、5～50 个竞品的情景换算份额和 RCI；情景换算不是销量预测。
- Step2 可选择默认、抖音、天猫、线下高端或自定义五维权重；正式权重冻结进快照。
- 报告提供渠道 what-if、价格数据缺口、营销漏斗桑基图和舆情演化。
- `POST /api/simulations/{id}/what-if` 只做确定性重算，不修改项目或重新调用模型。

新仿真使用 `commercial_differentiation_v1`：策略 ROI、渠道贡献和参数影响由场景、人群、渠道先验、购买驱动与可选成本输入确定性计算，不使用随机扰动强行拉开结果。策略详情可选填基础毛利率、让利比例、单笔推广成本和总预算；未填写时使用专家规则与场景匹配，只有现有成本数据能够证明亏损时才输出具体成本风险。历史冻结报告保持原算法，复制项目并重新运行后使用新版本。

### 产品价格正式迁移

2026-07-28 审核批次包含 366 条价格更新和 3 条无效记录删除。全新或已有数据库统一执行：

```bash
python scripts/migrate_product_prices_20260728.py --apply-db --verify
```

迁移按 `source_file + source_row` 匹配并校验品牌/SKU，不依赖跨环境自增 ID。生产 Compose 会通过 `data-init` 按建表、种子、迁移、完整性检查的顺序自动执行。

2 GB 单机部署默认关闭本地蒸馏模型；核心后端镜像不包含 Chromium、情感模型和 FAISS 备份，PDF 浏览器只存在于 export 镜像。

### 产品Excel与专用测试账号

- `scripts/create_batch_test_user.py` 由管理员幂等创建公开演示Pro测试账号 `123@test`；约定初始密码为 `123456`，创建和登录时仍通过环境变量注入。
- `scripts/batch_product_simulations.py` 支持 `template`、`sample`、`validate`、`compile`、`login-check`、`run`、`resume` 和安全 `cleanup`。
- 批量脚本只在本地运行，通过正式 API 串行提交；启动前强制校验登录用户名、用户ID和Pro状态，项目创建后再次核验归属，不调用注册、升级、PDF或分享接口。
- 非本地 HTTP 默认禁止；只有显式设置 `AGENTSIM_ALLOW_INSECURE_HTTP=true` 才允许连接当前测试站点，正式环境应使用 HTTPS。
- Excel采用测试任务、产品主表、参数明细、证据来源和任务级自由运行配置；模拟资料统一标记为 `synthetic`。`07_校验结果` 只输出关键输入的目标/竞品对照与输入拟合度，格式错误单列于 `08_输入检查`。
- 服务端项目和完整结果保存在专用测试账号；本地批次状态和JSON报告写入 `batch_runs/`，该目录不进入 Git。测试结束后只能通过批次编号确认删除本账号下带测试前缀且已停止的项目。

### 自定义竞品低优先级复用

- 新仿真运行入队后，系统会为冻结快照中的自定义竞品创建幂等回填待办，不影响主仿真提交结果。
- Monitor 默认每 60 秒检查一次；只有在专业版、普通版、兼容和导出队列均为空，且没有仿真运行锁或重资源锁时，才处理一条待办。该流程只查询和写入 MySQL，不调用 RAG、LLM、FAISS 或 PDF；`monitor.py --once` 不执行自定义竞品回填。
- 高度相似判断要求大类和小类一致、品牌相似度达到阈值，并且价格落在配置容差内；命中时复用库内产品，未命中时才新增产品。
- 缺少产品名、品牌、品类或有效价格，品类不在平台字典中，或人工复核状态为 `rejected` 的自定义竞品不会自动入库，原因会记录在待办结果中。
- 已处理项目按 `project_id + snapshot_hash` 幂等，不会因重复运行产生重复待办。删除尚未处理的测试项目时，会同步删除其回填待办；已经成功沉淀的产品保留供后续复用。

历史项目先预览、再按账号入队：

```bash
python scripts/enqueue_historical_custom_competitors.py --username "123@test"
python scripts/enqueue_historical_custom_competitors.py --username "123@test" --apply
```

`--apply` 只创建持久化待办，实际回填仍由 Monitor 在系统空闲时逐条完成。

- 拆分 `app/models.py`、`app/schemas.py` 为更细粒度模块；
- 将 `frontend/src/api.ts` 拆分为 auth、simulation、market、report 等 API 文件；
- 引入 Alembic，替代当前 `create_all` + `scripts/migrate_v24_indexes.py` 的轻量迁移方式；
- 将 Worker 中的仿真主流程拆成 simulator、snapshot_builder、progress_tracker 等模块；
- 增加 `llm_client.py` 统一封装大模型 API；
- 按目标云厂商进一步细化 systemd / nginx / HTTPS 部署参数；
- 对专业版多方案加入更完整的前端编辑与横向对比页面。

---

## 16. 快速排错

| 问题 | 检查项 |
|---|---|
| API 无法启动 | `.env`、数据库连接、依赖是否安装 |
| `/docs` 打不开 | `app.main:app` 路径是否正确 |
| 任务一直不动 | Redis 是否启动，Worker 是否运行 |
| 进度不更新 | `simulation:progress:{project_id}` 是否写入 |
| RAG 返回空 | `faiss_index` 和 `faiss_metadata.pkl` 是否存在 |
| 前端请求 404 | `VITE_API_BASE_URL` 或代理配置是否正确 |
| 报告为空 | Worker 是否成功写入 `simulation_projects.result_data` |
| 导出失败 | 用户版本、导出目录、`export_tasks` 状态 |

---

## 17. 项目一句话说明

Agentsim 是一个以 `product_definition → market_config → config_snapshot → Redis task → Worker simulation → result_data` 为主链路的产品市场仿真平台，核心能力由 RAG 知识检索、多 Agent 消费者决策、指标聚合、结果复核建议和结构化报告生成共同组成。
