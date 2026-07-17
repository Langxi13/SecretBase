# SecretBase API 规范文档

## 0. 文档状态与阶段标记

本文档定义 SecretBase 的目标 API 契约。接口按阶段标记：

| 标记 | 含义 |
|------|------|
| V1 | 基础可用版必须支持 |
| V1.1 | 产品完整版补齐 |
| V2 | 安全与工程增强 |

当前实现可以落后于本文档，但后续实现应以本文档为准。若实现临时采用简化方案，必须在对应章节写明“当前实现”和“目标行为”。

## 1. 概述

本文档定义了 SecretBase 后端 API 的详细规范，包括所有端点、请求/响应格式、错误处理等。

### 基础信息

- **Windows 本地开发 Base URL**: `http://127.0.0.1:10004`（前端静态服务直连后端）
- **Ubuntu 生产前端代理 Base URL**: `/api`（nginx 将 `/api/*` 转发到后端）
- **Content-Type**: `application/json`
- **字符编码**: UTF-8

### 通用响应格式

所有 API 响应遵循以下格式：

```json
{
  "success": true,
  "data": {},
  "message": "操作成功"
}
```

错误响应：

```json
{
  "success": false,
  "error": "ERROR_CODE",
  "message": "人类可读的错误描述",
  "details": {}
}
```

## 2. 错误码定义

| 错误码 | HTTP 状态码 | 说明 |
|--------|-------------|------|
| UNAUTHORIZED | 401 | 未授权（未解锁或密码错误） |
| FORBIDDEN | 403 | 禁止访问（如锁定状态下尝试操作） |
| NOT_FOUND | 404 | 资源不存在 |
| CONFLICT | 409 | 并发冲突 |
| VALIDATION_ERROR | 422 | 数据验证失败 |
| ENCRYPTION_ERROR | 500 | 加密/解密失败 |
| FILE_ERROR | 500 | 文件读写错误 |
| AI_ERROR | 502 | AI 服务调用失败 |
| RATE_LIMITED | 429 | 请求过于频繁 |
| REQUEST_TOO_LARGE | 413 | 请求体或上传文件超过限制 |
| VAULT_LOCKED | 423 | vault 锁文件被占用，可能有旧进程或其他进程正在写入 |
| WEBDAV_* | 502 | WebDAV 连接、认证、证书、ETag 或条件写入能力失败；不会触发 SecretBase 会话锁定 |
| SYNC_* | 404 / 409 / 422 | 同步空间缺失、并发变化、冲突失效或协议数据无效 |

## 3. 认证模块

### 3.0 认证模型

| 阶段 | 模型 | 说明 |
|------|------|------|
| V1 | 服务端内存解锁态 | 解锁后后端进程在内存中缓存 vault 密码和明文数据；锁定或重启后失效。返回的 `token` 可为固定占位值，用于前端状态判断。 |
| V2 | 不透明 session token | 已实现。解锁后生成随机 token；需要认证的 API 必须携带 `Authorization: Bearer <token>`；重新解锁、锁定、自动锁定或服务重启后 token 失效。 |

V1 阶段不把 token 当作安全边界，真正的安全边界是“后端是否处于已解锁状态”。V2.0 起，token 已成为受保护 API 的请求级安全边界。公网部署仍必须配合 HTTPS、严格 CORS、防火墙和系统权限控制。

### 3.1 初始化主密码

**首次使用时设置主密码。**

```
POST /auth/init
```

**请求体：**

```json
{
  "password": "your-master-password"
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "token": "random-session-token"
  },
  "message": "主密码设置成功"
}
```

**错误情况：**

- 422: 新主密码长度不在 8 至 128 个字符范围内
- 409: 主密码已设置

### 3.2 解锁

**输入主密码解锁数据。**

```
POST /auth/unlock
```

**请求体：**

```json
{
  "password": "your-master-password"
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "token": "random-session-token"
  },
  "message": "解锁成功"
}
```

**错误情况：**

- 401: 密码错误
- 429: 尝试次数过多（5 分钟内最多 5 次）

### 3.3 锁定

**手动锁定，销毁内存中的密钥。**

```
POST /auth/lock
```

**响应：**

```json
{
  "success": true,
  "data": null,
  "message": "已锁定"
}
```

### 3.4 查询状态

**查询当前锁定状态。**

```
GET /auth/status
```

**响应：**

```json
{
  "success": true,
  "data": {
    "locked": false,
    "initialized": true,
    "auto_lock_minutes": 5
  }
}
```

### 3.5 修改主密码

**修改主密码，重新加密 vault 数据，并同步重加密本机 AI 安全设置、同步配置和同步基线。**

```
POST /auth/change-password
```

**请求体：**

```json
{
  "old_password": "current-password",
  "new_password": "new-password"
}
```

**响应：**

```json
{
  "success": true,
  "data": null,
  "message": "主密码已更新"
}
```

**错误情况：**

- 401: 旧密码错误
- 422: 新密码不符合要求

## 4. 条目管理模块

阶段：V1。

### 4.1 获取条目列表

**获取所有条目，支持分页、排序、筛选。**

```
GET /entries
```

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页数量，默认 20 |
| search | string | 否 | 搜索关键词；必须配合 `search_scopes` 指定范围，否则不匹配任何条目 |
| search_scopes | string | 否 | 搜索范围，逗号分隔；可选值：`title`、`url`、`tags`、`field_names`、`field_values`、`remarks`。未传或传空字符串时不匹配任何范围；可复制字段明文值始终不参与搜索 |
| ids | string | 否 | 指定条目 id 列表，逗号分隔，用于工具报告定位 |
| tag | string | 否 | 标签筛选 |
| group | string | 否 | 密码组筛选 |
| tags | string | 否 | 多标签筛选，逗号分隔，要求同时包含所有标签 |
| untagged | boolean | 否 | 仅无标签 |
| created_from | string | 否 | 创建时间起，ISO 字符串或日期前缀 |
| created_to | string | 否 | 创建时间止，ISO 字符串或日期前缀 |
| updated_from | string | 否 | 更新时间起，ISO 字符串或日期前缀 |
| updated_to | string | 否 | 更新时间止，ISO 字符串或日期前缀 |
| has_url | boolean | 否 | `true` 仅有网址，`false` 仅无网址 |
| has_remarks | boolean | 否 | `true` 仅有备注，`false` 仅无备注 |
| starred | boolean | 否 | 仅星标 |
| sort_by | string | 否 | 排序字段：updated_at / created_at / title |
| sort_order | string | 否 | 排序方向：asc / desc |

