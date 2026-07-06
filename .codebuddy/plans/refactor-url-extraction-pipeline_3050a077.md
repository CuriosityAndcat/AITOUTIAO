---
name: refactor-url-extraction-pipeline
overview: 重构 URL 提取与流水线执行的关系：将提取作为独立前置步骤存入 session_state，流水线单向读取；消除重复分支；确保 UI 提示不干扰任务队列。
todos:
  - id: add-processed-url-default
    content: 在 _DEFAULTS 字典中新增 processed_url 键，同时在 clear_btn 重置列表中加入 processed_url
    status: completed
  - id: persist-url-in-render
    content: 在 render_main() 的 URL 检测逻辑中将提取结果写入 st.session_state.processed_url
    status: completed
  - id: simplify-click-handler
    content: 重构 main() 点击处理：删除 st.info 冗余提示，统一为单一路径从 session_state.processed_url 读取并执行流水线
    status: completed
    dependencies:
      - add-processed-url-default
      - persist-url-in-render
  - id: verify-single-pass
    content: 验证重构后的单向数据流：确认 URL 提取不阻塞流水线，各阶段正常触发
    status: completed
    dependencies:
      - simplify-click-handler
---

## 用户需求

修复 AIToutiao 一键生成器中 URL 提取干扰流水线执行的问题。当前当用户粘贴抖音分享文本后点击"一键生成"，系统检测到完整 URL 后显示"已自动提取链接"提示，但提示信息成为数据流的阻塞点，导致后续下载、转录、写作、改写、配图、组装步骤未能正常触发。

## 核心要求

1. URL 提取作为独立前置步骤，与流水线触发完全解耦
2. 提取状态提示仅限于 UI 展示（实时预览），不作为阻塞节点
3. 各步骤间数据严格单向传递，防止状态回溯污染
4. 消除重复分支，统一为单一执行路径

## 技术方案

### 问题根因

`main()` 函数的点击处理逻辑（第 1517-1542 行）存在三个结构性问题：

| 问题 | 描述 |
| --- | --- |
| 局部变量 `cleaned_url` | `st.rerun()` 后变量丢失，后续渲染周期无法访问 |
| 重复分支 | 两个分支仅差一个 `st.info()`，而 `render_main()` 中已有 `st.caption()` 实时预览 |
| 无单向通道 | URL 提取结果未持久化到 session_state，状态管理不可靠 |


### 修复策略

引入 `session_state.processed_url` 作为单向数据通道：

1. **输入阶段**（`render_main`）：每次文本输入变化时，检测并写入 `st.session_state.processed_url`
2. **触发阶段**（`main` 点击处理）：统一从 `st.session_state.processed_url` 读取，单路径执行 `execute_pipeline`
3. **重置阶段**（`clear_btn`）：清空时同步重置 `processed_url`

数据流变为严格单向：

```
用户输入 → extract_douyin_url() → session_state.processed_url → execute_pipeline()
                                    ↓
                              st.caption() UI预览（纯展示，不阻断）
```

### 修改范围

仅修改 `streamlit_app.py` 4 处，不涉及其他文件。

#### 改动 1：`_DEFAULTS` 新增键（第 152 行后）

```python
_DEFAULTS = {
    ...
    "elapsed_seconds": 0.0,
    "processed_url": "",          # [NEW] 单向数据通道
}
```

#### 改动 2：`render_main()` URL 检测写入 session_state（第 1340-1346 行）

```python
# 修复前
if url and url.strip():
    raw = url.strip()
    detected = extract_douyin_url(raw)
    if detected and detected != raw:
        st.caption(f"🔗 检测到链接：`{detected}`")
    elif detected is None:
        st.caption("⚠️ 未检测到有效链接...")

# 修复后
if url and url.strip():
    raw = url.strip()
    detected = extract_douyin_url(raw)
    st.session_state.processed_url = detected or ""  # [NEW] 持久化
    if detected and detected != raw:
        st.caption(f"🔗 检测到链接：`{detected}`")
    elif detected is None:
        st.caption("⚠️ 未检测到有效链接...")
```

#### 改动 3：`main()` 点击处理统一为单一路径（第 1517-1542 行）

```python
# 修复前
if generate_btn and url.strip():
    raw_input = url.strip()
    cleaned_url = extract_douyin_url(raw_input)
    if cleaned_url is None:
        st.error(...)
    elif cleaned_url != raw_input:
        st.info(...)           # 冗余阻断
        execute_pipeline(...)
        st.rerun()
    else:
        execute_pipeline(...)
        st.rerun()

# 修复后
if generate_btn and url.strip():
    processed = st.session_state.get("processed_url", "")
    if not processed:
        st.error("❌ 未在输入中找到有效的抖音链接，请粘贴包含 https://v.douyin.com/... 的分享内容")
    else:
        execute_pipeline(
            url=processed,
            style=style,
            enable_humanize=humanize,
            with_images=with_images,
            content_type=content_type,
        )
        st.rerun()
```

删除 `st.info("🔗 已自动提取链接")` 冗余提示（`st.caption` 实时预览已覆盖该需求）。

#### 改动 4：`clear_btn` 处理追加 `processed_url` 重置（第 1355 行）

```python
# 修复前
for k in ("logs", "result_data", "pipeline_state", "run_id"):
    st.session_state[k] = _DEFAULTS[k]

# 修复后
for k in ("logs", "result_data", "pipeline_state", "run_id", "processed_url"):
    st.session_state[k] = _DEFAULTS[k]
```

### 影响范围

- 仅修改 `streamlit_app.py`，不涉及 `pipeline.py`、`run.bat` 等其他文件
- 不影响已完成的下载/转录缓存，断点续跑逻辑保持不变
- `execute_pipeline()` 函数签名和内部逻辑完全不变