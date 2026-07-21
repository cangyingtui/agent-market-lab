# Agentsim 本地初始化指南

以下命令都在 `D:\agentsim` 目录下执行。

## 1. 使用项目虚拟环境

推荐直接使用项目虚拟环境里的 Python：

```powershell
.\.venv\Scripts\python.exe scripts\env_check.py
```

如果你想先激活环境，可以运行：

```powershell
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 提示执行策略限制，不用纠结，继续使用 `.\.venv\Scripts\python.exe` 这种显式路径即可。

## 2. 检查配置和服务

```powershell
.\.venv\Scripts\python.exe scripts\env_check.py
.\.venv\Scripts\python.exe scripts\check_services.py
```

`check_services.py` 里 MySQL 和 Redis 都必须返回 `ok`，再执行数据库初始化。

## 3. 初始化数据库和基础数据

```powershell
.\.venv\Scripts\python.exe scripts\init_db.py
.\.venv\Scripts\python.exe scripts\migrate_v24_indexes.py
.\.venv\Scripts\python.exe scripts\seed_categories.py
.\.venv\Scripts\python.exe scripts\seed_products.py
.\.venv\Scripts\python.exe scripts\seed_market_templates.py
.\.venv\Scripts\python.exe scripts\seed_feature_flags.py
.\.venv\Scripts\python.exe scripts\seed_demo_users.py
```

当前已验证导入结果：

- 品类：64 条
- 字段模板：425 条
- 产品/竞品：947 条
- 人群模板：15 条，已包含年龄、城市、收入、价格敏感、功能偏好、渠道偏好、购买动机和风险顾虑等结构化画像字段
- 策略模板：3 条
- 场景模板：4 条
- 功能开关：5 条
- 演示账号：`pro@example/123456`、`normal@example/123456`

## 4. 检查 FAISS 文件和 RAG 查询

```powershell
.\.venv\Scripts\python.exe scripts\check_faiss_rag.py
```

当前已使用百炼 `text-embedding-v3` 重建完成，索引应显示为 52,887 条、1024 维，并且 metadata 数量匹配。这个脚本还会用四个示例 query 做真实 ANN 检索。

## 5. 重建 FAISS 索引

重建前需要先在 `.env` 中配置同一个 embedding 服务：

```env
EMBEDDING_API_KEY=你的向量服务 key
EMBEDDING_API_BASE=你的向量服务地址
EMBEDDING_MODEL=你的向量模型名称
EMBEDDING_DIM=向量维度
```

如果使用百炼 `text-embedding-v3`，不要填写 384 维。该模型支持 64、128、256、512、768、1024，当前项目默认使用 1024。切换维度后必须重建 FAISS，因为查询向量维度必须和索引维度一致。

百炼兼容接口单批最多 10 条文本，所以 `scripts/build_faiss_index.py` 默认使用 `--batch-size 10`。全量重建约 52,887 条文本，大约会产生 5,289 次 embedding 请求。

全量重建支持断点续建。脚本会把每批向量缓存到 `knowledge_model/knowledge_base/faiss_vector_cache/`，如果中途超时或中断，重新运行同一条命令会跳过已完成批次。只有所有向量缓存完整后，才会备份旧索引并替换正式 `faiss_index`。

建议先用小样本验证。下面这条命令只验证 embedding API 和维度，不会覆盖正式索引：

```powershell
.\.venv\Scripts\python.exe scripts\build_faiss_index.py --limit 20 --batch-size 10
```

如果你想把小样本索引写到单独文件，可以使用：

```powershell
.\.venv\Scripts\python.exe scripts\build_faiss_index.py --limit 20 --batch-size 10 --output-index-path knowledge_model/knowledge_base/faiss_index.test
```

确认没问题后再全量重建：

```powershell
.\.venv\Scripts\python.exe scripts\build_faiss_index.py
.\.venv\Scripts\python.exe scripts\check_faiss_rag.py
```

注意：`LLM_API_KEY` 是给 DeepSeek 聊天、报告生成等大模型调用使用；`EMBEDDING_API_KEY` 是给 RAG 的向量化和 FAISS 检索使用。两者不是同一个概念。

如果 `EMBEDDING_API_BASE=https://api.deepseek.com/v1` 并返回 404，说明当前服务不支持 OpenAI-compatible `/embeddings` 接口或模型名不存在。此时需要换一个真正支持 embedding 的服务，例如 OpenAI embedding、硅基流动/阿里云等兼容 embedding 的服务，或你自己本地启动的 embedding 服务。只要建库和查询使用同一个 embedding 模型即可。

