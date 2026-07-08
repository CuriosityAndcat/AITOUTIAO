#!/usr/bin/env python3
"""
AIToutiao 端到端自动化流水线
==============================
串联 视频下载 → 语音转录 → AI改写 → 头条发布 全流程。

用法:
    python pipeline.py <URL或关键词>                     # 全流程（需先启动 toutiao-auto-publisher 服务）
    python pipeline.py <URL> --mode download             # 仅下载+转录
    python pipeline.py <URL> --mode write                # 下载+转录+AI改写
    python pipeline.py <URL> --mode full --content-type article  # 全流程，输出文章
    python pipeline.py --resume <run_id>                 # 断点续跑

环境要求:
    - toutiao-auto-publisher 服务运行中（localhost:8000），用于 AI 写作和发布
    - ffmpeg 可用（用于音频提取）
    - Node.js 可用（用于视频下载）
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# 加载根目录 .env 配置
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # python-dotenv 未安装时静默跳过

# 修复 Windows GBK 编码问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass  # 某些环境下 stdout 可能已被重定向

# ============================================================
# 配置
# ============================================================

PROJECT_ROOT = Path(__file__).parent
OUTPUTS_DIR = PROJECT_ROOT / os.getenv("PIPELINE_OUTPUT_DIR", "outputs")
VIDEO_DOWNLOAD_DIR = PROJECT_ROOT / os.getenv("VIDEO_DOWNLOAD_DIR", "video-batch-download-main")


def _normalize_whisper_model(model: str) -> str:
    """规范化 Whisper 模型名：去除 openai/whisper- 等前缀，faster-whisper 只需 short name。

    例: openai/whisper-small -> small, whisper-small -> small, small -> small
    """
    for prefix in ("openai/whisper-", "openai/", "whisper-"):
        if model.startswith(prefix):
            return model[len(prefix):]
    return model

# ── 强行预加载 backend/config 模块 ──
# 防止 from config import settings 错误解析到 wewrite-main/toolkit/config.py（YAML 配置加载器）
import importlib.util as _iu
_backend_cfg = PROJECT_ROOT / "toutiao-auto-publisher" / "backend" / "config.py"
_cfg_spec = _iu.spec_from_file_location("config", str(_backend_cfg))
_cfg_mod = _iu.module_from_spec(_cfg_spec)
sys.modules["config"] = _cfg_mod
_cfg_spec.loader.exec_module(_cfg_mod)
_ts = _cfg_mod.settings

# 尝试加载 toutiao-auto-publisher 的配置
try:
    # HOST=0.0.0.0 用于服务端绑定，客户端用 127.0.0.1（避免 IPv6 解析问题）
    _host = "127.0.0.1" if _ts.HOST in ("0.0.0.0", "::") else _ts.HOST
    PUBLISH_API_BASE = f"http://{_host}:{_ts.PORT}"
    WHISPER_MODEL = _normalize_whisper_model(_ts.WHISPER_MODEL)
    WHISPER_DEVICE = _ts.WHISPER_DEVICE
    WHISPER_COMPUTE_TYPE = _ts.WHISPER_COMPUTE_TYPE
    DEFAULT_CONTENT_TYPE = _ts.DEFAULT_CONTENT_TYPE
    DEFAULT_PUBLISH_MODE = _ts.DEFAULT_PUBLISH_MODE
    ENABLE_PUBLISH = _ts.ENABLE_PUBLISH
except Exception:
    WHISPER_MODEL = _normalize_whisper_model(os.getenv("WHISPER_MODEL", "small"))
    WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
    WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    DEFAULT_CONTENT_TYPE = os.getenv("DEFAULT_CONTENT_TYPE", "toutie")
    DEFAULT_PUBLISH_MODE = os.getenv("DEFAULT_PUBLISH_MODE", "publish")
    ENABLE_PUBLISH = os.getenv("ENABLE_PUBLISH", "true").lower() == "true"
    PUBLISH_API_BASE = os.getenv("PUBLISH_API_BASE_URL", "http://127.0.0.1:8000")


# ============================================================
# 枚举定义
# ============================================================

class PipelineMode(str, Enum):
    DOWNLOAD_ONLY = "download"   # 仅下载+转录
    WRITE_ONLY = "write"         # 下载+转录+AI改写
    FULL = "full"                # 全流程

class PipelineStage(str, Enum):
    DOWNLOAD = "download"
    TRANSCRIBE = "transcribe"
    WRITE = "write"
    GENERATE_IMAGES = "generate_images"
    PUBLISH = "publish"

    def next_stage(self) -> Optional["PipelineStage"]:
        order = list(PipelineStage)
        idx = order.index(self)
        return order[idx + 1] if idx + 1 < len(order) else None

    @classmethod
    def stages_for_mode(cls, mode: PipelineMode, with_images: bool = False) -> List["PipelineStage"]:
        if mode == PipelineMode.DOWNLOAD_ONLY:
            return [cls.DOWNLOAD, cls.TRANSCRIBE]
        elif mode == PipelineMode.WRITE_ONLY:
            stages = [cls.DOWNLOAD, cls.TRANSCRIBE, cls.WRITE]
            if with_images:
                stages.append(cls.GENERATE_IMAGES)
            return stages
        elif mode == PipelineMode.FULL:
            stages = [cls.DOWNLOAD, cls.TRANSCRIBE, cls.WRITE]
            if with_images:
                stages.append(cls.GENERATE_IMAGES)
            stages.append(cls.PUBLISH)
            return stages
        return []


# ============================================================
# 状态管理（断点续跑）
# ============================================================

class PipelineState:
    """流水线状态，支持序列化到 JSON 文件实现断点续跑"""

    def __init__(
        self,
        run_id: str = "",
        mode: PipelineMode = PipelineMode.FULL,
        input_url: str = "",
        content_type: str = "toutie",
        enable_humanize: bool = False,
        with_images: bool = False,
        completed_stages: Optional[List[str]] = None,
        outputs: Optional[Dict[str, Any]] = None,
        created_at: str = "",
        updated_at: str = "",
    ):
        self.run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.mode = mode
        self.input_url = input_url
        self.content_type = content_type
        self.enable_humanize = enable_humanize
        self.with_images = with_images
        self.completed_stages: List[str] = completed_stages or []
        self.outputs: Dict[str, Any] = outputs or {}
        self.created_at = created_at or datetime.now().isoformat()
        self.updated_at = updated_at or datetime.now().isoformat()

    @property
    def run_dir(self) -> Path:
        date_str = self.run_id[:8]
        return OUTPUTS_DIR / date_str / self.run_id

    @property
    def state_file(self) -> Path:
        return self.run_dir / "pipeline_state.json"

    def is_stage_done(self, stage: PipelineStage) -> bool:
        return stage.value in self.completed_stages

    def mark_done(self, stage: PipelineStage):
        if stage.value not in self.completed_stages:
            self.completed_stages.append(stage.value)
        self.updated_at = datetime.now().isoformat()

    def save(self):
        self.run_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "run_id": self.run_id,
            "mode": self.mode.value,
            "input_url": self.input_url,
            "content_type": self.content_type,
            "completed_stages": self.completed_stages,
            "outputs": self.outputs,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        self.state_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, run_id: str) -> "PipelineState":
        date_str = run_id[:8]
        state_file = OUTPUTS_DIR / date_str / run_id / "pipeline_state.json"
        if state_file.exists():
            data = json.loads(state_file.read_text(encoding="utf-8"))
            # 确保枚举类型正确
            if "mode" in data and isinstance(data["mode"], str):
                data["mode"] = PipelineMode(data["mode"])
            return cls(**data)
        raise FileNotFoundError(f"No state file found for run_id={run_id}")

    @classmethod
    def find_existing(cls, input_url: str) -> Optional["PipelineState"]:
        """查找相同 input_url 的已有运行"""
        if not OUTPUTS_DIR.exists():
            return None
        for date_dir in sorted(OUTPUTS_DIR.iterdir(), reverse=True):
            if not date_dir.is_dir():
                continue
            for run_dir in sorted(date_dir.iterdir(), reverse=True):
                state_file = run_dir / "pipeline_state.json"
                if state_file.exists():
                    try:
                        data = json.loads(state_file.read_text(encoding="utf-8"))
                        if data.get("input_url") == input_url:
                            if "mode" in data and isinstance(data["mode"], str):
                                data["mode"] = PipelineMode(data["mode"])
                            return cls(**data)
                    except Exception:
                        continue
        return None


# ============================================================
# 阶段执行器
# ============================================================

class StageRunner:
    """各阶段执行器的基类"""

    def __init__(self, state: PipelineState):
        self.state = state
        self.run_dir = state.run_dir

    def log(self, msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {msg}", flush=True)

    def run(self) -> bool:
        """返回 True 表示执行成功"""
        raise NotImplementedError


class DownloadStage(StageRunner):
    """视频下载阶段：调用 video-batch-download-main"""

    def run(self) -> bool:
        self.log(f"[1/4] 视频下载: {self.state.input_url}")

        script = VIDEO_DOWNLOAD_DIR / "scripts" / "download.mjs"
        if not script.exists():
            self.log(f"  ✗ 下载脚本不存在: {script}")
            return False

        self.run_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            "node", str(script),
            "--output", str(self.run_dir),
            "--no-transcribe",   # 分离下载和转录，方便调试
            self.state.input_url,
        ]

        self.log(f"  执行: node download.mjs --output {self.run_dir} ...")
        try:
            result = subprocess.run(
                cmd,
                cwd=str(VIDEO_DOWNLOAD_DIR),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=600,  # 10分钟超时
            )
            if result.returncode == 0:
                self.log("  ✓ 下载完成")
                # 查找下载的视频文件
                video_files = list(self.run_dir.glob("**/*.mp4"))
                self.state.outputs["video_files"] = [str(v) for v in video_files]
                self.log(f"  视频文件: {len(video_files)} 个")
                return True
            else:
                self.log(f"  ✗ 下载失败 (exit={result.returncode})")
                self.log(f"  stderr: {result.stderr[:500]}")
                return False
        except subprocess.TimeoutExpired:
            self.log("  ✗ 下载超时 (>10分钟)")
            return False
        except FileNotFoundError:
            self.log("  ✗ Node.js 不可用，请确保已安装 Node.js")
            return False


class TranscribeStage(StageRunner):
    """
    语音转录阶段。
    支持多种后端（环境变量 TRANSCRIBE_BACKEND）：
      - 'transformers':  使用 HuggingFace transformers pipeline（推荐，Windows 兼容）
      - 'whisper':       使用 openai-whisper（需本地模型）
      - 'node':          使用 download.mjs 内置转录
      - 'text':          从视频描述/已有文本兜底
      - 'skip':          跳过转录
    """

    BACKEND = os.getenv("TRANSCRIBE_BACKEND", "transformers")

    def run(self) -> bool:
        self.log(f"[2/4] 语音转录 (后端: {self.BACKEND})")

        if self.BACKEND == "skip":
            self.log("  → 跳过转录")
            return True

        # 查找视频文件
        video_files = self.state.outputs.get("video_files", [])
        if not video_files:
            # 搜索 .temp 目录
            temp_dir = self.run_dir / ".temp"
            video_files = [str(p) for p in temp_dir.glob("*.mp4")]

        if not video_files:
            self.log("  ✗ 没有找到视频文件")
            return False

        video_path = video_files[0]
        self.log(f"  视频: {Path(video_path).name}")

        if self.BACKEND == "text":
            return self._from_description(video_path)
        elif self.BACKEND == "node":
            return self._transcribe_via_node()
        else:
            return self._transcribe_via_python(video_path)

    def _transcribe_via_python(self, video_path: str) -> bool:
        """使用 transcribe.py（transformers/whisper 后端）转录"""
        transcribe_script = PROJECT_ROOT / "transcribe.py"
        transcript_file = self.run_dir / "transcript.txt"

        cmd = [
            sys.executable, str(transcribe_script),
            str(video_path),
            "--backend", self.BACKEND,
            "--model", WHISPER_MODEL,
            "--language", "zh",
            "--output", str(transcript_file),
        ]

        self.log(f"  模型: {WHISPER_MODEL}")

        try:
            result = subprocess.run(
                cmd,
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=1200,
            )
            if result.returncode == 0 and transcript_file.exists():
                text = transcript_file.read_text(encoding="utf-8").strip()
                self.log(f"  ✓ 转录完成 ({len(text)} 字符)")
                self.state.outputs["transcript_files"] = [str(transcript_file)]
                self.state.outputs["transcript_text"] = text
                return True
            else:
                self.log(f"  ✗ 转录失败 (exit={result.returncode})")
                if result.stderr:
                    self.log(f"  stderr: {result.stderr[-300:]}")
                # 降级到 text 后端
                self.log("  → 降级到 text 后端（使用视频描述）")
                return self._from_description(video_path)
        except subprocess.TimeoutExpired:
            self.log("  ✗ 转录超时")
            return self._from_description(video_path)
        except Exception as e:
            self.log(f"  ✗ 转录异常: {e}")
            return self._from_description(video_path)

    def _from_description(self, video_path: str) -> bool:
        """从视频 JSON 元数据中提取 description 作为转录文本"""
        video_dir = Path(video_path).parent.parent  # .temp -> run_dir
        for json_file in video_dir.glob("**/*.json"):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                desc = data.get("description", "")
                title = data.get("title", "").split("_")[0] if data.get("title") else ""
                if len(desc) > 30:
                    text = f"标题：{title}\n\n{desc}" if title else desc
                    transcript_file = self.run_dir / "transcript.txt"
                    transcript_file.write_text(text, encoding="utf-8")
                    self.log(f"  ✓ 从视频描述提取转录 ({len(text)} 字符)")
                    self.state.outputs["transcript_files"] = [str(transcript_file)]
                    self.state.outputs["transcript_text"] = text
                    return True
            except Exception:
                continue
        self.log("  ✗ 无法提取转录文本")
        return False

    def _transcribe_via_node(self) -> bool:
        """通过 download.mjs 内置功能完成转录（旧方案）"""
        script = VIDEO_DOWNLOAD_DIR / "scripts" / "download.mjs"
        if not script.exists():
            self.log(f"  ✗ 脚本不存在: {script}")
            return False

        cmd = [
            "node", str(script),
            "--output", str(self.run_dir),
            self.state.input_url,
        ]

        self.log(f"  执行 Node.js 转录...")
        try:
            result = subprocess.run(
                cmd,
                cwd=str(VIDEO_DOWNLOAD_DIR),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=1200,
            )
            if result.returncode == 0:
                transcript_files = list(self.run_dir.glob("**/*transcript*"))
                self.state.outputs["transcript_files"] = [str(t) for t in transcript_files]
                self.log(f"  ✓ 转录完成 ({len(transcript_files)} 个文件)")
                return True
            else:
                self.log(f"  ✗ 转录失败 (exit={result.returncode})")
                if result.stderr:
                    self.log(f"  stderr: {result.stderr[-500:]}")
                return False
        except subprocess.TimeoutExpired:
            self.log("  ✗ 转录超时")
            return False


class WriteStage(StageRunner):
    """AI 改写阶段：优先使用 Agent/Runner 编排，HTTP API 作为降级"""

    def run(self) -> bool:
        self.log(f"[3/4] AI 改写")

        # 1. 获取转录文本
        transcript = self._load_transcript()
        if not transcript:
            self.log("  ✗ 没有找到转录文本")
            return False

        self.log(f"  转录文本: {len(transcript)} 字符")

        content_type = self.state.content_type
        enable_humanize = self.state.enable_humanize

        # 2. 优先使用 Agent/Runner 编排
        self.log(f"  尝试 Agent 编排模式 (content_type={content_type})...")
        success = self._run_via_agent(transcript, content_type, enable_humanize)

        # 3. Agent 失败时降级到 HTTP API
        if not success:
            self.log("  Agent 模式不可用，降级到 HTTP API 模式...")
            success = self._run_via_api(transcript, content_type, enable_humanize)

        return success

    def _run_via_agent(
        self, transcript: str, content_type: str, enable_humanize: bool
    ) -> bool:
        """使用 Agent/Runner 编排生成内容"""
        try:
            from agent import Agent, Runner, RunConfig

            # 构造 Agent 指令
            if content_type == "toutie":
                agent_instructions = (
                    "你是一个专业的微头条内容创作者，擅长将原始素材改写成吸引人的微头条。\n"
                    "微头条要求：\n"
                    "- 字数控制在 200-500 字\n"
                    "- 开头用悬念、反问或金句吸引注意\n"
                    "- 观点鲜明，有个人态度\n"
                    "- 适当使用 emoji 增强可读性\n"
                    "- 符合头条平台调性，接地气但不低俗\n\n"
                    "请根据提供的转录文本，生成一篇高质量的微头条。\n"
                    "输出格式要求：返回一个 JSON 对象，包含 title 和 content 两个字段。\n"
                    '格式: {"title": "标题", "content": "正文内容"}'
                )
            else:
                agent_instructions = (
                    "你是一个专业的文章写作者，擅长将原始素材改写成深度文章。\n"
                    "文章要求：\n"
                    "- 结构完整：引言、正文（3-5个段落）、结论\n"
                    "- 逻辑清晰，论据充分\n"
                    "- 语言流畅，适合大众阅读\n"
                    "- 字数 800-2000 字\n\n"
                    "请根据提供的转录文本，生成一篇高质量的文章。\n"
                    "输出格式要求：返回一个 JSON 对象，包含 title 和 content 两个字段。\n"
                    '格式: {"title": "文章标题", "content": "文章正文（含段落分隔）"}'
                )

            # 构造任务描述
            task = f"请根据以下视频转录文本，生成一篇{content_type}：\n\n{transcript[:3000]}"

            # 创建 Agent 和配置
            agent = Agent(
                name="ContentWriter",
                instructions=agent_instructions,
                description=f"生成{content_type}内容的写作 Agent",
            )
            config = RunConfig(
                max_iterations=3,
                temperature=0.7,
                max_tokens=2000,
            )

            # 执行
            self.log("  执行 Agent 编排 (Search→Execute→Evaluate→Fix)...")
            result = Runner.run_sync(agent, task, config=config)

            if not result.is_success or not result.final_output:
                self.log(f"  Agent 执行未成功: status={result.status}")
                if result.error:
                    self.log(f"  错误: {result.error}")
                return False

            self.log(f"  Agent 执行完成: iterations={result.iterations}, status={result.status}")

            # 解析输出
            title, content = self._parse_agent_output(result.final_output)

            if not content:
                self.log("  ✗ Agent 输出解析失败")
                return False

            # 人工化改写
            humanized_content = None
            if enable_humanize:
                self.log("  🔄 人工化改写中（去 AI 味）...")
                try:
                    sys.path.insert(0, str(Path(__file__).parent / "toutiao-auto-publisher" / "backend"))
                    from ai_writer import AIWriter
                    hwriter = AIWriter()
                    hresult = hwriter.humanize(content)
                    humanized_content = hresult["content"]
                    self.log(f"  ✓ 人工化完成 ({hresult['char_count']} 字符)")
                except Exception as e:
                    self.log(f"  ⚠ 人工化失败（使用原文）: {e}")

            # 保存结果
            final_content = humanized_content or content
            self._save_output(title, final_content, content_type, humanized_content)
            return True

        except ImportError as e:
            self.log(f"  Agent 模块导入失败: {e}")
            return False
        except Exception as e:
            self.log(f"  Agent 模式异常: {e}")
            return False

    def _run_via_api(
        self, transcript: str, content_type: str, enable_humanize: bool
    ) -> bool:
        """降级模式：通过 HTTP API 调用生成（原有逻辑）"""
        import requests

        self.log(f"  调用 AI 生成 API (content_type={content_type})...")

        try:
            resp = requests.post(
                f"{PUBLISH_API_BASE}/api/generate",
                json={
                    "topic": transcript[:2000],
                    "content_type": content_type,
                    "content_style": "military",
                },
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("success"):
                title = data.get("title", "")
                content = data.get("content", "")
                char_count = data.get("char_count", 0)

                self.log(f"  ✓ AI 生成完成 ({char_count} 字符)")

                # 人工化改写
                humanized_content = None
                if enable_humanize:
                    self.log("  🔄 人工化改写中（去 AI 味）...")
                    try:
                        sys.path.insert(0, str(Path(__file__).parent / "toutiao-auto-publisher" / "backend"))
                        from ai_writer import AIWriter
                        hwriter = AIWriter()
                        hresult = hwriter.humanize(content)
                        humanized_content = hresult["content"]
                        self.log(f"  ✓ 人工化完成 ({hresult['char_count']} 字符)")
                    except Exception as e:
                        self.log(f"  ⚠ 人工化失败（使用原文）: {e}")

                final_content = humanized_content or content
                self._save_output(title, final_content, content_type, humanized_content)
                return True
            else:
                self.log(f"  ✗ AI 生成失败: {data.get('error', 'unknown')}")
                return False

        except requests.ConnectionError:
            self.log(f"  ✗ 无法连接 API 服务 ({PUBLISH_API_BASE})")
            self.log(f"  请先启动 toutiao-auto-publisher: cd toutiao-auto-publisher/backend && python main.py")
            return False
        except Exception as e:
            self.log(f"  ✗ API 调用异常: {e}")
            return False

    def _parse_agent_output(self, raw_output: str) -> tuple:
        """
        解析 Agent 输出的 JSON，提取 title 和 content。

        支持格式：
        - 纯 JSON: {"title": "...", "content": "..."}
        - JSON 包裹在代码块中: ```json ... ```
        - 无 title 时返回空 title + 全文作为 content
        """
        import json
        import re

        # 尝试提取 JSON 代码块
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw_output)
        if json_match:
            raw_output = json_match.group(1).strip()

        try:
            data = json.loads(raw_output)
            return data.get("title", ""), data.get("content", "")
        except json.JSONDecodeError:
            # 尝试从文本中提取 JSON 对象
            json_match = re.search(r"\{[\s\S]*\}", raw_output)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    return data.get("title", ""), data.get("content", "")
                except json.JSONDecodeError:
                    pass

        # 解析失败，全文作为 content
        return "", raw_output

    def _save_output(
        self, title: str, content: str, content_type: str,
        humanized_content: str | None = None,
    ):
        """保存生成内容到文件"""
        prefix = "微头条" if content_type == "toutie" else "文章"
        output_file = self.run_dir / f"{prefix}_{self.state.run_id}.md"
        output_file.write_text(
            f"# {title}\n\n{content}\n\n---\n*生成于 {datetime.now().isoformat()}*",
            encoding="utf-8",
        )

        # 同时保存原始 AI 版本
        if humanized_content:
            raw_file = self.run_dir / f"{prefix}_{self.state.run_id}_ai_raw.md"
            # 原始版本的 content 需要从 state 中还原
            original = self.state.outputs.get("_raw_ai_content", content)
            raw_file.write_text(
                f"# {title}\n\n{original}\n\n---\n*AI 原始生成，未经人工化处理*",
                encoding="utf-8",
            )

        self.state.outputs["generated_title"] = title
        self.state.outputs["generated_content"] = content
        self.state.outputs["generated_file"] = str(output_file)
        self.log(f"  输出: {output_file.name}")

    def _load_transcript(self) -> Optional[str]:
        """从已有的输出文件中加载转录文本"""
        # 1. 优先从 pipeline outputs 中找
        transcript_files = self.state.outputs.get("transcript_files", [])
        for tf in transcript_files:
            p = Path(tf)
            if p.exists():
                return p.read_text(encoding="utf-8")

        # 2. 从 run_dir 中搜索
        for pattern in ["**/*transcript*", "**/*.txt"]:
            for f in self.run_dir.glob(pattern):
                text = f.read_text(encoding="utf-8").strip()
                if len(text) > 50:  # 至少50字符的文本才有意义
                    self.state.outputs.setdefault("transcript_files", []).append(str(f))
                    return text

        return None


class PublishStage(StageRunner):
    """发布阶段：调用 toutiao-auto-publisher 的 /api/publish"""

    def run(self) -> bool:
        self.log(f"[4/4] 头条发布")

        if not ENABLE_PUBLISH:
            self.log("  → 跳过发布（ENABLE_PUBLISH=false）")
            return True

        title = self.state.outputs.get("generated_title", "")
        content = self.state.outputs.get("generated_content", "")

        if not title or not content:
            self.log("  ✗ 没有可发布的内容")
            return False

        self.log(f"  标题: {title[:40]}...")
        self.log(f"  内容: {len(content)} 字符")

        import requests

        try:
            resp = requests.post(
                f"{PUBLISH_API_BASE}/api/publish",
                json={
                    "title": title,
                    "content": content,
                    "auto_publish": DEFAULT_PUBLISH_MODE == "publish",
                    "content_type": self.state.content_type,
                },
                timeout=300,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("success"):
                task_id = data.get("task_id", "")
                self.log(f"  ✓ 发布任务提交成功 (task_id={task_id})")
                self.state.outputs["publish_task_id"] = task_id
                self._poll_publish_result(task_id)
                return True
            else:
                self.log(f"  ✗ 发布提交失败: {data.get('error', data.get('message', 'unknown'))}")
                return False

        except requests.ConnectionError:
            self.log(f"  ✗ 无法连接 API 服务 ({PUBLISH_API_BASE})")
            return False
        except Exception as e:
            self.log(f"  ✗ 发布异常: {e}")
            return False

    def _poll_publish_result(self, task_id: str, timeout: int = 120, interval: int = 5):
        """轮询发布任务状态"""
        import requests

        self.log(f"  等待发布结果 (task_id={task_id}, 最多 {timeout}s)...")
        start = time.time()
        while time.time() - start < timeout:
            try:
                resp = requests.get(f"{PUBLISH_API_BASE}/api/task/{task_id}", timeout=10)
                task = resp.json()
                status = task.get("status", "")
                message = task.get("message", "")

                if status == "success":
                    self.log(f"  ✓ 发布成功: {message}")
                    return
                elif status == "failed":
                    self.log(f"  ✗ 发布失败: {message}")
                    return
                else:
                    self.log(f"  ... {status}: {message}")
            except Exception as e:
                self.log(f"  ... 查询异常: {e}")

            time.sleep(interval)

        self.log("  ⚠ 发布超时，请手动检查状态")


class ImageGenStage(StageRunner):
    """
    配图生成阶段：基于已生成的文章内容，调用 AI 生成封面 + 内文配图。

    内部串联 CoverPromptBuilder → PromptSanitizer → ComplianceChecker → image_gen。
    所有 prompt 都会经过清洗和合规审查，确保：
      - 无中文标签文字被渲染到图上
      - 无 AI 水印
      - 无敏感违规内容
    """

    def run(self) -> bool:
        self.log(f"[图片] AI 配图生成（含审核+水印检测）")

        title = self.state.outputs.get("generated_title", "")
        content = self.state.outputs.get("generated_content", "")

        if not content:
            self.log("  ✗ 没有生成的文章内容，无法生成配图")
            return False

        # 提取标题（如果 AI 生成结果中没有单独标题，从内容第一行提取）
        if not title and content:
            first_line = content.split('\n')[0].strip()
            if len(first_line) < 50:
                title = first_line

        self.log(f"  标题: {title[:50]}...")
        self.log(f"  内容: {len(content)} 字符")

        # 图片输出目录
        images_dir = self.run_dir / "images"

        try:
            sys.path.insert(
                0,
                str(Path(__file__).parent / "toutiao-auto-publisher" / "backend"),
            )
            from ai_writer import AIWriter

            writer = AIWriter()

            # 使用 AIWriter 的新方法生成配图
            result = writer.generate_all_images(
                title=title,
                content=content,
                output_dir=str(images_dir),
                content_style="story_narrative",
                num_inline=3,
                prompt_lang="cn",  # 中文军事视觉隐喻风格（默认）
            )

            # ── 封面审核日志 ──
            cover = result.get("cover", {})
            cover_path = cover.get("path")
            expected_elements = cover.get("expected_elements", [])
            review_log = cover.get("review_log", [])
            retry_count = cover.get("retry_count", 0)

            if expected_elements:
                self.log(f"  🔍 封面审核：期望元素 {len(expected_elements)} 个 = {'、'.join(expected_elements)}")

            if cover_path:
                self.log(f"  ✓ 封面图: {Path(cover_path).name}")
                # 审核结果
                if review_log:
                    for entry in review_log:
                        status = "✅ 通过" if entry["passed"] else "❌ 不通过"
                        detail = f"(缺失: {', '.join(entry['missing'])})" if entry["missing"] else ""
                        self.log(f"    审核#{entry['attempt']}: {status} {detail}")
                if retry_count > 0:
                    self.log(f"    🔄 重试次数: {retry_count}")
                # 输出合规警告
                for w in cover.get("warnings", []):
                    self.log(f"    ⚠ {w}")
            else:
                cover_err = cover.get("error", "unknown")
                self.log(f"  ✗ 封面生成失败: {cover_err}")

            # 检查内文配图
            inline_results = result.get("inline", [])
            success_count = sum(1 for r in inline_results if r.get("path"))
            self.log(f"  ✓ 内文配图: {success_count}/{len(inline_results)} 张成功")
            for r in inline_results:
                if r.get("warnings"):
                    for w in r["warnings"]:
                        self.log(f"    ⚠ 配图{r['index']+1}: {w}")

            # 保存 prompt 记录 + 审核日志
            self._save_prompt_log(result)
            self._save_review_log(cover, self.run_dir)

            # 保存结果到 state
            self.state.outputs["cover_image"] = cover_path
            self.state.outputs["inline_images"] = [
                r.get("path") for r in inline_results if r.get("path")
            ]
            self.state.outputs["image_gen_prompts"] = {
                "cover": cover.get("prompt", ""),
                "inline": [r.get("prompt", "") for r in inline_results],
            }
            self.state.outputs["image_review"] = {
                "expected_elements": expected_elements,
                "review_log": review_log,
                "retry_count": retry_count,
            }

            # 回写图片引用到文章 markdown
            self._inject_images_into_article(cover_path, inline_results)

            return True

        except Exception as e:
            self.log(f"  ✗ 配图生成异常: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _save_prompt_log(self, result: dict):
        """保存 prompt 记录到 run 目录供调试"""
        cover = result.get("cover", {})
        log_lines = [
            "# 配图 Prompt 记录\n",
            f"## 封面\n```\n{cover.get('prompt', 'N/A')}\n```\n",
            f"视觉隐喻: {cover.get('visual_metaphor', 'N/A')}\n",
            f"风格: {cover.get('style', 'N/A')}\n",
            f"期望元素: {', '.join(cover.get('expected_elements', []))}\n\n",
            "## 内文配图\n",
        ]
        for r in result.get("inline", []):
            log_lines.append(
                f"### 配图 {r['index']+1}\n"
                f"叙事节点: {r.get('narrative_point', 'N/A')}\n"
                f"```\n{r.get('prompt', 'N/A')}\n```\n\n"
            )

        log_file = self.run_dir / "image_prompts_log.md"
        log_file.write_text("".join(log_lines), encoding="utf-8")
        self.log(f"  📄 Prompt 记录: {log_file.name}")

    def _save_review_log(self, cover: dict, run_dir: Path):
        """保存审核日志到独立文件"""
        expected_elements = cover.get("expected_elements", [])
        review_log = cover.get("review_log", [])
        retry_count = cover.get("retry_count", 0)
        cover_path = cover.get("path", "")

        if not review_log and not expected_elements:
            return

        lines = [
            "# 图片审核日志\n",
            f"## 封面\n",
            f"- 文件: {Path(cover_path).name if cover_path else 'N/A'}\n",
            f"- 期望元素 ({len(expected_elements)}): {'、'.join(expected_elements)}\n",
            f"- 重试次数: {retry_count}\n\n",
            "### 审核记录\n",
        ]

        for entry in review_log:
            status = "✅ 通过" if entry["passed"] else "❌ 不通过"
            lines.append(f"- **第{entry['attempt']}次**: {status}")
            if entry["missing"]:
                lines.append(f"  - 缺失: {', '.join(entry['missing'])}")
            if entry["suggestion"]:
                lines.append(f"  - 建议: {entry['suggestion']}")
            lines.append("")

        log_file = run_dir / "image_review_log.md"
        log_file.write_text("".join(lines), encoding="utf-8")
        self.log(f"  📄 审核日志: {log_file.name}")

    def _inject_images_into_article(self, cover_path: Optional[str], inline_results: list):
        """
        将生成的封面和内文配图引用回写到文章 markdown 文件中。

        封面插入文章开头（标题下方），内文配图按叙事节点插入对应段落之间。
        同时更新 state.outputs["generated_content"] 为含图版本。
        """
        generated_file = self.state.outputs.get("generated_file", "")
        if not generated_file:
            self.log("  ⚠ 没有找到文章文件，图片引用未回写")
            return

        article_path = Path(generated_file)
        if not article_path.exists():
            self.log(f"  ⚠ 文章文件不存在: {article_path}")
            return

        content = article_path.read_text(encoding="utf-8")

        # 1. 在标题后（第一个 # 标题行后）插入封面图
        if cover_path:
            cover_rel = f"images/{Path(cover_path).name}"
            cover_md = f"\n\n![封面]({cover_rel})\n\n> *AI 生成封面配图*\n"
            # 在第一个 # 标题行和其后的空行之间插入
            lines = content.split('\n')
            insert_idx = 0
            for i, line in enumerate(lines):
                if line.startswith('# '):
                    insert_idx = i + 1
                    # 跳过标题后的空行
                    while insert_idx < len(lines) and lines[insert_idx].strip() == '':
                        insert_idx += 1
                    break
            if insert_idx > 0:
                lines.insert(insert_idx, cover_md.strip())
                content = '\n'.join(lines)

        # 2. 按叙事节点位置插入内文配图
        # 策略：将文章按段落分割，在内文配图对应的叙事位置插入图片引用
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        inline_with_path = [r for r in inline_results if r.get("path")]

        if inline_with_path:
            # 计算插入位置：均匀分布在正文段落中（跳过标题段和封面段）
            body_start = 0
            for i, p in enumerate(paragraphs):
                if p.startswith('# ') or p.startswith('![') or p.startswith('> *'):
                    body_start = i + 1
                else:
                    break

            body_paragraphs = paragraphs[body_start:]
            num_body = len(body_paragraphs)
            num_images = len(inline_with_path)

            if num_body > 0 and num_images > 0:
                # 计算插入间距
                step = max(1, num_body // (num_images + 1))
                for img_idx, r in enumerate(inline_with_path):
                    img_rel = f"images/{Path(r['path']).name}"
                    insert_pos = body_start + step * (img_idx + 1)
                    if insert_pos < len(paragraphs):
                        img_md = (
                            f"\n\n> **📸 配图{img_idx + 1}**  \n> "
                            f"![配图{img_idx + 1}]({img_rel})\n"
                        )
                        paragraphs[insert_pos] = img_md.strip() + '\n\n' + paragraphs[insert_pos]

                content = '\n\n'.join(paragraphs)

        # 3. 写回文件
        article_path.write_text(content, encoding="utf-8")
        self.state.outputs["generated_content"] = content
        self.state.outputs["images_injected"] = True
        self.log(f"  📝 图片引用已回写到文章: {article_path.name}")


# ============================================================
# 流水线编排
# ============================================================

STAGE_RUNNERS = {
    PipelineStage.DOWNLOAD: DownloadStage,
    PipelineStage.TRANSCRIBE: TranscribeStage,
    PipelineStage.WRITE: WriteStage,
    PipelineStage.GENERATE_IMAGES: ImageGenStage,
    PipelineStage.PUBLISH: PublishStage,
}


def run_pipeline(
    url_or_keyword: str,
    mode: PipelineMode = PipelineMode.FULL,
    content_type: str = "toutie",
    resume_run_id: Optional[str] = None,
    enable_humanize: bool = False,
    with_images: bool = False,
) -> int:
    """主流水线入口"""

    print("=" * 60)
    print("AIToutiao 端到端自动化流水线")
    print("=" * 60)
    print(f"  输入: {url_or_keyword}")
    print(f"  模式: {mode.value}")
    print(f"  内容类型: {content_type}")
    print(f"  人工化: {'✅ 开启' if enable_humanize else '❌ 关闭'}")
    print(f"  AI配图: {'✅ 开启' if with_images else '❌ 关闭'}")
    print()

    # 1. 初始化/恢复状态
    if resume_run_id:
        try:
            state = PipelineState.load(resume_run_id)
            print(f"🔄 断点续跑: {resume_run_id}")
            print(f"   已完成阶段: {state.completed_stages}")
        except FileNotFoundError:
            print(f"✗ 找不到运行记录: {resume_run_id}")
            return 1
    else:
        # 检查是否有已有的运行
        existing = PipelineState.find_existing(url_or_keyword)
        if existing:
            done_stages = set(existing.completed_stages)
            needed_stages = PipelineStage.stages_for_mode(mode, with_images=with_images)
            all_needed = {s.value for s in needed_stages}
            if done_stages >= all_needed:
                print(f"✓ 此 URL 已有完整运行记录: {existing.run_id}")
                print(f"  输出目录: {existing.run_dir}")
                return 0
            elif done_stages:
                print(f"🔄 发现未完成的运行: {existing.run_id}")
                print(f"   已完成: {existing.completed_stages}")
                print(f"   仍需执行: {all_needed - done_stages}")
                # 更新 state 的 with_images 标志，确保后续阶段正确
                existing.with_images = with_images
                state = existing
            else:
                state = PipelineState(
                    input_url=url_or_keyword,
                    mode=mode,
                    content_type=content_type,
                    enable_humanize=enable_humanize,
                    with_images=with_images,
                )
        else:
            state = PipelineState(
                input_url=url_or_keyword,
                mode=mode,
                content_type=content_type,
                enable_humanize=enable_humanize,
                with_images=with_images,
            )

    print(f"📁 输出目录: {state.run_dir}")
    print(f"📋 运行 ID: {state.run_id}")
    print()

    # 2. 获取需要执行的阶段
    stages = PipelineStage.stages_for_mode(mode, with_images=with_images)

    # 3. 按顺序执行
    total = len(stages)
    failed = False
    for i, stage in enumerate(stages):
        if state.is_stage_done(stage):
            print(f"[{i+1}/{total}] ✓ {stage.value} (已完成，跳过)")
            continue

        runner_cls = STAGE_RUNNERS.get(stage)
        if runner_cls is None:
            print(f"  ⚠ 未知阶段: {stage.value}")
            continue

        runner = runner_cls(state)
        success = runner.run()

        if success:
            state.mark_done(stage)
            state.save()
        else:
            print(f"\n✗ 阶段 [{stage.value}] 执行失败，流水线中止")
            print(f"  已完成: {state.completed_stages}")
            print(f"  可稍后使用 --resume {state.run_id} 断点续跑")
            state.save()
            failed = True
            break

        print()

    # 4. 输出总结
    print("=" * 60)
    if not failed:
        print("✓ 流水线执行完成！")
    print(f"  运行 ID: {state.run_id}")
    print(f"  输出目录: {state.run_dir}")
    print(f"  完成阶段: {state.completed_stages}")
    print("=" * 60)

    return 1 if failed else 0


# ============================================================
# CLI 入口
# ============================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="AIToutiao 端到端自动化流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python pipeline.py "https://www.douyin.com/video/xxx"                    # 全流程（微头条）
  python pipeline.py "https://www.douyin.com/video/xxx" --mode download    # 仅下载+转录
  python pipeline.py "https://www.douyin.com/video/xxx" --content-type article  # 输出文章
  python pipeline.py --resume 20260704_143052                              # 断点续跑
        """,
    )
    parser.add_argument("input", nargs="?", help="视频 URL 或关键词")
    parser.add_argument(
        "--mode", choices=["download", "write", "full"], default="full",
        help="运行模式: download=下载+转录, write=下载+转录+AI改写, full=全流程 (默认: full)",
    )
    parser.add_argument(
        "--content-type", choices=["toutie", "article"], default="toutie",
        help="内容类型: toutie=微头条, article=文章 (默认: toutie)",
    )
    parser.add_argument("--resume", help="断点续跑的 run_id")
    parser.add_argument("--list", action="store_true", help="列出所有运行记录")
    parser.add_argument(
        "--humanize", action="store_true",
        help="启用人工化改写（去除 AI 味，输出更像真人的微头条）",
    )
    parser.add_argument(
        "--with-images", action="store_true",
        help="启用 AI 配图生成（封面 + 内文配图，需配置图片 API key）",
    )

    args = parser.parse_args()

    if args.list:
        list_runs()
        return 0

    if not args.input and not args.resume:
        parser.print_help()
        print("\n✗ 请提供视频 URL 或使用 --resume 续跑")
        return 1

    mode = PipelineMode(args.mode)

    return run_pipeline(
        url_or_keyword=args.input or "",
        mode=mode,
        content_type=args.content_type,
        resume_run_id=args.resume,
        enable_humanize=args.humanize,
        with_images=args.with_images,
    )


def list_runs():
    """列出所有运行记录"""
    if not OUTPUTS_DIR.exists():
        print("暂无运行记录")
        return

    runs = []
    for date_dir in sorted(OUTPUTS_DIR.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        for run_dir in sorted(date_dir.iterdir(), reverse=True):
            state_file = run_dir / "pipeline_state.json"
            if state_file.exists():
                try:
                    data = json.loads(state_file.read_text(encoding="utf-8"))
                    runs.append(data)
                except Exception:
                    pass

    if not runs:
        print("暂无运行记录")
        return

    print(f"{'Run ID':<20} {'日期':<12} {'模式':<12} {'阶段':<30} {'输入'}")
    print("-" * 100)
    for r in runs:
        completed = ",".join(r.get("completed_stages", []))
        print(f"{r['run_id']:<20} {r['run_id'][:8]:<12} {r['mode']:<12} {completed:<30} {r['input_url'][:40]}")


if __name__ == "__main__":
    sys.exit(main())