**响应：**

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "uuid",
        "title": "示例服务器",
        "url": "https://example.com/",
        "starred": true,
        "tags": ["示例云", "服务器", "重要"],
        "groups": ["工作账号", "服务器"],
        "fields": [
          {"name": "账号", "value": "demo-user", "copyable": true, "hidden": false, "masked": false},
          {"name": "密码", "value": "••••••", "copyable": true, "hidden": true, "masked": true}
        ],
        "remarks": "这是备注",
        "created_at": "2026-04-29T21:00:00+08:00",
        "updated_at": "2026-04-29T21:00:00+08:00"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 100,
      "total_pages": 5
    }
  }
}
```

**注意：** 列表接口必须对 `hidden=true` 的字段返回掩码值 `••••••`，并附带 `masked: true`。需要明文时通过 `GET /entries/{id}` 获取详情。`copyable=true` 只表示该字段提供复制入口，不再自动表示隐藏。兼容旧数据时，如果字段没有 `hidden` 属性且 `copyable=true`，服务端按隐藏字段处理。

### 4.2 获取单个条目

**获取条目详情（包含明文字段值）。**

```
GET /entries/{id}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "title": "示例服务器",
    "url": "https://example.com/",
    "starred": true,
    "tags": ["示例云", "服务器", "重要"],
    "groups": ["工作账号", "服务器"],
    "fields": [
      {"name": "账号", "value": "demo-user", "copyable": true, "hidden": false, "masked": false},
      {"name": "密码", "value": "demo-password", "copyable": true, "hidden": true, "masked": false}
    ],
    "remarks": "这是备注",
    "created_at": "2026-04-29T21:00:00+08:00",
    "updated_at": "2026-04-29T21:00:00+08:00"
  }
}
```

**错误情况：**

- 404: 条目不存在

### 4.3 创建条目

**新建条目。**

```
POST /entries
```

**请求体：**

```json
{
  "title": "新条目",
  "url": "https://example.com",
  "starred": false,
  "tags": ["标签1", "标签2"],
  "groups": ["工作账号"],
  "fields": [
    {"name": "账号", "value": "user@example.com", "copyable": true, "hidden": false},
    {"name": "密码", "value": "demo-password", "copyable": true, "hidden": true}
  ],
  "remarks": "备注信息"
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "id": "新生成的uuid",
    "title": "新条目",
    "created_at": "2026-04-29T21:00:00+08:00",
    "updated_at": "2026-04-29T21:00:00+08:00"
  },
  "message": "条目创建成功"
}
```

**错误情况：**

- 422: 数据验证失败（标题为空、字段名重复等）

### 4.4 更新条目

**更新现有条目。**

```
PUT /entries/{id}
```

**请求体：** （与创建相同，所有字段可选）

```json
{
  "title": "更新后的标题",
  "starred": true
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "updated_at": "2026-04-29T22:00:00+08:00"
  },
  "message": "条目更新成功"
}
```

**错误情况：**

- 404: 条目不存在
- 422: 数据验证失败

### 4.5 删除条目

**删除条目（移到回收站）。**

```
DELETE /entries/{id}
```

**响应：**

```json
{
  "success": true,
  "data": null,
  "message": "条目已移至回收站"
}
```

**错误情况：**

- 404: 条目不存在

### 4.6 批量删除

**批量删除多个条目。**

```
POST /entries/batch-delete
```

**请求体：**

```json
{
  "ids": ["uuid1", "uuid2", "uuid3"]
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "deleted_count": 3
  },
  "message": "已删除 3 个条目"
}
```

### 4.7 批量修改标签

**批量为条目添加或移除标签。**

```
POST /entries/batch-update-tags
```

**请求体：**

```json
{
  "ids": ["uuid1", "uuid2"],
  "add_tags": ["新标签"],
  "remove_tags": ["旧标签"]
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "updated_count": 2
  },
  "message": "已更新 2 个条目的标签"
}
```

### 4.8 批量星标

**批量设置或取消星标。**

```
POST /entries/batch-star
```

**请求体：**

```json
{
  "ids": ["uuid1", "uuid2"],
  "starred": true
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "updated_count": 2
  },
  "message": "已更新 2 个条目的星标状态"
}
```

## 5. 回收站模块

阶段：V1。

### 5.1 获取回收站条目

```
GET /trash
```

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页数量，默认 20 |

**响应：**

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "uuid",
        "title": "已删除的条目",
        "deleted_at": "2026-04-29T21:00:00+08:00",
        "expires_at": "2026-05-29T21:00:00+08:00"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 5,
      "total_pages": 1
    }
  }
}
```

### 5.2 恢复条目

```
POST /trash/{id}/restore
```

