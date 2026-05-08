# RAG 后端第一阶段优化方案

## 1. 背景

当前项目已经具备基础 RAG 后端能力，包括用户登录、文档上传、文档摄取、向量化入库、混合检索、重排序、普通问答、流式问答和会话列表管理。

但现有实现仍偏原型阶段，第一阶段优化目标不是重写 RAG 能力，而是先补齐后端稳定性和安全底座，让后续文档权限、多知识库、多角色管理等能力有可靠基础。

第一阶段聚焦以下五项：

1. 配置环境变量化。
2. 修复默认 root 密码每次启动被重置的问题。
3. 增加用户角色字段和管理员权限控制。
4. 修复 reset 接口只清业务表、不清实际索引数据的问题。
5. 修复文档 node_count 统计错误。

## 2. 总体目标

### 2.1 功能目标

- 服务启动配置不再依赖代码里的硬编码地址、模型名和密钥。
- 默认管理员账号只在首次初始化时创建，不在每次启动时覆盖密码。
- 系统具备基本角色模型，至少支持 `admin` 和 `user`。
- 高风险接口只允许管理员访问。
- reset 能明确清理 Chroma、Redis、BM25、SQLite 文档状态、上传文件和 PDF 图片等数据。
- 文档上传完成后，`documents.node_count` 能正确记录本次文档摄取生成的节点数量。

### 2.2 非目标

第一阶段暂不实现以下内容：

- 文档级权限过滤。
- 多 collection 或多向量库隔离。
- 完整聊天消息历史落库。
- ChatEngine memory。
- RAG 检索质量调优。
- 前端页面改造。

这些内容建议放入第二阶段。

## 3. 当前问题梳理

### 3.1 配置硬编码

涉及文件：

- `config/settings.py`
- `core/ingestion.py`
- `app/routers/users.py`

当前问题：

- Redis 地址固定为 `127.0.0.1:6380`。
- Ollama 地址固定为 `http://localhost:11434`。
- Ollama 模型固定为 `deepseek-r1:1.5b`。
- JWT `SECRET_KEY` 写死在 `users.py`。
- Chroma collection 固定为 `quickstart`。
- 本地 embedding/rerank 模型路径写死为 Windows 绝对路径。

风险：

- 部署环境变更时需要改代码。
- 密钥泄露风险高。
- 本地路径强绑定开发机器。

### 3.2 root 密码每次启动被重置

涉及文件：

- `app/routers/users.py`
- `core/userManager.py`

当前逻辑：

```python
user_manager.ensure_default_user(password_hash.hash("root"))
```

`ensure_default_user()` 使用 `ON CONFLICT DO UPDATE`，导致服务每次启动时都会把 root 密码更新为 `root`。

风险：

- 管理员修改密码后，重启服务会失效。
- 生产环境存在默认弱口令。

### 3.3 缺少角色权限控制

涉及文件：

- `core/userManager.py`
- `app/schemas.py`
- `app/routers/users.py`
- `app/routers/documents.py`

当前问题：

- 用户表没有 `role` 字段。
- 所有 active user 都能调用文档上传、reset、用户列表等接口。
- 没有区分管理员和普通用户。

风险：

- 普通用户可以重置系统。
- 普通用户可以查看所有用户。
- 后续文档权限无法建立在清晰的用户角色基础上。

### 3.4 reset 没有真正清理索引数据

涉及文件：

- `app/routers/documents.py`
- `app/services/rag_service.py`
- `core/application.py`
- `core/documentManager.py`
- `core/chatSessionManager.py`
- `core/ingestion.py`

当前问题：

- `RAGApplication.reset()` 基本为空实现。
- `RAGService.reset_system()` 只清理 SQLite 中的文档状态和会话列表。
- Chroma、Redis、BM25、上传文件、PDF 图片没有同步清理。

风险：

- `/api/docs/list` 显示无文档，但向量库里仍然存在历史文档。
- 用户以为知识库已清空，实际检索仍可能命中旧内容。

### 3.5 node_count 统计错误

涉及文件：

- `app/services/rag_service.py`
- `core/application.py`
- `core/ingestion.py`

当前问题：

`core/ingestion.py` 的 `ingest_documents()` 返回：

```python
return "success", result, pipeline_nodes
```

但 `core/application.py` 的 `upload_and_process_files()` 只返回：

```python
return status, result
```

导致 `RAGService.upload_and_process_file_paths()` 无法拿到 `pipeline_nodes`，最终 `node_count` 基本为 0。

风险：

- 文档状态展示不准确。
- 后续统计、审计、排查问题缺少基础数据。

## 4. 详细优化方案

## 4.1 配置环境变量化

### 4.1.1 新增配置项

在 `config/settings.py` 中补齐以下配置：

