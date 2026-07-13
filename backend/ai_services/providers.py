"""AI provider presets and endpoint safety validation."""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import asdict, dataclass
from urllib.parse import urlsplit, urlunsplit

from fastapi import HTTPException

from config import is_desktop_mode


@dataclass(frozen=True)
class ProviderPreset:
    id: str
    name: str
    base_url: str
    docs_url: str
    structured_output: str = "prompt_json"
    supports_models: bool = True
    category: str = "model_provider"


PROVIDERS: tuple[ProviderPreset, ...] = (
    ProviderPreset(
        id="openai",
        name="OpenAI",
        base_url="https://api.openai.com/v1",
        docs_url="https://developers.openai.com/api/reference/resources/models/methods/list/",
        structured_output="response_format",
    ),
    ProviderPreset(
        id="deepseek",
        name="DeepSeek",
        base_url="https://api.deepseek.com",
        docs_url="https://api-docs.deepseek.com/",
        structured_output="response_format",
    ),
    ProviderPreset(
        id="kimi",
        name="Kimi",
        base_url="https://api.moonshot.cn/v1",
        docs_url="https://platform.moonshot.cn/docs/guide/start-using-kimi-api",
    ),
    ProviderPreset(
        id="zhipu",
        name="智谱 GLM",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        docs_url="https://docs.bigmodel.cn/cn/guide/develop/openai/introduction",
    ),
    ProviderPreset(
        id="siliconflow",
        name="SiliconFlow",
        base_url="https://api.siliconflow.cn/v1",
        docs_url="https://docs.siliconflow.cn/cn/userguide/quickstart",
    ),
    ProviderPreset(
        id="gemini",
        name="Gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        docs_url="https://ai.google.dev/gemini-api/docs/openai",
        structured_output="response_format",
    ),
    ProviderPreset(
        id="openrouter",
        name="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        docs_url="https://openrouter.ai/docs/api/reference/overview",
        category="aggregator",
    ),
)

PROVIDER_MAP = {provider.id: provider for provider in PROVIDERS}
OFFICIAL_HOSTS = {
    urlsplit(provider.base_url).hostname
    for provider in PROVIDERS
    if urlsplit(provider.base_url).hostname
}
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
BLOCKED_HOSTS = {
    "metadata.google.internal",
    "metadata.azure.internal",
    "instance-data.ec2.internal",
}


def provider_presets() -> list[dict]:
    items = []
    for provider in PROVIDERS:
        item = asdict(provider)
        item["editable"] = True
        item["verified_at"] = "2026-07-14"
        items.append(item)
    items.append({
        "id": "custom",
        "name": "自定义 OpenAI 兼容接口",
        "base_url": "",
        "docs_url": "",
        "structured_output": "auto",
        "supports_models": True,
        "category": "custom",
        "editable": True,
        "verified_at": "",
    })
    return items


def provider_by_id(provider_id: str | None) -> ProviderPreset | None:
    return PROVIDER_MAP.get(str(provider_id or "").strip().lower())


def infer_provider_id(base_url: str) -> str:
    normalized = normalize_base_url(base_url)
    host = urlsplit(normalized).hostname
    for provider in PROVIDERS:
        if host == urlsplit(provider.base_url).hostname:
            return provider.id
    return "custom"


def normalize_base_url(base_url: str) -> str:
    value = str(base_url or "").strip().rstrip("/")
    for suffix in ("/chat/completions", "/models"):
        if value.endswith(suffix):
            value = value[: -len(suffix)].rstrip("/")

    try:
        parsed = urlsplit(value)
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Base URL 格式无效") from error
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise HTTPException(status_code=422, detail="Base URL 必须是有效的 HTTP(S) 地址")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise HTTPException(status_code=422, detail="Base URL 不能包含账号、密码、查询参数或锚点")

    host = parsed.hostname.lower()
    if parsed.scheme == "http" and not (is_desktop_mode() and host in LOOPBACK_HOSTS):
        raise HTTPException(status_code=422, detail="外部 AI 服务必须使用 HTTPS")
    if host in BLOCKED_HOSTS:
        raise HTTPException(status_code=422, detail="该 AI 服务地址已被安全策略阻止")

    try:
        port = parsed.port
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Base URL 端口无效") from error

    netloc = host
    if ":" in host and not host.startswith("["):
        netloc = f"[{host}]"
    if port:
        netloc = f"{netloc}:{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path.rstrip("/"), "", ""))


def _ip_is_blocked(address: str, allow_loopback: bool) -> bool:
    ip = ipaddress.ip_address(address)
    if ip.is_loopback:
        return not allow_loopback
    return any((
        ip.is_private,
        ip.is_link_local,
        ip.is_multicast,
        ip.is_reserved,
        ip.is_unspecified,
    ))


def validate_endpoint_target(base_url: str) -> str:
    """Validate the resolved destination before attaching an API key."""
    normalized = normalize_base_url(base_url)
    parsed = urlsplit(normalized)
    host = parsed.hostname or ""
    allow_loopback = is_desktop_mode() and host in LOOPBACK_HOSTS
    if host in OFFICIAL_HOSTS:
        return normalized

    try:
        direct_ip = ipaddress.ip_address(host)
    except ValueError:
        direct_ip = None
    if direct_ip is not None:
        if _ip_is_blocked(str(direct_ip), allow_loopback):
            raise HTTPException(status_code=422, detail="AI 服务地址指向受保护的网络")
        return normalized

    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)}
    except OSError as error:
        raise HTTPException(status_code=502, detail="无法解析 AI 服务地址") from error
    if not addresses or any(_ip_is_blocked(address, allow_loopback) for address in addresses):
        raise HTTPException(status_code=422, detail="AI 服务地址解析到受保护的网络")
    return normalized


def provider_runtime(provider_id: str | None, base_url: str) -> dict:
    normalized = normalize_base_url(base_url)
    resolved_id = str(provider_id or "").strip().lower()
    provider = provider_by_id(resolved_id)
    if provider is None:
        resolved_id = infer_provider_id(normalized)
        provider = provider_by_id(resolved_id)
    return {
        "provider_id": resolved_id if provider else "custom",
        "provider_name": provider.name if provider else "自定义接口",
        "base_url": normalized,
        "structured_output": provider.structured_output if provider else "auto",
        "supports_models": provider.supports_models if provider else True,
        "customized": bool(provider and normalized != normalize_base_url(provider.base_url)),
    }