**响应：**

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "restored_at": "2026-04-30T10:00:00+08:00"
  },
  "message": "条目已恢复"
}
```

**错误情况：**

- 404: 条目不在回收站中

### 5.3 彻底删除

```
DELETE /trash/{id}
```

**响应：**

```json
{
  "success": true,
  "data": null,
  "message": "条目已彻底删除"
}
```

**错误情况：**

- 404: 条目不在回收站中

### 5.4 清空回收站

```
POST /trash/empty
```

**响应：**

```json
{
  "success": true,
  "data": {
    "deleted_count": 5
  },
  "message": "回收站已清空，删除了 5 个条目"
}
```

## 6. 标签管理模块

阶段：V1。

### 6.1 获取所有标签

```
GET /tags
```

**响应：**

```json
{
  "success": true,
  "data": {
    "tags": [
      {
        "name": "示例云",
        "description": "云平台和控制台账号",
        "color": "#ff6600",
        "count": 3,
        "created_at": "2026-07-08T10:00:00",
        "updated_at": "2026-07-08T10:00:00"
      },
      {
        "name": "服务器",
        "description": "",
        "color": "#0066ff",
        "count": 5,
        "created_at": "",
        "updated_at": ""
      }
    ]
  }
}
```

标签是独立实体，可以没有绑定条目。`GET /tags` 返回 `tags_meta` 中的空标签，也返回历史条目中存在但缺少元数据的标签。

### 6.2 创建标签

```
POST /tags
```

**请求体：**

```json
{
  "name": "云服务",
  "description": "云平台和控制台账号",
  "color": "#2563eb"
}
```

**错误情况：**

- 409: 标签已存在
- 422: 标签名或颜色无效

### 6.3 更新标签

```
PUT /tags/{name}
```

**请求体：**

```json
{
  "name": "新标签名",
  "description": "标签简介",
  "color": "#16a34a"
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "old_name": "旧标签名",
    "new_name": "新标签名",
    "affected_count": 3
  },
  "message": "标签已更新"
}
```

**错误情况：**

- 404: 标签不存在
- 409: 新标签名已存在

### 6.4 删除标签

**删除标签实体，并从所有条目中移除该标签。空标签也可以删除。**

```
DELETE /tags/{name}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "affected_count": 5
  },
  "message": "标签已从 5 个条目中移除"
}
```

**错误情况：**

- 404: 标签不存在

### 6.5 批量删除标签

**一次删除多个标签实体，并从所有条目中移除这些标签。不存在的标签会在响应中返回，不影响已存在标签的删除。**

```
POST /tags/batch-delete
```

**请求体：**

```json
{
  "names": ["标签A", "标签B", "不存在标签"]
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "deleted_tags": ["标签A", "标签B"],
    "missing_tags": ["不存在标签"],
    "affected_count": 5
  },
  "message": "已删除 2 个标签，影响 5 个条目"
}
```

**错误情况：**

- 404: 请求中的标签均不存在
- 422: 标签名无效

### 6.6 合并标签

**将多个标签合并为一个，并维护目标标签的简介和颜色。**

```
POST /tags/merge
```

**请求体：**

```json
{
  "source_tags": ["标签A", "标签B"],
  "target_tag": "合并后的标签",
  "description": "合并后的标签简介",
  "color": "#f97316"
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "merged_count": 2,
    "affected_entries": 10
  },
  "message": "已将 2 个标签合并，影响 10 个条目"
}
```

**错误情况：**

- 404: 源标签不存在
- 422: 目标标签名无效

## 6A. 密码组管理模块

阶段：V1.4。

### 6A.1 获取所有密码组

```
GET /groups
```

**响应：**

```json
{
  "success": true,
  "data": {
    "groups": [
      {
        "name": "工作账号",
        "description": "公司系统、云平台、协作工具",
        "count": 3,
        "updated_at": "2026-07-08T10:00:00+08:00",
        "color": "#0066ff",
        "order_index": 0
      }
    ]
  }
}
```

未设置自定义排序时，密码组按条目数量降序、名称升序返回，`order_index` 为 `null`。设置自定义排序后，返回顺序优先使用 `order_index`，新出现且尚未写入顺序的密码组排在已有自定义顺序之后。

### 6A.2 创建密码组

```
POST /groups
```

**请求体：**

```json
{
  "name": "工作账号",
  "description": "公司系统、云平台、协作工具"
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "name": "工作账号"
  },
  "message": "密码组已创建"
}
```

**错误情况：**

- 409: 密码组已存在
- 422: 密码组名称为空或无效

### 6A.3 更新密码组

```
PUT /groups/{group_name}
```

**请求体：**

```json
{
  "name": "工作",
  "description": "工作相关密码"
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "old_name": "工作账号",
    "new_name": "工作"
  },
  "message": "密码组已更新"
}
```

**错误情况：**

- 404: 密码组不存在
- 409: 新密码组名称已存在

### 6A.4 更新密码组自定义排序

**保存密码组展示顺序。前端不需要单独排序组件，可在密码组卡片上通过上移/下移提交当前名称顺序。**

```
POST /groups/order
```

**请求体：**

```json
{
  "names": ["邮箱", "服务器", "工作账号", "开发资源"]
}
```

传入空数组表示清空自定义排序，恢复默认条目数量排序：

```json
{
  "names": []
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "groups": [
      {
        "name": "邮箱",
        "description": "",
        "count": 1,
        "updated_at": "2026-07-08T10:00:00+08:00",
        "color": "#0066ff",
        "order_index": 0
      }
    ]
  },
  "message": "密码组排序已更新"
}
```

服务端会忽略重复名称，并把未出现在 `names` 中的现有密码组追加到末尾。`names` 包含不存在的密码组时返回 `422`。

### 6A.5 删除密码组

**删除密码组元数据，并从所有条目中移除该组；不会删除条目。**

```
DELETE /groups/{group_name}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "affected_count": 5
  },
  "message": "密码组已移除，影响 5 个条目"
}
```

**错误情况：**

- 404: 密码组不存在

### 6A.6 批量将条目加入密码组

**将现有条目批量加入指定密码组；不会删除条目，也不会移除条目已有密码组。**

```
POST /groups/{group_name}/entries
```

**请求体：**

```json
{
  "ids": ["entry-uuid-1", "entry-uuid-2"]
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "updated_count": 1,
    "skipped_count": 1,
    "missing_count": 0
  },
  "message": "已将 1 个条目加入「工作账号」"
}
```

`updated_count` 表示本次新增归属的条目数量；`skipped_count` 表示已经属于该密码组的条目数量；`missing_count` 表示请求中不存在或已删除的条目数量。

**错误情况：**

- 404: 密码组不存在
- 422: 密码组名称为空或 ids 为空

## 7. AI 管家与专业工具模块

AI 是可选能力，未配置 API Key 时不能阻塞任何本地密码库功能。内置 OpenAI、DeepSeek、Kimi、智谱 GLM、SiliconFlow、Gemini、OpenRouter 和自定义 OpenAI-compatible 预设；所有 Base URL 均可手动编辑，不内置 Qwen。模型列表获取失败时允许用户手工填写模型 ID。

```
GET /ai/providers
```

该接口返回厂商名称、默认 Base URL、结构化输出模式和是否为聚合服务，不返回任何用户配置或 API Key。

### 7.0 查询 AI 状态

**查询 AI 是否已配置。该接口只返回厂商、Base URL、模型名、结构化输出模式和 Key 掩码，绝不能返回完整 API Key。**

```
GET /ai/status
```

**响应：**

```json
{
  "success": true,
  "data": {
    "configured": false,
    "provider_id": "custom",
    "provider_name": "自定义接口",
    "base_url": "",
    "model": "",
    "api_key_mask": "",
    "structured_output": "auto",
    "customized": false
  }
}
```

**错误情况：**

- 401: 未解锁

### 7.1 获取模型列表

**实时从 OpenAI-compatible 服务商拉取模型列表，不保存配置。Base URL 示例：`https://api.deepseek.com`、`https://api.openai.com/v1`。**

```
POST /ai/models
```

**请求体：**

```json
{
  "providerId": "deepseek",
  "baseUrl": "https://api.deepseek.com",
  "apiKey": "sk-..."
}
```

已保存 AI 配置后，如果 `baseUrl` 与当前保存值一致，`apiKey` 可以省略，后端会使用本机加密保存的 Key 重新拉取模型列表。

**响应：**

```json
{
  "success": true,
  "data": {
    "models": ["deepseek-v4-flash", "deepseek-v4-pro"],
    "provider_id": "deepseek"
  }
}
```

**错误情况：**

- 401: 未解锁
- 422: Base URL 或 API Key 缺失/无效
- 502: 服务商认证失败、网络错误、超时或模型列表响应格式无效

### 7.2 保存 AI 设置

**保存 AI 厂商、Base URL、模型和 API Key。后端使用固定无敏感请求验证模型连通性；不要求模型列表接口一定可用。**

```
PUT /ai/settings
```

**请求体：**

```json
{
  "baseUrl": "https://api.deepseek.com",
  "providerId": "deepseek",
  "apiKey": "sk-...",
  "model": "deepseek-v4-flash"
}
```

已保存 AI 配置后，如果只更换同一 Base URL 下的模型，`apiKey` 可以省略。API Key 只写入本机加密安全设置文件，不写入明文 `settings.json`，也不进入 vault 备份/恢复。外部地址必须使用 HTTPS；桌面模式仅允许显式配置回环 HTTP 接口。

**响应：**

```json
{
  "success": true,
  "data": {
    "configured": true,
    "provider_id": "deepseek",
    "provider_name": "DeepSeek",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-v4-flash",
    "api_key_mask": "sk-...abcd",
    "structured_output": "response_format",
    "customized": false
  },
  "message": "AI 设置已保存"
}
```

