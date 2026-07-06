"""
配置管理模块
从环境变量或 .env 文件读取配置
"""
import sys
from pathlib import Path

# 确保 backend 目录在 Python 路径中
_backend_dir = Path(__file__).parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # AI 模型配置
    AI_API_KEY: str = ""
    AI_BASE_URL: str = "https://api.openai.com/v1"
    AI_MODEL: str = "gpt-4o"
    AI_MAX_TOKENS: int = 2000
    AI_TEMPERATURE: float = 0.7

    # 今日头条配置
    TOUTIAO_LOGIN_URL: str = "https://mp.toutiao.com/auth/page/login"
    TOUTIAO_PUBLISH_URL: str = "https://mp.toutiao.com/profile_v4/graphic/publish"
    TOUTIAO_HOME_URL: str = "https://mp.toutiao.com/"

    # 浏览器配置
    BROWSER_HEADLESS: bool = False
    BROWSER_USER_DATA_DIR: str = ""

    # 路径配置
    BASE_DIR: Path = Path(__file__).parent
    DATA_DIR: Path = BASE_DIR / "data"
    BROWSER_STATE_DIR: Path = DATA_DIR / "browser_state"
    STATE_FILE: Path = BROWSER_STATE_DIR / "state.json"
    AUTH_INFO_FILE: Path = DATA_DIR / "auth_info.json"

    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ===== 流水线配置（pipeline.py 共用）=====
    # 输出目录（项目根目录下的相对路径）
    PIPELINE_OUTPUT_DIR: str = "outputs"
    # 视频下载子项目路径
    VIDEO_DOWNLOAD_DIR: str = "video-batch-download-main"
    # 头条发布 API 地址
    PUBLISH_API_BASE_URL: str = "http://localhost:8000"
    # Whisper 配置
    WHISPER_MODEL: str = "small"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"
    # 转录后端
    TRANSCRIBE_BACKEND: str = "transformers"
    # HuggingFace 镜像
    HF_ENDPOINT: str = "https://hf-mirror.com"
    # 默认内容类型
    DEFAULT_CONTENT_TYPE: str = "toutie"
    # 默认内容风格（military / general）
    DEFAULT_CONTENT_STYLE: str = "general"
    # 默认发布模式
    DEFAULT_PUBLISH_MODE: str = "publish"
    # 是否启用发布阶段
    ENABLE_PUBLISH: bool = True
    # 违规检测开关（预留）
    ENABLE_COMPLIANCE_CHECK: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
