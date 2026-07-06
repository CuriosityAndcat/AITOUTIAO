---
name: aitoutiao-end-to-end-pipeline
overview: 创建端到端自动化流水线，串联视频下载→语音转录→AI写作→违规检测→头条发布全流程，并修复 video-batch-download 转录流程的实际可用性问题。
todos:
  - id: check-deps
    content: 创建 check_deps.py 依赖检测脚本，自动检测 ffmpeg、faster-whisper、opencc 并给出缺失安装指引
    status: completed
  - id: unify-config
    content: 创建项目根目录统一 .env 配置文件，扩展 toutiao-auto-publisher/backend/config.py 增加 outputs 路径等配置项
    status: completed
  - id: verify-transcribe
    content: 验证 video-batch-download 转录流程，用测试视频跑通 download → transcribe 全链路，修复依赖缺失问题
    status: completed
    dependencies:
      - check-deps
      - unify-config
  - id: build-pipeline
    content: 创建 pipeline.py 流水线编排器，实现 download → transcribe → AI改写 → 发布四阶段串联，支持断点续跑和三种运行模式
    status: completed
    dependencies:
      - verify-transcribe
  - id: test-e2e
    content: 用真实抖音/B站视频链接端到端测试全流程，验证输出结果质量并调优
    status: completed
    dependencies:
      - build-pipeline
---

## 用户需求

将现有子项目串联成端到端自动化流水线，同时补全视频转录流程。

## 产品概述

AIToutiao 端到端自动化流水线：从视频 URL 输入到今日头条发布输出的全自动管线。用户只需提供一个抖音/B站/小红书视频链接，系统自动完成：下载视频 → 语音转录 → AI 改写为微头条/文章 → 头条发布 → 结果归档。

## 核心功能

- **一键流水线**：单一命令触发全流程，输入 URL 或关键词，端到端输出发布结果
- **转录修复**：验证并修复 video-batch-download 的 faster-whisper、ffmpeg、OpenCC 依赖，确保转录环节稳定可用
- **分步可中断**：流水线支持断点续跑，每步结果落盘到 outputs/YYYY-MM-DD/ 目录，失败后可从中断处恢复
- **多模式支持**：支持"仅下载+转录"、"下载+转录+AI改写"、"全流程发布"三种运行模式
- **状态可视化**：实时展示流水线进度，每步耗时、成功/失败状态清晰可读

## 技术栈

- **编排器**：Python 3.x（与 toutiao-auto-publisher 同语言，可直接复用其 AI 写作和配置模块）
- **视频下载+转录**：复用现有 Node.js 脚本（`download.mjs`）+ Python 转录服务（`transcribe_server.py`）
- **AI 写作**：调用 toutiao-auto-publisher 的 `AIWriter` 类（DeepSeek API）
- **头条发布**：调用 toutiao-auto-publisher 的 FastAPI `/api/publish` 端点
- **配置管理**：统一 `.env` 文件，兼容现有 `config.py` 的 pydantic-settings 模式

## 实现方案

### 整体策略

创建一个独立的 Python 编排脚本 `pipeline.py` 作为流水线入口。它通过子进程调用 `download.mjs` 完成下载+转录，然后直接 import `toutiao-auto-publisher` 的 `AIWriter` 和 HTTP 客户端调用发布 API，串联全流程。避免改动现有子项目的核心逻辑，仅做依赖修复和桥接。

### 流水线架构

```mermaid
flowchart TD
    A[pipeline.py 启动] --> B{运行模式}
    B -->|download| C[调用 download.mjs]
    B -->|full| C
    C --> D[Node.js: 下载视频]
    D --> E[Node.js: spawn transcribe_server.py]
    E --> F[Python faster-whisper: 语音转录]
    F --> G[Node.js: writeOutputs 落盘]
    G --> H{模式判断}
    H -->|download-only| Z[结束 - outputs/ 归档]
    H -->|write / full| I[读取转录文本]
    I --> J[调用 AIWriter.generate: AI改写为微头条/文章]
    J --> K[保存改写结果到 outputs/]
    K --> L{模式判断}
    L -->|write-only| Z
    L -->|full| M[HTTP POST /api/publish: 头条发布]
    M --> N[轮询 /api/task/{id}: 等待发布结果]
    N --> Z
```