## 6. 启动后端 API

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

启动后可以打开：

- `http://127.0.0.1:8000/docs`：接口调试页面
- `http://127.0.0.1:8000/health`：健康检查

API 当前统一返回：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

过渡期响应里仍保留旧字段镜像，所以之前的调试脚本大多还能继续使用；前端已优先读取 `data`。

当前已实现的主要接口：

- `/health`
- `/api/categories`
- `/api/categories/{id}/fields`
- `/api/products`
- `/api/products/{id}`
- `/api/market/templates`
- `/api/debug/faiss/status`
- `/api/debug/pdf/status`
- `/api/debug/rag/search`
- `/api/debug/distill/check`
- `/api/debug/queue/status`
- `/api/auth/register`
- `/api/auth/login`
- `/api/auth/me`
- `/api/user/profile`（GET/PUT）
- `/api/simulations`
- `/api/simulations/{id}/step1`
- `/api/simulations/{id}/step2`
- `/api/simulations/{id}/submit`
- `/api/simulations/{id}/run`
- `/api/simulations/{id}/progress`
- `/api/simulations/{id}/logs`
- `/api/simulations/{id}/cancel`
- `/api/simulations/{id}/report`
- `/api/simulations/{id}/draft`
- `/api/simulations/{id}/task`
- `/api/simulations/{id}/exports`
- `/api/simulations/{id}/export`（v2.4 兼容别名）
- `/api/exports/{export_task_id}`
- `/api/exports/{export_task_id}/download`
- `/api/simulations/{id}/share-tokens`
- `/api/simulations/{id}/share`（v2.4 兼容别名）
- `/api/share-tokens/{share_token_id}`
- `/api/share/{token}`
- `/api/share/{token}/revoke`

## 7. 启动前端工作台

前端代码在 `frontend/`，使用 React + Vite + TypeScript，并已接入 Ant Design、ECharts 和 React Router。当前页面风格已对齐旧设计：顶部“智测”导航、个人主页 Dashboard、普通/专业版测试账号切换、四步进度条、左侧主内容 + 右侧辅助面板、Step1 大品类/小品类和点击式参数添加、Step3 队列与 Worker 状态、运行日志、Step4 报告页签和图表。当前这台机器已安装 Node.js，已执行过 `npm install` 和 `npm run build`。

Step2 的人群设置已经从“只选一个人群名称”升级为结构化画像：

- 普通版：目标人群模板、价格敏感度、最多 3 个功能偏好、补充描述。
- 专业版：年龄段、城市层级、收入水平、职业/家庭阶段、价格敏感度、功能优先级、渠道偏好、购买动机、风险顾虑和补充描述。

保存时仍保留 `market_config.target_crowd`，同时新增 `market_config.crowd_profile`。旧项目没有 `crowd_profile` 也能继续运行，后端会按目标人群名称生成默认画像。

启动开发服务器：

```powershell
cd frontend
npm install
npm run dev
```

默认开发地址：

```text
http://127.0.0.1:5173
```

个人主页位于：

```text
http://127.0.0.1:5173/projects
```

个人主页会显示头像占位、账号昵称、会员版本、剩余仿真次数、新建仿真、快捷入口和历史项目列表。历史项目按钮会按状态跳转：未提交继续编辑，运行中查看进度，已完成查看报告，失败项目进入修改重试。

如需构建生产包：

```powershell
cd frontend
npm run build
```

如果新开的 PowerShell 里 `node` 或 `npm` 仍然识别不到，重开终端；或者临时使用完整路径：

```powershell
$env:Path="C:\Program Files\nodejs;$env:Path"
```

## 8. 启动 Worker

持续消费队列：

```powershell
.\.venv\Scripts\python.exe -m engine.worker
```

调试时只消费一个任务：

```powershell
.\.venv\Scripts\python.exe -m engine.worker --once --timeout 3
```

Worker 会消费 Redis 队列，写入心跳和进度，执行三类分层 evidence 检索、Agent 生成、购买决策、聚合和报告生成，并把结果写回数据库。

