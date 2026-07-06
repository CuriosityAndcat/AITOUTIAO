---
name: ytdlp-cookies-fix
overview: 为 yt-dlp 下载阶段添加浏览器 Cookies 支持，解决抖音 "Fresh cookies are needed" 错误。自动从 Chrome/Edge/Firefox 获取 cookies 并回退尝试，同时在侧边栏增加 Cookies 来源配置项。
todos:
  - id: add-session-defaults
    content: 在 _DEFAULTS 字典中新增 cookie_source 和 cookie_file 两个 session_state 键，默认值分别为 "auto" 和空字符串
    status: completed
  - id: add-cookie-to-ydl-opts
    content: 修改 step_download() 中的 ydl_opts 构建逻辑，根据 session_state 配置注入 cookiesfrombrowser 或 cookiefile 参数，内置依次尝试 chrome/edge/firefox 的自动探测
    status: completed
    dependencies:
      - add-session-defaults
  - id: add-sidebar-download-settings
    content: 在 render_sidebar() 中新增"下载设置"折叠面板，包含 cookies 来源选择（自动/Chrome/Edge/Firefox/cookies文件）和 cookies.txt 文件路径输入框
    status: completed
    dependencies:
      - add-session-defaults
---

## 问题

yt-dlp 下载抖音视频时报错 "Fresh cookies (not necessarily logged in) are needed"，因为抖音现在要求请求携带浏览器 cookies 才能访问视频资源。

## 修复目标

- 为 yt-dlp 添加浏览器 cookies 支持，自动尝试从 Chrome / Edge / Firefox 提取 cookies
- 同时支持手动指定 `cookies.txt` 文件路径作为备用方案
- 在侧边栏添加"下载设置"面板，让用户可见和配置 cookies 来源
- 自动尝试失败时，给出清晰的错误提示和操作指引

## 核心功能

1. **自动浏览器 cookies 提取**：依次尝试 Chrome → Edge → Firefox，首次成功即用
2. **手动 cookies.txt 支持**：用户可指定 Netscape 格式的 cookies 文件路径
3. **会话级配置持久化**：cookies 设置保存在 `session_state` 中，刷新不丢失
4. **降级容错**：自动尝试全部失败后，给出"请用浏览器打开抖音网页后重试"的提示

## 技术方案

### 实现策略

修改 `streamlit_app.py` 中 3 个位置，最小化改动范围：

1. **`_DEFAULTS` 字典**：新增 `cookie_source` 和 `cookie_file` 两个 session_state 键
2. **`step_download()` 函数**：在 `ydl_opts` 中注入 cookies 配置，内置自动浏览器尝试逻辑
3. **`render_sidebar()` 函数**：新增可折叠的"下载设置"面板

### 关键设计决策

**为什么用 session_state 而非 PipelineState？**

- cookies 配置属于 UI 层面设置，不应随流水线状态序列化到 JSON 文件
- 用户切换浏览器后无需重建运行记录即可立即生效

**自动浏览器探测策略**

- 按 `chrome → edge → firefox` 顺序尝试，因为 Chrome 在国内用户量最大
- 探测失败不阻塞流程，降级为无 cookies 尝试（让 yt-dlp 自行报错）
- 探测成功的浏览器名写入日志，方便用户确认

**cookiesfrombrowser vs cookiefile**

- `cookiesfrombrowser` 是 `yt-dlp>=2023.10.16` 的 Python API 参数，值为 `("browser_name",)` 元组
- `cookiefile` 指向 Netscape 格式文件，当用户手动提供时使用
- 两者互斥：优先 `cookie_file`，无则用 `cookiesfrombrowser`

### 实现注意事项

- yt-dlp 的 `cookiesfrombrowser` 在某些 Windows 环境下可能因浏览器锁而失败，需要用 `try/except` 包裹
- 日志中应明确展示使用了哪个浏览器或 cookies 文件
- `cookiefile` 路径需校验文件是否存在