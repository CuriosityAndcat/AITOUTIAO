"""
SenseVoice 本地离线转录脚本（修正版）
========================================
基于 FunAudioLLM/SenseVoice 官方仓库 (github.com/FunAudioLLM/SenseVoice)

解决 AutoModel("iic/SenseVoiceSmall") 联网卡死问题：
  - 传入本地绝对路径而非 ModelScope ID  ← 官方 README 确认可行
  - 设置 MODELSCOPE_DISABLE_REMOTE=1 强制离线
  - 启用 batch_size_s 动态批处理加速

使用方法：
  python _transcribe_local.py                          # 默认测试音频
  python _transcribe_local.py <音频文件路径>            # 指定音频
  python _transcribe_local.py --device cuda             # GPU 加速
  python _transcribe_local.py --vad                     # 长音频 VAD 分割
  python _transcribe_local.py --language auto           # 自动语言检测
"""

import os
import sys
import time
import argparse
from pathlib import Path

# ── Windows GBK 编码修复 ──
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── 环境配置 ──
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "4")

# ── 项目路径 ──
PROJECT_DIR = Path(__file__).parent
MODELS_CACHE = PROJECT_DIR / "models_cache"
MODEL_DIR = MODELS_CACHE / "iic" / "SenseVoiceSmall"

# 默认音频文件
DEFAULT_AUDIO = r"D:\AIToutiao\engine_mode\outputs\20260709\20260709_150248\audio.wav"

# SenseVoice 支持的语言列表（官方 README）
SUPPORTED_LANGUAGES = ["zh", "en", "yue", "ja", "ko", "nospeech", "auto"]


def check_model_files(model_dir: Path) -> dict:
    """检查模型文件完整性"""
    required = ["model.pt", "config.yaml", "configuration.json", "tokens.json",
                "am.mvn", "chn_jpn_yue_eng_ko_spectok.bpe.model"]
    status = {}
    for f in required:
        fp = model_dir / f
        exists = fp.exists()
        size = fp.stat().st_size if exists else 0
        status[f] = {"exists": exists, "size_mb": round(size / 1024 / 1024, 2)}
    return status


def main():
    parser = argparse.ArgumentParser(description="SenseVoice 本地离线转录")
    parser.add_argument("audio", nargs="?", default=DEFAULT_AUDIO,
                        help="音频文件路径（默认使用测试音频）")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"],
                        help="推理设备 (default: cpu)")
    parser.add_argument("--language", default="zh",
                        help=f"语言代码: {', '.join(SUPPORTED_LANGUAGES)} (default: zh)")
    parser.add_argument("--vad", action="store_true",
                        help="启用 VAD 分割（适合长音频，>30s 推荐）")
    parser.add_argument("--batch-size", type=int, default=60,
                        help="动态批处理大小（秒），越大越快但吃更多内存 (default: 60)")
    parser.add_argument("--output", default=None,
                        help="输出文件路径（默认与音频同目录、同前缀）")
    args = parser.parse_args()

    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(f"[错误] 音频文件不存在: {audio_path}")
        sys.exit(1)

    print("=" * 60)
    print("  SenseVoice 本地离线转录")
    print("=" * 60)
    print(f"  模型目录: {MODEL_DIR}")
    print(f"  音频文件: {audio_path}")
    print(f"  音频大小: {audio_path.stat().st_size / 1024 / 1024:.1f} MB")
    v = "[VAD]" if args.vad else "[No VAD]"
    print(f"  推理设备: {args.device}  {v}")
    print(f"  语言设置: {args.language}")
    print(f"  批处理大小: {args.batch_size}s")
    print()

    # ── Step 1: 验证模型文件 ──
    print("[Step 1/4] 检查模型文件...")
    file_status = check_model_files(MODEL_DIR)
    all_ok = True
    for fname, info in file_status.items():
        flag = "✓" if info["exists"] else "✗"
        size_str = f"{info['size_mb']} MB" if info["exists"] else "缺失"
        print(f"  {flag} {fname:45s} {size_str}")
        if not info["exists"]:
            all_ok = False

    if not all_ok:
        print("\n[错误] 模型文件不完整，请先运行:")
        print(f"  cd {PROJECT_DIR}")
        print(f"  python webmain.py download-model sensevoice-small")
        sys.exit(1)
    print("  模型文件完整 ✓\n")

    # ── Step 2: 设置离线环境 ──
    print("[Step 2/4] 配置离线模式...")
    os.environ['MODELSCOPE_CACHE'] = str(MODELS_CACHE)
    os.environ['MODELSCOPE_DISABLE_REMOTE'] = '1'
    print(f"  MODELSCOPE_CACHE={MODELS_CACHE}")
    print(f"  MODELSCOPE_DISABLE_REMOTE=1\n")

    # ── Step 3: 加载模型 ──
    print("[Step 3/4] 加载 SenseVoice 模型...")
    print("  (893MB 模型加载需要 60-90 秒，请耐心等待)")
    t_load_start = time.time()

    from funasr import AutoModel

    # 基础参数（参考官方 README）
    model_kwargs = dict(
        model=str(MODEL_DIR),           # ← 本地绝对路径，不是 "iic/SenseVoiceSmall"
        device=args.device,
        disable_pbar=True,
        disable_update=True,
        disable_log=True,
    )

    # VAD 模式：启用语音活动检测 + 自动分段（适合长音频）
    if args.vad:
        model_kwargs.update(dict(
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 30000},
            merge_vad=True,
            merge_length_s=15,
        ))
        print("  VAD 模式已启用 (fsmn-vad, max_segment=30s)")

    model = AutoModel(**model_kwargs)

    t_load = time.time() - t_load_start
    print(f"  加载完成! 耗时 {t_load:.1f}s\n")

    # ── Step 4: 转录 ──
    print("[Step 4/4] 转录音频...")
    t_trans_start = time.time()

    result = model.generate(
        input=str(audio_path),
        language=args.language,
        ban_emo_unk=True,
        use_itn=True,
        batch_size_s=args.batch_size,       # ← 动态批处理，参考官方 README
    )

    t_trans = time.time() - t_trans_start

    # ── 提取文本 ──
    text = result[0].get("text", "") if result else ""
    if isinstance(text, list):
        text = " ".join(str(t) for t in text)

    text_chars = len(text)

    # ── 保存结果 ──
    output_path = Path(args.output) if args.output else audio_path.with_suffix("").with_name(audio_path.stem + "_sensevoice.txt")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")

    # ── 输出摘要 ──
    print(f"  转录完成! 耗时 {t_trans:.1f}s\n")
    print("=" * 60)
    print(f"  模型加载:         {t_load:.1f}s")
    print(f"  转录耗时:         {t_trans:.1f}s")
    print(f"  总耗时:           {t_load + t_trans:.1f}s")
    print(f"  文本长度:         {text_chars} 字符")
    print(f"  音频时长估算:     {t_trans / 0.05:.1f}s  ← 仅供参考")
    print(f"  实时率 (RTF):     {t_trans / max(t_trans / 0.05, 1):.3f}")
    print(f"  结果文件:         {output_path}")
    print(f"  前 150 字预览:")
    print(f"    {text[:150]}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