提交时生成的 `config_snapshot` 现在包含 `snapshot_id`、`snapshot_hash`、`user_id`、`submitted_at`、`simulation_params` 和结构化 `rag_search_queries`。旧字段 `rag_search_text` 仍保留为兼容合并文本；Worker 优先读取 `rag_search_queries.product_query / competitor_query / market_query`，旧项目缺少结构化字段时会自动回退。

如果页面一直停在“排队中”或“等待 Worker”，通常不是后端 API 断开，而是 Redis 队列里有任务但没有 Worker 消费。此时 Step3 的队列状态卡会显示队列长度和 Worker 心跳；另开终端启动 Worker 后刷新即可。

当前 Worker 已经接入 DeepSeek 报告生成。正常情况下会生成包含以下字段的报告 JSON：

- `executive_summary`
- `target_segments`
- `competitor_insights`
- `pricing_analysis`
- `strategy_recommendations`
- `risk_warnings`
- `evidence_used`

如果 DeepSeek 调用失败，Worker 不会直接把任务标记失败，而是保留 RAG 和产品 evidence，写入 fallback 报告，并在 `fallback_reason` 中记录原因。

报告中还会额外保留：

- `structured_product_evidence`：MySQL 产品表生成的结构化竞品证据
- `user_profile_evidence`：FAISS 用户画像证据，会附带价格敏感、功能关注、品类偏好等标签
- `market_strategy_evidence`：后续用于市场策略分析的证据组
- `rag_summary` / `evidence_sources` / `insight_evidence_map`：三类 RAG 检索的最终证据摘要和报告段落引用关系
- `agent_samples`：虚拟消费者 Agent 样本
- `purchase_decisions`：每个 Agent 的购买意愿、驱动因素和阻碍因素
- `decision_model`：MAUT 五维购买模型、权重、维度均值和结果置信度
- `aggregation`：购买意愿均值、人群差异、价格敏感度、竞品优势、风险和置信度摘要
- `model_validation`：外部辅助模型一致性校验结果，默认关闭时会返回 disabled 标准结构
- `prompt_trace`：报告、决策、聚合等模块的 prompt 版本和模型调用摘要
- `formal_test_log_path`：本次运行的文件日志路径
- `quality_warnings`：报告质量检查提示，例如竞品价格缺失、缺少 evidence 引用等
- `chart_data`：前端和导出直接使用的图表数据，包含市场份额、购买意愿、价格敏感、功能重要性、策略 ROI 等；专业版还会包含竞品雷达和敏感性瀑布图

如果 embedding API 临时连接失败，Worker 会写入 `rag_error` 降级证据，并尽量继续使用 MySQL 产品 evidence、Agent fallback 决策和 fallback 报告完成任务。这样可以保证前端、导出和图表数据仍能用于调试；正式评估报告质量时，需要同时查看 `quality_warnings` 和运行日志里的 RAG 警告。

外部辅助小模型当前默认关闭，只保留 HTTP 服务接口位：

```env
ENABLE_DISTILL_CHECK=false
DISTILL_API_BASE=
DISTILL_API_KEY=
DISTILL_TIMEOUT_SECONDS=10
```

主项目不会安装 `torch`、`transformers`、`sentence-transformers`。后续小模型服务准备好后，可以在购买决策之后、聚合和报告生成之前做内部一致性检查；当前业务前端只展示结果置信度和复核建议，不展示模型训练相关术语。

如果设置 `ENABLE_DISTILL_CHECK=true` 且配置 `DISTILL_API_BASE`，Worker 会调用外部服务 `/consistency-check`，标准化写入 `model_validation`，并把样本明细写入 `distill_check_logs`。开发环境可用 `/api/debug/distill/check` 做接口预检。

启动 Worker 监控器：

```powershell
.\.venv\Scripts\python.exe -m engine.monitor
```

监控器会扫描运行锁和 heartbeat。若任务心跳丢失或运行超时，会标记项目 `failed`，写入 `WORKER_LOST` 或 `TASK_TIMEOUT`，释放锁，并回滚普通版配额。

## 9. 调试 RAG 和报告

FAISS 当前主要是用户画像数据；产品和竞品证据来自 MySQL `products` 表。调试时可以用下面接口同时看两类证据：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/debug/rag/search `
  -ContentType application/json `
  -Body '{"query":"高端智能手机 电池 价格","top_k":5,"include_products":true,"product_definition":{"category":"消费电子","subcategory":"智能手机","price_cny":4999}}'
