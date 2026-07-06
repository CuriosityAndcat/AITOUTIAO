---
name: fix-background-thread-state
overview: 修复后台线程无法访问 st.session_state 的问题，引入模块级共享状态 _PIPELINE_FEED 作为跨线程数据通道。
todos:
  - id: add-feed-and-helper
    content: 添加模块级 _PIPELINE_FEED 共享字典和 _is_script_thread() 上下文检测函数
    status: completed
  - id: refactor-add-log-set-stage
    content: 改造 add_log() 和 set_stage()，根据 ScriptRunContext 自动路由写入 st.session_state 或 _PIPELINE_FEED
    status: completed
    dependencies:
      - add-feed-and-helper
  - id: refactor-progress-writes
    content: 新增 _set_progress() 辅助函数，替换全部 15 处 st.session_state.progress_pct 直接写入
    status: completed
    dependencies:
      - add-feed-and-helper
  - id: refactor-pipeline-functions
    content: 改造 execute_pipeline、_execute_pipeline_core、_load_result_from_state 中的 st.session_state 直接写入为 Feed 写入
    status: completed
    dependencies:
      - refactor-add-log-set-stage
      - refactor-progress-writes
  - id: add-sync-and-main
    content: 新增 _sync_feed_to_session() 并在 main() 渲染之前调用；更新清空按钮同步重置 Feed
    status: completed
    dependencies:
      - add-feed-and-helper
  - id: verify-thread-safety
    content: 验证完整性：检查全文无遗漏的 st.session_state 后台写入，确认语法和 lint 通过
    status: completed
    dependencies:
      - add-sync-and-main
---

## 问题描述

上一轮重构将 `execute_pipeline` 改为后台线程执行后，启动时立即崩溃：

- `Thread-6: missing ScriptRunContext`
- `st.session_state has no key 'stage_status'`

根因：Streamlit 的 `st.session_state` 只能在主线程（有 ScriptRunContext）中访问，后台 daemon 线程直接访问即抛异常。

## 解决方案

引入模块级共享字典 `_PIPELINE_FEED` 作为跨线程数据通道：

```
后台线程 ──> write to _PIPELINE_FEED (普通 dict) ──> 主线程轮询 _sync_feed_to_session() ──> st.session_state ──> UI 渲染
```

核心原则：所有流水线函数中写入的状态（logs、stage_status、progress_pct、result_data 等）必须在后台线程执行时写入 Feed；主线程每次渲染前从 Feed 同步到 st.session_state。

## 改动的函数范围

- `add_log()` / `set_stage()` — 根据 ScriptRunContext 自动选择写入目标
- `execute_pipeline()` / `_execute_pipeline_core()` / `_load_result_from_state()` — 核心流水线逻辑
- 所有阶段函数中的 `st.session_state.progress_pct = ...` — 共 15 处
- `main()` — 添加同步调用
- `render_main()` 清空按钮 — 重置 Feed

## 技术方案

### 1. 线程检测机制

使用 Streamlit 内部 API 检测当前线程是否有 ScriptRunContext：

```python
from streamlit.runtime.scriptrunner import get_script_run_ctx

def _is_script_thread() -> bool:
    return get_script_run_ctx() is not None
```

返回 True → 主线程，可直接写 st.session_state；返回 False → 后台线程，写 Feed。

### 2. 共享状态结构

```python
_PIPELINE_FEED = {
    "logs": [],              # 新增日志条目列表
    "stage_status": {         # 阶段状态 {名称: pending/running/done/failed}
        "下载": "pending", "转录": "pending", "写作": "pending",
        "改写": "pending", "配图": "pending", "组装": "pending",
    },
    "current_stage": "",      # 当前正在执行的阶段名
    "progress_pct": 0.0,      # 进度百分比
    "pipeline_state": None,   # PipelineState 对象
    "run_id": "",             # 运行 ID
    "result_data": None,      # _build_result() 的结果 dict
    "error": None,            # 异常信息字符串
    "elapsed_seconds": 0.0,   # 耗时
    "is_running": False,      # 运行中标记
    "done": False,            # 完成标记
}
```

### 3. 核心函数改造

**add_log()**：追加日志到 `_PIPELINE_FEED["logs"]`（后台线程）或 `st.session_state.logs`（主线程）。主线程同步时将 Feed 日志合并到 st.session_state。

**set_stage()**：更新 `_PIPELINE_FEED["stage_status"]` 和 `current_stage`（后台）或直接写 st.session_state（主）。

**新增 _set_progress(val)**：统一入口，后台写 Feed，主线程写 st.session_state。替换所有 15 处 `st.session_state.progress_pct = X`。

**_sync_feed_to_session()**：将 Feed 中所有字段复制到 st.session_state。对 logs 做增量合并（避免重复），对 stage_status 做深度复制。

### 4. 同步时机

在 `main()` 中，**render_progress() / render_logs() 调用之前**执行 `_sync_feed_to_session()`，确保每次轮询渲染的数据是最新的。

### 5. 线程安全

Python GIL 保证单个 dict 操作原子性。Feed 的 list append、dict 赋值都是单步操作，无需额外加锁。同步时使用浅拷贝避免并发修改问题。