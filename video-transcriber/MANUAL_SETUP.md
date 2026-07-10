# SenseVoice 离线转录 — 手动执行方案 & 脚本执行方案

> 基于 [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice) 官方仓库

## 背景

`video-transcriber` 项目中的 `sensevoice_transcriber.py` 在加载模型时传入的是 ModelScope 仓库 ID（`"iic/SenseVoiceSmall"`），导致 `funasr.AutoModel()` 内部必须联网校验，在弱网环境会卡死在 "Downloading Model..." 阶段。

**根因**：`AutoModel(model="iic/SenseVoiceSmall")` → `modelscope.snapshot_download()` → 联网校验 → 卡死。

**解决**：传入本地绝对路径 + 设置 `MODELSCOPE_DISABLE_REMOTE=1`。**官方 README 确认这是正确做法。**

## 官方仓库关键信息

| 参数 | 官方示例 | 说明 |
|------|---------|------|
| `model` | 本地路径 或 `"iic/SenseVoiceSmall"` | 官方支持本地路径 |
| `batch_size_s` | `60` | 动态批处理加速（官方推荐） |
| `vad_model` | `"fsmn-vad"` | 长音频 VAD 分割 |
| `vad_kwargs` | `{"max_single_segment_time": 30000}` | 最大段 30 秒 |
| `merge_vad` | `True` | 合并短片段 |
| `merge_length_s` | `15` | 合并后最大长度 |
| `language` | `"auto"` / `"zh"` / `"en"` / `"yue"` / `"ja"` / `"ko"` | 支持 50+ 语言 |

> SenseVoice 非自回归架构，推理速度比 Whisper 快 **15 倍**。支持 ASR + 情感识别 + 音频事件检测。

---

## 前置条件（已完成）

| 步骤 | 状态 |
|------|------|
| `pip install funasr modelscope` | ✅ |
| `python webmain.py download-model sensevoice-small` | ✅ 893MB 模型已在 `models_cache/` |

---

## 方案一：一键脚本（推荐）

```powershell
cd D:\AIToutiao\video-transcriber

# 基础转录（CPU、中文、8.6MB 测试音频）
python _transcribe_local.py

# 长音频启用 VAD 分割
python _transcribe_local.py --vad "D:\path\to\long_audio.wav"

# GPU 加速
python _transcribe_local.py --device cuda

# 自动语言检测
python _transcribe_local.py --language auto
```

### 可选参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `audio` | 测试音频 | 音频文件路径 |
| `--device` | `cpu` | `cpu` / `cuda` |
| `--language` | `zh` | `zh` / `en` / `yue` / `ja` / `ko` / `auto` |
| `--vad` | 关 | 启用 VAD 分割（长音频推荐） |
| `--batch-size` | `60` | 批处理大小（秒） |
| `--output` | 自动 | 自定义输出路径 |

### 脚本做了什么

```
Step 1/4: 检查模型文件完整性（model.pt、config.yaml、tokens.json...）
Step 2/4: 配置离线环境（MODELSCOPE_DISABLE_REMOTE=1）
Step 3/4: 加载模型（传入本地绝对路径，约 60-90 秒）
Step 4/4: 转录 + 保存结果
```

---

## 方案二：手动逐步执行

如果你想理解每一步在做什么，或需要自定义流程，可以在 Python 交互环境或 Jupyter 中逐步运行：

### Step 1：验证模型文件

```python
import os
from pathlib import Path

MODEL_DIR = Path(r"D:\AIToutiao\video-transcriber\models_cache\iic\SenseVoiceSmall")

# 检查关键文件
for f in ["model.pt", "config.yaml", "configuration.json", "tokens.json",
          "am.mvn", "chn_jpn_yue_eng_ko_spectok.bpe.model"]:
    fp = MODEL_DIR / f
    print(f"{'✓' if fp.exists() else '✗'} {f}  ({fp.stat().st_size / 1024 / 1024:.1f} MB)" if fp.exists() else f"✗ {f}  缺失")
```

### Step 2：设置离线环境变量

```python
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
os.environ['MODELSCOPE_CACHE'] = str(Path(r"D:\AIToutiao\video-transcriber\models_cache"))
os.environ['MODELSCOPE_DISABLE_REMOTE'] = '1'  # ← 关键！禁止联网
```

### Step 3：加载模型（传入本地绝对路径）

```python
import time
from funasr import AutoModel

t1 = time.time()

model = AutoModel(
    model=str(MODEL_DIR),        # ← 绝对路径，不是 "iic/SenseVoiceSmall"
    device="cpu",                # 或用 "cuda"
    disable_pbar=True,
    disable_update=True,
    disable_log=True,
)

print(f"模型加载完成! 耗时 {time.time() - t1:.1f}s")
```

