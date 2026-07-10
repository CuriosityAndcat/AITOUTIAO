"""
用 modelscope snapshot_download 强制注册本地模型，然后加载
"""
import os, sys, time
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

CACHE_DIR = os.path.abspath("./models_cache")
MODEL_ID = "iic/SenseVoiceSmall"
MODEL_DIR = os.path.join(CACHE_DIR, MODEL_ID.replace("/", os.sep))

print(f"模型目录: {MODEL_DIR}", flush=True)
print(f"model.pt 存在: {os.path.exists(os.path.join(MODEL_DIR, 'model.pt'))}", flush=True)

# Step 1: 用 snapshot_download 注册本地缓存
print("\n[1] 注册模型到 modelscope 缓存...", flush=True)
from modelscope.hub.snapshot_download import snapshot_download

t0 = time.time()
try:
    local_path = snapshot_download(
        MODEL_ID,
        cache_dir=CACHE_DIR,
        local_files_only=True,
    )
    print(f"   本地模型路径: {local_path}", flush=True)
except Exception as e:
    print(f"   注册失败: {e}", flush=True)
    print("   尝试使用已存在的本地文件...", flush=True)
    local_path = MODEL_DIR

print(f"   耗时: {time.time()-t0:.1f}s", flush=True)

# Step 2: 加载模型
print("\n[2] 加载 AutoModel...", flush=True)
t1 = time.time()

from funasr import AutoModel
model = AutoModel(
    model=MODEL_ID,
    device="cpu",
    disable_pbar=True,
    disable_update=True,
    disable_log=True,
)
print(f"   模型加载完成! 耗时: {time.time()-t1:.1f}s", flush=True)

# Step 3: 转录
AUDIO = r"d:\AIToutiao\engine_mode\outputs\20260709\20260709_150248\audio.wav"
print(f"\n[3] 转录音频...", flush=True)
t2 = time.time()
result = model.generate(input=AUDIO, language="zh", ban_emo_unk=True, use_itn=True)
trans_time = time.time() - t2

text = result[0].get("text", "")
print(f"   转录耗时: {trans_time:.1f}s", flush=True)
print(f"   文本长度: {len(text)} 字符", flush=True)
print(f"\n--- 结果 ---\n{text[:300]}", flush=True)

# 保存
output_file = AUDIO.replace('.wav', '_sensevoice.txt')
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(text)
print(f"\n结果已保存: {output_file}", flush=True)
print(f"\n总计: 注册{time.time()-t0:.1f}s + 加载{t2-t1:.1f}s + 转录{trans_time:.1f}s", flush=True)
