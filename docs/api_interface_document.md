# RAG 后端接口文档

## 1. 基础说明

### 1.1 服务地址

默认本地服务地址：

```text
http://localhost:8000
```

实际前端项目中建议通过环境变量配置，例如：

```text
VITE_API_BASE_URL=http://localhost:8000
```

### 1.2 鉴权方式

除登录、注册、健康检查外，大多数接口都需要 JWT。

请求头格式：

```http
Authorization: Bearer <access_token>
```

登录接口返回：

```json
{
  "message": "login success",
  "access_token": "xxx",
  "token_type": "bearer",
  "username": "root"
}
```

前端保存 `access_token` 后，后续请求统一放入 `Authorization` 请求头。

### 1.3 用户角色

当前用户角色：

```text
admin
user
```

权限说明：

| 能力 | admin | user |
|---|---:|---:|
| 登录 | 是 | 是 |
| 查看自己信息 | 是 | 是 |
| 修改自己信息 | 是 | 是 |
| 查看文档列表 | 是 | 是 |
| 聊天问答 | 是 | 是 |
| 查看自己的会话列表 | 是 | 是 |
| 查看自己的会话历史 | 是 | 是 |
| 上传文档 | 是 | 否 |
| reset 系统 | 是 | 否 |
| 查看全部用户 | 是 | 否 |

### 1.4 通用错误格式

FastAPI 默认错误格式：

```json
{
  "detail": "错误信息"
}
```

常见状态码：

| 状态码 | 含义 |
|---:|---|
| 400 | 请求参数错误、用户被禁用 |
| 401 | 未登录、token 无效、用户名或密码错误 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 422 | 请求体格式不符合 Pydantic schema |
| 500 | 服务端异常 |

## 2. 健康检查

### 2.1 健康检查

```http
GET /api/health
```

是否需要登录：否。

请求参数：无。

响应：

```json
{
  "status": "ok",
  "message": "healthy"
}
```

前端用途：

- 可用于服务连通性检测。
- 不建议作为完整依赖可用性判断，因为当前只返回静态健康状态。

## 3. 用户接口

### 3.1 登录

```http
POST /users/token
Content-Type: application/x-www-form-urlencoded
```

是否需要登录：否。

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| username | string | 是 | 用户名 |
| password | string | 是 | 密码 |

请求示例：

```http
username=root&password=root
```

响应字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| message | string | 登录结果信息 |
| access_token | string | JWT token |
| token_type | string | 固定为 `bearer` |
| username | string | 当前登录用户名 |

响应示例：

```json
{
  "message": "login success",
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "username": "root"
}
```

前端注意：

- 该接口不是 JSON 请求体，而是表单格式。
- 使用 `fetch` 时可以用 `URLSearchParams`。
- 使用 axios 时可以传 `new URLSearchParams({ username, password })`。

### 3.2 注册

```http
POST /users/register
Content-Type: application/json
```

是否需要登录：否。

请求体：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| username | string | 是 | 用户名，唯一 |
| password | string | 是 | 密码 |
| email | string/null | 否 | 邮箱 |
| full_name | string/null | 否 | 昵称或真实姓名 |

请求示例：

```json
{
  "username": "alice",
  "password": "123456",
  "email": "alice@example.com",
  "full_name": "Alice"
}
```

响应字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| username | string | 用户名 |
| email | string/null | 邮箱 |
| full_name | string/null | 昵称或真实姓名 |
| disabled | boolean/null | 是否禁用 |
| role | string | 角色，默认 `user` |

响应示例：

```json
{
  "username": "alice",
  "email": "alice@example.com",
  "full_name": "Alice",
  "disabled": false,
  "role": "user"
}
```

### 3.3 退出登录

```http
POST /users/logout
Authorization: Bearer <access_token>
```

是否需要登录：是。

请求参数：无。

响应示例：

