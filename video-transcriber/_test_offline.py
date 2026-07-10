"""
SenseVoice 转录 - 强制离线模式（monkey-patch snapshot_download）
"""
import os, sys, time
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

AUDIO = r"d:\AIToutiao\engine_mode\outputs\20260709\20260709_150248\audio.wav"
RESULT_FILE = AUDIO.replace('.wav', '_sensevoice.txt')

print("=== SenseVoice 转录 (离线模式) ===", flush=True)

# Step 0: Monkey-patch modelscope.snapshot_download 强制离线
from modelscope.hub import snapshot_download as _orig_snapshot
import functools

@functools.wraps(_orig_snapshot)
def _patched_snapshot(model_id, revision='master', cache_dir=None, 
                       local_files_only=False, **kwargs):
    return _orig_snapshot(
        model_id, revision=revision, cache_dir=cache_dir,
        local_files_only=True,  # 强制离线
        **kwargs
    )

import modelscope.hub.snapshot_download
modelscope.hub.snapshot_download.snapshot_download = _patched_snapshot

# Also patch the hub module
import modelscope.hub.api
if hasattr(modelscope.hub.api, 'snapshot_download'):
    modelscope.hub.api.snapshot_download = _patched_snapshot

print("已启用强制离线模式", flush=True)

# Step 1: 加载模型
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

# Step 2: 转录
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
total_t = time.time() - t1 - load_t + load_t  # total from start

# 保存
with open(RESULT_FILE, 'w', encoding='utf-8') as f:
    f.write(text)

print(f"\n{'='*50}")
print(f"DONE! 加载={load_t:.1f}s 转录={trans_t:.1f}s 总计={load_t+trans_t:.1f}s")
print(f"文本: {len(text)} 字符 | 前200字: {text[:200]}")
print(f"结果: {RESULT_FILE}")
print(f"{'='*50}")