```

任务完成后查看报告：

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/simulations/你的项目ID/report `
  -Headers @{Authorization="Bearer 你的登录token"}
```

## 10. 导出和分享报告

任务完成后，专业版用户可以导出 JSON、Markdown、Excel 或 PDF：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/simulations/你的项目ID/exports `
  -Headers @{Authorization="Bearer 你的登录token"} `
  -ContentType application/json `
  -Body '{"format":"excel"}'
```

v2.4 兼容别名 `/api/simulations/{id}/export` 也可使用，返回结构与 `/exports` 相同。

查询导出状态：

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/exports/导出任务ID `
  -Headers @{Authorization="Bearer 你的登录token"}
```

下载导出文件：

```powershell
Invoke-WebRequest `
  -Uri http://127.0.0.1:8000/api/exports/导出任务ID/download `
  -Headers @{Authorization="Bearer 你的登录token"} `
  -OutFile report.md
```

导出文件默认写到：

```text
logs/exports/
```

普通版用户只能在线查看报告；导出会返回 `EXPORT_FORBIDDEN`。专业版项目导出的 Excel 会包含图表数据工作表，例如 `图表_概览指标`、`图表_市场份额`、`图表_购买意愿`、`图表_功能重要性`、`图表_价格敏感`、`图表_策略ROI`、`图表_渠道贡献`、`图表_竞品雷达`。PDF 使用前端打印路由和 Playwright/Chromium 渲染；如果浏览器内核未安装或前端服务不可访问，导出任务会返回 `pdf_render_failed`。

PDF 导出依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install playwright
.\.venv\Scripts\python.exe -m playwright install chromium
```

如果不想把浏览器内核装到用户缓存目录，可以在命令前设置 `PLAYWRIGHT_BROWSERS_PATH=d:\agentsim\.playwright-browsers`。

检查 PDF 环境：

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/debug/pdf/status
```

这个接口会返回前端地址是否可访问、Playwright 是否可导入、项目内浏览器目录等信息。若 PDF 导出失败，`/api/exports/{导出任务ID}` 的 `error_reason` 会尽量给出可读原因，例如前端服务未启动、浏览器内核未安装或浏览器启动被系统权限拒绝。JSON、Markdown、Excel 不依赖浏览器内核，因此 PDF 失败不会影响其他格式。

Excel 和 Markdown 导出已经对图表行数据做了清洗：如果某个图表数据里混入字符串、数组或空值，会转成可读的“value”列或“暂无数据”，避免出现类似 `'str' object has no attribute 'keys'` 的导出失败。

分享接口会同时返回：

- `frontend_share_url`：前端公开报告页，形如 `http://127.0.0.1:5173/share/{token}`。
- `api_share_url`：后端 JSON 接口，形如 `http://127.0.0.1:8000/api/share/{token}`。

前端按钮默认展示和复制前端公开报告页链接。

创建分享链接：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/simulations/你的项目ID/share-tokens `
  -Headers @{Authorization="Bearer 你的登录token"} `
  -ContentType application/json `
  -Body '{"expires_in_hours":72}'
```

v2.4 兼容别名也可使用：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/simulations/你的项目ID/share `
  -Headers @{Authorization="Bearer 你的登录token"} `
  -ContentType application/json `
  -Body '{"expires_in_hours":72}'
```

关闭分享链接：

```powershell
Invoke-RestMethod -Method Delete `
  -Uri http://127.0.0.1:8000/api/share-tokens/分享ID `
  -Headers @{Authorization="Bearer 你的登录token"}
```

如果只拿到了分享 token，也可以使用登录态撤销：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/share/分享token/revoke `
  -Headers @{Authorization="Bearer 你的登录token"}
```

公开报告接口无需登录：

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/share/分享token
```

分享报告只返回脱敏后的只读报告，不暴露用户信息、API key、prompt 原文、内部文件日志路径。

## 11. 运行测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

当前测试覆盖健康检查、统一响应、品类、产品、市场模板、FAISS 状态、注册登录、用户资料更新、仿真草稿、draft_version 冲突、v2.4 快照字段、项目级进度缓存、提交、入队、配额扣减/回滚、Worker 成功/取消/失败、monitor 心跳丢失、结构化竞品 evidence、fallback 报告、正式仿真模块、报告导出、导出/分享别名、分享 token 撤销、多方案结果结构和外部辅助模型接口默认关闭。测试不会主动调用 embedding API 或 DeepSeek。