**错误情况：**

- 401: 未解锁
- 422: Base URL、API Key 或模型无效，或目标地址被安全策略阻止
- 502: 固定连通测试失败

### 7.3 清除 AI 设置

**显式清除本机加密保存的 AI 设置。**

```
DELETE /ai/settings
```

**响应：**

```json
{
  "success": true,
  "data": {
    "configured": false,
    "provider_id": "custom",
    "provider_name": "自定义接口",
    "base_url": "",
    "model": "",
    "api_key_mask": "",
    "structured_output": "auto",
    "customized": false
  },
  "message": "AI 设置已清除"
}
```

**错误情况：**

- 401: 未解锁

### 7.4 解析文本

**使用 AI 解析自然语言文本为条目结构。**

AI 解析要求用户已解锁并完成 AI 设置。前端调用前必须先查询 `GET /ai/status`，未配置时提示用户进入设置页配置 AI。单次输入最多 6000 个字符。AI 会尝试自主判断输入中是否包含多个独立条目。后端请求模型时使用严格 JSON object 输出约束，要求顶层返回 `entries` 数组。为兼容旧前端，响应仍保留 `parsed` 表示第一条解析结果；V1.2 新增 `parsed_entries` 和 `entry_count` 用于多条目录入。后端会归一化常见 AI 格式偏差，如 `items`、`accounts`、`records`、字段字典、标签字符串、`copyable`/`hidden` 字符串等。

```
POST /ai/parse
```

**请求体：**

```json
{
  "text": "示例服务器 账号:demo-user 密码:demo-password IP:192.0.2.10"
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "parsed": {
      "title": "示例服务器",
      "url": "",
      "fields": [
        {"name": "账号", "value": "demo-user", "copyable": true, "hidden": false},
        {"name": "密码", "value": "demo-password", "copyable": true, "hidden": true},
        {"name": "IP", "value": "192.0.2.10", "copyable": true, "hidden": false}
      ],
      "tags": ["示例云", "服务器"],
      "groups": ["服务器"],
      "remarks": ""
    },
    "parsed_entries": [
      {
        "title": "示例服务器",
        "url": "",
        "fields": [
          {"name": "账号", "value": "demo-user", "copyable": true, "hidden": false},
          {"name": "密码", "value": "demo-password", "copyable": true, "hidden": true},
          {"name": "IP", "value": "192.0.2.10", "copyable": true, "hidden": false}
        ],
        "tags": ["示例云", "服务器"],
        "groups": ["服务器"],
        "remarks": ""
      }
    ],
    "entry_count": 1,
    "confidence": 0.95
  }
}
```

**错误情况：**

- 502: AI 服务未配置或服务不可用
- 422: 无法解析输入文本
- 429: 5 秒内重复解析，或内容未变化重复解析

### 7.5 生成 AI 整理建议

**基于当前筛选范围，为条目生成标签或密码组整理建议。该接口只返回建议，不写入 vault。**

整理请求只发送条目标题、网址 hostname、字段名、现有标签和密码组，不发送字段值、完整网址、备注或真实 UUID。标签整理和密码组整理必须分开执行，`organize_tags` 与 `organize_groups` 不能同时为 `true`。单次最多整理 100 条，超过后前端应提示缩小筛选范围。

```
POST /ai/organize/preview
```

**请求体：**

```json
{
  "filters": {
    "tag": "待整理",
    "group": "",
    "search": "",
    "searchScopes": [],
    "sortBy": "updated_at",
    "sortOrder": "desc"
  },
  "organize_tags": true,
  "organize_groups": false,
  "user_prompt": "本次优先保留现有标签，只补充缺失标签"
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "entry_count": 1,
    "plan_token": "server-side-token",
    "source_revision": 8,
    "summary": {
      "affected_entries": 1,
      "add_tags": 2,
      "remove_tags": 1,
      "add_groups": 1,
      "add_group_assignments": 1,
      "assigned_groups": 1,
      "remove_groups": 0
    },
    "suggestions": [
      {
        "id": "organize-1",
        "entry_id": "uuid",
        "entry_title": "公司邮箱",
        "selected": true,
        "current_tags": ["待整理"],
        "current_groups": [],
        "add_tags": ["邮箱", "工作"],
        "remove_tags": ["待整理"],
        "add_groups": ["工作账号"],
        "remove_groups": [],
        "group_descriptions": {
          "工作账号": "公司邮箱、协作工具和内部系统"
        },
        "reason": "标题和字段名显示这是工作邮箱账号"
      }
    ],
    "warnings": [],
    "privacy_note": "本次整理未向 AI 发送任何字段值。"
  }
}
```

`summary.add_groups` 表示本次建议中需要新建的唯一密码组数量；`summary.add_group_assignments` 表示条目加入密码组的分配次数；`summary.assigned_groups` 表示本次涉及加入的唯一密码组数量。

**错误情况：**

- 401: 未解锁
- 413: 当前筛选结果超过 100 条
- 422: 没有可整理条目，未选择整理标签/密码组，或同时选择了标签和密码组
- 502: AI 服务未配置或服务不可用

### 7.6 应用 AI 整理建议

**应用用户确认后的整理建议。动作正文保存在服务端待处理区，前端只能提交计划令牌和所选建议 ID。**

```
POST /ai/organize/apply
```

**请求体：**

```json
{
  "plan_token": "server-side-token",
  "selected_ids": ["organize-1"],
  "expected_revision": 8
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "updated_count": 1,
    "created_groups": ["工作账号"],
    "undo_token": "undo-token",
    "revision": 9
  },
  "message": "已整理 1 个条目"
}
```

**错误情况：**

- 401: 未解锁
- 409: Vault revision 已变化
- 410: 计划已过期或不属于当前解锁会话
- 422: 未选择有效建议

### 7.7 生成 AI 标签系统管理建议

**面向标签体系本身生成治理建议。该接口独立于条目标签整理和密码组整理，默认分析当前密码库未删除条目，最多 100 条。不会向 AI 发送字段值。**

```
POST /ai/tags/preview
```

**请求体：**

```json
{
  "filters": {},
  "user_prompt": "本次优先合并语义重复标签，不要删除高频标签"
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "entry_count": 2,
    "plan_token": "server-side-token",
    "source_revision": 8,
    "summary": {
      "total_actions": 3,
      "affected_entries": 1,
      "create_tag": 1,
      "update_tag": 1,
      "delete_tag": 0,
      "merge_tags": 1,
      "replace_tag": 0,
      "assign_tag": 0
    },
    "suggestions": [
      {
        "id": "tag-1",
        "action": "merge_tags",
        "selected": true,
        "source_tags": ["git", "代码"],
        "target_tag": "代码仓库",
        "description": "代码托管和版本管理账号",
        "color": "#0891b2",
        "entry_ids": [],
        "reason": "两个标签语义高度相近"
      }
    ],
    "warnings": [],
    "privacy_note": "本次标签系统管理不会发送任何字段值。"
  }
}
```