```json
{
  "message": "logout success",
  "username": "alice",
  "logout_time": "2026-05-09T01:20:00.000000+00:00"
}
```

前端注意：

- 当前后端没有 token 黑名单，退出登录主要由前端删除本地 token。

### 3.4 获取当前用户

```http
GET /users/me
Authorization: Bearer <access_token>
```

是否需要登录：是。

响应示例：

```json
{
  "username": "alice",
  "email": "alice@example.com",
  "full_name": "Alice",
  "disabled": false,
  "role": "user"
}
```

### 3.5 修改当前用户

```http
PUT /users/me
Authorization: Bearer <access_token>
Content-Type: application/json
```

是否需要登录：是。

请求体：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| email | string/null | 否 | 邮箱 |
| full_name | string/null | 否 | 昵称或真实姓名 |

请求示例：

```json
{
  "email": "new@example.com",
  "full_name": "Alice New"
}
```

响应示例：

```json
{
  "username": "alice",
  "email": "new@example.com",
  "full_name": "Alice New",
  "disabled": false,
  "role": "user"
}
```

### 3.6 删除当前用户

```http
DELETE /users/me
Authorization: Bearer <access_token>
```

是否需要登录：是。

响应示例：

```json
{
  "message": "User account deleted successfully",
  "deleted_user": "alice",
  "deleted_at": "2026-05-09T01:20:00.000000+00:00"
}
```

### 3.7 查看全部用户

```http
GET /users/all
Authorization: Bearer <access_token>
```

是否需要登录：是。

权限要求：`admin`。

响应字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| users | User[] | 用户列表 |
| total | number | 用户数量 |
| requested_by | string | 请求人 |

响应示例：

```json
{
  "users": [
    {
      "username": "root",
      "email": "admin@example.com",
      "full_name": "Administrator",
      "disabled": false,
      "role": "admin"
    }
  ],
  "total": 1,
  "requested_by": "root"
}
```

## 4. 文档接口

### 4.1 上传文档

```http
POST /api/docs/upload
Authorization: Bearer <access_token>
Content-Type: multipart/form-data
```

是否需要登录：是。

权限要求：`admin`。

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| files | File[] | 是 | 上传文件列表，字段名必须是 `files` |

请求说明：

- 支持多文件上传。
- 后端会保存到 `file/resources`。
- 如果文件名冲突，会自动追加 `_1`、`_2` 等后缀。
- 上传后会触发文档解析、切分、向量化和索引入库。

响应字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| status | string | `success` 或 `error` |
| message | string | 处理结果说明 |
| processed_files | string[] | 已处理文件名 |

响应示例：

```json
{
  "status": "success",
  "message": "成功处理 1 个文件",
  "processed_files": ["产品手册.pdf"]
}
```

前端注意：

- 该接口可能耗时较长，目前不是后台异步任务。
- 上传时建议显示 loading。
- 失败时读取 `detail` 或 `message` 展示错误。

### 4.2 文档列表

```http
GET /api/docs/list
Authorization: Bearer <access_token>
```

是否需要登录：是。

响应字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| documents | DocumentStatus[] | 文档状态列表 |

`DocumentStatus` 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| doc_id | string | 文档 ID，当前格式类似 `knowledge_base/xxx.pdf` |
| file_name | string | 文件名 |
| file_path | string/null | 文件保存路径 |
| file_type | string/null | 文件后缀，例如 `.pdf` |
| file_size | number | 文件大小，单位 byte |
| status | string | `processing`、`completed`、`failed` 等 |
| message | string | 状态说明 |
| node_count | number | 该文档生成的 node 数量 |
| error | string | 错误信息 |
| created_at | string | 创建时间 |
| updated_at | string | 更新时间 |

响应示例：

