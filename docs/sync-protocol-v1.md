# SecretBase Sync Protocol V1

本文档定义 SecretBase V5.2 的 WebDAV 端到端加密同步协议。Python Web/桌面实现和后续 Android 实现必须通过 `tests/fixtures/sync-v1/` 黄金向量，不能根据某一端当前代码自行推断或更改格式。

## 1. 安全边界

- 每个同步 Vault 使用独立随机 256 位同步密钥，不复用主密码、Vault 派生密钥或 WebDAV 密码。
- WebDAV 上的索引和完整快照均先压缩，再使用 AES-256-GCM 加密。条目标题、字段名、字段值、备注、标签和密码组都不以明文上传。
- WebDAV 服务仍可观察目录名、对象数量、密文大小、请求时间和账户网络信息；端到端加密不隐藏这些流量元数据。
- 本机 `sync-settings.enc` 保存 WebDAV 地址、用户名、应用密码、同步密钥和设备身份；`sync-base.enc` 保存最近一次合并基线。二者使用当前 Vault 解锁密钥派生的独立用途密钥加密，只能在 Vault 解锁后读取。
- 二维码、恢复码和 `secretbase://` 配对链接等同于同步密钥。界面必须在再次验证主密码后显示，不能写入浏览器持久化存储、日志或诊断报告。
- 生产接口只允许 HTTPS WebDAV；不提供忽略 TLS 证书错误的选项，不跟随 HTTP 重定向。自动化测试通过注入本机传输适配器验证协议，不放宽生产 URL 校验。

## 2. 远端布局

```text
secretbase-sync-v1/<vault_id>/
  head.sbh
  snapshots/<snapshot_id>.sbs
```

`vault_id` 和 `snapshot_id` 是规范化小写 UUID。`head.sbh` 与 `.sbs` 均为 Sync Bundle V1 密文。快照对象不可变；当前版本只通过条件更新 `head.sbh` 推进。

## 3. Sync Bundle V1

Bundle 先对紧凑 UTF-8 JSON 使用 Gzip 压缩，再执行 AES-256-GCM。二进制布局如下：

| 偏移 | 长度 | 内容 |
| --- | ---: | --- |
| 0 | 4 | ASCII magic `SBS1` |
| 4 | 1 | bundle 版本 `0x01` |
| 5 | 1 | 对象类型：`0x01` head，`0x02` snapshot |
| 6 | 12 | 每次写入随机生成的 AES-GCM nonce |
| 18 | 可变 | `ciphertext || 16-byte authentication tag` |

同步密钥必须正好为 32 字节。生产写入不得复用 nonce。单个密文和解压后的 JSON 当前均限制为 64 MiB；WebDAV GET 必须流式累计并在越界时立即终止，不能先无上限读入内存再检查。

AAD 固定为以下字节串：

```text
UTF8("SecretBase Sync V1") || 0x00 || kind ||
UTF8(canonical_vault_uuid) || 0x00 || UTF8(object_id)
```

head 的 `object_id` 固定为 `head`；快照使用其 `snapshot_id`。因此密文不能在 Vault、对象类型或对象 ID 之间替换使用。

## 4. 加密 Payload

head 解密后是：

```json
{
  "schema_version": 1,
  "vault_id": "uuid",
  "generation": 7,
  "current_snapshot_id": "uuid",
  "history": [
    {
      "snapshot_id": "uuid",
      "created_at": "UTC ISO-8601",
      "device_id": "uuid",
      "device_name": "设备名称"
    }
  ]
}
```

`history[0]` 必须等于 `current_snapshot_id`，最多保留 10 项，ID 不得重复。

snapshot 解密后是：

```json
{
  "schema_version": 1,
  "vault_id": "uuid",
  "snapshot_id": "uuid",
  "parents": ["previous_snapshot_uuid"],
  "created_at": "UTC ISO-8601",
  "device_id": "uuid",
  "device_name": "设备名称",
  "document": { "Vault V1 完整文档": true }
}
```

`document` 同步条目、回收站、标签元数据、密码组元数据、密码组排序和 Vault V1 兼容扩展字段。AI 配置与对话、自动填充绑定、生物识别凭据、更新偏好和界面偏好不属于 Vault 文档，不参与同步。

## 5. WebDAV 提交语义

兼容服务必须支持 Basic Auth 或应用密码、`MKCOL`、`GET`、`PUT`、`DELETE`、稳定强 ETag、`If-None-Match: *` 和 `If-Match`。能力测试必须验证：

1. 创建、读取和内容一致性。
2. 重复 `If-None-Match: *` 写入返回 `412`。
3. 当前强 ETag 可以条件更新。
4. 使用过期 ETag 更新或删除返回 `412`。
5. 探测对象和临时目录在测试后删除。