支持动作：`create_tag`、`update_tag`、`delete_tag`、`merge_tags`、`replace_tag`、`assign_tag`。所有建议都必须由用户确认后再应用。

### 7.8 应用 AI 标签系统管理建议

```
POST /ai/tags/apply
```

**请求体：**

```json
{
  "plan_token": "server-side-token",
  "selected_ids": ["tag-1"],
  "expected_revision": 8
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "applied_count": 1,
    "updated_entries": 1
  },
  "message": "已应用 1 条标签管理建议"
}
```

### 7.9 生成 AI 交互操作计划

**根据用户自然语言指令生成结构化操作计划。该接口只返回计划，不写入 vault。**

后端只发送条目标题、网址 hostname、标签、密码组、字段名、字段索引和字段隐藏/可复制状态，不发送字段值、完整网址、备注或真实 UUID。AI 返回的危险动作会被过滤；字段拆分时真实字段值只在 `/ai/actions/apply` 中由后端本地复制。

```
POST /ai/actions/preview
```

**请求体：**

```json
{
  "instruction": "创建 demo-service 密码组，将 demo.example 条目的三个字段独立作为条目，从属于该密码组",
  "filters": {
    "search": "demo",
    "searchScopes": ["title"]
  }
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "entry_count": 1,
    "plan_token": "server-side-token",
    "source_revision": 8,
    "summary": {
      "total_actions": 6,
      "create_group": 1,
      "update_group": 1,
      "create_entry": 0,
      "create_entry_from_field": 3,
      "update_entry": 1
    },
    "actions": [
      {
        "id": "action-1",
        "type": "create_group",
        "selected": true,
        "group": "demo-service",
        "description": "demo.example 相关凭据",
        "reason": "用户要求创建独立密码组"
      },
      {
        "type": "update_group",
        "selected": true,
        "group": "待归档",
        "group_new": "客户系统",
        "description": "客户系统和业务资料相关凭据",
        "reason": "用户希望整理已有密码组"
      },
      {
        "type": "create_entry_from_field",
        "selected": true,
        "source_entry_id": "uuid",
        "source_entry_title": "demo.example",
        "field_index": 0,
        "field_name": "账号",
        "title": "demo-service 账号",
        "groups": ["demo-service"],
        "tags": ["demo-service"],
        "reason": "把字段拆成独立条目"
      },
      {
        "type": "update_entry",
        "selected": true,
        "entry_id": "uuid",
        "entry_title": "demo.example",
        "add_tags": ["云平台"],
        "reason": "给原条目补充分类标签"
      }
    ],
    "warnings": [],
    "privacy_note": "本次 AI 交互不会发送任何字段值，字段拆分由后端本地复制真实值。"
  }
}
```

允许动作：`create_group`、`update_group`、`create_entry`、`create_entry_from_field`、`update_entry`。`update_group` 必须提供原密码组 `group`，可通过 `group_new` 改名，也可通过 `description` 更新简介；至少提供其中一项。不允许删除条目、删除字段、覆盖字段值或删除密码组。`update_entry` 只能更新标题、标签、密码组和字段名，不能修改已有网址或备注。

**错误情况：**

- 401: 未解锁
- 413: 当前筛选结果超过 100 条
- 422: 指令为空或当前筛选范围没有可分析条目
- 502: AI 服务未配置或服务不可用

### 7.10 应用 AI 交互操作计划

```
POST /ai/actions/apply
```

**请求体：**

```json
{
  "plan_token": "server-side-token",
  "selected_ids": ["action-1"],
  "expected_revision": 8
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "applied_count": 1,
    "created_entries": 1,
    "created_groups": 0,
    "updated_groups": 0,
    "updated_entries": 0
  },
  "message": "已应用 1 项 AI 操作计划"
}
```

应用前后端会重新校验来源条目、字段索引、字段名、解锁会话和 Vault revision，并在写入前创建加密恢复快照。任何选中动作无效时都不会写入。

### 7.11 对话式 AI 管家

默认 AI 工作区使用三阶段协议：`preview` 不接收用户提示词，只生成目标服务、数据类型、范围和临时别名清单；用户逐次确认后，`prepare` 才绑定本轮提示词；`submit` 原子消费令牌并调用模型。普通模式禁止发送已有字段值、完整 URL、备注和真实 UUID；`sensitive_create` 仅用于用户主动提交新条目原文。

```text
GET    /ai/assistant/conversations
POST   /ai/assistant/conversations
GET    /ai/assistant/conversations/{conversation_id}
DELETE /ai/assistant/conversations/{conversation_id}
DELETE /ai/assistant/conversations
POST   /ai/assistant/scope/catalog
POST   /ai/assistant/turns/preview
POST   /ai/assistant/turns/prepare
POST   /ai/assistant/turns/submit
POST   /ai/assistant/plans/apply
POST   /ai/assistant/plans/undo
GET    /ai/assistant/diagnostics/preview
POST   /ai/assistant/diagnostics/run
GET    /ai/assistant/diagnostics/status
```

`POST /ai/assistant/turns/preview` 请求示例：

```json
{
  "mode": "assistant",
  "scope": "all",
  "filters": {}
}
```

`scope` 默认为 `all`。`current_view` 表示主页当前筛选条件命中的全部分页结果，不等同于当前可见页；`selection` 只使用 `filters.entryIds` 指定的自定义条目，不继续叠加主页筛选条件。

`POST /ai/assistant/scope/catalog` 用于范围选择弹窗，请求可包含主页筛选条件、标题或 hostname 搜索、标签、密码组、收藏状态、分页和已选 ID。响应仅返回条目 ID、标题、hostname、标签、密码组和收藏状态，同时返回全部条目数、当前筛选结果数和仍然有效的已选 ID；不得返回字段、字段值、备注或完整 URL。该接口只访问本地密码库，不调用第三方 AI。

响应包含 `preview_token`、目标厂商、目标 host、模型、数据类型、条目数量、风险提示和 `source_revision`，但该请求及服务端待处理项均不包含用户提示词。前端必须展示发送清单和仍保留在浏览器内的提示词，不允许自动跳过确认。

用户确认后的 `POST /ai/assistant/turns/prepare` 请求：

```json
{
  "preview_token": "server-side-preview-token",
  "conversation_id": null,
  "message": "帮我统一当前范围内的字段命名"
}
```

`prepare` 会校验 Vault revision 与 AI 厂商、Base URL、模型是否仍和确认页一致。要求读取、列出、显示、复制或导出已有字段值的请求会在此阶段本地终止，不会进入第三方调用队列；其他请求返回一次性 `turn_token`。配置或密码库变化时必须重新预览和确认。

`POST /ai/assistant/turns/submit` 只接收 `turn_token` 和值为 `true` 的 `acknowledge_risk`。该令牌在进入模型调用前原子消费，重复点击、重放或并发请求不会再次调用第三方 AI。模型允许返回密码组管理、标签管理、条目/字段重命名、空字段、字段属性、空条目模板、本地字段拆分和条目定位动作；不提供删除条目、删除字段、字段值写入、已有 URL/备注修改或密码组删除动作。服务端还会按原始指令再次执行字段值访问策略，禁止模型用 `open_entry` 等动作规避限制。