```json
{
  "documents": [
    {
      "doc_id": "knowledge_base/产品手册.pdf",
      "file_name": "产品手册.pdf",
      "file_path": "D:\\projects\\rag\\file\\resources\\产品手册.pdf",
      "file_type": ".pdf",
      "file_size": 102400,
      "status": "completed",
      "message": "document has been vectorized",
      "node_count": 32,
      "error": "",
      "created_at": "2026-05-09T01:20:00.000000+00:00",
      "updated_at": "2026-05-09T01:21:00.000000+00:00"
    }
  ]
}
```

### 4.3 系统重置

```http
POST /api/docs/reset
Authorization: Bearer <access_token>
```

是否需要登录：是。

权限要求：`admin`。

请求参数：无。

响应示例：

```json
{
  "status": "success",
  "message": "系统已重置"
}
```

前端注意：

- 这是高风险操作。
- 会清理知识库相关存储和文档状态。
- 建议前端增加二次确认。

## 5. 聊天与会话接口

### 5.1 普通问答

```http
POST /api/chat/chat
Authorization: Bearer <access_token>
Content-Type: application/json
```

是否需要登录：是。

请求体：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| session_id | string/null | 否 | null | 会话 ID；为空则创建新会话 |
| query | string | 是 | 无 | 用户问题 |
| model | string/null | 否 | 后端配置默认模型 | 模型名，例如 `deepseek-r1:1.5b` |
| knowledge_bool | boolean/null | 否 | null | 是否启用知识库检索；建议前端明确传 `true` 或 `false` |
| temperature | number/null | 否 | 后端配置默认值 | 生成温度 |
| max_tokens | number | 否 | 100 | 最大生成 token 数 |

请求示例：

```json
{
  "session_id": null,
  "query": "请总结一下产品手册的核心功能",
  "model": "deepseek-r1:1.5b",
  "knowledge_bool": true,
  "temperature": 0.7,
  "max_tokens": 512
}
```

响应字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| session_id | string | 会话 ID，新会话时由后端生成 |
| messages | ChatMessage | 本次 assistant 回复 |

`ChatMessage` 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| role | string | 当前为 `assistant` |
| content | string | 回答内容 |
| sources | string[] | 引用来源列表 |

响应示例：

```json
{
  "session_id": "b8b9f2c1-1111-2222-3333-abcdefabcdef",
  "messages": {
    "role": "assistant",
    "content": "产品手册的核心功能包括...",
    "sources": [
      "1. 相似度: 0.823 | 文件: 产品手册.pdf\n   内容: ..."
    ]
  }
}
```

历史保存行为：

- 问答成功后，后端会保存两条历史消息：
  - `role=user` 的用户问题。
  - `role=assistant` 的模型回答。
- 如果请求带了已有 `session_id`，历史会追加到该会话。
- 如果不带 `session_id`，后端会创建新会话并返回新的 `session_id`。

### 5.2 流式问答

```http
POST /api/chat/chat/stream
Authorization: Bearer <access_token>
Content-Type: application/json
Accept: text/event-stream
```

是否需要登录：是。

请求体同普通问答：

```json
{
  "session_id": "b8b9f2c1-1111-2222-3333-abcdefabcdef",
  "query": "继续详细说明",
  "model": "deepseek-r1:1.5b",
  "knowledge_bool": true,
  "temperature": 0.7,
  "max_tokens": 512
}
```

响应类型：

```text
text/event-stream
```

每个 SSE 事件格式：

```text
data: {"type":"text","finished":false,"content":"内容片段"}
```

事件类型一：session

新建或确认会话时返回。

```json
{
  "type": "session",
  "finished": false,
  "content": {
    "session_id": "b8b9f2c1-1111-2222-3333-abcdefabcdef",
    "title": "请总结一下产品手册"
  }
}
```

事件类型二：sources

知识库检索模式下，可能先返回引用来源。

```json
{
  "type": "sources",
  "finished": false,
  "content": [
    "1. 相似度: 0.823 | 文件: 产品手册.pdf\n   内容: ..."
  ]
}
```

事件类型三：text

增量文本片段。

