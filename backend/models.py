from pydantic import BaseModel, validator, Field
from typing import Optional, List
from datetime import datetime
import uuid


class FieldItem(BaseModel):
    """自定义字段"""
    name: str = Field(..., min_length=1, max_length=100)
    value: str = Field(default="", max_length=10000)
    copyable: bool = False


class EntryBase(BaseModel):
    """条目基础模型"""
    title: str = Field(..., min_length=1, max_length=200)
    url: Optional[str] = Field(default="", max_length=2000)
    starred: bool = False
    tags: List[str] = Field(default_factory=list)
    fields: List[FieldItem] = Field(default_factory=list)
    remarks: Optional[str] = Field(default="", max_length=2000)

    @validator('url')
    def validate_url(cls, v):
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('URL 必须以 http:// 或 https:// 开头')
        return v

    @validator('tags')
    def validate_tags(cls, v):
        for tag in v:
            if not tag.strip():
                raise ValueError('标签不能为空')
        return list(set(tag.strip() for tag in v if tag.strip()))

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
        for tag in v:
            if not tag.strip():
                raise ValueError('标签不能为空')
        return list(set(tag.strip() for tag in v if tag.strip()))

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
    new_name: str = Field(..., min_length=1, max_length=50)


class TagMergeRequest(BaseModel):
    """标签合并请求"""
    source_tags: List[str] = Field(..., min_items=1)
    target_tag: str = Field(..., min_length=1, max_length=50)


class AiParseRequest(BaseModel):
    """AI 解析请求"""
    text: str = Field(..., min_length=1)


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
