"""faster-whisper 转录速度测试"""
import time, sys, traceback

print("开始导入 faster_whisper...")
sys.stdout.flush()
try:
    from faster_whisper import WhisperModel
    print("导入成功")
    sys.stdout.flush()
except Exception as e:
    print(f"导入失败: {e}")
    traceback.print_exc()
    sys.exit(1)

audio = "outputs/20260709/20260709_150248/audio.wav"

print("加载 faster-whisper 模型 (small, cpu, int8)...")
sys.stdout.flush()

try:
    t0 = time.time()
    model = WhisperModel("small", device="cpu", compute_type="int8",
                         download_root=None, local_files_only=False)
    print(f"模型加载耗时: {time.time() - t0:.0f}s")
    sys.stdout.flush()
except Exception as e:
    print(f"模型加载失败: {e}")
    traceback.print_exc()
    sys.exit(1)

print("开始转录...")
sys.stdout.flush()
try:
    t1 = time.time()
    segments, info = model.transcribe(audio, language="zh", beam_size=5)
    print(f"检测语言: {info.language} (概率: {info.language_probability:.2f})")

    text_parts = []
    for seg in segments:
        text_parts.append(seg.text)

    text = "".join(text_parts)
    elapsed = time.time() - t1

    print(f"转录完成! 耗时: {elapsed:.0f}秒 ({elapsed / 60:.1f}分钟)")
    print(f"文本长度: {len(text)} 字符")
    print(f"文本预览: {text[:200]}...")
except Exception as e:
    print(f"转录失败: {e}")
    traceback.print_exc()
    sys.exit(1)