```json
{
  "type": "text",
  "finished": false,
  "content": "产品"
}
```

事件类型四：complete

流式完成，`content` 是完整回答。

```json
{
  "type": "complete",
  "finished": true,
  "content": "产品手册的核心功能包括..."
}
```

事件类型五：error

流式异常。

```json
{
  "type": "error",
  "finished": true,
  "content": "流式传输错误: xxx"
}
```

历史保存行为：

- 只有收到后端内部完成事件后，才会保存完整历史。
- 保存内容包括用户问题、完整 assistant 回答和 sources。
- 如果中途异常，新建会话可能会被删除，避免留下空会话。

前端建议：

- 收到 `session` 事件后，立即保存 `session_id`。
- 收到 `sources` 后展示引用卡片。
- 收到多个 `text` 后拼接到当前回答。
- 收到 `complete` 后用完整 content 校准最终回答。
- 收到 `error` 后展示错误状态。

### 5.3 会话列表

```http
GET /api/chat/sessions
Authorization: Bearer <access_token>
```

是否需要登录：是。

响应字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| sessions | ChatSession[] | 当前用户的会话列表 |

`ChatSession` 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| session_id | string | 会话 ID |
| title | string | 会话标题，默认由首次问题截断生成 |
| first_query | string | 首次问题 |
| last_message | string | 最近一条用户问题 |
| message_count | number | 消息数量，当前一轮问答计 2 条 |
| created_at | string | 创建时间 |
| updated_at | string | 更新时间 |

响应示例：

```json
{
  "sessions": [
    {
      "session_id": "b8b9f2c1-1111-2222-3333-abcdefabcdef",
      "title": "请总结一下产品手册",
      "first_query": "请总结一下产品手册的核心功能",
      "last_message": "继续详细说明",
      "message_count": 4,
      "created_at": "2026-05-09T01:20:00.000000+00:00",
      "updated_at": "2026-05-09T01:22:00.000000+00:00"
    }
  ]
}
```

前端用途：

- 用于左侧会话列表。
- 点击某个会话后，调用历史接口加载完整消息。

### 5.4 会话历史

```http
GET /api/chat/history
Authorization: Bearer <access_token>
```

是否需要登录：是。

查询参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| session_id | string | 否 | 指定会话 ID；不传则返回当前用户全部历史消息 |

推荐调用：

```http
GET /api/chat/history?session_id=b8b9f2c1-1111-2222-3333-abcdefabcdef
```

响应类型：

```text
ChatMessage[]
```

响应字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| role | string | `user` 或 `assistant` |
| content | string | 消息内容 |
| sources | string[] | 引用来源；用户消息通常为空数组 |

响应示例：

```json
[
  {
    "role": "user",
    "content": "请总结一下产品手册的核心功能",
    "sources": []
  },
  {
    "role": "assistant",
    "content": "产品手册的核心功能包括...",
    "sources": [
      "1. 相似度: 0.823 | 文件: 产品手册.pdf\n   内容: ..."
    ]
  }
]
```

前端建议：

- 进入聊天页面时先调用 `/api/chat/sessions`。
- 用户点击某个会话时调用 `/api/chat/history?session_id=xxx`。
- 渲染时按数组顺序展示。
- `role=user` 展示为用户气泡。
- `role=assistant` 展示为 AI 气泡，并展示 sources。

### 5.5 删除会话

```http
DELETE /api/chat/sessions/{session_id}
Authorization: Bearer <access_token>
```

是否需要登录：是。

路径参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| session_id | string | 是 | 要删除的会话 ID |

响应示例：

```json
{
  "status": "success",
  "message": "session deleted"
}
```

错误示例：

```json
{
  "detail": "session not found"
}
```

删除行为：

- 只允许删除当前登录用户自己的会话。
- 删除会话时会同步删除该会话下的消息历史。

### 5.6 清空指定会话历史

