from pydantic import BaseModel, validator, Field
from typing import Optional, List
from datetime import datetime
import uuid


def _normalize_entity_names(values: List[str], label: str) -> List[str]:
    cleaned = []
    for item in values:
        name = str(item or "").strip()
        if not name:
            raise ValueError(f"{label}不能为空")
        if len(name) > 50:
            raise ValueError(f"{label}名称不能超过 50 个字符")
        if name not in cleaned:
            cleaned.append(name)
    return cleaned


class FieldItem(BaseModel):
    """自定义字段"""
    name: str = Field(..., min_length=1, max_length=100)
    value: str = Field(default="", max_length=10000)
    copyable: bool = False
    hidden: Optional[bool] = None


class EntryBase(BaseModel):
    """条目基础模型"""
    title: str = Field(..., min_length=1, max_length=200)
    url: Optional[str] = Field(default="", max_length=2000)
    starred: bool = False
    tags: List[str] = Field(default_factory=list)
    groups: List[str] = Field(default_factory=list)
    fields: List[FieldItem] = Field(default_factory=list)
    remarks: Optional[str] = Field(default="", max_length=2000)

    @validator('url')
    def validate_url(cls, v):
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('URL 必须以 http:// 或 https:// 开头')
        return v

    @validator('tags')
    def validate_tags(cls, v):
        return _normalize_entity_names(v, "标签")

    @validator('groups')
    def validate_groups(cls, v):
        return _normalize_entity_names(v, "密码组")

    @validator('fields')
    def validate_fields(cls, v):
        names = set()
        for field in v:
            if not field.name.strip():
                raise ValueError('字段名不能为空')
            if field.name in names:
                raise ValueError(f'字段名重复: {field.name}')
            names.add(field.name)
        return v


class EntryCreate(EntryBase):
    """创建条目请求"""
    pass


class EntryUpdate(BaseModel):
    """更新条目请求"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    url: Optional[str] = Field(None, max_length=2000)
    starred: Optional[bool] = None
    tags: Optional[List[str]] = None
    groups: Optional[List[str]] = None
    fields: Optional[List[FieldItem]] = None
    remarks: Optional[str] = Field(None, max_length=2000)

    @validator('url')
    def validate_url(cls, v):
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('URL 必须以 http:// 或 https:// 开头')
        return v

    @validator('tags')
    def validate_tags(cls, v):
        if v is None:
            return v
        return _normalize_entity_names(v, "标签")

    @validator('groups')
    def validate_groups(cls, v):
        if v is None:
            return v
        return _normalize_entity_names(v, "密码组")

    @validator('fields')
    def validate_fields(cls, v):
        if v is None:
            return v
        names = set()
        for field in v:
            if not field.name.strip():
                raise ValueError('字段名不能为空')
            if field.name in names:
                raise ValueError(f'字段名重复: {field.name}')
            names.add(field.name)
        return v


class Entry(EntryBase):
    """完整条目模型"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    deleted: bool = False
    deleted_at: Optional[str] = None


class EntryResponse(BaseModel):
    """条目响应（隐藏敏感字段）"""
    id: str
    title: str
    url: str = ""
    starred: bool = False
    tags: List[str] = []
    groups: List[str] = []
    fields: List[dict] = []
    remarks: str = ""
    created_at: str
    updated_at: str


class BatchRequest(BaseModel):
    """批量操作请求"""
    ids: List[str] = Field(..., min_items=1)


class BatchTagRequest(BaseModel):
    """批量标签操作请求"""
    ids: List[str] = Field(..., min_items=1)
    add_tags: List[str] = Field(default_factory=list)
    remove_tags: List[str] = Field(default_factory=list)

    @validator('add_tags', 'remove_tags')
    def validate_tags(cls, v):
        for tag in v:
            if not tag.strip():
                raise ValueError('标签不能为空')
            if len(tag.strip()) > 50:
                raise ValueError('标签不能超过 50 个字符')
        return list(set(tag.strip() for tag in v if tag.strip()))


