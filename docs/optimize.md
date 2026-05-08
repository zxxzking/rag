# RAG 服务企业级生产可用优化方案

## 1. 背景

当前项目已经具备基础 RAG 后端闭环，包括用户认证、文档上传、文档摄取、向量化入库、混合检索、重排序、普通问答、SSE 流式问答、文档状态管理和会话列表管理。

但从企业生产级 RAG 服务的角度看，当前系统仍更接近内部原型或 PoC。它已经能证明核心链路可行，但在权限隔离、数据治理、任务可靠性、可观测性、安全配置、测试保障和运维能力方面还不完整。

本文档用于梳理当前项目距离企业级可用的主要差距，并给出分阶段、可执行的优化方案。

## 2. 企业级目标定义

企业级 RAG 服务至少应满足以下目标：

1. 用户只能检索自己有权限访问的文档内容。
2. 文档上传、解析、索引、删除、重建过程具备可靠状态和失败恢复能力。
3. 系统能够支持部门、角色、密级、知识库等多维度隔离。
4. 聊天记录、检索来源、引用文档和关键操作可以审计。
5. 服务配置、密钥、模型地址、存储地址可按环境切换。
6. 检索质量和回答质量可评估、可调优、可回归测试。
7. 系统具备基础监控、日志、错误追踪和健康检查。
8. 具备自动化测试与上线前验证流程。

## 3. 当前差距总览

| 模块 | 当前状态 | 企业级差距 | 优先级 |
|---|---|---|---|
| 用户权限 | 只有 `admin/user` 角色 | 缺少文档级、部门级、密级权限 | P0 |
| 检索安全 | 查询时未做文档权限过滤 | 有越权检索风险 | P0 |
| 文档管理 | 支持上传和状态记录 | 缺少删除、重建、权限变更、版本管理 | P0 |
| 会话管理 | 只有会话列表 | 缺少完整消息历史和引用记录 | P1 |
| 摄取任务 | 同步执行为主 | 缺少异步任务、重试、进度、取消 | P1 |
| 数据一致性 | SQLite、Chroma、Redis、BM25 分散 | 缺少事务边界和补偿机制 | P1 |
| 多知识库 | 默认单 collection | 缺少多知识库、多租户隔离策略 | P1 |
| 审计日志 | 基本无审计 | 无法追踪用户行为和数据访问 | P1 |
| 安全配置 | CORS 宽松，默认配置偏开发 | 缺少生产安全基线 | P0 |
| 运维监控 | 只有简单健康检查 | 缺少指标、链路、错误、资源监控 | P2 |
| 测试保障 | 自动化测试不足 | 缺少权限、接口、摄取、检索回归测试 | P1 |

## 4. 第一阶段：安全与权限底座

### 4.1 文档权限模型

目标：每个文档和每个向量 chunk 都带有可检索过滤的权限 metadata。

建议在 `documents` 表增加字段：

```sql
owner_username TEXT,
access_level INTEGER NOT NULL DEFAULT 1,
department TEXT,
allowed_roles TEXT,
visibility TEXT NOT NULL DEFAULT 'public'
```

字段含义：

- `owner_username`：文档上传者或归属人。
- `access_level`：文档密级，例如 `1` 公开、`2` 内部、`3` 管理员。
- `department`：部门标识。
- `allowed_roles`：允许访问的角色列表，可先用 JSON 字符串保存。
- `visibility`：公开范围，例如 `public`、`department`、`private`、`role_based`。

同时，在文档摄取生成 node 时，将这些字段写入 node metadata：

```python
node.metadata["owner_username"] = owner_username
node.metadata["access_level"] = access_level
node.metadata["department"] = department
node.metadata["allowed_roles"] = allowed_roles
node.metadata["visibility"] = visibility
node.metadata["doc_id"] = doc_id
```

验收标准：

- 上传文档时可以指定访问级别。
- 文档状态列表能展示权限信息。
- Chroma 中的向量 metadata 包含权限字段。
- 未授权用户无法通过检索拿到高权限文档 chunk。