若模型对一句请求返回多个管理领域，Web/桌面服务端将全部可执行动作保存在同一个复合计划令牌中。`submit` 返回 `domain: "mixed"`、实际 `domains`、全部 `actions` 和可选 `conflicts`；每个 action 带所属 `domain`，也可带仅用于本地详情定位的 `entry_targets: [{"id": "...", "title": "..."}]`，不包含字段、字段值、备注或完整 URL。前端按领域分组审核，点击“查看条目”后复用 `GET /entries/{entry_id}` 在本地按需读取完整详情，不得将读取结果加入后续 AI 请求。

计划应用请求统一为：

```json
{
  "plan_token": "server-side-token",
  "selected_ids": ["assistant-1"],
  "expected_revision": 8
}
```

`plans/apply` 会先在不消费计划令牌的情况下检查当前选中项；如果冲突仍同时被选中，返回 422，用户可以取消其中一项后重试。通过校验后令牌才会原子消费，动作按固定阶段排序并在单个 Vault 副本中执行；任一动作失败都不会保存。成功写入只返回一个 `undo_token`、新 revision 和实际领域列表。用户输入精确的“确认”“确认执行”等确认词时，前端只调用当前 `/plans/apply`，不得把确认词再次发送给模型。撤销接口只能在 Vault 未发生其他变化时使用。对话历史使用用途隔离密钥保存在本机加密文件中；AI 新建原文不会写入历史或后续模型上下文。

真实模型兼容性诊断必须先调用 `GET /ai/assistant/diagnostics/preview` 展示测试数量、数据类型和保守 token 上限，再由用户提交：

```json
{
  "acknowledge_cost": true
}
```

`POST /ai/assistant/diagnostics/run` 在后台依次执行 16 个合成场景，`GET /ai/assistant/diagnostics/status` 返回进度、场景结果和建议。诊断请求只包含合成标题、hostname、标签、密码组和字段名；不读取真实 Vault，不发送字段值，也不会创建服务端待应用计划。模型返回禁止动作或禁止键时仍由正式计划归一化器拦截。当前保守估算约 13 万 token，代码硬上限为 30 万 token。

## 8. 导入导出模块

阶段：V1.1。该模块是完整愿景的一部分，但不阻塞 V1 基础可用版发布。

### 8.1 导出加密备份

**导出加密的备份文件。**

```
POST /export/encrypted
```

**响应：**

返回文件流，Content-Type: `application/octet-stream`

```
Content-Disposition: attachment; filename="secretbase-backup-20260429.enc"
```

### 8.2 导出明文 JSON

**导出明文 JSON 文件（需要二次确认）。**

```
POST /export/plain
```

**请求体：**

```json
{
  "confirm": true
}
```

**响应：**

返回文件流，Content-Type: `application/json`

```
Content-Disposition: attachment; filename="secretbase-backup-20260429.json"
```

**错误情况：**

- 422: 未确认导出（confirm 不为 true）

### 8.3 导入加密备份

导入加密备份要求当前 vault 已解锁，且上传文件必须能被当前主密码解密。导入前后端会先自动备份当前数据文件。

```
POST /import/encrypted
```

**请求体：** `multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | file | 是 | 加密备份文件 |
| password | string | 否 | V2.2 起可选；用于导入不同 salt 的旧加密备份 |

V2.2 起，未提供 `password` 且当前会话密钥无法读取上传备份时，返回 `BACKUP_PASSWORD_REQUIRED` 和 `data.needs_password=true`。

**响应：**

```json
{
  "success": true,
  "data": {
    "imported_count": 50,
    "skipped_count": 0,
    "conflicts": []
  },
  "message": "成功导入 50 个条目"
}
```

### 8.4 导入明文 JSON

```
POST /import/plain
```

**请求体：** `multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | file | 是 | JSON 文件 |
| conflict_strategy | string | 否 | 冲突处理策略：skip / overwrite / ask |

当前前端支持三种冲突策略：跳过已有条目、覆盖已有条目、发现冲突时停止并提示。

导入成功的条目会合并其引用标签和密码组的元数据。已有本地元数据优先；本地说明为空时才使用导入文件中的标签说明、标签颜色或密码组简介。导入文件中与回收站条目相同的 ID 同样属于冲突；`overwrite` 会以导入条目恢复该 ID，避免活动条目与回收站出现重复 ID。

前端必须把 `ask` 策略下返回的冲突展示为详情弹窗，而不是只显示 toast。弹窗至少展示冲突数量、前若干条冲突标题，并提示用户可改用“跳过已有条目”或“覆盖已有条目”后重新导入。

**响应（无冲突）：**

```json
{
  "success": true,
  "data": {
    "imported_count": 50,
    "skipped_count": 0,
    "conflicts": []
  },
  "message": "成功导入 50 个条目"
}
```

**响应（有冲突，策略为 ask）：**

```json
{
  "success": false,
  "error": "CONFLICT",
  "data": {
    "conflicts": [
      {
        "id": "uuid",
        "existing_title": "现有条目",
        "import_title": "导入条目",
        "existing_deleted": false
      }
    ]
  },
  "message": "发现冲突，请选择处理方式"
}
```

### 8.5 示例数据

阶段：V1.1。示例数据不新增后端接口，避免污染 API。前端在首次引导中本地生成明显的假示例条目，并逐条调用 `POST /entries` 创建。

示例条目必须满足：

- 标题清楚标记为示例。
- 标签包含 `示例`。
- 备注说明“这是示例数据，可删除”。
- 不包含真实服务、真实账号或真实密码。

### 8.6 导入明文 JSON 预览

阶段：V1.2/V1.3。导入前只解析上传文件并与当前 vault 对比，不写入数据。V1.3 起响应包含 `entries` 预览列表，用于前端逐条勾选导入。

```
POST /import/plain/preview
```

**响应：**

```json
{
  "success": true,
  "data": {
    "total_count": 50,
    "new_count": 45,
    "conflict_count": 5,
    "entries": [
      {"id": "uuid", "title": "导入条目", "is_conflict": false, "field_count": 3, "tag_count": 2, "tags": ["服务器"]}
    ],
    "conflicts": [
      {"id": "uuid", "existing_title": "现有条目", "import_title": "导入条目", "existing_deleted": false}
    ]
  }
}
```

`POST /import/plain` 额外接受可选表单字段 `selected_entry_ids`，值为 JSON 字符串数组或逗号分隔字符串。传入后只导入这些 id 对应的条目；未传时保持旧行为，导入文件内全部条目。

`POST /import/plain` 额外接受可选表单字段 `conflict_resolutions`，值为 JSON object，key 为导入条目 id，value 为 `skip`、`overwrite` 或 `ask`。逐条策略优先于全局 `conflict_strategy`。

