"""
最小化 SenseVoice 转录测试
直接使用 funasr AutoModel 从本地缓存加载，避免 CLI 开销
"""
import os
import sys
import time

# 设置环境变量
os.environ['MODELSCOPE_CACHE'] = os.path.abspath('./models_cache')
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# 确保模型已经下载到本地
MODEL_DIR = os.path.join(os.path.abspath('./models_cache'), 'iic', 'SenseVoiceSmall')
if not os.path.exists(os.path.join(MODEL_DIR, 'model.pt')):
    print(f"错误: 模型文件不存在: {MODEL_DIR}")
    print("请先运行: python webmain.py download-model sensevoice-small")
    sys.exit(1)
print(f"模型缓存路径: {MODEL_DIR}")

# 音频文件
AUDIO_FILE = r"d:\AIToutiao\engine_mode\outputs\20260709\20260709_150248\audio.wav"

if not os.path.exists(AUDIO_FILE):
    print(f"错误: 音频文件不存在: {AUDIO_FILE}")
    sys.exit(1)

print("=" * 60)
print("SenseVoice 转录测试")
print("=" * 60)

# Step 1: 加载模型
print("\n[1] 加载模型 sensevoice-small (CPU)...")
t0 = time.time()

# funasr 默认从 {MODELSCOPE_CACHE}/models/{model_name} 加载
# 把模型复制/链接到正确的位置
import shutil
FUNASR_MODEL_DIR = os.path.join(os.path.abspath('./models_cache'), 'models', 'iic', 'SenseVoiceSmall')
if not os.path.exists(os.path.join(FUNASR_MODEL_DIR, 'model.pt')):
    print(f"   复制模型到 funasr 缓存路径...")
    os.makedirs(os.path.dirname(FUNASR_MODEL_DIR), exist_ok=True)
    if os.path.exists(FUNASR_MODEL_DIR):
        shutil.rmtree(FUNASR_MODEL_DIR)
    shutil.copytree(MODEL_DIR, FUNASR_MODEL_DIR)
    print(f"   模型已复制到: {FUNASR_MODEL_DIR}")

from funasr import AutoModel

model = AutoModel(
    model="iic/SenseVoiceSmall",
    device="cpu",
    disable_pbar=True,
    disable_update=True,
    local_dir=FUNASR_MODEL_DIR,  # 直接指定本地目录
)

load_time = time.time() - t0
print(f"   模型加载完成，耗时: {load_time:.1f} 秒")

# Step 2: 转录音频
print(f"\n[2] 转录音频: {os.path.basename(AUDIO_FILE)}")
file_size_mb = os.path.getsize(AUDIO_FILE) / (1024 * 1024)
print(f"   文件大小: {file_size_mb:.2f} MB")

t1 = time.time()
result = model.generate(
    input=AUDIO_FILE,
    language="zh",
    ban_emo_unk=True,
    use_itn=True,  # 逆文本标准化
)
transcribe_time = time.time() - t1

# Step 3: 输出结果
print(f"\n[3] 转录完成，耗时: {transcribe_time:.1f} 秒")
print(f"   总耗时: {load_time + transcribe_time:.1f} 秒")

if result and len(result) > 0:
    text = result[0].get("text", "")
    print(f"\n--- 转录结果 ({len(text)} 字符) ---")
    print(text[:500])
    if len(text) > 500:
        print(f"... (共 {len(text)} 字符)")

    # 保存结果
    output_file = AUDIO_FILE.replace('.wav', '_sensevoice.txt')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f"\n结果已保存到: {output_file}")
else:
    print("\n错误: 没有转录结果！")
    sys.exit(1)

print("\n" + "=" * 60)
print("测试完成!")
print(f"  模型加载: {load_time:.1f}s")
print(f"  转录耗时: {transcribe_time:.1f}s")
print(f"  文本长度: {len(text)} 字符")
print("=" * 60)