### 4.2 检索阶段权限过滤

目标：查询前根据当前用户构造检索过滤条件，避免越权召回。

推荐策略：

1. 普通用户只能检索 `access_level <= 用户级别` 的文档。
2. 用户只能检索自己部门可见或公开文档。
3. admin 可以检索全部文档。
4. 检索过滤应在向量库召回阶段执行，而不是生成回答后再过滤。

示例逻辑：

```text
admin:
  不限制 access_level

普通用户:
  access_level <= user.access_level
  AND (
    visibility = public
    OR owner_username = current_user
    OR department = current_user.department
    OR allowed_roles 包含 current_user.role
  )
```

如果继续使用 Chroma，需要基于 LlamaIndex metadata filter 能力接入过滤条件。若 Chroma 当前过滤能力不能满足复杂条件，应将第一阶段权限模型控制在简单可落地的范围内，例如先只做 `access_level <= user.access_level`。

验收标准：

- 用普通用户检索 admin 文档，结果为空。
- 用 admin 检索同一问题，可以召回 admin 文档。
- SSE 和非 SSE 两种问答都走同一套权限过滤。
- source 返回结果不会泄漏无权限文档名称和片段。

### 4.3 用户模型增强

目标：用户不仅有角色，还应具备企业权限属性。

建议在 `users` 表增加字段：

```sql
department TEXT,
access_level INTEGER NOT NULL DEFAULT 1,
created_by TEXT,
last_login_at TEXT
```

同时新增或调整接口：

- admin 创建用户。
- admin 修改用户角色、部门、密级。
- admin 禁用用户。
- 普通用户只能修改自己的基础资料，不能修改角色和密级。

验收标准：

- admin 可以维护用户权限属性。
- 普通用户无法提权。
- JWT 中可以包含必要的角色信息，但服务端仍以数据库最新用户信息为准。

## 5. 第二阶段：文档生命周期治理

### 5.1 文档删除与索引清理

目标：删除文档时同时清理 SQLite 记录、Chroma 向量、Redis docstore/index store、BM25 数据和本地原文件。

建议新增接口：

```text
DELETE /api/docs/{doc_id}
```

删除流程：

```text
权限校验 -> 标记 deleting -> 删除向量数据 -> 删除 docstore/index 数据
-> 删除 BM25 相关数据 -> 删除原文件/图片 -> 删除或标记 SQLite 文档记录
```

验收标准：

- 删除后文档不再出现在文档列表。
- 删除后检索不会召回该文档内容。
- 任意一步失败时保留错误状态，方便重试。

### 5.2 文档重建索引

目标：支持单文档重新解析和向量化，避免每次 reset 全库。

建议新增接口：

```text
POST /api/docs/{doc_id}/reindex
```

验收标准：

- 单文档可以重新摄取。
- 重建过程中状态从 `processing` 到 `completed` 或 `failed`。
- 重建失败不影响其他文档。

### 5.3 文档版本管理

目标：同名文件重复上传时可以追踪版本，而不是简单覆盖。

建议新增字段：

```sql
version INTEGER NOT NULL DEFAULT 1,
checksum TEXT,
is_active INTEGER NOT NULL DEFAULT 1
```

验收标准：

- 同一文档可以保留多个版本。
- 默认只检索 active 版本。
- 可回滚到指定版本。

## 6. 第三阶段：会话历史与审计

### 6.1 聊天消息表

目标：完整保存每轮用户问题、模型回答、引用来源和模型参数。

建议新增表：

```sql
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    username TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    sources TEXT DEFAULT '[]',
    model TEXT,
    knowledge_bool INTEGER NOT NULL DEFAULT 0,
    temperature REAL,
    max_tokens INTEGER,
    created_at TEXT NOT NULL
);
```

建议索引：

```sql
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created
ON chat_messages(session_id, created_at);
```

验收标准：

- `/api/chat/history` 可以返回完整历史。
- 清空会话会清理对应消息。
- 每次回答保存 source 列表，便于复盘。

### 6.2 审计日志

