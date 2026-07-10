"""
SenseVoice 语音转录命令行工具
用法: python transcribe.py <音频文件> [--language zh] [--output output.txt]
"""

import os
import sys
import time
import argparse
from pathlib import Path

# Windows OpenMP 保护（必须放在 import torch/funasr 之前）
if sys.platform == "win32":
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess


# 模型路径（相对于脚本所在目录）
MODEL_DIR = Path(__file__).parent / "models" / "iic" / "SenseVoiceSmall"


def load_model(device="cpu"):
    """加载 SenseVoiceSmall 模型"""
    if not (MODEL_DIR / "model.pt").exists():
        raise FileNotFoundError(
            f"模型未找到: {MODEL_DIR}\n"
            f"请先下载模型到 models/iic/SenseVoiceSmall/"
        )

    print(f"[1/3] 加载模型: {MODEL_DIR}", flush=True)
    t0 = time.time()

    model = AutoModel(
        model=str(MODEL_DIR),
        device=device,
        disable_update=True,
        disable_log=True,
        check_latest=False,
    )

    print(f"[1/3] 加载完成 ({time.time() - t0:.1f}s)", flush=True)
    return model


def transcribe(model, audio_path, language="zh", use_postprocess=True):
    """转录单个音频文件，返回文本"""
    print(f"[2/3] 转录: {audio_path}", flush=True)

    if not Path(audio_path).exists():
        raise FileNotFoundError(f"音频文件不存在: {audio_path}")

    t0 = time.time()
    result = model.generate(
        input=audio_path,
        language=language,
        ban_emo_unk=True,
        use_itn=True,
        batch_size_s=60,
    )
    print(f"[2/3] 转录完成 ({time.time() - t0:.1f}s)", flush=True)

    text = result[0].get("text", "") if result else ""
    if isinstance(text, list):
        text = " ".join(str(t) for t in text)
    text = text.strip()

    if use_postprocess:
        try:
            text = rich_transcription_postprocess(text)
        except Exception:
            pass

    return text


def main():
    parser = argparse.ArgumentParser(description="SenseVoice 语音转录工具")
    parser.add_argument("audio", help="音频文件路径")
    parser.add_argument(
        "--language", "-l", default="zh",
        help="语言代码: zh/en/ja/ko/yue/auto (默认: zh)"
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help="输出文件路径 (默认: 打印到控制台)"
    )
    parser.add_argument(
        "--no-postprocess", action="store_true",
        help="跳过后处理（保留原始标签）"
    )
    args = parser.parse_args()

    model = load_model()
    text = transcribe(model, args.audio, args.language, not args.no_postprocess)

    print(f"[3/3] {len(text)} 字符")
    print("=" * 60)
    print(text[:800])
    if len(text) > 800:
        print("...")
    print("=" * 60)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"已保存到: {os.path.abspath(args.output)}")


if __name__ == "__main__":
    main()
