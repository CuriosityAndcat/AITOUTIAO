#!/usr/bin/env python3
"""
AIToutiao Streamlit 一键内容生成器
====================================
基于 Streamlit 的 Web 界面，将视频下载→语音转录→AI写作→人工化改写→配图生成→图文组装
封装为一键式操作，双击 run.bat 即可在浏览器中使用。
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

# ── 修复 Windows GBK 编码 ──
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── 路径初始化 ──
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT / "toutiao-auto-publisher" / "backend"))
sys.path.insert(0, str(PROJECT_ROOT / "wewrite-main" / "toolkit"))

OUTPUTS_DIR = PROJECT_ROOT / os.getenv("PIPELINE_OUTPUT_DIR", "outputs")

# ── 强行预加载 backend/config 模块 ──
# 防止 ai_writer.py 中的 from config import settings 错误解析到 wewrite-main/toolkit/config.py
import importlib.util
_backend_config_path = PROJECT_ROOT / "toutiao-auto-publisher" / "backend" / "config.py"
_config_spec = importlib.util.spec_from_file_location("config", str(_backend_config_path))
_config_mod = importlib.util.module_from_spec(_config_spec)
sys.modules["config"] = _config_mod
_config_spec.loader.exec_module(_config_mod)
settings = _config_mod.settings

# ── 加载 .env ──
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

# ── 从 backend 导入（config 已在顶部预加载，避免路径冲突）──
try:
    from models import ContentType, ContentStyle
except Exception:
    ContentType = None
    ContentStyle = None

# ── 页面配置 ──
st.set_page_config(
    page_title="AIToutiao 一键生成器",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# 自定义 CSS（暗色军事风）
# ============================================================
def _inject_css():
    st.markdown(
        """
    <style>
        .stApp { background-color: #0D1117; }
        .main-header {
            background: linear-gradient(135deg, #FF6B35 0%, #E85D04 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 28px; font-weight: 700; text-align: center;
            padding: 10px 0; margin-bottom: 5px;
        }
        .stage-indicator {
            display: inline-block; width: 14px; height: 14px;
            border-radius: 50%; margin: 0 3px;
            border: 2px solid #30363D;
        }
        .stage-indicator.done { background: #3FB950; border-color: #3FB950; }
        .stage-indicator.running { background: #FF6B35; border-color: #FF6B35; animation: pulse 1.2s infinite; }
        .stage-indicator.pending { background: transparent; border-color: #30363D; }
        .stage-indicator.failed { background: #F85149; border-color: #F85149; }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        .log-container {
            background: #161B22; border: 1px solid #30363D;
            border-radius: 8px; padding: 12px; max-height: 320px;
            overflow-y: auto; font-family: 'Consolas', 'Courier New', monospace;
            font-size: 13px; color: #E6EDF3; line-height: 1.6;
        }
        .log-line.info { color: #E6EDF3; }
        .log-line.success { color: #3FB950; }
        .log-line.error { color: #F85149; }
        .log-line.warning { color: #D29922; }
        .log-line.stage { color: #58A6FF; }
        .result-card {
            background: #161B22; border: 1px solid #30363D;
            border-radius: 12px; padding: 24px; margin-top: 20px;
        }
        .stat-badge {
            display: inline-block; background: #21262D; border-radius: 6px;
            padding: 4px 10px; font-size: 12px; color: #8B949E; margin-right: 6px;
        }
        button[kind="primary"] {
            background: linear-gradient(135deg, #FF6B35 0%, #E85D04 100%) !important;
            border: none !important; font-weight: 600 !important;
        }
        input[type="text"] {
            background: #161B22 !important; border: 1px solid #30363D !important;
            color: #E6EDF3 !important; border-radius: 8px !important;
        }
        .stTextInput > div > div > input:focus {
            border-color: #FF6B35 !important; box-shadow: 0 0 0 2px rgba(255,107,53,0.3) !important;
        }
        div[data-testid="stSidebar"] {
            background-color: #0D1117; border-right: 1px solid #21262D;
        }
        div[data-testid="stSidebar"] * { color: #E6EDF3; }
        footer { visibility: hidden; }
    </style>
    """,
        unsafe_allow_html=True,
    )


_inject_css()

# ============================================================
# Session State 初始化
# ============================================================
_DEFAULTS = {
    "logs": [],
    "progress_pct": 0.0,
    "current_stage": "",
    "stage_status": {
        "下载": "pending",
        "转录": "pending",
        "写作": "pending",
        "改写": "pending",
        "配图": "pending",
        "组装": "pending",
    },
    "pipeline_state": None,
    "result_data": None,
    "run_id": "",
    "is_running": False,
    "elapsed_seconds": 0.0,
    "processed_url": "",   # 单向数据通道：URL 提取 → 流水线执行
    "pipeline_error": None,  # 后台线程异常信息
    "pipeline_done": False,  # 后台线程完成标记
    # Cookies 相关已不再需要 — 使用 Playwright 浏览器全自动下载
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ============================================================
# 辅助函数
# ============================================================
def add_log(msg: str, level: str = "info"):
    """添加日志条目，自动裁剪到 200 行。"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = {"time": timestamp, "msg": msg, "level": level}
    st.session_state.logs.append(entry)
    if len(st.session_state.logs) > 200:
        st.session_state.logs = st.session_state.logs[-200:]


def set_stage(name: str, status: str):
    """更新阶段状态。"""
    st.session_state.stage_status[name] = status
    st.session_state.current_stage = name


def _emoji_for_level(level: str) -> str:
    return {"info": "📝", "success": "✅", "error": "❌", "warning": "⚠️", "stage": "🔷"}.get(
        level, "📝"
    )


# ============================================================
# PipelineState（轻量版，Streamlit 用）
# ============================================================
class PipelineState:
    """流水线状态管理，支持断点续跑。"""

    def __init__(
        self,
        run_id: str = "",
        input_url: str = "",
        content_type: str = "toutie",
        content_style: str = "story_narrative",
        enable_humanize: bool = False,
        with_images: bool = False,
        completed_stages: Optional[List[str]] = None,
        outputs: Optional[Dict[str, Any]] = None,
    ):
        self.run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.input_url = input_url
        self.content_type = content_type
        self.content_style = content_style
        self.enable_humanize = enable_humanize
        self.with_images = with_images
        self.completed_stages: List[str] = completed_stages or []
        self.outputs: Dict[str, Any] = outputs or {}

    @property
    def run_dir(self) -> Path:
        return OUTPUTS_DIR / self.run_id[:8] / self.run_id

    @property
    def state_file(self) -> Path:
        return self.run_dir / "pipeline_state.json"

    def is_done(self, stage: str) -> bool:
        return stage in self.completed_stages

    def mark_done(self, stage: str):
        if stage not in self.completed_stages:
            self.completed_stages.append(stage)

    def save(self):
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(
            json.dumps(
                {
                    "run_id": self.run_id,
                    "input_url": self.input_url,
                    "content_type": self.content_type,
                    "content_style": self.content_style,
                    "enable_humanize": self.enable_humanize,
                    "with_images": self.with_images,
                    "completed_stages": self.completed_stages,
                    "outputs": self.outputs,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, run_id: str) -> Optional["PipelineState"]:
        date_str = run_id[:8]
        sf = OUTPUTS_DIR / date_str / run_id / "pipeline_state.json"
        if sf.exists():
            data = json.loads(sf.read_text(encoding="utf-8"))
            return cls(**data)
        return None

    @classmethod
    def find_existing(cls, url: str) -> Optional["PipelineState"]:
        if not OUTPUTS_DIR.exists():
            return None
        for date_dir in sorted(OUTPUTS_DIR.iterdir(), reverse=True):
            if not date_dir.is_dir():
                continue
            for run_dir in sorted(date_dir.iterdir(), reverse=True):
                sf = run_dir / "pipeline_state.json"
                if sf.exists():
                    try:
                        data = json.loads(sf.read_text(encoding="utf-8"))
                        if data.get("input_url") == url:
                            return cls(**data)
                    except Exception:
                        continue
        return None


# ============================================================
# URL 提取工具
# ============================================================
def extract_douyin_url(raw_text: str) -> Optional[str]:
    """从用户粘贴的分享文本中提取抖音链接。

    用户从抖音复制分享链接时，粘贴的往往是整段描述文本，例如：
        "1.74 aAG:/ ... 抖音独家 | 普京急了... https://v.douyin.com/wPI_y-7jkO4/ 复制此链接..."
    此函数从中提取出真正的 URL。
    """
    import re

    raw_text = raw_text.strip()

    # 如果已经是纯 URL，直接返回
    if re.match(r'^https?://', raw_text):
        # 检查是否以 URL 开头但也有尾随文本，清理之
        m = re.match(r'^(https?://[^\s]+)', raw_text)
        if m:
            url = m.group(1).rstrip('.,;:!?。，；：！？')
            return url
        return raw_text

    # 从文本中提取 URL
    url_patterns = [
        r'https?://v\.douyin\.com/[^\s]+',
        r'https?://www\.douyin\.com/video/[^\s]+',
        r'https?://www\.douyin\.com/user/[^\s]+',
        r'https?://www\.iesdouyin\.com/[^\s]+',
        r'https?://[^\s]*douyin[^\s]*',
        r'https?://[^\s]+',  # 通用兜底
    ]

    for pattern in url_patterns:
        m = re.search(pattern, raw_text)
        if m:
            url = m.group(0).rstrip('.,;:!?。，；：！？')
            # 确保 URL 看起来有效
            if len(url) > 15 and ('douyin.com' in url or 'iesdouyin.com' in url):
                return url
            elif len(url) > 15:
                return url

    return None


# ============================================================
# 阶段1：视频下载（全自动，支持抖音/多平台）
# ============================================================
# ── 下载脚本目录（Playwright Node.js 方案）──
_VIDEO_DL_DIR = PROJECT_ROOT / "video-batch-download-main"
_DOWNLOAD_SCRIPT = _VIDEO_DL_DIR / "scripts" / "download.mjs"
_SETUP_SCRIPT = _VIDEO_DL_DIR / "scripts" / "setup.mjs"

# 抖音域名特征
_DOUYIN_PATTERNS = ["douyin.com", "iesdouyin.com"]


def _is_douyin_url(url: str) -> bool:
    """判断是否为抖音链接。"""
    url_lower = url.lower()
    return any(p in url_lower for p in _DOUYIN_PATTERNS)


def _ensure_node_env() -> bool:
    """确保 Node.js + Playwright 环境就绪（自动安装）。返回是否就绪。"""
    import subprocess as sp

    # 1. 检查 Node.js
    try:
        sp.run(["node", "--version"], capture_output=True, check=True, timeout=10)
    except (FileNotFoundError, sp.CalledProcessError):
        add_log("❌ Node.js 未安装，请安装 Node.js >= 20 后重试", "error")
        add_log("   下载地址: https://nodejs.org/", "info")
        return False

    # 2. 检查 Playwright npm 包
    pkg_json = _VIDEO_DL_DIR / "package.json"
    node_modules = _VIDEO_DL_DIR / "node_modules" / "playwright"
    if not node_modules.exists() and pkg_json.exists():
        add_log("📦 安装 Playwright 依赖...", "info")
        try:
            import sys as _sys
            _sys.stderr.write("[node-env] npm install 开始...\n"); _sys.stderr.flush()
            sp.run(["npm", "install"], cwd=str(_VIDEO_DL_DIR),
                   capture_output=True, check=True, timeout=120)
            _sys.stderr.write("[node-env] npm install 完成\n"); _sys.stderr.flush()
        except sp.CalledProcessError as e:
            add_log(f"npm install 失败: {e.stderr.decode()[:300] if e.stderr else '未知错误'}", "warning")
        except FileNotFoundError:
            add_log("npm 未找到（Node.js 可能安装不完整）", "warning")
            return False

    # 3. 检查/安装 Playwright Chromium
    if _SETUP_SCRIPT.exists():
        try:
            import sys as _sys
            _sys.stderr.write("[node-env] Playwright setup 开始...\n"); _sys.stderr.flush()
            result = sp.run(["node", str(_SETUP_SCRIPT)], cwd=str(_VIDEO_DL_DIR),
                           capture_output=True, text=True, timeout=180)
            _sys.stderr.write(f"[node-env] Playwright setup 完成, rc={result.returncode}\n"); _sys.stderr.flush()
            if result.returncode == 0:
                return True
            add_log(f"Playwright setup 失败: {result.stderr[:300]}", "warning")
        except sp.TimeoutExpired:
            add_log("Playwright Chromium 安装超时（>3分钟）", "warning")
        except Exception as e:
            add_log(f"Playwright setup 异常: {e}", "warning")

    # 即使 setup 没输出成功，只要脚本存在就尝试
    return _DOWNLOAD_SCRIPT.exists() and node_modules.exists()


def _download_via_node(state: PipelineState) -> Optional[Dict[str, Any]]:
    """使用 Node.js Playwright 脚本下载视频（全自动，无需 cookies）。
    返回 {'video_files': [...], 'title': '...', 'description': '...'} 或 None。
    """
    import subprocess as sp

    state.run_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "node", str(_DOWNLOAD_SCRIPT),
        "--output", str(state.run_dir),
        "--no-transcribe",
        "--page-timeout", "60",
        "--media-wait", "30",
        state.input_url,
    ]

    add_log("🌐 Playwright 浏览器自动抓取中...", "info")
    add_log(f"  自动打开页面拦截视频流，无需 cookies", "info")

    try:
        result = sp.run(
            cmd,
            cwd=str(_VIDEO_DL_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        stdout = result.stdout or ""
        if result.returncode != 0:
            stderr = (result.stderr or "")[:500]
            add_log(f"Node.js 下载返回非零: {result.returncode}", "warning")
            if stderr:
                add_log(f"  stderr: {stderr}", "warning")
            return None

        # 从 stdout JSON 中提取元数据
        title = ""
        description = ""
        try:
            json_match = __import__("re").search(r'\{[\s\S]*"results"[\s\S]*\}', stdout)
            if json_match:
                data = json.loads(json_match.group())
                for r in data.get("results", []):
                    if r.get("title"):
                        title = r["title"]
                    if r.get("jsonPath"):
                        meta_path = Path(r["jsonPath"])
                        if meta_path.exists():
                            meta = json.loads(meta_path.read_text(encoding="utf-8"))
                            title = title or meta.get("title", "")
                            description = meta.get("description", "")
                    break
        except Exception:
            pass
        if not title:
            title = state.input_url.rsplit("/", 1)[-1][:50]

        # 查找下载的视频文件
        video_files = []
        for ext in ("*.mp4", "*.mkv", "*.webm", "*.mov", "*.flv"):
            video_files.extend(state.run_dir.glob(f"**/{ext}"))

        if not video_files:
            temp_dir = state.run_dir / ".temp"
            for ext in ("*.mp4", "*.mkv"):
                video_files.extend(temp_dir.glob(ext))

        if video_files:
            return {
                "video_files": [str(v) for v in video_files],
                "title": title,
                "description": description or "",
            }

        add_log("Node.js 下载完成但未找到视频文件", "warning")
        return None

    except sp.TimeoutExpired:
        add_log("Node.js 下载超时（>5分钟）", "warning")
        return None
    except FileNotFoundError:
        add_log("Node.js 不可用", "warning")
        return None
    except Exception as e:
        add_log(f"Node.js 下载异常: {e}", "warning")
        return None


def _download_via_ytdlp(state: PipelineState, temp_dir: Path) -> Optional[Dict[str, Any]]:
    """使用 yt-dlp 下载（非抖音平台，或作为后备）。
    返回 {'video_files': [...], 'title': '...', 'description': '...'} 或 None。
    """
    import sys as _sys
    _sys.stderr.write("[yt-dlp] 开始...\n"); _sys.stderr.flush()
    try:
        _sys.stderr.write("[yt-dlp] import yt_dlp...\n"); _sys.stderr.flush()
        import yt_dlp
        _sys.stderr.write("[yt-dlp] import 成功\n"); _sys.stderr.flush()
    except ImportError:
        add_log("yt-dlp 未安装，正在自动安装...", "warning")
        import subprocess as _sp
        _sp.check_call([sys.executable, "-m", "pip", "install", "yt-dlp", "-q"])
        import yt_dlp

    def _progress_hook(d):
        if d["status"] == "downloading":
            pct = d.get("_percent_str", "0%").strip("%")
            try:
                p = float(pct) / 100
            except ValueError:
                p = 0
            st.session_state.progress_pct = 0.05 + p * 0.10

    ydl_opts = {
        "outtmpl": str(temp_dir / "%(id)s.%(ext)s"),
        "progress_hooks": [_progress_hook],
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
    }

    try:
        _sys.stderr.write("[yt-dlp] extract_info 开始...\n"); _sys.stderr.flush()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(state.input_url, download=True)
        _sys.stderr.write("[yt-dlp] extract_info 完成\n"); _sys.stderr.flush()
    except Exception as e:
        add_log(f"yt-dlp 下载失败: {str(e).split(chr(10))[0][:200]}", "warning")
        return None

    video_files = []
    for f in temp_dir.iterdir():
        if f.suffix in (".mp4", ".mkv", ".webm", ".mov", ".flv"):
            video_files.append(str(f))

    if video_files:
        return {
            "video_files": video_files,
            "title": info.get("title", ""),
            "description": info.get("description", ""),
        }
    return None


def step_download(state: PipelineState) -> bool:
    """全自动视频下载：抖音用 Playwright 浏览器拦截，其他用 yt-dlp。"""
    import sys as _sys
    _sys.stderr.write("[download] step_download 开始\n"); _sys.stderr.flush()
    set_stage("下载", "running")
    add_log(f"阶段1/6: 视频下载 - {state.input_url[:60]}...", "stage")

    temp_dir = state.run_dir / ".temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    _sys.stderr.write(f"[download] temp_dir={temp_dir}\n"); _sys.stderr.flush()

    is_douyin = _is_douyin_url(state.input_url)
    _sys.stderr.write(f"[download] is_douyin={is_douyin}\n"); _sys.stderr.flush()
    result = None

    # ── 抖音：Playwright 浏览器自动化（零人工干预）──
    if is_douyin:
        add_log("📱 检测到抖音链接，使用 Playwright 浏览器自动化下载", "info")
        _sys.stderr.write("[download] 调用 _ensure_node_env...\n"); _sys.stderr.flush()
        if _ensure_node_env():
            _sys.stderr.write("[download] Node 环境就绪，调用 _download_via_node...\n"); _sys.stderr.flush()
            result = _download_via_node(state)
        else:
            _sys.stderr.write("[download] Node 环境不完整\n"); _sys.stderr.flush()
            add_log("⚠️ Node.js/Playwright 环境不完整，回退到 yt-dlp", "warning")

    # ── 非抖音 / Node.js 失败 → yt-dlp ──
    if result is None:
        import sys as _sys
        _sys.stderr.write("[download] 回退到 yt-dlp...\n"); _sys.stderr.flush()
        if is_douyin:
            add_log("🔄 回退到 yt-dlp 下载...", "info")
        _sys.stderr.write("[download] 调用 _download_via_ytdlp...\n"); _sys.stderr.flush()
        result = _download_via_ytdlp(state, temp_dir)
        _sys.stderr.write(f"[download] yt-dlp 返回: {result is not None}\n"); _sys.stderr.flush()

    # ── 处理结果 ──
    if result and result.get("video_files"):
        state.outputs["video_files"] = result["video_files"]
        state.outputs["video_title"] = result.get("title", "")
        state.outputs["video_description"] = result.get("description", "")
        size_mb = sum(Path(vf).stat().st_size for vf in result["video_files"]) / (1024 * 1024)
        add_log(f"视频下载完成 ({size_mb:.1f} MB, {len(result['video_files'])} 个文件)", "success")
        set_stage("下载", "done")
        state.mark_done("download")
        return True

    # ── 兜底：检查缓存 ──
    existing = list(temp_dir.glob("*.mp4")) + list(temp_dir.glob("*.mkv"))
    existing += list(state.run_dir.glob("**/*.mp4")) + list(state.run_dir.glob("**/*.mkv"))
    if existing:
        state.outputs["video_files"] = [str(v) for v in existing]
        add_log(f"使用已缓存的视频文件 ({len(existing)} 个)", "warning")
        set_stage("下载", "done")
        state.mark_done("download")
        return True

    add_log("❌ 所有下载方式均失败", "error")
    set_stage("下载", "failed")
    return False


# ============================================================
# 阶段2：语音转录
# ============================================================
def step_transcribe(state: PipelineState) -> bool:
    """使用 faster-whisper 或 transformers 转录视频音频。

    转录后端优先级（由 TRANSCRIBE_BACKEND 环境变量控制）：
      - "transformers"  → 直接使用 HuggingFace transformers（国内可配 HF_ENDPOINT 镜像）
      - "faster_whisper" → 使用 faster-whisper（CTranslate2，可能某些 Windows 环境不兼容）
      - 未设置/其他     → 优先 faster-whisper，失败回退 transformers
    """
    import sys as _sys
    _sys.stderr.write("[transcribe] step_transcribe 开始\n"); _sys.stderr.flush()
    set_stage("转录", "running")
    add_log("阶段2/6: 语音转录", "stage")

    # 查找视频文件
    video_files = state.outputs.get("video_files", [])
    _sys.stderr.write(f"[transcribe] video_files={len(video_files)}\n"); _sys.stderr.flush()
    if not video_files:
        temp_dir = state.run_dir / ".temp"
        video_files = [str(p) for p in temp_dir.glob("*.mp4")] + [str(p) for p in temp_dir.glob("*.mkv")]
        _sys.stderr.write(f"[transcribe] fallback video_files={len(video_files)}\n"); _sys.stderr.flush()

    if not video_files:
        # 尝试从描述兜底
        desc = state.outputs.get("video_description", "")
        title = state.outputs.get("video_title", "")
        if desc and len(desc) > 30:
            text = f"标题：{title}\n\n{desc}" if title else desc
            transcript_file = state.run_dir / "transcript.txt"
            transcript_file.write_text(text, encoding="utf-8")
            state.outputs["transcript_text"] = text
            state.outputs["transcript_files"] = [str(transcript_file)]
            add_log(f"无视频文件，使用视频描述作为文本 ({len(text)} 字符)", "warning")
            set_stage("转录", "done")
            state.mark_done("transcribe")
            return True
        add_log("没有找到视频文件且无视频描述文本", "error")
        set_stage("转录", "failed")
        return False

    video_path = video_files[0]
    _sys.stderr.write(f"[transcribe] video_path={video_path}\n"); _sys.stderr.flush()
    add_log(f"转录文件: {Path(video_path).name}", "info")

    # 确定转录后端
    backend = os.getenv("TRANSCRIBE_BACKEND", "faster_whisper").strip().lower()
    model = os.getenv("WHISPER_MODEL", "small")
    _sys.stderr.write(f"[transcribe] backend={backend} model={model}\n"); _sys.stderr.flush()

    # 对于 transformers 后端，使用短名映射
    MODEL_MAP = {"tiny": "openai/whisper-tiny", "small": "openai/whisper-small",
                 "base": "openai/whisper-base", "medium": "openai/whisper-medium"}

    st.session_state.progress_pct = 0.18

    # ── 根据 TRANSCRIBE_BACKEND 选择策略 ──
    if backend == "transformers":
        # 用户明确要求 transformers，跳过 faster-whisper
        _sys.stderr.write("[transcribe] 直接使用 transformers 后端\n"); _sys.stderr.flush()
        add_log("使用 transformers 后端（HuggingFace）", "info")
        return _transcribe_transformers(video_path, backend, model, MODEL_MAP, state)

    # 默认策略：优先尝试 faster-whisper，失败回退 transformers
    try:
        _sys.stderr.write("[transcribe] 尝试导入 faster_whisper...\n"); _sys.stderr.flush()
        from faster_whisper import WhisperModel as FWModel
        _sys.stderr.write("[transcribe] faster_whisper import 成功\n"); _sys.stderr.flush()

        device = os.getenv("WHISPER_DEVICE", "cpu")
        compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
        # 规范化模型名：去除 openai/whisper- 等前缀，faster-whisper 只需 short name
        fw_model_name = model
        for prefix in ("openai/whisper-", "openai/", "whisper-"):
            if fw_model_name.startswith(prefix):
                fw_model_name = fw_model_name[len(prefix):]
                break

        add_log(f"使用 faster-whisper: {fw_model_name} ({device}/{compute_type})", "info")
        _sys.stderr.write(f"[transcribe] 加载模型: {fw_model_name}...\n"); _sys.stderr.flush()
        fw = FWModel(fw_model_name, device=device, compute_type=compute_type)
        _sys.stderr.write("[transcribe] 模型加载完成\n"); _sys.stderr.flush()

        # 提取音频
        audio_path = _extract_audio(video_path, state.run_dir)

        segments = []
        seg_iter, info = fw.transcribe(audio_path, language="zh", beam_size=5)
        for s in seg_iter:
            text = s.text.strip()
            if text:
                segments.append(text)

        transcript = "\n".join(segments)
        transcript_file = state.run_dir / "transcript.txt"
        transcript_file.write_text(transcript, encoding="utf-8")

        state.outputs["transcript_text"] = transcript
        state.outputs["transcript_files"] = [str(transcript_file)]

        add_log(f"转录完成 ({len(transcript)} 字符)", "success")
        set_stage("转录", "done")
        state.mark_done("transcribe")
        st.session_state.progress_pct = 0.28
        return True

    except ImportError:
        add_log("faster-whisper 未安装，回退到 transformers...", "warning")
        return _transcribe_transformers(video_path, backend, model, MODEL_MAP, state)
    except Exception as e:
        add_log(f"faster-whisper 转录失败: {e}", "error")
        add_log("回退到 transformers...", "warning")
        return _transcribe_transformers(video_path, backend, model, MODEL_MAP, state)


def _extract_audio(video_path: str, run_dir: Path) -> str:
    """从视频提取 16kHz WAV 音频。"""
    import subprocess as sp

    audio_path = run_dir / "audio.wav"
    if audio_path.exists():
        return str(audio_path)

    ffmpeg_paths = ["ffmpeg", "ffmpeg.exe"]
    ffmpeg_exe = None
    for fp in ffmpeg_paths:
        try:
            sp.run([fp, "-version"], capture_output=True, timeout=5)
            ffmpeg_exe = fp
            break
        except Exception:
            continue

    if ffmpeg_exe:
        sp.run(
            [ffmpeg_exe, "-i", video_path, "-ar", "16000", "-ac", "1",
             "-f", "wav", str(audio_path), "-y", "-loglevel", "error"],
            check=True, timeout=300,
        )
        return str(audio_path)
    else:
        add_log("ffmpeg 未找到，直接转录视频文件（可能较慢）", "warning")
        return video_path


def _transcribe_transformers(video_path, backend, model, model_map, state):
    """使用 transformers 后端转录。"""
    import torch

    if "HF_ENDPOINT" not in os.environ:
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

    from transformers import pipeline

    hf_model = model_map.get(model, model)
    add_log(f"使用 transformers: {hf_model}", "info")

    pipe = pipeline(
        "automatic-speech-recognition",
        model=hf_model,
        chunk_length_s=30,
        device="cpu",
        torch_dtype=torch.float32,
    )

    audio_path = _extract_audio(video_path, state.run_dir)
    result = pipe(audio_path, generate_kwargs={"language": "zh", "task": "transcribe"})
    text = result["text"].strip()

    # 繁体转简体
    try:
        import opencc
        text = opencc.OpenCC("t2s").convert(text)
    except ImportError:
        pass

    # 清洗重复循环
    import re
    pattern = re.compile(r'(.{1,4}?)\1{5,}')
    match = pattern.search(text)
    if match:
        text = text[:match.start()].strip()
        add_log("检测到重复循环，已截断", "warning")

    transcript_file = state.run_dir / "transcript.txt"
    transcript_file.write_text(text, encoding="utf-8")

    state.outputs["transcript_text"] = text
    state.outputs["transcript_files"] = [str(transcript_file)]

    add_log(f"转录完成 ({len(text)} 字符)", "success")
    set_stage("转录", "done")
    state.mark_done("transcribe")
    st.session_state.progress_pct = 0.28
    return True


# ============================================================
# 阶段3：AI 写作
# ============================================================
def step_write(state: PipelineState) -> bool:
    """直接调用 AIWriter.generate() 生成微头条/文章。"""
    set_stage("写作", "running")
    add_log("阶段3/6: AI 写作（调用 DeepSeek API）", "stage")

    transcript = state.outputs.get("transcript_text", "")
    if not transcript:
        # 尝试从描述读取
        desc = state.outputs.get("video_description", "")
        title = state.outputs.get("video_title", "")
        transcript = f"标题：{title}\n\n{desc}" if (title or desc) else ""
        if not transcript:
            add_log("没有转录文本，无法生成内容", "error")
            set_stage("写作", "failed")
            return False

    add_log(f"输入文本: {len(transcript)} 字符", "info")
    add_log(f"风格: {state.content_style}", "info")

    st.session_state.progress_pct = 0.32

    try:
        from ai_writer import AIWriter

        writer = AIWriter()

        # 确定 content_style 枚举
        cs = state.content_style
        if ContentStyle and isinstance(cs, str):
            try:
                cs = ContentStyle(cs)
            except ValueError:
                cs = ContentStyle.GENERAL

        # 确定 content_type：若 ContentType 导入失败则安全降级为字符串
        if ContentType is not None:
            if state.content_type == "article":
                ct = ContentType.ARTICLE
            else:
                ct = ContentType.TOUTIE
            result = writer.generate(
                topic=transcript[:2000],
                content_type=ct,
                content_style=cs if state.content_type == "toutie" else None,
                max_chars=2000 if state.content_type == "article" else 1200,
            )
        else:
            # ContentType 枚举不可用，用字符串参数兼容旧版 AIWriter
            add_log("ContentType 枚举未加载，使用字符串降级模式", "warning")
            if state.content_type == "article":
                result = writer.generate(
                    topic=transcript[:2000],
                    content_type="article",
                    max_chars=2000,
                )
            else:
                result = writer.generate(
                    topic=transcript[:2000],
                    content_type="toutie",
                    content_style=cs,
                    max_chars=1200,
                )

        title = result.get("title", "")
        content = result.get("content", "")
        char_count = result.get("char_count", len(content))

        if not content or len(content) < 50:
            add_log("AI 生成内容过短，可能出现问题", "error")
            set_stage("写作", "failed")
            return False

        # 保存
        prefix = "微头条" if state.content_type == "toutie" else "文章"
        raw_file = state.run_dir / f"{prefix}_{state.run_id}_ai_raw.md"
        raw_file.write_text(
            f"# {title}\n\n{content}\n\n---\n*AI 原始生成 | {datetime.now().isoformat()}*",
            encoding="utf-8",
        )

        state.outputs["generated_title"] = title
        state.outputs["generated_content"] = content
        state.outputs["generated_file"] = str(raw_file)
        state.outputs["char_count"] = char_count

        add_log(f"AI 写作完成 ({char_count} 字符)", "success")
        set_stage("写作", "done")
        state.mark_done("write")
        st.session_state.progress_pct = 0.45
        return True

    except Exception as e:
        add_log(f"AI 写作失败: {e}", "error")
        traceback.print_exc()
        set_stage("写作", "failed")
        return False


# ============================================================
# 阶段4：人工化改写
# ============================================================
def step_humanize(state: PipelineState) -> bool:
    """调用 AIWriter.humanize() 去除 AI 味。"""
    if not state.enable_humanize:
        add_log("跳过阶段4: 人工化改写（未启用）", "info")
        set_stage("改写", "done")
        state.mark_done("humanize")
        return True

    set_stage("改写", "running")
    add_log("阶段4/6: 人工化改写（去 AI 味）", "stage")

    content = state.outputs.get("generated_content", "")
    if not content:
        add_log("无内容可改写，跳过", "warning")
        set_stage("改写", "done")
        state.mark_done("humanize")
        return True

    st.session_state.progress_pct = 0.48

    try:
        from ai_writer import AIWriter
        writer = AIWriter()
        result = writer.humanize(content)
        humanized = result["content"]
        char_count = result["char_count"]

        add_log(f"人工化改写完成 ({char_count} 字符)", "success")

        # 保存人工化版本，同时保留原始版本
        prefix = "微头条" if state.content_type == "toutie" else "文章"
        output_file = state.run_dir / f"{prefix}_{state.run_id}.md"
        title = state.outputs.get("generated_title", "")
        output_file.write_text(
            f"# {title}\n\n{humanized}\n\n---\n*人工化改写 | {datetime.now().isoformat()}*",
            encoding="utf-8",
        )

        state.outputs["humanized_content"] = humanized
        state.outputs["generated_content"] = humanized  # 后续阶段用人工化版本
        state.outputs["generated_file"] = str(output_file)
        state.outputs["humanized_file"] = str(output_file)

        set_stage("改写", "done")
        state.mark_done("humanize")
        st.session_state.progress_pct = 0.55
        return True

    except Exception as e:
        add_log(f"人工化改写失败（使用 AI 原文）: {e}", "warning")
        set_stage("改写", "done")
        state.mark_done("humanize")
        return True  # 不阻断流水线


# ============================================================
# Pollinations 免费图片 API 辅助函数
# ============================================================

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"

def _generate_pollinations_image(prompt: str, output_path: Path,
                                  width: int = 1024, height: int = 768,
                                  model: str = "flux",
                                  timeout: int = 120) -> Optional[str]:
    """调用 Pollinations 免费 API 生成图片，保存到 output_path。
    成功返回文件路径字符串，失败返回 None。
    """
    import urllib.parse
    import requests as _req

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 构造 URL（Prompt 中的特殊字符需要编码）
    encoded = urllib.parse.quote(prompt, safe="")
    url = f"{POLLINATIONS_BASE}/{encoded}?model={model}&width={width}&height={height}&nologo=true"

    import sys as _sys
    _sys.stderr.write(f"[pollinations] 请求: {url[:120]}...\n"); _sys.stderr.flush()

    try:
        resp = _req.get(url, timeout=timeout)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if "image" not in content_type:
            _sys.stderr.write(f"[pollinations] 非图片响应: {content_type[:80]}\n"); _sys.stderr.flush()
            return None

        output_path.write_bytes(resp.content)
        _sys.stderr.write(f"[pollinations] 图片已保存: {output_path.name} ({len(resp.content)} bytes)\n"); _sys.stderr.flush()
        return str(output_path)

    except _req.Timeout:
        _sys.stderr.write(f"[pollinations] 超时 ({timeout}s)\n"); _sys.stderr.flush()
        return None
    except _req.RequestException as e:
        _sys.stderr.write(f"[pollinations] 请求失败: {e}\n"); _sys.stderr.flush()
        return None


def _build_cover_prompt(title: str, context: str = "") -> str:
    """为文章标题构建封面图 prompt（Pollinations flux 模型，英文效果更好）。"""
    base = (f"A dramatic photorealistic illustration for a military news article titled '{title}'. "
            f"Epic cinematic composition, dramatic lighting, professional news photography style, "
            f"highly detailed, sharp focus, soldiers or military equipment in action, "
            f"no text, no watermark, no signature, no logo")
    return base[:500]  # 防止 prompt 过长


def _build_inline_prompts(title: str, content: str, count: int = 2) -> list:
    """从文章正文提取关键词，构建内文配图 prompt 列表。"""
    # 简单策略：取正文前 300 字 + 后 200 字作为上下文
    body = content[:300] + (content[-200:] if len(content) > 400 else "")
    # 提取可能的主题词（取标题和前几句中的名词性短语）
    keywords = title[:60]
    if len(body) > 50:
        keywords = body[:80].replace("\n", " ")

    prompts = []
    themes = [
        "military strategic overview, satellite imagery style, geopolitical map visualization",
        "military exercise scene, realistic war game simulation, troops and equipment formation",
        "naval fleet at sea, warships in formation, dramatic ocean sunset, realistic photography",
    ]
    for i in range(min(count, len(themes))):
        p = (f"A photorealistic image depicting: {themes[i]}. "
             f"Article theme: {keywords[:80]}. "
             f"Highly detailed, sharp focus, cinema-quality lighting, "
             f"no text, no watermark, no signature")
        prompts.append(p[:500])

    return prompts


# ============================================================
# 阶段5：配图生成（Pollinations 免费 API）
# ============================================================
def step_images(state: PipelineState) -> bool:
    """使用 Pollinations 免费 API 生成封面和内文配图。
    绕过 image_gen.py（付费 API 无可用 Key），直接 HTTP 调用。
    """
    import sys as _sys

    # 未启用配图
    if not state.with_images:
        _sys.stderr.write("[images] 配图未启用，跳过\n"); _sys.stderr.flush()
        add_log("跳过阶段5: 配图生成（未启用）", "info")
        set_stage("配图", "done")
        state.mark_done("generate_images")
        state.outputs["images_injected"] = False
        st.session_state.progress_pct = 0.65
        return True

    _sys.stderr.write("[images] step_images 开始（Pollinations）\n"); _sys.stderr.flush()
    set_stage("配图", "running")
    add_log("阶段5/6: AI 配图生成（Pollinations 免费 API）", "stage")

    title = state.outputs.get("generated_title", "")
    content = state.outputs.get("generated_content", "")
    if not content:
        _sys.stderr.write("[images] 无文章内容\n"); _sys.stderr.flush()
        add_log("无文章内容，跳过配图生成", "warning")
        set_stage("配图", "done")
        state.mark_done("generate_images")
        state.outputs["images_injected"] = False
        return True

    if not title and content:
        first_line = content.split("\n")[0].strip()
        if len(first_line) < 80:
            title = first_line

    images_dir = state.run_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    st.session_state.progress_pct = 0.58

    cover_path = None
    inline_paths = []
    inline_prompts_used = []
    images_injected = False

    try:
        # ── 1. 生成封面图 ──
        cover_prompt = _build_cover_prompt(title, content[:200])
        add_log(f"封面 prompt: {cover_prompt[:80]}...", "info")
        cover_file = images_dir / "cover.png"
        _sys.stderr.write("[images] 生成封面图...\n"); _sys.stderr.flush()

        cover_path = _generate_pollinations_image(
            cover_prompt, cover_file, width=1024, height=576, timeout=180
        )

        if cover_path:
            add_log(f"封面图: {Path(cover_path).name}", "success")
            state.outputs["cover_image"] = cover_path
        else:
            add_log("封面图生成失败（Pollinations 无响应或超时）", "warning")

        st.session_state.progress_pct = 0.62

        # ── 2. 生成内文配图 ──
        inline_prompts = _build_inline_prompts(title, content, count=2)
        add_log(f"计划生成 {len(inline_prompts)} 张内文配图", "info")

        for idx, iprompt in enumerate(inline_prompts):
            _sys.stderr.write(f"[images] 生成内文图 {idx+1}/{len(inline_prompts)}...\n"); _sys.stderr.flush()
            inline_file = images_dir / f"inline_{idx + 1}.png"
            result = _generate_pollinations_image(
                iprompt, inline_file, width=1024, height=768, timeout=180
            )
            if result:
                inline_paths.append(result)
                inline_prompts_used.append(iprompt)
                add_log(f"内文配图 {idx+1}: {Path(result).name}", "success")
            else:
                add_log(f"内文配图 {idx+1} 生成失败", "warning")

        st.session_state.progress_pct = 0.67

        # ── 3. 汇总结果 ──
        success_count = len(inline_paths)
        add_log(f"配图汇总: 封面{'✅' if cover_path else '❌'} | 内文 {success_count}/{len(inline_prompts)}",
                "success" if (cover_path or success_count > 0) else "warning")

        state.outputs["inline_images"] = inline_paths
        state.outputs["image_gen_prompts"] = {
            "cover": cover_prompt,
            "inline": inline_prompts_used,
        }
        state.outputs["image_provider"] = "pollinations"

        # ── 4. 注入图片到文章 ──
        images_injected = _inject_images_v2(state, cover_path, inline_paths)

    except ImportError as e:
        _sys.stderr.write(f"[images] ImportError: {e}\n"); _sys.stderr.flush()
        add_log(f"图片生成依赖缺失: {e}。Pollinations 需要 requests 库（pip install requests）", "warning")
        state.outputs["images_injected"] = False
    except Exception as e:
        _sys.stderr.write(f"[images] Exception: {e}\n"); _sys.stderr.flush()
        traceback.print_exc()
        add_log(f"配图生成异常: {e}（已跳过配图，不影响后续阶段）", "warning")
        state.outputs["images_injected"] = False

    # 始终标记阶段完成（不阻断流水线），但通过 images_injected 告知真实结果
    state.outputs["images_injected"] = images_injected
    set_stage("配图", "done")
    state.mark_done("generate_images")
    st.session_state.progress_pct = 0.70

    if not images_injected:
        add_log("⚠️ 本篇文章无配图，最终稿件为纯文本版", "warning")

    _sys.stderr.write(f"[images] 完成, images_injected={images_injected}\n"); _sys.stderr.flush()
    return True


def _inject_images_v2(state, cover_path, inline_paths: list) -> bool:
    """将图片引用注入文章 Markdown（v2: 有图才生成配图版）。

    返回 images_injected 布尔值。
    """
    generated_file = state.outputs.get("generated_file", "")
    if not generated_file:
        return False

    article_path = Path(generated_file)
    if not article_path.exists():
        return False

    content = article_path.read_text(encoding="utf-8")
    has_any_image = bool(cover_path or inline_paths)

    if not has_any_image:
        # 无图片：不生成配图版，assembled_file 指向原始文件
        state.outputs["assembled_file"] = str(article_path)
        return False

    # ── 注入封面图 ──
    if cover_path:
        cover_rel = f"images/{Path(cover_path).name}"
        cover_md = f"\n\n![封面]({cover_rel})\n\n> *AI 生成封面配图*\n"
        lines = content.split("\n")
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("# "):
                insert_idx = i + 1
                while insert_idx < len(lines) and lines[insert_idx].strip() == "":
                    insert_idx += 1
                break
        if insert_idx > 0:
            lines.insert(insert_idx, cover_md.strip())
            content = "\n".join(lines)

    # ── 注入内文配图 ──
    if inline_paths:
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        body_start = 0
        for i, p in enumerate(paragraphs):
            if p.startswith("# ") or p.startswith("![") or p.startswith("> *"):
                body_start = i + 1
            else:
                break

        body = paragraphs[body_start:]
        if body and len(inline_paths) > 0:
            step_size = max(1, len(body) // (len(inline_paths) + 1))
            for img_idx, img_path in enumerate(inline_paths):
                img_rel = f"images/{Path(img_path).name}"
                pos = body_start + step_size * (img_idx + 1)
                if pos < len(paragraphs):
                    img_md = (
                        f"\n\n> **📸 配图{img_idx + 1}**  \n> "
                        f"![配图{img_idx + 1}]({img_rel})\n"
                    )
                    paragraphs[pos] = img_md.strip() + "\n\n" + paragraphs[pos]
            content = "\n\n".join(paragraphs)

    # ── 写回：有图才生成配图版文件名 ──
    assembled_file = state.run_dir / "完整稿件_配图版.md"
    assembled_file.write_text(content, encoding="utf-8")
    state.outputs["generated_content"] = content
    state.outputs["assembled_file"] = str(assembled_file)
    return True


# ============================================================
# 阶段6：图文组装（水印裁剪）
# ============================================================
def step_assemble(state: PipelineState) -> bool:
    """最终组装：检查水印、确保输出完整。"""
    set_stage("组装", "running")
    add_log("阶段6/6: 图文最终组装", "stage")

    st.session_state.progress_pct = 0.80

    # 确保有最终文件
    final_file = state.outputs.get("assembled_file") or state.outputs.get("generated_file")
    if not final_file or not Path(final_file).exists():
        add_log("没有找到最终稿件文件", "warning")
        set_stage("组装", "done")
        state.mark_done("assemble")
        return True

    add_log(f"最终稿件: {Path(final_file).name}", "success")

    # 文件清单
    file_list = []
    for f in state.run_dir.glob("**/*"):
        if f.is_file() and ".temp" not in str(f):
            size_kb = f.stat().st_size / 1024
            file_list.append({"name": f.name, "path": str(f), "size_kb": round(size_kb, 1)})

    state.outputs["file_list"] = file_list
    add_log(f"输出目录: {state.run_dir}", "info")
    add_log(f"共 {len(file_list)} 个文件", "info")

    set_stage("组装", "done")
    state.mark_done("assemble")
    st.session_state.progress_pct = 1.0
    return True


# ============================================================
# 流水线总调度
# ============================================================
def execute_pipeline(url: str, style: str, enable_humanize: bool,
                     with_images: bool, content_type: str):
    """按序执行全部 6 个阶段（同步阻塞执行）。"""
    import sys as _sys

    t_start = time.time()
    st.session_state.is_running = True
    st.session_state.pipeline_error = None
    st.session_state.pipeline_done = False

    try:
        _sys.stderr.write("[pipeline] 查找已有运行记录...\n"); _sys.stderr.flush()
        # 初始化/恢复状态
        existing = PipelineState.find_existing(url)
        if existing:
            done = set(existing.completed_stages)
            needed = {"download", "transcribe", "write", "humanize", "generate_images", "assemble"}
            if done >= needed:
                add_log(f"该链接已有完整运行记录: {existing.run_id}", "success")
                state = existing
                _load_result_from_state(state)
                _sys.stderr.write("[pipeline] 命中缓存，直接返回\n"); _sys.stderr.flush()
                return
            elif done:
                add_log(f"发现未完成运行: {existing.run_id}，将断点续跑", "warning")
                add_log(f"已完成: {', '.join(done)}", "info")
                existing.content_style = style
                existing.enable_humanize = enable_humanize
                existing.with_images = with_images
                state = existing
            else:
                state = PipelineState(
                    input_url=url, content_type=content_type,
                    content_style=style, enable_humanize=enable_humanize,
                    with_images=with_images,
                )
        else:
            state = PipelineState(
                input_url=url, content_type=content_type,
                content_style=style, enable_humanize=enable_humanize,
                with_images=with_images,
            )

        st.session_state.pipeline_state = state
        st.session_state.run_id = state.run_id
        add_log(f"运行 ID: {state.run_id}", "info")
        add_log(f"输出目录: {state.run_dir}", "info")

        # 阶段列表
        stages = [
            ("download", "下载", step_download),
            ("transcribe", "转录", step_transcribe),
            ("write", "写作", step_write),
            ("humanize", "改写", step_humanize),
            ("generate_images", "配图", step_images),
            ("assemble", "组装", step_assemble),
        ]

        for stage_id, stage_name, stage_fn in stages:
            if state.is_done(stage_id):
                set_stage(stage_name, "done")
                add_log(f"阶段 {stage_name}: 已完成，跳过", "info")
                continue

            try:
                _sys.stderr.write(f"[pipeline] 开始阶段: {stage_name}\n"); _sys.stderr.flush()
                success = stage_fn(state)
                state.save()
                _sys.stderr.write(f"[pipeline] 阶段 {stage_name} 完成, success={success}\n"); _sys.stderr.flush()

                if not success:
                    add_log(f"阶段 {stage_name} 执行失败，流水线中止", "error")
                    break
            except Exception as e:
                add_log(f"阶段 {stage_name} 异常: {e}", "error")
                traceback.print_exc()
                set_stage(stage_name, "failed")
                state.save()
                break

        # 完成
        result = _build_result(state)
        st.session_state.result_data = result
        elapsed = round(time.time() - t_start, 1)
        st.session_state.elapsed_seconds = elapsed
        if all(state.is_done(s[0]) for s in stages):
            add_log(f"全部完成！耗时 {elapsed:.0f} 秒", "success")
        else:
            add_log(f"流水线未完全完成。可重新运行以断点续跑", "warning")
        _sys.stderr.write(f"[pipeline] 流水线结束, all_done={all(state.is_done(s[0]) for s in stages)}\n"); _sys.stderr.flush()

    except Exception as e:
        _sys.stderr.write(f"[pipeline] Exception 捕获: {e}\n"); _sys.stderr.flush()
        add_log(f"流水线发生未预期异常: {e}", "error")
        traceback.print_exc()
        st.session_state.pipeline_error = str(e)
    except BaseException as e:
        # 捕获 SystemExit / KeyboardInterrupt 等致命异常，防止整进程崩溃
        _sys.stderr.write(f"[pipeline] 致命异常 BaseException: {type(e).__name__}: {e}\n"); _sys.stderr.flush()
        traceback.print_exc()
        st.session_state.pipeline_error = f"致命错误({type(e).__name__}): {e}"
        st.session_state.is_running = False
        st.session_state.pipeline_done = True
        raise  # 重新抛出，让上层 main() 的 BaseException 处理器最终兜底
    finally:
        st.session_state.is_running = False
        st.session_state.pipeline_done = True


def _build_result(state: PipelineState) -> dict:
    """从 PipelineState 构建结果数据。"""
    final_file = state.outputs.get("assembled_file") or state.outputs.get("generated_file")
    content = ""
    if final_file and Path(final_file).exists():
        content = Path(final_file).read_text(encoding="utf-8")

    cover_image = state.outputs.get("cover_image", "")
    inline_images = state.outputs.get("inline_images", [])
    file_list = state.outputs.get("file_list", [])

    return {
        "run_id": state.run_id,
        "run_dir": str(state.run_dir),
        "title": state.outputs.get("generated_title", ""),
        "content": content,
        "char_count": state.outputs.get("char_count", 0),
        "cover_image": cover_image,
        "inline_images": inline_images,
        "file_list": file_list,
    }


def _load_result_from_state(state: PipelineState):
    """从已有状态加载结果数据。"""
    st.session_state.pipeline_state = state
    st.session_state.run_id = state.run_id
    st.session_state.result_data = _build_result(state)
    for s_name in state.completed_stages:
        stage_map = {
            "download": "下载", "transcribe": "转录", "write": "写作",
            "humanize": "改写", "generate_images": "配图", "assemble": "组装",
        }
        set_stage(stage_map.get(s_name, s_name), "done")
    st.session_state.progress_pct = 1.0


# ============================================================
# UI 侧边栏
# ============================================================
def render_sidebar():
    """渲染侧边栏配置面板。"""
    with st.sidebar:
        st.markdown("### ⚙️ 配置面板")

        style = st.selectbox(
            "内容风格",
            options=[
                ("story_narrative", "📖 评书故事型（听风的蚕）"),
                ("military", "🔥 军事深度分析型"),
                ("sharp_commentary", "✒️ 冷静克制型（牛弹琴）"),
                ("data_list", "📊 硬核论证型（静思有我）"),
                ("flash_news", "⚡ 快讯速报型"),
                ("discussion", "💬 互动讨论型"),
                ("general", "📝 通用风格"),
            ],
            format_func=lambda x: x[1],
            key="sidebar_style",
        )

        content_type = st.radio(
            "内容类型",
            options=[("toutie", "微头条"), ("article", "文章")],
            format_func=lambda x: x[1],
            horizontal=True,
            key="sidebar_content_type",
        )

        humanize = st.toggle("✍️ 人工化改写", value=True, help="去除 AI 味，输出更像真人手笔")
        with_images = st.toggle("🖼️ AI 配图生成", value=True,
                                help="AI 生成封面图 + 内文配图（需配置图片 API Key）")

        st.divider()

        # API 设置
        with st.expander("🔑 API 密钥设置"):
            api_key = st.text_input(
                "DeepSeek API Key",
                value=os.getenv("AI_API_KEY", ""),
                type="password",
                placeholder="sk-...",
            )
            api_base = st.text_input(
                "API Base URL",
                value=os.getenv("AI_BASE_URL", "https://api.deepseek.com/v1"),
            )
            api_model = st.text_input(
                "Model",
                value=os.getenv("AI_MODEL", "deepseek-chat"),
            )
            if st.button("💾 保存到 .env", use_container_width=True):
                _save_env(api_key, api_base, api_model)
                st.success("配置已保存！")

        # 下载设置
        with st.expander("📥 下载设置"):
            st.caption("抖音：Playwright 真实浏览器自动拦截视频流，全自动无需 cookies。")
            st.caption("其他平台：yt-dlp 直连下载。")
            st.caption(f"依赖：Node.js + Playwright Chromium（首次自动安装）")

        st.divider()

        st.markdown("### 📖 快捷参考")
        st.caption(
            "| 风格 | 字数 | 特点 |\n"
            "|------|------|------|\n"
            "| 评书故事型 | 800-1200 | 河南方言，评书韵味 |\n"
            "| 军事深度 | 800-1200 | 七层递进法，证据驱动 |\n"
            "| 冷静克制冷 | 800-1200 | 事实为主，独到视角 |\n"
            "| 硬核论证型 | 800-1200 | 数据驱动，逻辑严密 |\n"
            "| 快讯速报型 | 300-500 | 3段讲清，零铺垫 |\n"
            "| 互动讨论型 | 500-800 | 开放式提问，撩互动 |"
        )

        return style[0], content_type[0], humanize, with_images


def _save_env(api_key: str, api_base: str, api_model: str):
    """保存配置到 .env 文件。"""
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").split("\n")
    else:
        lines = []

    updated = {"AI_API_KEY": api_key, "AI_BASE_URL": api_base, "AI_MODEL": api_model}
    new_lines = []
    found = set()
    for line in lines:
        stripped = line.strip()
        for k, v in updated.items():
            if stripped.startswith(f"{k}=") and k not in found:
                new_lines.append(f"{k}={v}")
                found.add(k)
                break
        else:
            new_lines.append(line)

    for k, v in updated.items():
        if k not in found:
            new_lines.append(f"{k}={v}")

    env_path.write_text("\n".join(new_lines), encoding="utf-8")
    # 更新环境变量
    for k, v in updated.items():
        os.environ[k] = v


# ============================================================
# UI 主区域
# ============================================================
def render_main():
    """渲染主操作区。"""
    st.markdown('<div class="main-header">🔮 AIToutiao 一键内容生成器</div>',
                unsafe_allow_html=True)

    # 状态指示灯
    is_running = st.session_state.is_running
    has_result = st.session_state.result_data is not None

    status_color = "#D29922" if is_running else ("#3FB950" if has_result else "#8B949E")
    status_text = "● 运行中" if is_running else ("● 已完成" if has_result else "● 就绪")
    st.markdown(
        f'<div style="text-align:center;margin-bottom:16px;"><span style="color:{status_color};font-size:14px;">'
        f'{status_text}</span></div>',
        unsafe_allow_html=True,
    )

    # URL 输入行
    col1, col2, col3 = st.columns([5, 1.5, 1])
    with col1:
        url = st.text_input(
            "抖音视频链接",
            key="url_input",
            placeholder="直接粘贴抖音复制的分享内容即可，自动提取链接",
            label_visibility="collapsed",
        )
    # 实时 URL 检测提示（纯 UI 预览，不阻断流水线）
    if url and url.strip():
        raw = url.strip()
        detected = extract_douyin_url(raw)
        st.session_state.processed_url = detected or ""  # 单向数据通道：提取 → 执行
        if detected and detected != raw:
            st.caption(f"🔗 检测到链接：`{detected}`")
        elif detected is None:
            st.caption("⚠️ 未检测到有效链接，请粘贴抖音分享内容")

    with col2:
        generate_btn = st.button("▶ 一键生成", use_container_width=True,
                                  type="primary", disabled=is_running)
    with col3:
        clear_btn = st.button("🗑 清空", use_container_width=True, disabled=is_running)

    if clear_btn:
        for k in ("logs", "result_data", "pipeline_state", "run_id", "processed_url",
                  "pipeline_error", "pipeline_done"):
            st.session_state[k] = _DEFAULTS[k]
        for s_name in st.session_state.stage_status:
            st.session_state.stage_status[s_name] = "pending"
        st.session_state.progress_pct = 0.0
        st.rerun()

    return url, generate_btn


# ============================================================
# UI 进度条 + 阶段指示灯
# ============================================================
def render_progress():
    """渲染阶段进度条和指示灯。"""
    stages_order = ["下载", "转录", "写作", "改写", "配图", "组装"]

    # 阶段指示灯行
    cols = st.columns(len(stages_order))
    for i, name in enumerate(stages_order):
        status = st.session_state.stage_status.get(name, "pending")
        with cols[i]:
            indicator_html = f"""
            <div style="text-align:center;">
                <div class="stage-indicator {status}" style="display:inline-block;"></div>
                <div style="font-size:11px;color:#8B949E;margin-top:4px;">{name}</div>
            </div>
            """
            st.markdown(indicator_html, unsafe_allow_html=True)

    # 进度条
    st.progress(st.session_state.progress_pct)

    # 当前阶段描述
    if st.session_state.is_running:
        current = st.session_state.current_stage
        if current:
            st.caption(f"⏳ 正在执行：{current}")
    elif st.session_state.progress_pct >= 1.0:
        elapsed = st.session_state.get("elapsed_seconds", 0)
        st.caption(f"✅ 执行完成 | 耗时 {elapsed:.0f} 秒")


# ============================================================
# UI 运行日志
# ============================================================
def render_logs():
    """渲染运行日志区域。"""
    logs = st.session_state.logs
    if not logs:
        return

    # 构建日志 HTML
    html_lines = ['<div class="log-container">']
    for entry in logs:
        emoji = _emoji_for_level(entry["level"])
        html_lines.append(
            f'<div class="log-line {entry["level"]}">'
            f'[{entry["time"]}] {emoji} {entry["msg"]}</div>'
        )
    html_lines.append("</div>")

    st.markdown("\n".join(html_lines), unsafe_allow_html=True)


# ============================================================
# UI 结果展示
# ============================================================
def render_results():
    """渲染结果展示区。"""
    result = st.session_state.result_data
    if not result:
        return

    st.markdown("---")

    col_img, col_text = st.columns([1, 2])

    with col_img:
        cover = result.get("cover_image", "")
        if cover and Path(cover).exists():
            st.image(str(cover), caption="封面图（AI 生成）", use_container_width=True)

        # 统计信息
        st.markdown("#### 📊 统计")
        st.markdown(
            f'<span class="stat-badge">📝 {result.get("char_count", 0)} 字符</span>'
            f'<span class="stat-badge">📁 {len(result.get("file_list", []))} 个文件</span>'
            f'<span class="stat-badge">🆔 {result.get("run_id", "")}</span>',
            unsafe_allow_html=True,
        )

        # 内文配图预览
        inline = result.get("inline_images", [])
        if inline:
            st.markdown("#### 🖼️ 内文配图")
            for img_path in inline:
                if Path(img_path).exists():
                    st.image(str(img_path), use_container_width=True)

    with col_text:
        content = result.get("content", "")
        if content:
            st.markdown("#### 📄 生成的稿件")
            with st.container(height=500):
                st.markdown(content)

        # 操作按钮
        st.markdown("#### ⚡ 操作")
        btn_cols = st.columns(4)
        with btn_cols[0]:
            run_dir = result.get("run_dir", "")
            if run_dir and Path(run_dir).exists():
                if st.button("📂 打开目录", use_container_width=True):
                    os.startfile(run_dir) if sys.platform == "win32" else None
                    st.info(f"目录: {run_dir}")

        with btn_cols[1]:
            if content:
                st.download_button(
                    "📥 下载稿件",
                    data=content,
                    file_name=f"AIToutiao_{result.get('run_id', 'output')}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )

        with btn_cols[2]:
            if content:
                if st.button("📋 复制内容", use_container_width=True):
                    try:
                        import pyperclip
                        pyperclip.copy(content)
                        st.success("已复制到剪贴板！")
                    except ImportError:
                        st.code(content, language="markdown")
                        st.info("请手动复制上方内容（安装 pyperclip 可支持一键复制）")

        with btn_cols[3]:
            raw_file = Path(result.get("run_dir", "")) / f"微头条_{result.get('run_id', '')}_ai_raw.md"
            if raw_file.exists():
                with st.expander("🔍 查看 AI 原始版本"):
                    st.markdown(raw_file.read_text(encoding="utf-8"))

        # 文件清单
        file_list = result.get("file_list", [])
        if file_list:
            with st.expander("📋 所有输出文件"):
                for f in file_list:
                    st.caption(f"📄 {f['name']} ({f['size_kb']} KB)")


# ============================================================
# 主入口
# ============================================================
def main():
    style, content_type, humanize, with_images = render_sidebar()
    url, generate_btn = render_main()

    # ── 触发执行（同步阻塞，URL 提取已在 render_main() 中完成）──
    # 关键修复：将 render_progress()/render_logs() 放在 if 块之后，
    # 确保流水线执行完才渲染进度状态，避免显示执行前旧状态。
    pipeline_ran = False  # 标记本次是否执行了流水线
    if generate_btn and url.strip():
        processed = st.session_state.get("processed_url", "")
        if not processed:
            st.error("❌ 未在输入中找到有效的抖音链接，请粘贴包含 https://v.douyin.com/... 的分享内容")
        else:
            import sys as _sys
            _sys.stderr.write(f"[AIToutiao] 开始执行流水线: {processed}\n")
            _sys.stderr.flush()
            st.info("⏳ 流水线执行中，请稍候...（控制台可查看详细进度）")
            try:
                execute_pipeline(processed, style, humanize, with_images, content_type)
                pipeline_ran = True
                _sys.stderr.write("[AIToutiao] 流水线执行完成\n")
                _sys.stderr.flush()
            except Exception as _exc:
                _sys.stderr.write(f"[AIToutiao] Exception: {_exc}\n")
                _sys.stderr.flush()
                import traceback as _tb
                _tb.print_exc()
                add_log(f"流水线崩溃: {_exc}", "error")
                st.error(f"流水线执行失败: {_exc}")
            except BaseException as _exc:
                # SystemExit / KeyboardInterrupt 等致命异常
                _sys.stderr.write(f"[AIToutiao] 致命异常 ({type(_exc).__name__}): {_exc}\n")
                _sys.stderr.flush()
                import traceback as _tb
                _tb.print_exc()
                add_log(f"流水线致命错误({type(_exc).__name__}): {_exc}", "error")
                st.error(f"流水线致命错误({type(_exc).__name__}): {_exc}")
                # 不重新抛出，让 Streamlit 继续运行

    # ── UI 区域：进度 / 日志 / 结果 ──
    # 放在 if 之后，确保看到的是最新状态（无论是否刚执行完流水线）
    render_progress()
    render_logs()

    # 显示结果
    render_results()

    # 错误提示
    if st.session_state.get("pipeline_error"):
        st.error(f"流水线执行异常: {st.session_state.pipeline_error}")


if __name__ == "__main__":
    main()
