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

- 422: 密码为空或太短（最少 8 位）
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

**修改主密码，重新加密数据。**

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
        "fields": [
          {"name": "账号", "value": "demo-user", "copyable": true},
          {"name": "密码", "value": "••••••", "copyable": true, "masked": true}
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

**注意：** 列表接口必须对 `copyable=true` 的字段返回掩码值 `••••••`，并附带 `masked: true`。需要明文时通过 `GET /entries/{id}` 获取详情。非 copyable 字段可直接显示原值。

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
    "fields": [
      {"name": "账号", "value": "demo-user", "copyable": true},
      {"name": "密码", "value": "demo-password", "copyable": true}
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
  "fields": [
    {"name": "账号", "value": "user@example.com", "copyable": true},
    {"name": "密码", "value": "demo-password", "copyable": true}
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
        "color": "#ff6600",
        "count": 3
      },
      {
        "name": "服务器",
        "color": "#0066ff",
        "count": 5
      }
    ]
  }
}
```

### 6.2 重命名标签

```
PUT /tags/{name}
```

**请求体：**

```json
{
  "new_name": "新标签名"
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
  "message": "标签已重命名"
}
```

**错误情况：**

- 404: 标签不存在
- 409: 新标签名已存在

### 6.3 删除标签

**从所有条目中移除该标签。**

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

### 6.4 合并标签

**将多个标签合并为一个。**

```
POST /tags/merge
```

**请求体：**

```json
{
  "source_tags": ["标签A", "标签B"],
  "target_tag": "合并后的标签"
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

## 7. AI 智能录入模块

阶段：V1.1/V1.2。若未配置 AI API Key，前端必须允许用户继续手动录入，不能阻塞核心功能。AI 接入由用户在解锁后进入设置页配置 Base URL、API Key，并实时拉取模型列表选择模型。

### 7.0 查询 AI 状态

**查询 AI 是否已配置。该接口只返回配置状态、Base URL、模型名和 Key 掩码，绝不能返回完整 API Key。**

```
GET /ai/status
```

**响应：**

```json
{
  "success": true,
  "data": {
    "configured": false,
    "base_url": "",
    "model": "",
    "api_key_mask": ""
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
    "models": ["deepseek-v4-flash", "deepseek-v4-pro"]
  }
}
```

**错误情况：**

- 401: 未解锁
- 422: Base URL 或 API Key 缺失/无效
- 502: 服务商认证失败、网络错误、超时或模型列表响应格式无效

### 7.2 保存 AI 设置

**保存 AI Base URL、模型和 API Key。保存前后端必须先拉取模型列表，确认 `model` 来自服务商返回列表，再用所选模型执行固定无敏感连通测试。**

```
PUT /ai/settings
```

**请求体：**

```json
{
  "baseUrl": "https://api.deepseek.com",
  "apiKey": "sk-...",
  "model": "deepseek-v4-flash"
}
```

已保存 AI 配置后，如果只更换同一 Base URL 下的模型，`apiKey` 可以省略。API Key 只写入本机加密安全设置文件，不写入明文 `settings.json`，也不进入 vault 备份/恢复。

**响应：**

```json
{
  "success": true,
  "data": {
    "configured": true,
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-v4-flash",
    "api_key_mask": "sk-...abcd"
  },
  "message": "AI 设置已保存"
}
```

**错误情况：**

- 401: 未解锁
- 422: Base URL、API Key 或模型无效，或模型不在服务商返回列表中
- 502: 获取模型列表失败或固定连通测试失败

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
    "base_url": "",
    "model": "",
    "api_key_mask": ""
  },
  "message": "AI 设置已清除"
}
```

**错误情况：**

- 401: 未解锁

### 7.4 解析文本

**使用 AI 解析自然语言文本为条目结构。**

AI 解析要求用户已解锁并完成 AI 设置。前端调用前必须先查询 `GET /ai/status`，未配置时提示用户进入设置页配置 AI。AI 会尝试自主判断输入中是否包含多个独立条目。后端请求模型时使用严格 JSON object 输出约束，要求顶层返回 `entries` 数组。为兼容旧前端，响应仍保留 `parsed` 表示第一条解析结果；V1.2 新增 `parsed_entries` 和 `entry_count` 用于多条目录入。后端会归一化常见 AI 格式偏差，如 `items`、`accounts`、`records`、字段字典、标签字符串、`copyable` 字符串等。

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
        {"name": "账号", "value": "demo-user", "copyable": true},
        {"name": "密码", "value": "demo-password", "copyable": true},
        {"name": "IP", "value": "192.0.2.10", "copyable": true}
      ],
      "tags": ["示例云", "服务器"],
      "remarks": ""
    },
    "parsed_entries": [
      {
        "title": "示例服务器",
        "url": "",
        "fields": [
          {"name": "账号", "value": "demo-user", "copyable": true},
          {"name": "密码", "value": "demo-password", "copyable": true},
          {"name": "IP", "value": "192.0.2.10", "copyable": true}
        ],
        "tags": ["示例云", "服务器"],
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
        "import_title": "导入条目"
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
      {"id": "uuid", "existing_title": "现有条目", "import_title": "导入条目"}
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
  "auto_backup_retention": 60
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
    "language": "zh-CN"
  },
  "message": "设置已更新"
}
```

**错误情况：**

- 422: 设置值无效（如 page_size 不是正整数）

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
- 导入接口：10MB

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
    "version": "1.0.0",
    "uptime": 3600
  }
}
```