目标：记录关键操作，满足企业内部追踪要求。

建议新增表：

```sql
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    detail TEXT DEFAULT '{}',
    ip_address TEXT,
    user_agent TEXT,
    created_at TEXT NOT NULL
);
```

需要记录的事件：

- 登录成功/失败。
- 上传文档。
- 删除文档。
- 修改文档权限。
- 检索问答。
- reset。
- 用户创建、禁用、权限变更。

验收标准：

- 高风险接口全部写入审计日志。
- admin 可以按用户、时间、操作类型查询审计日志。

## 7. 第四阶段：摄取任务可靠性

### 7.1 异步任务化

目标：上传文件后立即返回任务 ID，由后台任务执行解析、切分、向量化。

建议新增表：

```sql
CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL UNIQUE,
    doc_id TEXT NOT NULL,
    status TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    error TEXT DEFAULT '',
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

接口建议：

```text
POST /api/docs/upload      -> 返回 job_id
GET  /api/docs/jobs/{id}   -> 查询任务状态
POST /api/docs/jobs/{id}/retry
POST /api/docs/jobs/{id}/cancel
```

验收标准：

- 大文件上传不会长时间阻塞 HTTP 请求。
- 解析失败可以重试。
- 前端可以看到处理进度和失败原因。

### 7.2 一致性补偿

目标：避免 SQLite 记录显示成功，但向量库或 docstore 部分失败。

建议引入状态机：

```text
uploaded -> parsing -> chunking -> embedding -> indexing -> completed
                                 -> failed
                                 -> deleting
```

每个阶段都写入状态和错误信息。失败后支持基于 `doc_id` 清理残留数据再重试。

验收标准：

- 任一阶段失败都能定位原因。
- 重试前可以清理该文档残留索引。
- reset 不再是唯一恢复手段。

## 8. 第五阶段：多知识库与隔离策略

### 8.1 collection 策略

当前默认使用单个 Chroma collection。企业场景可以选择两种方案：

方案 A：单 collection + metadata filter

- 优点：维护简单，跨权限聚合检索方便。
- 缺点：强依赖 metadata filter 正确性。
- 适合：中小规模、权限模型相对简单。

方案 B：多 collection

- 优点：物理或逻辑隔离更清晰。
- 缺点：检索时需要 fan-out 到多个 collection，再合并排序。
- 适合：多租户、强隔离、不同部门知识库独立管理。

建议当前项目优先采用：

```text
第一步：单 collection + access_level metadata filter
第二步：增加 knowledge_base_id
第三步：必要时再演进到多 collection
```

### 8.2 多 collection 检索

如果后续采用多 collection，admin 查询时可以按权限选择多个 collection：

```text
普通用户:
  检索 public_collection + department_collection + own_private_collection

admin:
  检索 level_1_collection + level_2_collection + level_3_collection