```http
POST /api/chat/clear
Authorization: Bearer <access_token>
Content-Type: application/json
```

是否需要登录：是。

请求体：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| session_id | string | 是 | 要清空历史的会话 ID |

请求示例：

```json
{
  "session_id": "b8b9f2c1-1111-2222-3333-abcdefabcdef"
}
```

响应示例：

```json
{
  "status": "success",
  "message": "会话已清空"
}
```

清空行为：

- 删除当前用户该会话下的消息。
- 会话本身仍保留在会话列表中。
- `message_count` 会重置为 `0`。
- `last_message` 会重置为空字符串。

## 6. 前端推荐调用流程

### 6.1 登录流程

```text
用户输入账号密码
-> POST /users/token
-> 保存 access_token
-> GET /users/me
-> 保存用户信息和 role
```

### 6.2 首页初始化

```text
GET /users/me
GET /api/chat/sessions
GET /api/docs/list
```

如果当前用户是 `admin`，可以显示上传文档和 reset 按钮。

### 6.3 新建聊天

```text
前端本地创建空白聊天界面
-> 用户输入问题
-> POST /api/chat/chat 或 /api/chat/chat/stream，session_id 传 null
-> 后端返回 session_id
-> 前端把该 session_id 绑定到当前聊天
-> 刷新 /api/chat/sessions
```

### 6.4 继续已有聊天

```text
用户点击左侧会话
-> GET /api/chat/history?session_id=xxx
-> 渲染历史消息
-> 用户继续提问时请求体带 session_id=xxx
```

### 6.5 上传文档

```text
检查当前用户 role 是否为 admin
-> 选择一个或多个文件
-> POST /api/docs/upload
-> 上传成功后 GET /api/docs/list 刷新文档列表
```

## 7. TypeScript 类型建议

```ts
export interface TokenResponse {
  message: string
  access_token: string
  token_type: 'bearer'
  username: string
}

export interface User {
  username: string
  email?: string | null
  full_name?: string | null
  disabled?: boolean | null
  role: 'admin' | 'user' | string
}

export interface DocumentStatus {
  doc_id: string
  file_name: string
  file_path?: string | null
  file_type?: string | null
  file_size: number
  status: string
  message: string
  node_count: number
  error: string
  created_at: string
  updated_at: string
}

export interface ChatRequest {
  session_id?: string | null
  query: string
  model?: string | null
  knowledge_bool?: boolean | null
  temperature?: number | null
  max_tokens?: number
}

export interface ChatMessage {
  role: 'user' | 'assistant' | string
  content: string
  sources: string[]
}

export interface ChatResponse {
  session_id: string
  messages: ChatMessage
}

export interface ChatSession {
  session_id: string
  title: string
  first_query: string
  last_message: string
  message_count: number
  created_at: string
  updated_at: string
}

export type StreamEvent =
  | {
      type: 'session'
      finished: false
      content: {
        session_id: string
        title: string
      }
    }
  | {
      type: 'sources'
      finished: false
      content: string[]
    }
  | {
      type: 'text'
      finished: false
      content: string
    }
  | {
      type: 'complete'
      finished: true
      content: string
    }
  | {
      type: 'error'
      finished: true
      content: string
    }
```

## 8. 当前接口注意事项

1. `/users/token` 使用 `application/x-www-form-urlencoded`，不是 JSON。
2. `/api/docs/upload` 使用 `multipart/form-data`，文件字段名必须是 `files`。
3. `/api/chat/history` 推荐传 `session_id`，否则会返回当前用户全部消息。
4. `/api/chat/chat/stream` 是 SSE 流式返回，前端需要按 `data:` 行解析 JSON。
5. 当前后端还没有文档级权限过滤，前端不要展示“文档权限管理”类能力。
6. 当前 reset 是高风险操作，仅 admin 可用，前端必须二次确认。
7. 当前删除会话会删除消息历史；清空会话只删除消息，不删除会话。
