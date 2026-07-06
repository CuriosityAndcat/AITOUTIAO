"""
Pydantic 数据模型 — 请求/响应结构
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class ContentType(str, Enum):
    TOUTIE = "toutie"       # 微头条
    ARTICLE = "article"     # 文章


class ContentStyle(str, Enum):
    """内容风格枚举 — 对标今日头条头部军事/时政账号"""
    GENERAL = "general"                   # 通用风格（原有 TOUTIE_PROMPT）
    MILITARY = "military"                 # 🔥 你的专属：军事深度分析型，七层递进+证据驱动+博弈拆解
    STORY_NARRATIVE = "story_narrative"   # 📖 对标「听风的蚕」：军事评书，悬念铺陈+通俗比喻+方言韵味
    SHARP_COMMENTARY = "sharp_commentary" # ✒️ 对标「牛弹琴」：冷静克制，事实为主+观点为辅+娓娓道来
    DATA_LIST = "data_list"               # 📊 对标「静思有我」：硬核论证，数据驱动+逻辑链+论文质感
    FLASH_NEWS = "flash_news"             # ⚡ 快讯速报型：3段讲清、信息密度极高、零铺垫
    DISCUSSION = "discussion"             # 💬 互动讨论型：开放式提问、"你怎么看"为主轴、撩互动


class GenerateRequest(BaseModel):
    topic: str = Field(..., description="主题或关键词")
    content_type: ContentType = ContentType.ARTICLE
    max_chars: Optional[int] = Field(None, description="最大字数（微头条默认1000，文章默认5000）")
    tone: str = Field("专业且易懂", description="语调风格")
    content_style: ContentStyle = Field(ContentStyle.GENERAL, description="内容风格（military/general）")
    include_title: bool = True


class GenerateResponse(BaseModel):
    success: bool
    title: Optional[str] = None
    content: str
    content_type: ContentType
    char_count: int
    error: Optional[str] = None


class PublishRequest(BaseModel):
    title: str
    content: str
    cover_path: Optional[str] = None
    auto_publish: bool = True
    content_type: ContentType = ContentType.ARTICLE


class PublishResponse(BaseModel):
    success: bool
    message: str
    task_id: Optional[str] = None
    error: Optional[str] = None


class LoginStatusResponse(BaseModel):
    authenticated: bool
    auth_age_hours: Optional[float] = None
    warning: Optional[str] = None


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class TaskInfo(BaseModel):
    task_id: str
    task_type: str  # "generate" or "publish"
    status: TaskStatus
    message: str = ""
    result: Optional[dict] = None
    created_at: str