V1.4 起，`POST /import/plain` 成功响应的 `data` 中除保留 `imported_count`、`skipped_count`、`conflicts` 外，新增：

- `created_count`：本次新增条目数量。
- `overwritten_count`：本次覆盖已有条目数量。

这两个字段用于前端导入完成报告；旧前端可继续只读取 `imported_count` 和 `skipped_count`。

### 8.7 备份管理

阶段：V1.2/V1.3/V2.4。备份管理接口必须要求解锁。

```
GET /backups
POST /backups
GET /backups/{filename}/download/encrypted
POST /backups/{filename}/download/plain
GET /backups/{filename}/summary
POST /backups/{filename}/summary
POST /backups/{filename}/restore
```

`GET /backups` 返回备份文件名、类型、可读显示名、建议下载名、大小、修改时间，以及能用当前会话密钥读取时的条目数和回收站数。`type` 为 `manual`、`auto` 或兼容旧目录时的 `legacy`。`POST /backups` 手动创建当前 vault 的加密备份，并写入 `BACKUP_DIR/manual/`。写入 vault 或恢复备份前创建的自动快照写入 `BACKUP_DIR/auto/`。

自动备份按设置项 `auto_backup_retention` 数量轮转，默认保留 30 个，范围 5-200；手动备份不参与自动轮转。旧版本根目录下的 `secretbase.enc.*.bak` 会在备份列表、手动备份或恢复路径解析时默认迁移到 `BACKUP_DIR/auto/`。

`GET /backups/{filename}/download/encrypted` 下载指定服务器备份的加密 `.bak` 文件。`POST /backups/{filename}/download/plain` 下载指定服务器备份的明文 JSON，请求体必须包含 `{ "confirm": true }`；旧备份或不同 salt 备份还可传 `{ "password": "backup-master-password" }`。未确认、未提供所需密码或密码错误均返回 422。

`GET /backups/{filename}/summary` 使用当前会话密钥解密备份并返回条目数、回收站条目数、版本、文件大小、修改时间、类型，以及当前 vault 的条目数和回收站条目数，供恢复向导核对影响。

