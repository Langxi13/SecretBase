"""Local instruction policies that must not depend on provider behavior."""

from __future__ import annotations

import re


FIELD_VALUE_REQUEST_MESSAGE = (
    "AI 无法读取或列出已有字段值。请在本地条目详情中自行查看或复制；本轮不会生成操作计划。"
)
FIELD_VALUE_ACTIONS_BLOCKED_WARNING = (
    "检测到读取已有字段值的请求；系统已忽略模型返回的全部操作。"
)

_TAXONOMY_TERMS = (
    "密码组",
    "密码分组",
    "口令组",
    "密钥组",
    "password group",
    "password groups",
    "credential group",
    "credential groups",
)
_EXPLICIT_VALUE_TERMS = (
    "字段值",
    "field value",
    "真实密码",
    "密码值",
    "密码内容",
    "口令值",
    "令牌值",
    "token value",
    "密钥值",
    "secret value",
    "隐藏字段值",
)
_METADATA_ONLY_TERMS = (
    "字段名",
    "field name",
    "field names",
)
_TAG_METADATA_TERMS = (
    "密码标签",
    "口令标签",
    "令牌标签",
    "访问令牌标签",
    "密钥标签",
    "账号标签",
    "用户名标签",
    "password tag",
    "password tags",
    "token tag",
    "token tags",
    "secret tag",
    "secret tags",
)
_ACCESS_TERMS = (
    "列出",
    "显示",
    "展示",
    "读取",
    "获取",
    "导出",
    "返回",
    "提供",
    "发给",
    "告诉",
    "给我",
    "查看",
    "复制",
    "打印",
    "是什么",
    "show",
    "list",
    "reveal",
    "read",
    "export",
    "give me",
    "tell me",
)
_VALUE_TERMS = _EXPLICIT_VALUE_TERMS + (
    "所有密码",
    "全部密码",
    "真实口令",
    "访问令牌",
    "api token",
    "access token",
    "api key",
    "apikey",
    "私钥",
    "隐藏字段",
    "密码",
    "口令",
    "令牌",
    "token",
    "密钥",
    "secret",
    "账号",
    "用户名",
    "邮箱地址",
    "password",
    "passwords",
    "passcode",
    "passcodes",
    "tokens",
    "secrets",
    "private key",
    "private keys",
    "username",
    "usernames",
    "email address",
    "email addresses",
)


def _contains_term(text: str, term: str) -> bool:
    if term.isascii():
        return bool(re.search(rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])", text))
    return term in text


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(_contains_term(text, term) for term in terms)


def requests_existing_field_values(message: str) -> bool:
    compact = " ".join(str(message or "").strip().lower().split())
    if not compact:
        return False

    for term in _TAXONOMY_TERMS:
        compact = compact.replace(term, "")
    for term in _TAG_METADATA_TERMS:
        compact = compact.replace(term, "")

    if _contains_any(compact, _METADATA_ONLY_TERMS):
        if not _contains_any(compact, _EXPLICIT_VALUE_TERMS):
            return False

    return _contains_any(compact, _ACCESS_TERMS) and _contains_any(compact, _VALUE_TERMS)
