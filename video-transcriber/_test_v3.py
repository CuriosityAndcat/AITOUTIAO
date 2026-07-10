"""
SenseVoice 最小转录测试 - 使用默认 modelscope 缓存目录
"""
import os, sys, time
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

AUDIO = r"d:\AIToutiao\engine_mode\outputs\20260709\20260709_150248\audio.wav"
RESULT_FILE = AUDIO.replace('.wav', '_sensevoice.txt')

t_total = time.time()

print("=== SenseVoice 转录测试 ===", flush=True)

# 确认模型在默认缓存
cache = os.path.expanduser("~/.cache/modelscope/hub/models/iic/SenseVoiceSmall")
print(f"缓存检查: {cache}")
print(f"model.pt: {os.path.exists(os.path.join(cache, 'model.pt'))}", flush=True)

# 加载模型
print("\n[1/2] 加载模型...", flush=True)
t1 = time.time()
from funasr import AutoModel
model = AutoModel(
    model="iic/SenseVoiceSmall",
    device="cpu",
    disable_pbar=True,
    disable_update=True,
    disable_log=True,
)
load_t = time.time() - t1
print(f"     完成! {load_t:.1f}s", flush=True)

# 转录
print("\n[2/2] 转录音频...", flush=True)
t2 = time.time()
result = model.generate(
    input=AUDIO,
    language="zh",
    ban_emo_unk=True,
    use_itn=True,
)
trans_t = time.time() - t2

text = result[0].get("text", "")
text_len = len(text)

# 保存
with open(RESULT_FILE, 'w', encoding='utf-8') as f:
    f.write(text)

total_t = time.time() - t_total

print(f"\n{'='*50}")
print(f"转录完成!")
print(f"  模型加载: {load_t:.1f}s")
print(f"  转录耗时: {trans_t:.1f}s")
print(f"  总耗时:   {total_t:.1f}s")
print(f"  文本长度: {text_len} 字符")
print(f"  前200字: {text[:200]}")
print(f"  结果文件: {RESULT_FILE}")
print(f"{'='*50}")
