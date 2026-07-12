# SecretBase Vault V1 Format

本文档是 SecretBase Vault V1 的规范性说明。实现代码、桌面包和未来移动端必须通过仓库中的黄金向量验证，不能仅依赖当前 Python 行为推断格式。

## 1. 加密封装

Vault V1 是一个二进制文件，头部固定为 65 字节，后接可变长度密文。

| 偏移 | 长度 | 内容 |
| --- | ---: | --- |
| 0 | 4 | ASCII magic `SB01` |
| 4 | 1 | envelope 版本 `0x01` |
| 5 | 32 | PBKDF2 salt |
| 37 | 12 | AES-GCM nonce |
| 49 | 16 | AES-GCM authentication tag |
| 65 | 可变 | AES-GCM ciphertext |

密码按 UTF-8 编码。密钥派生固定使用 PBKDF2-HMAC-SHA256、600000 次迭代、32 字节输出。内容加密固定使用 AES-256-GCM，不使用 AAD。常规写入必须为每个文件生成新的随机 salt 和 nonce，任何实现都不得复用 nonce。

AES-GCM 库通常返回 `ciphertext || tag`；SecretBase 文件格式必须重新排列为 `header || tag || ciphertext`，不能直接把库返回值追加到头部。

## 2. JSON Payload

解密结果必须是 UTF-8 JSON 对象。根对象的 `version` 缺省为 `1.0`，当前只接受主版本 `1`。高于或低于主版本 `1` 的 payload 必须明确拒绝，不能静默迁移。

根对象包含：

- `version`：payload 版本字符串。
- `created_at`：vault 创建时间。
- `app_name`：默认 `SecretBase`。
- `entries`：当前条目数组，缺省为空数组。
- `deleted_entries`：回收站条目数组，缺省为空数组。
- `tags_meta`：标签元数据对象，缺省为空对象。
- `groups_meta`：密码组元数据对象，缺省为空对象。

条目保留 `id`、`title`、`url`、`starred`、`tags`、`groups`、`fields`、`remarks`、`created_at`、`updated_at`、`deleted` 和 `deleted_at`。自定义字段保留 `name`、`value`、`copyable` 和 `hidden`；`hidden: null` 表示旧数据兼容语义，由业务层决定是否按可复制字段隐藏。

V1 结构约束与当前生产模型一致：条目标题为 1-200 个字符，URL 最长 2000 个字符且非空时必须使用 HTTP(S)，备注最长 2000 个字符；标签和密码组名称去除首尾空白、去重后为 1-50 个字符；字段名为 1-100 个字符且同一条目内不能重复，字段值最长 10000 个字符。

同一 payload 主版本中的未知 JSON 字段必须在解密、加载和重新序列化时保留。该规则适用于根对象、条目和自定义字段。读取端可以忽略未知字段的业务含义，但不得因保存其他字段而删除它们。

## 3. 兼容与错误

- envelope 版本不是 `0x01`：`UNSUPPORTED_ENVELOPE_VERSION`。
- magic、长度或头部无效：`INVALID_FORMAT`。
- 密码错误或密文、tag 被篡改：统一返回 `AUTHENTICATION_FAILED`，不得向调用方区分原因。
- JSON、UTF-8 或 V1 数据结构无效：`INVALID_PAYLOAD`。
- payload 主版本不是 `1`：`UNSUPPORTED_PAYLOAD_VERSION`。

生产日志不得记录主密码、派生密钥、明文 payload 或解密后的字段值。解析头部可以返回版本、salt、nonce 和密文长度用于诊断，但不能将其误认为密码验证成功。

## 4. 黄金向量

`tests/fixtures/vault-v1/` 中的数据全部是公开测试数据：

- `empty.json` 验证最小完整文档。
- `unicode-rich.json` 验证 UTF-8、标签、密码组、隐藏字段、回收站和未知字段保留。
- 对应 `.vault` 文件使用固定 salt 和 nonce，仅用于可重复的兼容测试。
- `manifest.json` 和 `SHA256SUMS.txt` 固定算法参数与预期摘要。

固定 nonce 的生成器禁止用于生产写入。任何格式实现都必须同时完成以下验证：解密现有向量、按固定参数生成完全相同的字节、使用随机参数完成加密后可被另一语言解密，以及拒绝错误密码和损坏数据。

## 5. 版本演进

V1 文件不执行隐式迁移。未来新增 payload 次版本字段时必须遵守未知字段保留规则；需要改变密钥派生、AAD、头部或密文布局时必须创建新的 envelope 版本和独立黄金向量。任何迁移功能都必须先创建可恢复的加密备份。
