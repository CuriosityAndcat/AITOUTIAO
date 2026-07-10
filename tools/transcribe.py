#!/usr/bin/env python3
"""
独立转录工具 — 多后端语音转文字

支持后端:
  - whisper       : openai-whisper (pip install openai-whisper)
  - faster-whisper: faster-whisper + ctranslate2 (pip install faster-whisper)
  - transformers  : HuggingFace transformers whisper (pip install transformers torch)
  - text          : 直接读取已有 .txt/.md 文件（无需 ASR）

用法:
  python transcribe.py <video_or_audio_path>                    # 自动检测后端
  python transcribe.py <path> --backend whisper --model tiny    # 指定后端和模型
  python transcribe.py <path> --backend text                    # 读取已有文本
  python transcribe.py <path> --output result.txt               # 输出到文件
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# 修复 Windows GBK 编码问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ============================================================
# 后端: text（读取已有文本文件）
# ============================================================

def transcribe_text(file_path: str) -> dict:
    """直接读取已有的转录文本文件"""
    p = Path(file_path)
    if p.suffix in (".txt", ".md"):
        text = p.read_text(encoding="utf-8").strip()
    else:
        # 如果是视频/音频文件，在同目录下找对应的文本文件
        candidates = list(p.parent.glob(f"{p.stem}*transcript*")) + \
                     list(p.parent.glob(f"{p.stem}*.txt")) + \
                     list(p.parent.glob(f"{p.stem}*.md"))
        text = ""
        for c in candidates:
            content = c.read_text(encoding="utf-8").strip()
            if len(content) > 50:
                text = content
                break

    if not text:
        return {"error": f"no text file found for {file_path}", "transcript": ""}

    return {
        "transcript": text,
        "segments": [],
        "meta": {"backend": "text", "model": "none"},
    }


# ============================================================
# 后端: whisper (openai-whisper)
# ============================================================

def transcribe_whisper(
    audio_path: str,
    model_name: str = "tiny",
    language: str = "zh",
) -> dict:
    """使用 openai-whisper 转录"""
    import whisper

    model = whisper.load_model(model_name)
    result = model.transcribe(audio_path, language=language)

    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "start": round(seg["start"], 3),
            "end": round(seg["end"], 3),
            "text": seg["text"].strip(),
        })

    return {
        "transcript": result["text"],
        "segments": segments,
        "meta": {
            "backend": "whisper",
            "model": model_name,
            "language": result.get("language", language),
        },
    }


# ============================================================
# 后端: faster-whisper (ctranslate2)
# ============================================================

def transcribe_faster_whisper(
    audio_path: str,
    model_name: str = "small",
    language: str = "zh",
    device: str = "cpu",
    compute_type: str = "int8",
) -> dict:
    """使用 faster-whisper 转录"""
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    seg_iter, info = model.transcribe(audio_path, language=language, beam_size=5)

    segments = []
    for s in seg_iter:
        text = s.text.strip()
        if text:
            segments.append({
                "start": round(float(s.start), 3),
                "end": round(float(s.end), 3),
                "text": text,
            })

    transcript = "\n".join(s["text"] for s in segments)

    return {
        "transcript": transcript,
        "segments": segments,
        "meta": {
            "backend": "faster-whisper",
            "model": model_name,
            "language": getattr(info, "language", language),
        },
    }


# ============================================================
# 后端: transformers pipeline（推荐，Windows 兼容）
# ============================================================

def _clean_transcript(text: str) -> tuple:
    """
    清洗转录文本：检测并移除重复循环/幻觉输出。

    whisper-tiny 在长音频上容易产生重复循环（如 "各种各种各种..."），
    此函数检测并截断，返回 (cleaned_text, warning_msg)。

    Returns:
        (cleaned_text, warning) — warning 为空字符串表示无问题
    """
    import re

    warning = ""

    # 1. 检测连续重复词/字 > 5 次（经典 whisper 幻觉）
    #    匹配中文单字或双字词在连续出现时的循环
    pattern = re.compile(r'(.{1,4}?)\1{5,}')
    matches = list(pattern.finditer(text))
    if matches:
        first_loop_start = matches[0].start()
        # 从第一个循环前截断
        text = text[:first_loop_start].rstrip()
        warning = f"检测到重复循环，已截断（从位置 {first_loop_start}）"
        print(f"[clean] {warning}")

    # 2. 去除末尾不完整的半句（以逗号/句号/问号/感叹号结尾为正常）
    if text and not text[-1] in '。！？，、.!?,，':
        # 找到最后一个完整句子结尾
        last_period = max(
            text.rfind('。'),
            text.rfind('！'),
            text.rfind('？'),
        )
        if last_period > len(text) * 0.6:  # 至少保留 60% 的内容
            text = text[:last_period + 1]
            warning = warning + "；已截断尾部不完整句子"

    return text.strip(), warning


def transcribe_transformers(
    audio_path: str,
    model_name: str = "openai/whisper-tiny",
    language: str = "zh",
) -> dict:
    """使用 HuggingFace transformers pipeline 转录，支持 hf-mirror.com 国内镜像"""
    import torch

    # 设置 HF 镜像（国内加速）
    if "HF_ENDPOINT" not in os.environ:
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

    from transformers import pipeline

    pipe = pipeline(
        "automatic-speech-recognition",
        model=model_name,
        chunk_length_s=30,
        device="cpu",
        torch_dtype=torch.float32,
    )
    result = pipe(
        audio_path,
        generate_kwargs={"language": language, "task": "transcribe"},
    )
    text = result["text"].strip()

    # 繁体→简体转换
    try:
        import opencc
        cc = opencc.OpenCC("t2s")
        text = cc.convert(text)
    except ImportError:
        pass

    # 清洗重复循环/幻觉输出
    text, warning = _clean_transcript(text)

    return {
        "transcript": text,
        "segments": [],
        "meta": {
            "backend": "transformers",
            "model": model_name,
            "language": language,
            "warning": warning,
        },
    }


# ============================================================
# 音频提取（从视频中提取 WAV）
# ============================================================

def extract_audio(video_path: str, output_path: Optional[str] = None) -> str:
    """使用 ffmpeg 从视频中提取 16kHz 单声道 WAV 音频"""
    if output_path is None:
        output_path = str(Path(video_path).with_suffix(".wav"))

    if Path(output_path).exists():
        return output_path

    cmd = [
        "ffmpeg", "-i", video_path,
        "-ar", "16000", "-ac", "1",
        "-f", "wav", output_path,
        "-y", "-loglevel", "error",
    ]
    subprocess.run(cmd, check=True, timeout=300)
    return output_path


# ============================================================
# 后端自动检测和调度
# ============================================================

def _is_audio_file(path: str) -> bool:
    return Path(path).suffix.lower() in (".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg")


def _is_video_file(path: str) -> bool:
    return Path(path).suffix.lower() in (".mp4", ".avi", ".mkv", ".mov", ".webm", ".flv")


def transcribe(
    file_path: str,
    backend: str = "auto",
    model: str = "tiny",
    language: str = "zh",
) -> dict:
    """
    智能转录：自动检测文件类型和后端可用性

    Args:
        file_path: 视频/音频文件路径，或文本文件路径（backend=text 时）
        backend: 后端名称 (auto/whisper/faster-whisper/transformers/text)
        model: 模型名称
        language: 语言代码

    Returns:
        {"transcript": str, "segments": list, "meta": dict}
    """
    p = Path(file_path)
    if not p.exists():
        return {"error": f"文件不存在: {file_path}", "transcript": ""}

    # 如果是文本文件，直接用 text 后端
    if p.suffix in (".txt", ".md"):
        backend = "text"

    # 自动检测可用后端
    if backend == "auto":
        backends = _detect_backends()
        if not backends:
            return {"error": "没有可用的转录后端，请安装 whisper/faster-whisper/transformers", "transcript": ""}
        backend = backends[0]
        print(f"[auto] 使用后端: {backend}")

    # transformers 后端：短名映射到完整 HF 模型 ID
    TRANSFORMER_MODELS = {
        "tiny": "openai/whisper-tiny",
        "small": "openai/whisper-small",
        "base": "openai/whisper-base",
        "medium": "openai/whisper-medium",
        "large": "openai/whisper-large-v3",
        "large-v3": "openai/whisper-large-v3",
    }
    if backend == "transformers" and model in TRANSFORMER_MODELS:
        model = TRANSFORMER_MODELS[model]

    # 如果是视频文件，先提取音频
    audio_path = file_path
    if _is_video_file(file_path):
        print(f"[ffmpeg] 从视频中提取音频...")
        try:
            audio_path = extract_audio(file_path)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            return {"error": f"音频提取失败: {e} (需要 ffmpeg)", "transcript": ""}

    # 调用对应后端
    t0 = time.time()

    if backend == "text":
        result = transcribe_text(file_path)
    elif backend == "whisper":
        result = transcribe_whisper(audio_path, model, language)
    elif backend == "faster-whisper":
        result = transcribe_faster_whisper(audio_path, model, language)
    elif backend == "transformers":
        result = transcribe_transformers(audio_path, model, language)
    else:
        return {"error": f"未知后端: {backend}", "transcript": ""}

    if "meta" in result:
        result["meta"]["elapsed_seconds"] = round(time.time() - t0, 1)

    return result


def _detect_backends() -> list:
    """检测可用的转录后端，按优先级排序（transformers 最优先）"""
    available = []

    # 检查 transformers（优先，Windows 兼容最好）
    try:
        import transformers  # noqa
        available.append("transformers")
    except ImportError:
        pass

    # 检查 openai-whisper
    try:
        import whisper  # noqa
        available.append("whisper")
    except ImportError:
        pass

    # 检查 faster-whisper（Windows 上 ctranslate2 可能卡死）
    try:
        import faster_whisper  # noqa
        available.append("faster-whisper")
    except ImportError:
        pass

    return available


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="多后端语音转文字工具")
    parser.add_argument("input", help="视频/音频文件路径或文本文件路径")
    parser.add_argument("--backend", default="auto",
                        choices=["auto", "whisper", "faster-whisper", "transformers", "text"],
                        help="转录后端 (默认: auto)")
    parser.add_argument("--model", default="tiny", help="模型名称 (默认: tiny)")
    parser.add_argument("--language", default="zh", help="语言代码 (默认: zh)")
    parser.add_argument("--output", "-o", help="输出文件路径 (默认: stdout)")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")

    args = parser.parse_args()

    print(f"转录: {args.input}")
    print(f"后端: {args.backend}, 模型: {args.model}")
    print()

    result = transcribe(
        file_path=args.input,
        backend=args.backend,
        model=args.model,
        language=args.language,
    )

    if "error" in result:
        print(f"✗ {result['error']}")
        sys.exit(1)

    transcript = result["transcript"]
    print(f"✓ 转录完成 ({len(transcript)} 字符, {result['meta'].get('elapsed_seconds', 0)}s)")
    print(f"  后端: {result['meta'].get('backend')}, 模型: {result['meta'].get('model')}")
    print(f"  语言: {result['meta'].get('language')}")
    print()

    if args.json:
        output = json.dumps(result, ensure_ascii=False, indent=2)
    else:
        output = transcript

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"结果已保存到: {args.output}")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
