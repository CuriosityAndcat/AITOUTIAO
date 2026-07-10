# SenseVoice ASR 语音转录工具

基于 [FunASR/SenseVoice](https://github.com/FunAudioLLM/SenseVoice) 的 **Windows CPU** 语音转文本工具，已验证可在 Python 3.12 环境下稳定运行。

## 📊 转录成功要素（关键版本组合）

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.12 | |
| PyTorch | 2.5.1+cpu | CPU 推理 |
| funasr | 1.3.10 | PyTorch 后端（**非 ONNX**） |
| **sentencepiece** | **0.2.0** ⚠️ | 0.2.1 在 Windows 上会导致 Access Violation 崩溃 |
| numpy | ≥2.0.0 | 1.26.4 会与 PyTorch 2.5 冲突 |
| SenseVoiceSmall 模型 | model.pt (893MB) | 需从 ModelScope 下载 |

### 🔴 踩坑记录

1. **sentencepiece 0.2.1 Windows bug** — `Load()` .model 文件时 Access Violation（0xC0000005），降级到 0.2.0 解决
2. **ONNX 路线失败** — `funasr-onnx` 强制 numpy≤1.26.4，与 PyTorch 2.5 不兼容，且本地模型为 PyTorch 格式
3. **KMP_DUPLICATE_LIB_OK** — Windows 上必须设置此环境变量，防止 OpenMP 冲突

---

## 🚀 快速开始

### 1. 安装 PyTorch

```powershell
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```

### 2. 安装依赖

```powershell
pip install -r requirements.txt
```

### 3. 下载模型

从 ModelScope 下载 SenseVoiceSmall 模型：

```powershell
python -c "
import os
os.environ['MODELSCOPE_CACHE'] = r'.\models'
from modelscope import snapshot_download
snapshot_download('iic/SenseVoiceSmall', cache_dir=r'.\models')
"
```

或手动从 [ModelScope](https://www.modelscope.cn/models/iic/SenseVoiceSmall) 下载后，将文件放到：

```
models/
└── iic/
    └── SenseVoiceSmall/
        ├── model.pt          (893 MB)
        ├── config.yaml
        ├── configuration.json
        ├── tokens.json
        ├── am.mvn
        └── chn_jpn_yue_eng_ko_spectok.bpe.model
```

### 4. 运行转录

```powershell
# 基础用法
python transcribe.py <音频文件路径>

# 指定语言和输出文件
python transcribe.py audio.wav --language zh --output result.txt

# 自动检测语言
python transcribe.py audio.wav --language auto

# 支持的语言: zh / en / ja / ko / yue / auto
```

---

## 📦 项目文件说明

| 文件 | 用途 |
|------|------|
| `transcribe.py` | CLI 命令行转录工具 |
| `sensevoice_transcriber.py` | Python 模块，供其他项目 `import` 调用 |
| `requirements.txt` | Python 依赖列表 |
| `models/` | 模型存放目录（需单独下载） |
| `SenseVoice-main/` | SenseVoice 官方源码（参考用） |

---

## 🔧 Python API 用法

```python
from sensevoice_transcriber import transcribe

text = transcribe(
    "audio.wav",
    language="zh",      # 语言: zh/en/ja/ko/yue/auto
    device="cpu",       # 设备: cpu/cuda
    use_itn=True,       # 逆文本正则化
)

print(text)
```

---

## ⚙️ 验证环境

| 检查项 | 命令 |
|--------|------|
| PyTorch 版本 | `python -c "import torch; print(torch.__version__)"` |
| funasr 版本 | `python -c "import funasr; print(funasr.__version__)"` |
| sentencepiece 版本 | `python -c "import sentencepiece; print(sentencepiece.__version__)"` |
| 模型文件 | `dir models\iic\SenseVoiceSmall\model.pt` |

---

## 📝 转录性能参考

测试环境：Windows 11, CPU, Python 3.12

| 阶段 | 耗时 |
|------|------|
| 模型加载 | ~90-100 秒 |
| 转录推理（3 分钟音频） | ~80 秒 |
| 总耗时 | ~3 分钟 |