### Step 4：转录音频

```python
audio_file = r"D:\AIToutiao\engine_mode\outputs\20260709\20260709_150248\audio.wav"

t2 = time.time()
result = model.generate(
    input=audio_file,
    language="zh",       # 中文；支持 zh/en/yue/ja/ko/auto
    ban_emo_unk=True,    # 去除情感标记
    use_itn=True,        # 反文本正则化（输出标点）
    batch_size_s=60,     # ← 动态批处理加速（官方推荐）
)

text = result[0].get("text", "")
print(f"转录完成! 耗时 {time.time() - t2:.1f}s")
print(f"文本长度: {len(text)} 字符")
print(f"内容预览:\n{text[:200]}")
```

### Step 5：保存结果

```python
output_path = Path(audio_file).with_suffix("").with_name(
    Path(audio_file).stem + "_sensevoice.txt"
)
output_path.write_text(text, encoding="utf-8")
print(f"结果已保存: {output_path}")
```

---

## 预期输出

```
============================================================
  SenseVoice 本地离线转录
============================================================
  模型目录: D:\AIToutiao\video-transcriber\models_cache\iic\SenseVoiceSmall
  音频文件: D:\AIToutiao\engine_mode\outputs\20260709\20260709_150248\audio.wav
  音频大小: 12.3 MB
  推理设备: cpu

[Step 1/4] 检查模型文件...
  ✓ model.pt                                      xxx.x MB
  ✓ config.yaml                                    0.0x MB
  ✓ configuration.json                             0.0x MB
  ✓ tokens.json                                    0.0x MB
  ✓ am.mvn                                         0.0x MB
  ✓ chn_jpn_yue_eng_ko_spectok.bpe.model             x.x MB
  模型文件完整 ✓

[Step 2/4] 配置离线模式...
  MODELSCOPE_CACHE=...\models_cache
  MODELSCOPE_DISABLE_REMOTE=1

[Step 3/4] 加载 SenseVoice 模型...
  (893MB 模型加载需要 60-90 秒，请耐心等待)
  加载完成! 耗时 xx.xs

[Step 4/4] 转录音频...
  转录完成! 耗时 xx.xs

============================================================
  模型加载:         xx.xs
  转录耗时:         xx.xs
  总耗时:           xx.xs
  文本长度:         xxxx 字符
  结果文件:         ...\audio_sensevoice.txt
  前 200 字预览:
    xxx...
============================================================
```

---

## 常见问题

### Q: 运行时提示 `MODELSCOPE_DISABLE_REMOTE` 不生效？
确认是在 `import modelscope` 或 `from funasr import AutoModel` **之前**设置的环境变量。代码示例中已确保顺序正确。

### Q: 模型文件在哪里？
```
models_cache/
└── iic/
    └── SenseVoiceSmall/
        ├── model.pt         ← 主模型权重
        ├── config.yaml      ← 模型配置
        ├── tokens.json      ← 词表
        ├── am.mvn           ← 均值方差归一化
        ├── configuration.json
        └── chn_jpn_yue_eng_ko_spectok.bpe.model
```

### Q: 仍然卡在 "Downloading Model..."？
1. 确认 `model=str(MODEL_DIR)` 传入的是**绝对路径**，不是 `"iic/SenseVoiceSmall"`
2. 确认 `MODELSCOPE_DISABLE_REMOTE=1` 在 import 之前设置
3. 尝试升级 funasr: `pip install --upgrade funasr`

### Q: 如何集成到 engine_app.py？
在 `engine_app.py` 的转录流程中，使用本脚本的加载方式：

```python
# engine_app.py 中替换原有的转录调用
from pathlib import Path
import os

def transcribe_with_sensevoice(audio_path: str) -> str:
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    os.environ['MODELSCOPE_CACHE'] = str(Path(__file__).parent.parent / "video-transcriber" / "models_cache")
    os.environ['MODELSCOPE_DISABLE_REMOTE'] = '1'
    
    MODEL_DIR = Path(r"D:\AIToutiao\video-transcriber\models_cache\iic\SenseVoiceSmall")
    
    from funasr import AutoModel
    model = AutoModel(
        model=str(MODEL_DIR),
        device="cpu",
        disable_pbar=True,
        disable_update=True,
        disable_log=True,
    )
    
    result = model.generate(input=audio_path, language="zh", ban_emo_unk=True, use_itn=True)
    return result[0].get("text", "")
```