当前还覆盖了结构化人群画像保存、画像关键词进入 RAG 检索文本、Agent 读取画像字段、报告和导出包含目标人群画像、PDF 预检状态、以及导出行数据清洗。

测试会自动清理 `pytest_` 开头的用户、项目、日志和 Redis key。若之前手动测试留下了 `smoke_`、`worker_`、`e2e_` 等测试用户，可以运行：

```powershell
.\.venv\Scripts\python.exe scripts\cleanup_test_data.py
```

## 12. 检查数据质量

```powershell
.\.venv\Scripts\python.exe scripts\check_data_quality.py
```

这个脚本只读数据库，不会改数据。它会输出产品总数、有产品名数量、有价格数量、规格缺失率、主要子品类和高频规格字段。

当前已知情况是产品价格缺失较多，所以报告里的价格分析会偏保守；Worker 会在报告中提示价格数据不完整。

若要生成“待补全产品候选清单”，可运行：

```powershell
.\.venv\Scripts\python.exe scripts\generate_data_enrichment_candidates.py --limit 100
```

输出目录：

```text
logs/data_enrichment_candidates/
```

该脚本只生成候选 JSONL，不联网，不改正式 `products` 表。后续若接搜索 API，应先写入候选补全记录并保留来源 URL、置信度和人工确认状态，再决定是否覆盖正式产品字段。

## 13. 避免 PowerShell 中文乱码

PowerShell 的 inline Python 脚本里直接写中文，有时会被控制台编码成 `????`。如果只是通过 API 或代码文件传中文，一般没有问题。调试时建议：

```powershell
chcp 65001
$env:PYTHONUTF8=1
```

或者在临时 Python 脚本里使用 Unicode 转义，例如 `\u667a\u80fd\u624b\u673a` 表示“智能手机”。

## 14. 运行正式功能场景

下面命令会跑 4 个内置正式场景：高端智能手机、电动牙刷、户外帐篷、护理床。它会真实走 API、Redis、Worker、RAG、Agent、购买决策、聚合和报告生成。

```powershell
.\.venv\Scripts\python.exe scripts\run_formal_scenarios.py
```

只跑前 1 个场景：

```powershell
.\.venv\Scripts\python.exe scripts\run_formal_scenarios.py --limit 1
```

指定日志目录：

```powershell
.\.venv\Scripts\python.exe scripts\run_formal_scenarios.py --run-dir logs/formal_runs/my_test
```

每次运行会生成：

- `summary.jsonl`：每个任务一行，方便快速横向比较
- `formal_summary.json`：本次场景总览
- 单场景 JSON：包含配置快照、RAG evidence 摘要、Agent 样本、购买决策、聚合、prompt trace、报告和质量提示

日志会保存 prompt 摘要和模型返回截断内容，便于你观察报告问题并调整 prompt；不会保存 API key。

## 15. 运行前端流程返回日志

如果你想观察“前端页面主流程对应的接口返回”，使用下面命令。它会走注册/登录、创建项目、Step1、Step2、submit、run、progress、logs、report、export、share，并把返回摘要单独保存。

快速验证导出和分享，不调用 LLM：

```powershell
.\.venv\Scripts\python.exe scripts\run_frontend_scenarios.py --limit 1 --sample-report
```

真实消费 Worker，生成真实报告：

```powershell
.\.venv\Scripts\python.exe scripts\run_frontend_scenarios.py --limit 1 --run-worker
```

追加一个多方案场景：

```powershell
.\.venv\Scripts\python.exe scripts\run_frontend_scenarios.py --limit 1 --run-worker --multi-scheme
```

日志目录：

```text
logs/frontend_runs/YYYYMMDD_HHMMSS/
```

每次运行会生成：

- `summary.jsonl`：每个前端流程场景一行，方便快速看状态、导出任务、分享链接和报告质量提示。
- `scenario_*.json`：单场景详细返回摘要，包括 progress、运行日志、report 摘要、`chart_data_summary`、`public_report_text`、导出文件本地路径和分享链接。

`summary.jsonl` 和单场景 JSON 还会写入：