class TagBatchDeleteRequest(BaseModel):
    """批量删除标签请求"""
    names: List[str] = Field(..., min_items=1)

    @validator('names')
    def validate_names(cls, v):
        cleaned = []
        for name in v:
            value = str(name or "").strip()
            if not value:
                raise ValueError('标签名称不能为空')
            if len(value) > 50:
                raise ValueError('标签不能超过 50 个字符')
            if value not in cleaned:
                cleaned.append(value)
        return cleaned


class BatchStarRequest(BaseModel):
    """批量星标请求"""
    ids: List[str] = Field(..., min_items=1)
    starred: bool


class AuthRequest(BaseModel):
    """认证请求"""
    password: str = Field(..., min_length=1)


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


class TagRenameRequest(BaseModel):
    """标签重命名请求"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    new_name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    description: str = Field(default="", max_length=300)
    color: Optional[str] = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class TagRequest(BaseModel):
    """标签创建/更新请求"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    new_name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    description: str = Field(default="", max_length=300)
    color: Optional[str] = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class TagMergeRequest(BaseModel):
    """标签合并请求"""
    source_tags: List[str] = Field(..., min_items=1)
    target_tag: str = Field(..., min_length=1, max_length=50)
    description: str = Field(default="", max_length=300)
    color: Optional[str] = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class GroupRequest(BaseModel):
    """密码组创建/更新请求"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    description: str = Field(default="", max_length=300)


class GroupOrderRequest(BaseModel):
    """密码组自定义排序请求"""
    names: List[str] = Field(default_factory=list)


class AiParseRequest(BaseModel):
    """AI 解析请求"""
    text: str = Field(..., min_length=1)


class AiOrganizePreviewRequest(BaseModel):
    """AI 整理预览请求"""
    filters: dict = Field(default_factory=dict)
    organize_tags: bool = True
    organize_groups: bool = False
    user_prompt: str = Field(default="", max_length=1000)


class AiOrganizeSuggestion(BaseModel):
    """AI 整理建议"""
    entry_id: str = Field(..., min_length=1)
    selected: bool = True
    add_tags: List[str] = Field(default_factory=list)
    remove_tags: List[str] = Field(default_factory=list)
    add_groups: List[str] = Field(default_factory=list)
    remove_groups: List[str] = Field(default_factory=list)
    group_descriptions: dict = Field(default_factory=dict)
    reason: str = Field(default="", max_length=500)

    @validator('add_tags', 'remove_tags', 'add_groups', 'remove_groups')
    def validate_names(cls, v):
        cleaned = []
        seen = set()
        for item in v:
            name = str(item or "").strip()
            if not name or name in seen:
                continue
            if len(name) > 50:
                raise ValueError('标签或密码组名称不能超过 50 个字符')
            seen.add(name)
            cleaned.append(name)
        return cleaned


class AiOrganizeApplyRequest(BaseModel):
    """应用 AI 整理建议请求"""
    suggestions: List[AiOrganizeSuggestion] = Field(..., min_items=1)


class AiTagGovernancePreviewRequest(BaseModel):
    """AI 标签系统管理预览请求"""
    filters: dict = Field(default_factory=dict)
    user_prompt: str = Field(default="", max_length=1000)


class AiTagGovernanceSuggestion(BaseModel):
    """AI 标签系统管理建议"""
    action: str = Field(..., pattern="^(create_tag|update_tag|delete_tag|merge_tags|replace_tag|assign_tag)$")
    selected: bool = True
    tag: Optional[str] = Field(default=None, max_length=50)
    new_tag: Optional[str] = Field(default=None, max_length=50)
    source_tags: List[str] = Field(default_factory=list)
    target_tag: Optional[str] = Field(default=None, max_length=50)
    entry_ids: List[str] = Field(default_factory=list)
    description: str = Field(default="", max_length=300)
    color: Optional[str] = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    reason: str = Field(default="", max_length=500)

    @validator('tag', 'new_tag', 'target_tag')
    def validate_optional_name(cls, v):
        if v is None:
            return v
        cleaned = str(v).strip()
        return cleaned or None

    @validator('source_tags', 'entry_ids')
    def validate_name_lists(cls, v):
        cleaned = []
        seen = set()
        for item in v:
            name = str(item or "").strip()
            if name and name not in seen:
                seen.add(name)
                cleaned.append(name)
        return cleaned


class AiTagGovernanceApplyRequest(BaseModel):
    """应用 AI 标签系统管理建议请求"""
    suggestions: List[AiTagGovernanceSuggestion] = Field(..., min_items=1)


class AiActionPreviewRequest(BaseModel):
    """AI 自然语言操作计划预览请求"""
    instruction: str = Field(..., min_length=1, max_length=2000)
    filters: dict = Field(default_factory=dict)


class AiActionPlanItem(BaseModel):
    """AI 操作计划项。字段值不允许由 AI 提供。"""
    type: str = Field(..., pattern="^(create_group|update_group|create_entry|create_entry_from_field|update_entry)$")
    selected: bool = True
    group: Optional[str] = Field(default=None, max_length=50)
    group_new: Optional[str] = Field(default=None, max_length=50)
    description: str = Field(default="", max_length=300)
    title: Optional[str] = Field(default=None, max_length=200)
    url: Optional[str] = Field(default=None, max_length=2000)
    tags: List[str] = Field(default_factory=list)
    groups: List[str] = Field(default_factory=list)
    remarks: str = Field(default="", max_length=2000)
    fields: List[FieldItem] = Field(default_factory=list)
    entry_id: Optional[str] = Field(default=None, max_length=100)
    entry_title: Optional[str] = Field(default=None, max_length=200)
    source_entry_id: Optional[str] = Field(default=None, max_length=100)
    source_entry_title: Optional[str] = Field(default=None, max_length=200)
    field_index: Optional[int] = Field(default=None, ge=0)
    field_name: Optional[str] = Field(default=None, max_length=100)
    field_name_new: Optional[str] = Field(default=None, max_length=100)
    add_tags: List[str] = Field(default_factory=list)
    remove_tags: List[str] = Field(default_factory=list)
    add_groups: List[str] = Field(default_factory=list)
    remove_groups: List[str] = Field(default_factory=list)
    reason: str = Field(default="", max_length=500)

    @validator('group', 'group_new', 'title', 'entry_id', 'source_entry_id', 'field_name', 'field_name_new')
    def validate_optional_text(cls, v):
        if v is None:
            return v
        cleaned = str(v).strip()
        return cleaned or None

    @validator('tags', 'groups', 'add_tags', 'remove_tags', 'add_groups', 'remove_groups')
    def validate_name_lists(cls, v):
        cleaned = []
        seen = set()
        for item in v:
            name = str(item or "").strip()
            if name and name not in seen:
                if len(name) > 50:
                    raise ValueError('标签或密码组名称不能超过 50 个字符')
                seen.add(name)
                cleaned.append(name)
        return cleaned

    @validator('url')
    def validate_optional_url(cls, v):
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('URL 必须以 http:// 或 https:// 开头')
        return v


class AiActionApplyRequest(BaseModel):
    """应用 AI 自然语言操作计划请求"""
    actions: List[AiActionPlanItem] = Field(..., min_items=1)


class ImportConflictRequest(BaseModel):
    """导入冲突处理请求"""
    conflict_strategy: str = Field(default="skip", pattern="^(skip|overwrite|ask)$")


class Settings(BaseModel):
    """用户设置"""
    theme: str = Field(default="system", pattern="^(dark|light|system)$")
    page_size: int = Field(default=20, ge=1, le=1000)
    auto_lock_minutes: int = Field(default=5, ge=0, le=1440)
    auto_backup_retention: int = Field(default=30, ge=5, le=200)
    language: str = Field(default="zh-CN")


class PaginationParams(BaseModel):
    """分页参数"""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=1000)


class VaultData(BaseModel):
    """Vault 数据结构"""
    version: str = "1.0"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    app_name: str = "SecretBase"
    entries: List[Entry] = Field(default_factory=list)
    deleted_entries: List[Entry] = Field(default_factory=list)
    tags_meta: dict = Field(default_factory=dict)
    groups_meta: dict = Field(default_factory=dict)