`GET /backups` 响应示例：

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "filename": "secretbase.manual.20260512_153000_123456.bak",
        "type": "manual",
        "display_name": "手动备份-2026年05月12日15时30分00秒.bak",
        "download_name_encrypted": "手动备份-2026年05月12日15时30分00秒.bak",
        "download_name_plain": "手动备份-2026年05月12日15时30分00秒.json",
        "size": 4096,
        "modified_at": "2026-05-12T15:30:00",
        "entry_count": 50,
        "deleted_count": 2,
        "created_at": "2026-05-01T10:00:00",
        "version": "1.0",
        "summary_available": true,
        "needs_password": false
      },
      {
        "filename": "secretbase.auto.20260512_152900_123456.bak",
        "type": "auto",
        "display_name": "自动备份-2026年05月12日15时29分00秒.bak",
        "download_name_encrypted": "自动备份-2026年05月12日15时29分00秒.bak",
        "download_name_plain": "自动备份-2026年05月12日15时29分00秒.json",
        "size": 4096,
        "modified_at": "2026-05-12T15:29:00",
        "entry_count": null,
        "deleted_count": null,
        "created_at": null,
        "version": null,
        "summary_available": false,
        "needs_password": true
      }
    ],
    "total": 2
  }
}
```

V2.2 起，`POST /backups/{filename}/summary` 可使用请求体 `{ "password": "backup-master-password" }` 读取不同 salt 的旧备份概况。

备份概况响应中的 `current_entry_count` 和 `current_deleted_count` 表示当前 vault 状态；`entry_count` 和 `deleted_count` 表示该备份恢复后的目标状态。

V2.2 起，`POST /backups/{filename}/restore` 支持请求体 `{ "password": "backup-master-password" }`。带密码恢复成功后，后端会用当前解锁会话密钥重新写回 vault，不升级文件格式。

若备份无法用当前会话密钥读取，返回：

```json
{
  "success": false,
  "error": "BACKUP_PASSWORD_REQUIRED",
  "message": "备份无法用当前会话密钥读取，可能是旧备份或主密码不匹配。请输入该备份对应的主密码后重试。",
  "data": {"needs_password": true}
}
```

## 8A. 管理工具模块

阶段：V1.2。所有接口要求解锁，只在本地解锁数据中计算，不上传任何内容。

### 8A.1 密码健康检查

```
GET /tools/health-report
```

返回弱密码、重复密码、长期未更新条目统计和样例。

### 8A.2 数据维护报告

```
GET /tools/maintenance-report
```

返回重复标题、无标签条目、空字段条目、示例数据条目统计和样例。

### 8A.3 安全自检

阶段：V2.2。接口要求解锁，不返回敏感环境变量值。

```
GET /tools/security-report
```

返回 HOST、CORS、vault 目录、备份目录和日志目录的检查结果。生产环境如果 `CORS_ORIGINS=*` 或后端监听非 `127.0.0.1`，应显示 warning。

## 8B. WebDAV 端到端加密同步

阶段：V5.2。完整二进制协议、WebDAV 条件提交和三方合并规则见 [Sync Protocol V1](sync-protocol-v1.md)。所有接口都要求 Vault 已解锁并携带有效 session token。

同步 API 同时挂载在 `/sync/*` 和 `/api/sync/*`。WebDAV 密码、同步密钥、恢复码和字段值不得出现在状态、冲突或历史列表响应中。

### 8B.1 查询同步状态

```
GET /sync/status
```

响应 `data` 包含 `configured`、`pending_join`、`phase`、`message`、`last_error`、`pending_conflicts`、`auto_sync`、`host`、`base_url`、脱敏 `username_mask`、`device_name`、`vault_id`、`last_synced_at` 和 `generation`。加入现有 Vault 产生冲突时，`pending_join=true` 且 `configured=false`，避免客户端把尚未持久化的配置误当成可用同步连接。

### 8B.2 测试 WebDAV 能力

```
POST /sync/config/test
```

```json
{
  "base_url": "https://dav.example.invalid/secretbase",
  "username": "user",
  "password": "app-password",
  "device_name": "Windows 工作站",
  "auto_sync": true
}
```

服务端会创建临时探测目录，验证强 ETag、`If-None-Match`、当前/过期 `If-Match`、条件删除和读写一致性后清理。生产接口只允许 HTTPS；本机 HTTP 仅用于注入式自动化传输测试。

### 8B.3 创建同步空间

```
POST /sync/create
```

请求体与连接测试相同。成功后上传当前完整 Vault 的首个加密快照，只返回同步状态，不直接返回恢复码。前端必须再通过 8B.9 验证主密码后显示配对材料。

### 8B.4 加入同步空间

```
POST /sync/join
```

```json
{
  "base_url": "https://dav.example.invalid/secretbase",
  "username": "user",
  "password": "app-password",
  "device_name": "macOS 笔记本",
  "auto_sync": true,
  "recovery_code": "SBSYNC1-...",
  "merge_existing": false
}
```

当前 Vault 有内容时必须显式设置 `merge_existing=true`。无冲突时直接加入；存在同实体双端修改时返回 `conflict_token` 和脱敏 `conflicts`，本机配置仅在冲突成功处理后持久化。

### 8B.5 更新或断开本机配置

```
PUT /sync/config
DELETE /sync/config
```

`PUT` 可选更新 `base_url`、`username`、`password`、`device_name` 和 `auto_sync`。连接字段变化时会验证远端当前 Vault；仅修改设备名或自动同步偏好时只更新本机加密配置，不依赖网络。空密码表示继续使用已保存密码。`DELETE` 只清除本机加密配置、基线或待处理加入计划，不删除远端密文。

### 8B.6 立即同步

```
POST /sync/run
```

成功响应的 `action` 为 `none`、`uploaded`、`downloaded` 或 `merged`。存在冲突时返回：

```json
{
  "status": { "phase": "conflict", "pending_conflicts": 1 },
  "conflict_token": "opaque-token",
  "conflicts": [
    {
      "conflict_id": "entry:uuid",
      "kind": "entry",
      "label": "条目标题",
      "local": { "state": "active", "updated_at": "...", "field_count": 3 },
      "remote": { "state": "active", "updated_at": "...", "field_count": 4 },
      "changed_sections": ["自定义字段"],
      "allow_both": true
    }
  ]
}
```

冲突摘要不得包含 `fields`、字段名列表或任何字段值。

### 8B.7 读取和处理冲突

```
GET /sync/conflicts
POST /sync/conflicts/resolve
```

```json
{
  "conflict_token": "opaque-token",
  "resolutions": {
    "entry:uuid": "both",
    "tags_meta:工作": "remote"
  }
}
```

处理方式仅允许 `local`、`remote` 和条目可用的 `both`。计划绑定解锁会话、Vault revision 和远端 ETag，任一变化后返回 `SYNC_CONFLICT_EXPIRED` 或 `SYNC_REMOTE_CHANGED`。

### 8B.8 历史版本

```
GET /sync/history
POST /sync/history/{snapshot_id}/restore
```

历史列表最多 10 项，只返回快照 ID、时间和设备信息。恢复会把所选加密快照发布为新的最新版本，并返回新的 Vault revision。

### 8B.9 显示恢复材料

```
POST /sync/recovery-code
```

```json
{ "password": "current-master-password" }
```

主密码验证成功后返回 `recovery_code`、`pairing_uri` 和仅用于当前界面显示的 SVG `qr_data_uri`。这些字段等同于同步密钥。

### 8B.10 轮换同步密钥

```
POST /sync/rotate-key
```

请求体同 8B.9。成功后返回新的恢复材料和 `previous_key_invalidated=true`；旧设备、旧恢复码和旧加密历史立即失效。

### 8B.11 删除远端同步数据

```
POST /sync/reset
```

```json
{
  "password": "current-master-password",
  "confirmation": "DELETE"
}
```

删除当前 Vault 的远端 head 和最近 10 个加密快照，并清除本机同步配置。本机 Vault 不会删除。

## 9. 设置模块

阶段：V1。

前端内部状态可以使用 camelCase 字段（如 `pageSize`、`autoLockMinutes`、`totalPages`），但后端 API 请求和响应统一使用 snake_case（如 `page_size`、`auto_lock_minutes`、`total_pages`）。前端必须在 API 边界做字段映射，不能直接假设后端返回 camelCase。

`auto_backup_retention` 控制自动备份保留数量，默认 `30`，有效范围 `5-200`。该设置只影响自动备份轮转，不会删除手动备份。

### 9.1 获取设置

```
GET /settings
```

**响应：**

```json
{
  "success": true,
  "data": {
    "theme": "dark",
    "page_size": 20,
    "auto_lock_minutes": 5,
    "auto_backup_retention": 30,
    "close_to_tray": false,
    "confirm_close": true,
    "desktop_zoom_percent": 100,
    "language": "zh-CN"
  }
}
```

### 9.2 更新设置

```
PUT /settings
```

**请求体：**

```json
{
  "theme": "light",
  "page_size": 30,
  "auto_backup_retention": 60,
  "close_to_tray": true,
  "confirm_close": false,
  "desktop_zoom_percent": 110
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "theme": "light",
    "page_size": 30,
    "auto_lock_minutes": 5,
    "auto_backup_retention": 60,
    "close_to_tray": true,
    "confirm_close": false,
    "desktop_zoom_percent": 110,
    "language": "zh-CN"
  },
  "message": "设置已更新"
}
```

**错误情况：**

- 422: 设置值无效（如 page_size 不是正整数）

`close_to_tray` 只影响支持托盘的 Windows 桌面壳，默认 `false`；macOS 会忽略并强制关闭该能力。`confirm_close` 默认 `true`：Windows 显示隐藏到托盘/退出/取消，macOS 首版只显示退出/取消。服务端模式会保存这两个字段，但不会启动系统托盘或显示桌面关闭确认。

`desktop_zoom_percent` 默认 `100`，有效范围 `25-500`。桌面壳可在 vault 未解锁时直接更新该本机字段；后端设置模型必须保留它，避免保存主题或分页设置时丢失缩放比例。普通浏览器模式不使用该字段覆盖浏览器自身缩放。

## 10. 认证中间件

### V1 历史模型

所有敏感 API 都必须检查服务端 vault 是否已解锁。V1 不强制要求请求头携带 token。

当前需要解锁状态的模块包括：条目、标签、回收站、设置、AI、导入导出。

### V2 当前模型

所有需要解锁状态的 API 都需要在请求头中携带 token：

```
Authorization: Bearer <session-token>
```

### Token 生命周期

- Token 在解锁时生成
- 锁定时销毁
- 自动锁定时销毁
- 服务重启时销毁

以上 Token 生命周期已在 V2.0 实现。V1 历史版本返回的 `authenticated` 只是前端状态占位值，不应被视为随机 session 凭证。

### 无需认证的端点

- `POST /auth/init`
- `POST /auth/unlock`
- `GET /auth/status`
- `GET /health`

## 11. 请求限制

### 速率限制

- 解锁尝试：5 次 / 5 分钟
- 其他 API：100 次 / 分钟

### 请求体大小限制

- 普通 API：1MB
- 导入接口：10MB（包括 `/import/*` 与 `/api/import/*` 别名）

后端会根据 `Content-Length` 拒绝超限请求；导入接口还会在读取文件后再次校验文件大小。

## 12. CORS 配置

默认允许所有来源访问。可通过 `.env` 的 `CORS_ORIGINS` 配置：

```env
# 允许所有
CORS_ORIGINS=*

# 允许特定来源
CORS_ORIGINS=https://example.com,https://app.example.com
```

## 13. 健康检查

阶段：V1。`uptime` 为可选增强字段，未实现时前端不得依赖它。

```
GET /health
```

**响应：**

```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "version": "5.2.0",
    "uptime": 3600
  }
}
```