- `acceptance`：上线前关键验收项，包括 completed、导出、分享脱敏、快照契约、报告契约、项目级进度缓存和多方案对比。
- `v24_contract`：快照字段、RAG query key、RAG trace、distill log、task log、share token 和公开报告安全检查摘要。

`chart_data_summary` 会保存市场份额合计、价格敏感曲线、功能重要性数量、是否包含竞品雷达和敏感性瀑布图，方便你判断前端图表是否有足够数据。`public_report_text` 是可直接阅读的公开报告摘要，不需要打开网页。日志不会保存 API key、登录 token、密码、prompt 原文和内部 prompt trace。`--sample-report` 生成的报告只用于验证前端接口和日志结构；要评估真实 prompt 和报告质量，请使用 `--run-worker` 或 `scripts/run_formal_scenarios.py`。

## 16. v2.4 自主 debug 流程

先跑本地预检：

```powershell
.\.venv\Scripts\python.exe scripts\v24_preflight.py
```

如果 API 和前端已经启动，要求 Web 地址也必须可访问：

```powershell
.\.venv\Scripts\python.exe scripts\v24_preflight.py --require-web
```

排查顺序建议固定为：

1. `scripts\check_services.py`：MySQL / Redis。
2. `scripts\check_faiss_rag.py`：FAISS、metadata、embedding 维度和检索。
3. `http://127.0.0.1:8000/health`：API、MySQL、Redis、FAISS、蒸馏配置。
4. `/api/debug/queue/status`：队列长度、progress key、heartbeat、Worker 是否在线。
5. `/api/simulations/{id}/progress`：单项目进度和卡住原因。
6. `/api/debug/rag/search`：指定 query 检查产品 evidence 和 FAISS evidence。
7. `/api/debug/pdf/status`：PDF 依赖、前端地址、浏览器内核。
8. `/api/debug/distill/check`：队友蒸馏服务联调预检。

任务卡住时，优先看 Worker 窗口、Monitor 窗口、`simulation:worker:*:heartbeat`、`simulation:progress:*` 和项目状态。报告质量异常时，优先看 `rag_trace_logs`、`result_data.rag_summary`、`evidence_sources`、`insight_evidence_map`、`quality_warnings`。

## 17. 知识蒸馏联调约定

队友交付外部蒸馏服务后，至少需要提供：

- `GET /health`
- `POST /consistency-check`

主项目 `.env` 示例：

```env
ENABLE_DISTILL_CHECK=true
DISTILL_API_BASE=http://127.0.0.1:9000
DISTILL_API_KEY=
DISTILL_TIMEOUT_SECONDS=10
```

联调步骤：

1. 先直接访问 `DISTILL_API_BASE/health`。
2. 再调用 `POST http://127.0.0.1:8000/api/debug/distill/check`。
3. 再跑 `.\.venv\Scripts\python.exe scripts\run_frontend_scenarios.py --limit 1 --run-worker`。
4. 检查报告里的 `model_validation`，以及数据库 `distill_check_logs` 是否写入样本级记录。

主项目仍不安装 `torch`、`transformers` 或本地重模型依赖。

## 18. 远程服务器长期启动

Linux 服务器建议把代码放在 `/opt/agentsim`，创建 `agentsim` 用户，使用 systemd 托管：

```text
deploy/systemd/agentsim-api.service
deploy/systemd/agentsim-worker.service
deploy/systemd/agentsim-monitor.service
deploy/systemd/agentsim-frontend.service
```

安装模板：

```bash
sudo cp deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now agentsim-api agentsim-worker agentsim-monitor agentsim-frontend
sudo systemctl status agentsim-api agentsim-worker agentsim-monitor agentsim-frontend
```

如果使用 nginx 对外暴露，可参考：

```text
deploy/nginx/agentsim.conf
```

上线前必须执行：

```bash
cd /opt/agentsim
source .venv/bin/activate
python scripts/v24_preflight.py --require-web
python scripts/check_services.py
python scripts/check_faiss_rag.py
python -m pytest -q
cd frontend && npm run build
```

前端构建后，如果不用 nginx 静态目录，也可以用项目内 SPA 静态服务：

```bash
python scripts/serve_frontend.py --host 0.0.0.0 --port 5173 --root frontend/dist
```

如果远程服务器是 Windows，长期启动建议改用 NSSM 或计划任务分别守护 API、Worker、Monitor 和前端静态服务。