发布顺序固定为：

1. 使用 `If-None-Match: *` 上传新的不可变快照。
2. 使用 head 当前强 ETag 执行 `If-Match`，首次创建使用 `If-None-Match: *`。
3. head 提交失败时删除刚上传的孤立快照并重新读取远端。
4. head 提交成功后清理超出最近 10 项的旧快照；清理失败不能回滚已经成功的 head。

任何 `412` 都视为并发版本变化，不允许无条件覆盖远端 head。

## 6. 三方合并

每台设备保存最近成功同步的完整基线。同步时比较 `base`、`local`、`remote`：

- 仅本机变化：上传本机文档。
- 仅远端变化：条件替换本机文档。
- 两端修改不同条目或不同标签/密码组：自动合并并发布新快照。
- 同一条目、同一标签、同一密码组或同一根扩展字段在两端发生不同修改：停止提交并要求用户逐项选择。

条目冲突可选择本机、远端或保留两份。保留两份时远端版本保留原 UUID，本机版本生成新 UUID，并在标题后增加“（本机冲突副本）”。删除与修改冲突不得静默删除。冲突 API 和界面只能返回状态、标题、更新时间、字段数量和变化区块，不得返回字段值。

冲突计划绑定当前解锁会话、Vault revision 和远端 head ETag。锁定、重新解锁、本地再次写入或远端 head 变化后，旧计划必须失效。

## 7. 自动触发与失败恢复

自动同步在以下时机安排：

- Vault 解锁后。
- 成功写入 Vault 后 5 秒防抖。
- 应用在后台超过 60 秒后回到前台。
- 用户点击“立即同步”。

同一进程只允许一个同步操作。同步接口自身产生的 Vault revision 响应头不得递归触发下一次自动同步。远端提交失败时，若流程刚用乐观锁替换了本机文档，应仅在 revision 仍匹配时回滚，不得覆盖用户随后产生的新修改。

客户端必须拒绝远端 `generation` 低于本机基线，或同一代数指向不同快照的回退/分叉。密钥轮换会有意重置历史链，本机加密配置保存对应的历史起点；若配置已经落盘但基线保存失败，下一次同步可据此恢复，而不会把正常轮换误判为攻击。

WebDAV `401/403` 对同步接口映射为受控上游错误，不能被前端误认为 SecretBase 会话失效而锁定应用。

## 8. 恢复码和密钥轮换

恢复码原始数据为：

```text
version(1 byte) || vault_uuid(16 bytes) || sync_key(32 bytes) || checksum(4 bytes)
```

`checksum` 是 `SHA256(UTF8("SBSYNC1") || preceding_payload)` 的前 4 字节。整体使用无 padding 的 Base32 编码，每 5 个字符分组，并加前缀 `SBSYNC1-`。

配对 URI 为 `secretbase://sync/join`，包含协议版本、Vault ID、恢复码、WebDAV 地址和用户名，不包含 WebDAV 密码。旧版 URI 可能使用 `key` 参数；新客户端应优先使用恢复码参数。

轮换同步密钥时，用新密钥发布只包含当前文档的新 head 和快照。旧历史必须等本机新配置成功保存后再清理；旧设备随后必须使用新恢复码重新加入。若本机新配置保存失败，实现应使用新 head 的 ETag 把 head 回退为旧密钥，同时保留原历史链并恢复本机旧配置与基线，避免远端与本机密钥永久失配。

## 9. 历史和彻底删除

恢复历史不会改写旧快照，而是把所选文档发布为新的最新快照。彻底删除的数据会继续存在于尚未淘汰的加密历史版本中；当包含该数据的最后一个历史快照超出 10 个版本并被删除后，协议层不再保留它。

删除远端同步空间需要再次验证主密码并输入 `DELETE`。实现必须使用当前 head 强 ETag 条件删除索引，再删除快照集合和 Vault 集合，避免并发设备推进 head 后被无条件删除；随后清除本机同步配置。本机 Vault 文档不受影响。

## 10. 黄金向量与版本演进

`tests/fixtures/sync-v1/manifest.json` 使用公开测试密钥、固定 nonce 和公开字段值，仅用于 Python/Rust 字节兼容测试。固定 nonce 禁止用于生产。

实现至少必须验证：正确解密、bundle SHA-256、对象类型、AAD 上下文、错误密钥和密文篡改。改变 magic、头部、压缩算法、AAD、密钥长度或 payload 主结构时必须创建 Sync Bundle V2；不能在 V1 下静默改变字节语义。
