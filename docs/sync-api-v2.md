# Sync API V2

V2 API 只在 Vault 已解锁且本机 session 有效时可用。所有响应中的 `status` 只包含脱敏状态，不包含 WebDAV 密码、同步密钥或字段值。

## 主要接口

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `POST` | `/sync/config/test` | 测试 HTTPS、Basic Auth、基础 WebDAV、PROPFIND 和上传后读取 |
| `POST` | `/sync/create` | 创建新空间并上传初始加密快照，`protocol_version=2` |
| `POST` | `/sync/join` | 使用 `SBSYNC2` 恢复码加入 |
| `PUT` | `/sync/config` | 更新连接、设备名或自动同步偏好；连接变化时验证远端身份 |
| `POST` | `/sync/run` | 发现 DAG、同步、自动合并或返回脱敏冲突 |
| `GET` | `/sync/conflicts` | 获取当前一次性冲突 token 和脱敏摘要 |
| `POST` | `/sync/conflicts/resolve` | 提交 `local`、`remote` 或条目 `both` 选择；多分支可能返回下一批冲突 |
| `GET` | `/sync/history` | 获取加密快照元数据列表 |
| `POST` | `/sync/history/{snapshot_id}/restore` | 从历史文档创建新的最新快照 |
| `POST` | `/sync/rotate-key` | 验证主密码后创建新空间和新同步密钥 |
| `POST` | `/sync/compact` | 输入主密码和 `COMPACT`，在基线一致时创建新根空间并清理旧空间 |
| `DELETE` | `/sync/config` | 只断开本机，不删除远端 |
| `POST` | `/sync/reset` | 输入主密码和 `DELETE` 后删除当前远端空间 |

## 压缩请求

```json
{
  "password": "当前 Vault 主密码",
  "confirmation": "COMPACT"
}
```

压缩前服务端会检查：本机文档等于加密基线、远端 frontier 等于基线、远端折叠文档等于基线、没有未处理冲突。成功后响应包含新的 `SBSYNC2` 恢复码；旧设备不会自动切换。

## 传输约束

- 生产地址必须为 HTTPS；不接受重定向和忽略证书错误。
- V2 不发送 `If-Match`、`If-None-Match`，不依赖 ETag。
- `PROPFIND` 使用 `Depth: 1`，解析 XML 本地名称以兼容 `DAV:` 前缀。
- 临时超时、429 和 5xx 只有限重试；认证、TLS、重定向和参数错误不重试。
- 每次 `PUT` 后重新 `GET`，逐字节校验密文；失败不会更新本机基线。
- 单对象密文和解压内容分别限制为 64 MiB；一次发现最多 1000 个快照，累计密文和累计解密内容分别限制为 256 MiB，frontier 最多 32 个。

## 清理边界

压缩和远端删除会先验证 DAG，逐对象删除已知快照，再重新枚举目录；发现未知对象、并发新增或删除失败时立即停止。本机 Vault 不参与远端删除。

基础 WebDAV 没有目录树级原子 CAS，最后一次空目录检查与删除之间仍存在服务端竞态。因此接口不会宣称远端删除具备事务原子性，只保证检测到变化时不误报成功，且压缩后的新空间和本机 Vault 不会因旧空间清理失败而被删除。
