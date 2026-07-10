# CLAUDE.md

## 项目概述

今日头条自动化写作与上传系统。核心管线：选题/热点抓取 → AI 写作生成 → 违规检测 → 发布上传。

## 技术栈

- **语言**: Python（首选），Node.js/TypeScript（浏览器自动化侧）
- **AI 平台对接**: DeepSeek API, Claude API
- **浏览器自动化**: Terminator MCP, Chrome CDP, Playwright
- **发布平台**: 今日头条（mp.toutiao.com / 头条号后台）

## 项目结构

```
AIToutiao/
├── src/
│   ├── content/       # AI 写作、内容生成
│   ├── compliance/    # 违规检测、敏感词过滤
│   ├── upload/        # 浏览器自动化上传
│   └── topics/        # 选题、热点抓取
├── tests/
├── outputs/           # 生成的文章/草稿输出
└── data/              # 素材库、模板、热词表
```

## 核心约定

- 所有生成内容落盘到 `outputs/`，按日期分目录：`outputs/YYYY-MM-DD/`
- 发布前必须走违规检测管线
- API Key 等敏感配置放环境变量，不写进代码
- 头条文案字数控制在 800-2000 字（微头条 300-500 字）

## 常用技能

| 技能 | 用途 |
|------|------|
| `laohan-chuangzuo` | 口播稿/文章写作引擎 |
| `laohan-weigui` | 抖音/头条文案违规检测 |
| `laohan-redian` | AI 热点抓取 |
| `browser-cdp` | 浏览器自动化（复用登录态） |
| `delegate-to-deepseek` | 批量任务派给 DeepSeek 执行 |
| `create-project-backup` | 创建项目备份 |

## 注意事项

- Windows 环境，使用 Git Bash 终端
- 今日头条后台需保持登录态，优先用 CDP 复用 cookie
- 发布频率控制，避免触发平台限流

---

## Obsidian Knowledge Brain — Auto-Maintained Blocks

<!-- ═══════════════════════════════════════════════════════════ -->
<!-- The two COMPILED blocks below are auto-maintained by compiler.py. DO NOT EDIT MANUALLY. -->
<!-- ═══════════════════════════════════════════════════════════ -->

<!-- COMPILED:RULES_START -->
| Rule ID | Title | Category | Applies To | Status |
|---------|-------|----------|------------|--------|
<!-- COMPILED:RULES_END -->

<!-- COMPILED:PROJECTS_START -->
| Project | Decisions | Pitfalls | Last Session |
|---------|-----------|----------|-------------|
| aitoutiao | 0 | 0 | 2026-06-30 |
<!-- COMPILED:PROJECTS_END -->

---

## Session Annotation Rules (Knowledge Brain Sensory System)

> **Priority 0 — MANDATORY. NO EXCEPTIONS.**
> These annotations feed the knowledge brain. Every un-annotated decision is lost knowledge.
> Every un-annotated error will be repeated.

### [DECISION] — Appended to EVERY technical decision

Format (inline, single line at end of reply):

```
[DECISION: <one-line summary> | context: <why this choice>]
```

Example: `[DECISION: Use browser-act chrome type instead of chrome-direct | context: avoid Chrome remote debugging prompts]`

### [ERROR] — Appended to EVERY resolved error

Format (inline, single line at end of reply):

```
[ERROR: type=<from-error-taxonomy> | resolution=<how fixed>]
```

Example: `[ERROR: type=api-network_gfw_block | resolution=改用 hellotik.app 下载 + videocompress.ai 转录]`

### [SESSION_SUMMARY] — Output at session END

Triggers when user says "好的/谢谢/完成/收尾/bye/整理" or conversation naturally concludes.

```
[SESSION_SUMMARY]
projects: [aitoutiao]
primary: aitoutiao
decisions:
  - id: TT-D<NN>
    text: "<one-liner>"
    context: "<why>"
errors:
  - type: "<from error-taxonomy>"
    resolution: "<how fixed>"
    repeated_from: [<session-ids>]
summary: "<2 sentences summarizing the session>"
[/SESSION_SUMMARY]
```

### Knowledge Brain Paths

| 资源 | 路径 |
|------|------|
| Vault 根 | `knowledge-brain/` |
| 规则库 | `knowledge-brain/00-Rules/` |
| 项目记忆 | `knowledge-brain/01-Projects/aitoutiao/Memory/` |
| 决策日志 | `knowledge-brain/01-Projects/aitoutiao/Memory/decisions.md` |
| 踩坑记录 | `knowledge-brain/01-Projects/aitoutiao/Memory/pitfalls.md` |
| 错误分类 | `knowledge-brain/04-Feedback/error-taxonomy.md` |
| 脚本 | `knowledge-brain/scripts/`