```python
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1:1.5b")
OLLAMA_REQUEST_TIMEOUT = float(os.getenv("OLLAMA_REQUEST_TIMEOUT", "600.0"))

REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6380"))
REDIS_INDEX_NAMESPACE = os.getenv("REDIS_INDEX_NAMESPACE", "redis_index")
REDIS_DOCS_NAMESPACE = os.getenv("REDIS_DOCS_NAMESPACE", "redis_docs")
REDIS_CACHE_COLLECTION = os.getenv("REDIS_CACHE_COLLECTION", "redis_cache")

CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "quickstart")

DEFAULT_ADMIN_USERNAME = os.getenv("DEFAULT_ADMIN_USERNAME", "root")
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "")
ENABLE_DEFAULT_ADMIN = os.getenv("ENABLE_DEFAULT_ADMIN", "true").lower() == "true"

EMBEDDING_MODEL_PATH = os.getenv(
    "EMBEDDING_MODEL_PATH",
    r"D:\llm\Local_model\BAAI\bge-large-zh-v1___5",
)
RERANK_MODEL_PATH = os.getenv(
    "RERANK_MODEL_PATH",
    r"D:\llm\Local_model\BAAI\bge-reranker-large",
)
```

### 4.1.2 调整调用点

`core/ingestion.py` 中：

- Ollama 使用 `AppSettings.OLLAMA_BASE_URL`。
- 模型名使用 `AppSettings.OLLAMA_MODEL` 或接口传入的 model。
- Redis host/port 使用 `AppSettings.REDIS_HOST` 和 `AppSettings.REDIS_PORT`。
- Chroma collection 使用 `AppSettings.CHROMA_COLLECTION`。

`app/routers/users.py` 中：

- `SECRET_KEY`、`ALGORITHM`、`ACCESS_TOKEN_EXPIRE_MINUTES` 从 `AppSettings` 获取。

### 4.1.3 示例 `.env`

建议新增 `.env.example`：

```env
JWT_SECRET_KEY=change-me-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=deepseek-r1:1.5b
OLLAMA_REQUEST_TIMEOUT=600

REDIS_HOST=127.0.0.1
REDIS_PORT=6380
REDIS_INDEX_NAMESPACE=redis_index
REDIS_DOCS_NAMESPACE=redis_docs
REDIS_CACHE_COLLECTION=redis_cache

CHROMA_COLLECTION=quickstart

ENABLE_DEFAULT_ADMIN=true
DEFAULT_ADMIN_USERNAME=root
DEFAULT_ADMIN_PASSWORD=root

EMBEDDING_MODEL_PATH=D:\llm\Local_model\BAAI\bge-large-zh-v1___5
RERANK_MODEL_PATH=D:\llm\Local_model\BAAI\bge-reranker-large
```

### 4.1.4 验收标准

- 修改 Redis、Ollama、collection、JWT 配置无需改代码。
- 未配置 `JWT_SECRET_KEY` 时，开发环境可以启动，但日志应给出警告。
- 生产环境部署文档要求必须显式配置 `JWT_SECRET_KEY`。

## 4.2 修复默认 root 密码重置问题

### 4.2.1 数据初始化策略

修改 `core/userManager.py`：

- `ensure_default_user()` 只在用户不存在时创建。
- 如果用户已存在，不更新密码。
- 默认用户角色为 `admin`。

建议逻辑：

```python
def ensure_default_user(self, username: str, hashed_password: str) -> None:
    existing = self.get_user(username)
    if existing:
        return
    self.create_user(
        username=username,
        hashed_password=hashed_password,
        email="admin@example.com",
        full_name="Administrator",
        role="admin",
    )
```

### 4.2.2 启动逻辑

修改 `app/routers/users.py`：

- 仅当 `ENABLE_DEFAULT_ADMIN=true` 时创建默认管理员。
- 如果 `DEFAULT_ADMIN_PASSWORD` 为空，开发环境可默认 root，生产环境应拒绝或警告。

建议：

```python
if AppSettings.ENABLE_DEFAULT_ADMIN:
    user_manager.ensure_default_user(
        username=AppSettings.DEFAULT_ADMIN_USERNAME,
        hashed_password=password_hash.hash(AppSettings.DEFAULT_ADMIN_PASSWORD or "root"),
    )
```

### 4.2.3 验收标准

- 修改 root 密码后，重启服务不会恢复为 `root`。
- 首次启动无用户时，可以自动创建默认管理员。
- 已存在管理员时，不覆盖其密码、邮箱、名称、角色。

## 4.3 增加角色字段和管理员权限控制

### 4.3.1 数据结构变更

修改 `users` 表，新增字段：

```sql
role TEXT NOT NULL DEFAULT 'user'
```

角色枚举：

```text
admin  管理员
user   普通用户
```

后续可扩展：

```text
editor
viewer
```

### 4.3.2 SQLite 迁移策略

