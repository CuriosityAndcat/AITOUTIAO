---
name: fix-pipeline-import-and-model-bugs
overview: 修复两个 Bug：1) faster-whisper 模型名缺少 whisker- 前缀剥离导致的 Invalid model size 错误；2) sys.path 顺序导致 config 模块导入冲突，使 AI 写作阶段报 cannot import name 'settings'。
todos:
  - id: fix-sys-path
    content: 修复 sys.path 导入优先级：交换 streamlit_app.py 第 32-33 行顺序，使 toutiao-auto-publisher/backend 优先于 wewrite-main/toolkit
    status: completed
  - id: fix-model-name
    content: 修复 faster-whisper 模型名转换：streamlit_app.py 第 617 行追加 .replace("whisper-", "") 彻底去除前缀
    status: completed
  - id: verify-pipeline
    content: 验证一键生成器完整流水线：确认下载→转录→写作三个阶段均正常执行
    status: completed
    dependencies:
      - fix-sys-path
      - fix-model-name
---

## 用户需求

修复 AIToutiao 一键生成器（streamlit_app.py）中两个 bug，使从下载到写作的完整流水线能够正常执行。

### Bug 1：faster-whisper 转录失败

- 错误信息：`Invalid model size 'whisper-small', expected one of: tiny.en, tiny, base.en, base, small.en, small, ...`
- 根因：`.env` 中 `WHISPER_MODEL=openai/whisper-small`，代码仅做了 `.replace("openai/", "")` 得到 `whisper-small`，faster-whisper 要求纯模型名 `small`
- 修复位置：`streamlit_app.py` 第 617 行

### Bug 2：AI 写作失败

- 错误信息：`cannot import name 'settings' from 'config'`
- 根因：`sys.path` 中 `wewrite-main/toolkit` 优先级高于 `toutiao-auto-publisher/backend`，`ai_writer.py` 的 `from config import settings` 被路由到 wewrite 的 config.py（该文件没有 settings 导出）
- 修复位置：`streamlit_app.py` 第 32-33 行

## 技术方案

### Bug 1 修复

在模型名转换链中追加 `whisper-` 前缀剥离：

```python
# 修复前
fw_model_name = model.replace("openai/", "")

# 修复后
fw_model_name = model.replace("openai/", "").replace("whisper-", "")
```

转换覆盖所有场景：

| .env 配置值 | 修复前 | 修复后 |
| --- | --- | --- |
| `openai/whisper-small` | `whisper-small` (报错) | `small` (正确) |
| `whisper-small` | `whisper-small` (报错) | `small` (正确) |
| `small` | `small` (正确) | `small` (正确) |


### Bug 2 修复

交换 `sys.path.insert` 的两行顺序，使 `toutiao-auto-publisher/backend` 在 `wewrite-main/toolkit` 之后插入，从而获得更高的搜索优先级：

```python
# 修复前（wewrite/toolkit 优先级最高）
sys.path.insert(0, str(PROJECT_ROOT / "toutiao-auto-publisher" / "backend"))  # → index 1
sys.path.insert(0, str(PROJECT_ROOT / "wewrite-main" / "toolkit"))            # → index 0

# 修复后（backend 优先级最高）
sys.path.insert(0, str(PROJECT_ROOT / "wewrite-main" / "toolkit"))            # → index 1
sys.path.insert(0, str(PROJECT_ROOT / "toutiao-auto-publisher" / "backend"))  # → index 0
```

`sys.path.insert(0, x)` 将 x 插入到列表最前面，后插入者排在更前。修复后 `from config import settings` 优先找到 `toutiao-auto-publisher/backend/config.py`。

### 影响范围

仅修改 `streamlit_app.py` 两处，不影响其他模块。