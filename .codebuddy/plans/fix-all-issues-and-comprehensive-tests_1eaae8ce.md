---
name: fix-all-issues-and-comprehensive-tests
overview: 修复代码库中所有已知问题（config 导入冲突、Whisper 模型名处理、Streamlit 网络解析、AI 写作容错等），并编写覆盖所有核心模块（URL 提取、PipelineState、转录音、AI 写作、流水线编排）的完整性测试，迭代执行直到全部通过。
todos:
  - id: fix-config-conflict-pipeline
    content: 修复 pipeline.py 的 config 模块导入冲突：采用 importlib.util 预加载 backend/config.py 到 sys.modules
    status: completed
  - id: fix-whisper-model-pipeline
    content: 修复 pipeline.py 的 Whisper 模型名规范化：提取 normalize_whisper_model_name 函数并复用
    status: completed
  - id: fix-ipv6-runbat
    content: 修复 run.bat 的 IPv6 问题：将所有 localhost 改为 127.0.0.1
    status: completed
  - id: fix-aiwriter-path
    content: 优化 ai_writer.py 的路径操作：为 sys.path.insert 添加清晰的注释说明，确保独立性
    status: completed
  - id: fix-enum-tolerance
    content: 修复 streamlit_app.py step_write 的枚举容错：ContentType 为 None 时的安全降级
    status: completed
  - id: create-test-suite
    content: 创建完整性测试套件（test_url_extraction / test_whisper_model / test_pipeline_state / test_config_loading / test_ai_writer_import）
    status: completed
    dependencies:
      - fix-config-conflict-pipeline
      - fix-whisper-model-pipeline
      - fix-ipv6-runbat
      - fix-aiwriter-path
      - fix-enum-tolerance
  - id: run-tests-iterate
    content: 执行测试套件并根据失败日志迭代修复，直到全部测试通过
    status: completed
    dependencies:
      - create-test-suite
---

## 用户需求

对 AIToutiao 代码库中所有已知问题进行全面修复，确保逻辑和功能恢复正常。修复完成后，编写覆盖所有核心功能的完整性测试用例并执行，若测试未通过则根据失败日志迭代修复，直到全部通过。

## 产品概述

AIToutiao 是一键内容生成器，核心流水线为：视频下载 -> 语音转录 -> AI写作 -> 人工化改写 -> 配图生成 -> 图文组装。通过 Streamlit Web 界面或 CLI 命令行两种方式使用。

## 已确认需要修复的 5 个核心 Bug

### Bug 1：pipeline.py config 模块导入冲突

`pipeline.py` 第 58-59 行通过 `sys.path.insert` + `from config import settings` 导入配置，可能被 `wewrite-main/toolkit/config.py`（YAML 加载器，无 `settings` 属性）抢注，导致 `ImportError`。需与 `streamlit_app.py` 第 37-45 行采用相同的 `importlib.util` 预加载策略。

### Bug 2：pipeline.py Whisper 模型名未规范化

`.env` 中 `WHISPER_MODEL=openai/whisper-small`，`pipeline.py` 第 63 行直接使用该值传给子进程或 faster-whisper。`streamlit_app.py` 第 630-635 行已修复（for 循环前缀匹配剥离），但 `pipeline.py` 未同步修复，导致 faster-whisper 收到无法识别的模型名。

### Bug 3：run.bat 使用 localhost 导致 IPv6/IPv4 解析失败

Windows 上 `localhost` 优先解析为 IPv6 地址 `::1`，而 uvicorn 仅绑定 IPv4 `0.0.0.0`，导致浏览器无法连接。需将 `http://localhost:8501` 改为 `http://127.0.0.1:8501`。

### Bug 4：ai_writer.py 路径操作存在污染风险

第 21-22 行在模块顶层无条件 `sys.path.insert(0, _backend_dir)`，对已正确解析的 config 导入无实际影响但属于冗余操作。第 1052-1053 行、1224-1225 行在 `generate_cover_image` / `generate_inline_images` 中动态插入 `wewrite-main/toolkit` 到 sys.path 最前方，虽已有 guard (`if toolkit_dir not in sys.path`)，但注释说明不清晰。

### Bug 5：streamlit_app.py step_write 中枚举为 None 时的容错

第 794、800 行：当 `ContentType` 导入失败设为 `None` 时，`ContentType.ARTICLE if ContentType else "article"` 传给 `AIWriter.generate()` 的是字符串而非枚举类型，而 `AIWriter.generate()` 第 969 行执行 `content_type == ContentType.TOUTIE` 会因类型不匹配导致逻辑分支错误（字符串 `"article"` 不等于枚举 `ContentType.TOUTIE`）。