```

检索合并流程：

```text
根据用户权限选择 collections
-> 每个 collection 独立检索 top_k
-> 合并候选 nodes
-> 全局 rerank
-> 截取最终 top_n
-> 生成回答
```

验收标准：

- admin 可以跨多个 collection 检索。
- 普通用户只能访问授权 collection。
- 合并后的结果统一 rerank，避免不同 collection 分数不可比。

## 9. 第六阶段：生产安全基线

### 9.1 配置安全

需要调整：

- 禁止生产环境使用默认 JWT secret。
- 禁止生产环境使用默认 admin 密码。
- CORS 改为明确域名白名单。
- `.env` 不进入 Git。
- 敏感配置通过环境变量或密钥管理系统注入。

验收标准：

- 启动时检测弱密钥和默认密码，生产模式直接拒绝启动。
- CORS 只允许配置中的前端域名。

### 9.2 接口安全

需要增加：

- 登录失败次数限制。
- 上传文件大小限制。
- 上传文件类型白名单。
- 文件名安全处理。
- API 访问频率限制。
- 高风险接口二次确认或强权限校验。

验收标准：

- 非白名单文件无法上传。
- 超大文件被明确拒绝。
- 高频请求被限流。

## 10. 第七阶段：可观测性与运维

### 10.1 健康检查增强

当前 `/api/health` 只返回静态状态。建议拆分：

```text
GET /api/health/live
GET /api/health/ready
```

`ready` 应检查：

- SQLite 可连接。
- Chroma 可访问。
- Redis 可访问。
- Ollama 或 LLM 服务可访问。
- embedding/rerank 模型路径可用。

### 10.2 日志与指标

建议记录：

- 每次请求耗时。
- 检索耗时。
- rerank 耗时。
- LLM 生成耗时。
- 上传文件大小和处理耗时。
- 召回文档数量。
- 异常堆栈和错误码。

验收标准：

- 可以定位慢查询发生在哪个阶段。
- 可以统计每天上传量、问答量、失败率。

## 11. 第八阶段：测试与质量评估

### 11.1 自动化测试

建议补齐：

- 用户注册、登录、禁用测试。
- admin 权限测试。
- 文档上传测试。
- 权限过滤测试。
- 普通问答测试。
- SSE 流式问答测试。
- reset/delete/reindex 测试。

### 11.2 RAG 质量评估

建议准备固定评测集：

```text
问题
期望答案要点
期望引用文档
允许访问级别
```

验收标准：

- 每次改动后可以跑一组固定问题。
- 召回文档和答案质量可以量化比较。

## 12. 推荐实施路线

### 阶段 A：必须先做

1. 用户表增加 `department`、`access_level`。
2. 文档表增加权限字段。
3. 上传接口支持文档权限参数。
4. 摄取时写入 node metadata。
5. 查询时增加 metadata filter。
6. SSE 和普通问答统一权限过滤。
7. CORS、JWT secret、默认 admin 安全检查。

阶段 A 完成后，系统可以进入受控内部试用。

### 阶段 B：生产可用核心

1. 新增聊天消息表。
2. 新增审计日志表。
3. 新增文档删除接口。
4. 新增单文档重建索引。
5. 摄取任务状态机。
6. 自动化测试覆盖核心接口。

阶段 B 完成后，系统可以支撑小规模企业内部生产。

### 阶段 C：规模化与治理

1. 多知识库管理。
2. 多 collection 或 collection 路由。
3. 后台任务队列。
4. 指标监控和告警。
5. RAG 质量评估平台。
6. 文档版本管理。

阶段 C 完成后，系统具备多部门、多权限、多知识库的企业级扩展基础。

## 13. 优先级清单

P0 必须项：

- 文档级权限 metadata。
- 检索阶段权限过滤。
- 用户 access level 和 department。
- 生产环境安全配置检查。
- 上传文件类型和大小限制。

P1 重要项：

- 聊天消息落库。
- 审计日志。
- 文档删除和索引清理。
- 单文档 reindex。
- 摄取失败重试。
- 核心接口自动化测试。

P2 增强项：

- 多 collection。
- 文档版本管理。
- 监控指标。
- RAG 质量评估。
- 更完整的后台管理接口。

## 14. 企业级验收标准

当以下条件满足时，可以认为系统基本达到企业内部生产可用：

1. 普通用户无法检索无权限文档。
2. admin 可以配置用户和文档权限。
3. 每次问答都能追溯用户、问题、答案、引用来源。
4. 文档上传、失败、删除、重建都有明确状态。
5. 删除文档后不会继续被检索召回。
6. 系统具备基础接口测试和权限测试。
7. 生产环境不会使用默认密钥、默认密码和全开放 CORS。
8. 出现故障时可以通过日志定位到摄取、检索、rerank 或生成阶段。

## 15. 总结

当前项目已经完成 RAG 主链路，但还没有完成企业生产级最关键的安全隔离和治理能力。

最优先的优化方向不是继续堆模型能力，而是先补齐：

```text
用户权限 -> 文档权限 -> 检索过滤 -> 消息落库 -> 审计日志 -> 文档生命周期治理
```

这条路线完成后，项目才能从“可演示的 RAG 原型”逐步升级为“可在企业内部受控上线的 RAG 服务”。