由于当前项目没有迁移工具，可以在 `_init_db()` 中做轻量迁移：

1. 查询 `PRAGMA table_info(users)`。
2. 如果没有 `role` 字段，则执行：

```sql
ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'
```

3. 将默认管理员用户更新为 `admin`：

```sql
UPDATE users SET role = 'admin' WHERE username = ?
```

### 4.3.3 Schema 调整

修改 `app/schemas.py`：

```python
class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    role: str = "user"
```

`UserCreate` 初期不暴露 role，避免用户注册时自选 admin：

```python
class UserCreate(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    full_name: Optional[str] = None
```

如需管理员创建用户，可第二阶段增加独立管理接口。

### 4.3.4 权限依赖函数

在 `app/routers/users.py` 中新增：

```python
async def get_current_admin_user(
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permission required",
        )
    return current_user
```

### 4.3.5 接口权限收紧

需要管理员权限的接口：

- `POST /api/docs/upload`
- `POST /api/docs/reset`
- `GET /users/all`

保留普通用户可用的接口：

- `POST /api/chat/chat`
- `POST /api/chat/chat/stream`
- `GET /api/chat/sessions`
- `DELETE /api/chat/sessions/{session_id}`
- `GET /users/me`
- `PUT /users/me`
- `POST /users/logout`

待讨论接口：

- `POST /users/register`

建议第一阶段先保留开放注册，但注册用户默认为 `user`。如果业务不允许开放注册，则改为仅 admin 可创建用户。

### 4.3.6 验收标准

- 普通用户调用上传文档返回 403。
- 普通用户调用 reset 返回 403。
- 普通用户调用用户列表返回 403。
- admin 可以正常上传、reset、查看用户列表。
- 新注册用户 role 默认为 `user`。

## 4.4 修复 reset 清理逻辑

### 4.4.1 reset 范围定义

第一阶段建议 reset 语义为“清空知识库和相关业务状态”，包括：

- Chroma collection 数据。
- Redis docstore。
- Redis index store。
- Redis ingestion cache。
- BM25 持久化目录。
- SQLite documents 表。
- 上传文件目录 `file/resources`。
- PDF 图片目录 `file/image`。
- 内存中的 `ingestion_pipeline.index` 和 `workflow`。

是否清理 chat sessions：

- 建议 reset 知识库时不清会话列表。
- 如果需要全量系统重置，可新增 `POST /api/admin/reset-all`。

当前 `RAGService.reset_system()` 会清 session，建议改为不清 session，避免用户历史会话侧栏被误删。

### 4.4.2 新增清理方法

建议在 `core/ingestion.py` 增加：

```python
def reset_storage(self) -> None:
    self.index = None
    # delete chroma collection and recreate it
    # clear redis namespaces/cache
    # remove bm25 directory
    # recreate storage context and pipelines
```

Chroma 清理方式：

```python
client = chromadb.PersistentClient(AppSettings.CHROMA_PERSIST_DIR)
try:
    client.delete_collection(AppSettings.CHROMA_COLLECTION)
except Exception:
    pass
collection = client.get_or_create_collection(AppSettings.CHROMA_COLLECTION)
```

Redis 清理方式：

- 如果 LlamaIndex 封装没有 clear API，可使用 `redis` 客户端按 namespace pattern 删除。
- 删除前必须限定 prefix，避免误删 Redis 中其他业务数据。

建议 pattern：

```text
redis_index*
redis_docs*
redis_cache*
```

如果 namespace 实际 key 格式不确定，应先增加日志打印或封装一个 `dry_run` 方法。

文件目录清理：

```python
def clear_directory(path: str) -> None:
    target = Path(path)
    if not target.exists():
        return
    for child in target.iterdir():
        if child.is_file():
            child.unlink()
        elif child.is_dir():
            shutil.rmtree(child)
```

注意：

- 不直接删除 `file` 根目录。
- 只清理明确配置的子目录。

### 4.4.3 调整调用链

`RAGApplication.reset()`：

```python
def reset(self) -> None:
    self.ingestion_pipeline.reset_storage()
    self.workflow = None
```

`RAGService.reset_system()`：

```python
def reset_system(self):
    self.app.reset()
    self.doc_manager.clear_all()
```

是否清理 sessions 单独拆方法：

```python
def reset_all(self):
    self.reset_system()
    self.session_manager.clear_all()
```

### 4.4.4 验收标准

- reset 后 `/api/docs/list` 返回空。
- reset 后相同问题不再检索到旧文档内容。
- reset 后重新上传文档可以正常检索。
- reset 不误删 SQLite users。
- reset 不误删项目源码和非目标目录。

## 4.5 修复 node_count 统计

### 4.5.1 调整返回值

建议统一上传处理返回结构，避免 tuple 层层猜测。

短期最小改动：

`core/application.py` 的 `upload_and_process_files()` 改为返回：