## 技术栈

- Python 3.10+
- Streamlit (Web UI)
- pydantic_settings (配置管理)
- faster-whisper / transformers (语音转录)
- OpenAI SDK (AI 写作，调用 DeepSeek API)
- pytest + pytest-cov (测试框架)
- importlib.util (模块预加载)

## 修复策略

### Bug 1 修复：pipeline.py config 预加载

在 `pipeline.py` 导入区（第 34 行之后）添加与 `streamlit_app.py` 第 37-45 行相同的 `importlib.util` 预加载逻辑，从绝对路径加载 `toutiao-auto-publisher/backend/config.py` 并注册到 `sys.modules["config"]`。随后删除第 58-59 行 `sys.path.insert` 后的 `from config import settings` 改为直接引用已预加载的模块。

### Bug 2 修复：pipeline.py Whisper 模型名规范化

在 `pipeline.py` 第 63 行获取 `WHISPER_MODEL` 后，提取可复用的 `normalize_whisper_model_name()` 函数（或复用 `streamlit_app.py` 中的逻辑），剥离 `openai/whisper-` / `openai/` / `whisper-` 前缀。由于 `pipeline.py` 中 `TranscribeStage` 通过子进程调用 `transcribe.py`（传入 `--model $WHISPER_MODEL`），最快修复是在赋值处规范化。

### Bug 3 修复：run.bat IPv6 规避

将 `run.bat` 第 22 行的提示信息和第 28 行的启动命令中的 `localhost` 全部改为 `127.0.0.1`。

### Bug 4 修复：ai_writer.py 路径操作优化

- 第 19-22 行：在 `if` guard 已经存在的基础上，注释说明其必要性（确保独立运行时 config 可找到）。
- 第 1048-1053 行、1220-1225 行：现有的 `if toolkit_dir not in sys.path` guard 已防重复 insert。保持现状，增加注释说明。

### Bug 5 修复：streamlit_app.py 枚举容错

当 `ContentType` 为 None 时不应调用 `AIWriter.generate()`（因为该函数需要枚举类型）。修改 `step_write` 第 791-803 行：在 ContentType 为 None 时直接用字符串构建请求，或给出明确报错而非将字符串传给枚举参数。

## 测试策略

### 测试架构

```
tests/
├── test_url_extraction.py      # URL 提取逻辑（纯函数，无外部依赖）
├── test_whisper_model.py       # 模型名规范化（纯函数）
├── test_pipeline_state.py      # PipelineState 序列化/反序列化
├── test_config_loading.py      # config 模块预加载正确性
├── test_ai_writer_import.py    # AIWriter 导入不冲突
├── test_pipeline_smoke.py      # CLI pipeline 烟雾测试（跳过耗时的下载/转录）
└── conftest.py                 # 共享 fixtures
```

### 测试分层

1. **单元测试（快速，无网络/IO 依赖）**：URL 提取、模型名规范化、PipelineState 序列化、config 导入正确性
2. **集成测试（需要本地文件系统）**：PipelineState 断点续跑、config 模块冲突防护
3. **烟雾测试（可选，需要 API Key）**：AIWriter 实例化、generate 方法调用

### 执行与迭代

- 每次运行 `python -m pytest tests/ -v` 
- 分析失败日志，定位并修复
- 重复直到全部通过

## 目录结构

```
d:\AIToutiao\
├── streamlit_app.py                    # [MODIFY] Bug 5 修复：step_write 枚举容错
├── pipeline.py                         # [MODIFY] Bug 1+2 修复：config 预加载 + Whisper 模型名规范化
├── run.bat                             # [MODIFY] Bug 3 修复：localhost → 127.0.0.1
├── toutiao-auto-publisher\backend\
│   └── ai_writer.py                   # [MODIFY] Bug 4 修复：路径操作注释优化
├── tests\                              # [NEW] 测试目录
│   ├── __init__.py                     # [NEW] 测试包初始化
│   ├── conftest.py                     # [NEW] pytest fixtures（临时目录、环境变量 mock）
│   ├── test_url_extraction.py          # [NEW] extract_douyin_url 全部场景覆盖
│   ├── test_whisper_model.py           # [NEW] normalize_whisper_model_name 函数及测试
│   ├── test_pipeline_state.py          # [NEW] PipelineState 序列化/断点续跑/已存在查找
│   ├── test_config_loading.py          # [NEW] config 预加载防冲突验证
│   └── test_ai_writer_import.py        # [NEW] AIWriter 导入不受 wewrite config 干扰
└── _run_tests.bat                      # [NEW] 一键运行全部测试的批处理
```