### 关键设计决策

1. **编排器用 Python 而非 Node.js**：因为 toutiao-auto-publisher 的核心能力（AIWriter、config）是 Python 模块，直接 import 比跨语言 HTTP 调用更高效可靠。下载环节通过 `subprocess.run` 调用 Node.js CLI。

2. **转录修复策略**：不重写转录逻辑（transcribe_server.py 代码已经完整），而是添加依赖检测脚本 `check_deps.py`，自动检测 faster-whisper、ffmpeg、opencc 是否安装，给出缺失提示和安装命令。同时在 `pipeline.py` 启动时预检。

3. **断点续跑**：每步完成后写入 `pipeline_state.json` 到 outputs 目录，记录已完成步骤和产物路径。重新运行时自动跳过已完成步骤。

4. **配置统一**：创建项目根目录的 `.env` 文件，聚合所有子项目的配置项（AI_API_KEY、AI_MODEL、下载输出目录等），各子项目通过各自的方式读取（Python 用 pydantic-settings，Node.js 用 dotenv）。

### 性能考量

- 转录是最大瓶颈（faster-whisper small 模型在 CPU 上约 5-10x 实时），已在 download.mjs 中实现串行转录队列避免资源争抢
- AI 写作 API 调用约 3-10 秒，发布约 15-30 秒（浏览器自动化），均在可接受范围
- 流水线总耗时预估：下载(30s-2min) + 转录(1-5min) + AI写作(3-10s) + 发布(15-30s) = 约 2-8 分钟

## 实现细节

### 目录结构

```
d:/AIToutiao/
├── .env                          # [NEW] 统一配置文件，聚合所有子项目配置
├── pipeline.py                   # [NEW] 端到端流水线编排器主脚本
├── check_deps.py                 # [NEW] 依赖检测脚本，验证 ffmpeg/faster-whisper/opencc
├── toutiao-auto-publisher/
│   └── backend/
│       ├── config.py             # [MODIFY] 扩展配置项，支持 outputs 路径、下载配置
│       └── ai_writer.py          # [EXISTING] 复用，无需修改
├── video-batch-download-main/
│   └── scripts/
│       ├── download.mjs          # [EXISTING] 复用，通过子进程调用
│       └── transcribe_server.py  # [EXISTING] 复用，无需修改
└── outputs/                      # [EXISTING] 流水线产物输出目录
    └── YYYY-MM-DD/               # 按日期组织
```

### 关键接口

**pipeline.py 核心流程**:

```python
class PipelineMode(Enum):
    DOWNLOAD_ONLY = "download"     # 仅下载+转录
    WRITE_ONLY = "write"           # 下载+转录+AI改写
    FULL = "full"                  # 全流程：下载+转录+改写+发布

class PipelineStage(Enum):
    DOWNLOAD = "download"
    TRANSCRIBE = "transcribe"
    WRITE = "write"
    PUBLISH = "publish"

# 主函数
def run_pipeline(url_or_keyword: str, mode: PipelineMode, content_type: str = "toutie"):
    state = load_state()  # 断点恢复
    # 按 stage 顺序执行，跳过已完成步骤
    # 每步完成后 save_state()
```

**check_deps.py 检测逻辑**:

- `shutil.which("ffmpeg")` 检测 ffmpeg
- `import faster_whisper` 检测 faster-whisper
- `import opencc` 检测 opencc
- 输出缺失列表和安装命令

### 向后兼容

- 不修改现有子项目的核心逻辑
- 仅扩展 toutiao-auto-publisher 的 config.py 增加配置项（非破坏性）
- pipeline.py 独立运行，不影响 toutiao-auto-publisher 的 Web UI
- download.mjs 的 CLI 接口保持不变