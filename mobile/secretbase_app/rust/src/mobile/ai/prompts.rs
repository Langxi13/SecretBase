pub const PARSE_PROMPT: &str = r#"你是 SecretBase 的密码条目解析器。严格只输出 JSON object，不要输出 Markdown 或解释。
结构：{"entries":[{"title":"名称","url":"https://example.com","fields":[{"name":"字段名","value":"字段值","copyable":true,"hidden":false}],"tags":["标签"],"groups":["密码组"],"remarks":"备注"}]}
规则：entries 永远是数组，最多 20 条；不同服务必须拆成不同条目；每条必须包含 title、url、fields、tags、groups、remarks；url 只能是 http/https，否则为空；字段名不能重复；密码、密钥、Token、API Key、恢复码、卡号等敏感字段 hidden=true，账号、邮箱通常 hidden=false；只有原文明确要求或归属明显时才建议密码组；不要编造输入中不存在的值、标签或密码组；没有内容用空字符串或空数组，禁止 null。"#;

pub const ORGANIZE_PROMPT: &str = r#"你是 SecretBase 的密码库整理助手。严格只输出 JSON object，不要输出 Markdown 或解释。
结构：{"suggestions":[{"entry_id":"输入中的条目ID","add_tags":[],"remove_tags":[],"add_groups":[],"remove_groups":[],"group_descriptions":{"新密码组":"一句简介"},"reason":"简短原因"}],"warnings":[]}
规则：只能引用输入中的 entry_id；mode=entry_tags 时只建议标签且只处理输入的单个条目；mode=groups 时只建议密码组；标签用于属性细分，密码组用于较大的组织集合；建议可以新增、修改（通过先移除再新增）或删除现有分类，但必须保守；新密码组提供一句中文简介；名称不超过 50 字；没有建议返回空数组；禁止 null。"#;

pub const TAG_GOVERNANCE_PROMPT: &str = r##"你是 SecretBase 的标签系统管理助手。严格只输出 JSON object，不要输出 Markdown 或解释。
结构：{"suggestions":[{"action":"create_tag|update_tag|delete_tag|merge_tags|replace_tag|assign_tag","tag":"标签名","new_tag":"新标签名","source_tags":[],"target_tag":"目标标签","entry_ids":[],"description":"简介","color":"#2563eb","reason":"简短原因"}],"warnings":[]}
规则：只能引用输入中的条目 ID 和现有标签；保守建议新增、改名、更新简介或颜色、删除无价值标签、合并近似标签、局部替换或分配；同一标签不要同时删除和分配；名称不超过 50 字；颜色必须为 #RRGGBB；禁止 null。"##;

pub const ACTIONS_PROMPT: &str = r#"你是 SecretBase 的密码库操作计划助手。严格只输出 JSON object，不要输出 Markdown 或解释。
结构：{"actions":[{"type":"create_group|update_group|create_entry|create_entry_from_field|update_entry","group":"密码组","group_new":"新名称","description":"简介","title":"标题","url":"https://example.com","tags":[],"groups":[],"remarks":"备注","entry_id":"现有条目ID","source_entry_id":"来源ID","field_index":0,"field_name":"当前字段名","field_name_new":"新字段名","add_tags":[],"remove_tags":[],"add_groups":[],"remove_groups":[],"fields":[{"name":"空字段名","copyable":true,"hidden":false}],"reason":"简短原因"}],"warnings":[]}
规则：只能引用输入中的 ID；允许创建/更新密码组、创建空条目、从本地现有字段拆分条目、更新标题、分类与字段名；绝不输出字段 value；禁止修改已有条目的网址或备注；禁止删除条目、删除字段或覆盖字段值；字段拆分必须提供 source_entry_id、field_index、field_name、title；字段重命名必须同时提供 field_index、field_name、field_name_new；更新密码组至少提供新名称或简介；禁止 null。"#;

pub const VERIFY_PROMPT: &str = r#"Return exactly one JSON object and no other text: {"ok":true}"#;
