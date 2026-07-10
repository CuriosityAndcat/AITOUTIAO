"""手动测试 Whisper 转录耗时"""
import time
from transformers import pipeline
import torch

audio = "outputs/20260709/20260709_150248/audio.wav"

print("加载模型（仅本地缓存）...")
t0 = time.time()

pipe = pipeline(
    "automatic-speech-recognition",
    model="openai/whisper-small",
    device="cpu",
    torch_dtype=torch.float32,
    local_files_only=True,
)
print(f"模型加载耗时: {time.time() - t0:.0f}s")

print("开始转录...")
t1 = time.time()
result = pipe(
    audio,
    return_timestamps=True,
    generate_kwargs={"language": "zh", "task": "transcribe"},
)
elapsed = time.time() - t1

text = result["text"].strip()
print(f"转录完成! 耗时: {elapsed:.0f}秒 ({elapsed / 60:.1f}分钟)")
print(f"文本长度: {len(text)} 字符")
print(f"文本预览: {text[:200]}...")