```python
return status, result, pipeline_nodes
```

异常时返回：

```python
return "error", error_msg, []
```

`app/services/rag_service.py` 当前已有兼容逻辑，可以直接计算：

```python
node_count = len(result[2])
```

### 4.5.2 多文件统计问题

当前一次上传多个文件时，`node_count` 会把所有文件生成的节点总数写到每个文件上。

第一阶段可接受最小修复：

- `node_count` 先记录批次总节点数。

更准确方案：

- 在 `pipeline_nodes` 里根据 `metadata["file_name"]` 聚合。
- 每个文件记录自己的节点数量。

建议直接实现准确方案：

```python
from collections import Counter

counts = Counter(
    node.metadata.get("file_name")
    for node in pipeline_nodes
)
```

然后：

```python
node_count=counts.get(filename, 0)
```

### 4.5.3 验收标准

- 上传单文件后，`documents.node_count > 0`。
- 上传多个文件后，每个文件的 `node_count` 与对应节点数量匹配。
- 重复上传未生成新节点时，node_count 不错误显示为批次总数。

## 5. 推荐实施顺序

### Step 1 配置收敛

涉及文件：

- `config/settings.py`
- `core/ingestion.py`
- `app/routers/users.py`
- `.env.example`

完成后先保证服务能启动。

### Step 2 用户角色和默认管理员

涉及文件：

- `core/userManager.py`
- `app/schemas.py`
- `app/routers/users.py`

完成后验证登录、注册、获取当前用户。

### Step 3 接口权限收紧

涉及文件：

- `app/routers/documents.py`
- `app/routers/users.py`

完成后验证普通用户 403、admin 正常。

### Step 4 node_count 修复

涉及文件：

- `core/application.py`
- `app/services/rag_service.py`

完成后上传文档验证 `/api/docs/list`。

### Step 5 reset 真清理

涉及文件：

- `core/ingestion.py`
- `core/application.py`
- `app/services/rag_service.py`
- `app/routers/documents.py`

完成后验证 reset 后旧内容不可检索。

## 6. 测试方案

### 6.1 手工测试

1. 启动 Redis 和 Ollama。
2. 配置 `.env`。
3. 启动 FastAPI。
4. 使用默认 admin 登录。
5. 注册普通用户。
6. 普通用户调用上传接口，应返回 403。
7. admin 上传文档，应返回 success。
8. 查看文档列表，node_count 应大于 0。
9. 使用知识库问答，应能检索到文档内容。
10. admin 调用 reset。
11. 查看文档列表，应为空。
12. 再次问同样问题，不应命中旧文档。

### 6.2 自动化测试建议

建议新增测试覆盖：

- `test_user_auth.py`
  - 登录成功。
  - 登录失败。
  - token 过期或非法 token 被拒。

- `test_roles.py`
  - 新注册用户 role 为 user。
  - 普通用户访问 admin 接口返回 403。
  - admin 访问 admin 接口成功。

- `test_documents.py`
  - 上传成功后 documents 状态为 completed。
  - 上传失败后状态为 failed。
  - node_count 正确。

- `test_reset.py`
  - reset 后 documents 为空。
  - reset 后索引不可检索旧文档。

## 7. 风险与注意事项

### 7.1 SQLite 迁移风险

当前没有 Alembic 等迁移工具。第一阶段使用轻量 `ALTER TABLE` 可以接受，但要保证幂等：

- 字段存在时不重复添加。
- 数据迁移失败要记录日志。

### 7.2 Redis 清理风险

Redis 可能被其他服务共用。删除 key 时必须限制 namespace，禁止 `flushdb`。

### 7.3 Chroma 清理风险

删除 collection 前应确认 collection 名来自配置，避免误删其他 collection。

### 7.4 默认管理员风险

开发环境可以保留默认管理员，生产环境必须：

- 显式配置强密码。
- 或关闭 `ENABLE_DEFAULT_ADMIN`。
- 或在首次启动后立即修改密码。

## 8. 第一阶段完成定义

第一阶段完成时，项目应满足：

- 所有关键运行参数都可以通过环境变量配置。
- root 密码不会因服务重启被重置。
- 用户具备 role 字段，普通用户和 admin 权限有明确区别。
- 文档上传、reset、用户列表接口仅 admin 可调用。
- 文档上传后的 node_count 准确。
- reset 后业务状态和真实知识库索引状态一致。
- 原有登录、上传、问答、流式问答功能不回退。

## 9. 后续阶段衔接

第一阶段完成后，可以自然进入第二阶段：

1. 文档级权限控制。
2. 文档 metadata 增加 `owner_id`、`access_level`、`department`。
3. 检索时使用 metadata filter。
4. 多 collection 或多知识库隔离。
5. 聊天消息完整落库。
6. 管理员后台接口。
7. 操作审计日志。
