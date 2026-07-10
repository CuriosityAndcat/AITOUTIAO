"""
仅测试 SenseVoice 模型加载（不转录）
"""
import os, sys, time

os.environ['MODELSCOPE_CACHE'] = os.path.abspath('./models_cache')
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

print("测试模型加载...", flush=True)
print(f"MODELSCOPE_CACHE={os.environ['MODELSCOPE_CACHE']}", flush=True)

# 确认模型文件存在
model_pt = "./models_cache/iic/SenseVoiceSmall/model.pt"
print(f"模型文件: {model_pt} ({os.path.getsize(model_pt)/1024/1024:.0f} MB)", flush=True)

print("导入 funasr...", flush=True)
t0 = time.time()

from funasr import AutoModel
print(f"导入耗时: {time.time()-t0:.1f}s", flush=True)

print("开始加载模型 (CPU, 约需30-90秒)...", flush=True)
t1 = time.time()

model = AutoModel(
    model="iic/SenseVoiceSmall",
    device="cpu",
    disable_pbar=True,
    disable_update=True,
    disable_log=True,
)

print(f"模型加载完成! 耗时: {time.time()-t1:.1f}s", flush=True)
print(f"总耗时: {time.time()-t0:.1f}s", flush=True)
print("SUCCESS", flush=True)
