---
name: agentic-workflow-rules-setup
overview: 按照 Agentic AI 四模式流程，为项目创建 CodeBuddy 行为规则体系和权限约束配置，实现元工作流的自动化触发与安全管控。
todos:
  - id: create-agentic-workflow-rule
    content: 创建 .codebuddy/rules/agentic-workflow.mdc，包含 YAML 元数据（agent-requested 类型）和五个模块（复杂度判定、反射协议、规划协议、多角色审查、迭代修正），控制在 300 行以内
    status: completed
  - id: create-settings-json
    content: 创建 .codebuddy/settings.json，配置 permissions.deny（保护敏感文件/禁止危险命令）、permissions.allow（常用安全命令）、permissions.ask（git push 等需审批），设置 defaultMode 为 default
    status: completed
  - id: fix-agent-md-positioning
    content: 修改 AGENT.md 头部，添加 HTML 注释定位说明，明确区分 Python Agent 系统设计文档与 CodeBuddy AI 行为规则
    status: completed
  - id: reflect-and-review
    content: 执行反射审查：对三个文件逐一进行 5 维度评分（正确性/集成性/安全性/性能/可维护性），输出 Reflection 结果（score + missing + superfluous + verdict），评分
    status: completed
    dependencies:
      - create-agentic-workflow-rule
      - create-settings-json
      - fix-agent-md-positioning
---

## 用户需求

为 d:\AIToutiao 项目创建 CodeBuddy 官方约束体系，包含三个文件：

1. **`.codebuddy/rules/agentic-workflow.mdc`**：agent-requested 类型的行为规则，实现吴恩达 Agentic AI 四大模式——复杂度判定、反射协议、规划协议、多角色审查、迭代修正。仅在复杂任务（多文件修改、架构决策、系统重构）时自动触发，简单任务（单文件小改、问答）直接跳过。
2. **`.codebuddy/settings.json`**：权限硬约束配置，deny 层保护 .env 等敏感文件、禁止 rm -rf 等危险命令；allow 层放行常用安全命令（npm/pip/git）；ask 层对 git push 等操作需审批；defaultMode 设为 default。
3. **`AGENT.md` 头部修正**：在文件开头添加定位说明，明确这是 Python Agent 系统设计文档，非 CodeBuddy AI 行为规则，防止 CodeBuddy 误读后重复注入上下文。

## 核心功能

- **复杂度自适应**：AI 根据任务描述自动判定是否需要加载工作流规则，简单任务零额外开销
- **反射自审查**：复杂任务执行后，AI 自动进行多维度自我审查（正确性、集成性、安全性、性能、可维护性），评分 0-100
- **迭代修正**：评分 < 80 时自动修正，最多 3 轮，每轮须有实质改进
- **权限硬约束**：deny 规则覆盖敏感文件保护和危险命令拦截，优先级最高
- **上下文高效**：规则文件控制在 300 行以内，agent-requested 类型不总是占用 Token

## 技术方案

### 文件概述

创建 2 个新文件、修改 1 个现有文件，均依赖 CodeBuddy 官方约束机制的现有标准。

### 实现细节

#### 1. `.codebuddy/rules/agentic-workflow.mdc`（新建，核心规则文件）

**格式**：CodeBuddy Rules 标准 `.mdc` 格式（YAML frontmatter + Markdown 正文）

**YAML 元数据设计**：

```
---
description: >
  Agentic Workflow Rule — 当任务涉及多文件修改、架构设计、系统重构、模块拆分、
  性能优化、安全审计、代码审查等复杂场景时自动激活。实现吴恩达 Agentic AI 的
  四大模式：Reflection（反射自审查）、Planning（规划先于执行）、Tool Use（搜索增强）、
  Multi-Agent（多角色模拟）。触发关键词：重构、架构、优化、多模块、系统设计、
  从零搭建、性能、安全审查、全面测试、大改
alwaysApply: false
enabled: true
updatedAt: 2026-07-08T14:00:00.000Z
provider:
---
```

**正文内容结构（共五个模块，控制在 300 行内）**：

| 模块 | 行数预算 | 内容 |
| --- | --- | --- |
| 模块一：复杂度判定 | ~30 行 | Tier 1 简单（直接执行）、Tier 2 中等（反射模式）、Tier 3 复杂（规划+反射+可选多角色）的判定标准表格 |
| 模块二：反射协议 | ~80 行 | 5 维度检查清单（正确性/集成性/安全性/性能/可维护性各 20 分），Reflection 输出格式（score/missing/superfluous/verdict），PASS(≥80)/FIXABLE(<80)/BLOCKED 三种结论 |
| 模块三：规划协议 | ~60 行 | 规划触发条件、Plan 结构要求（步骤ID/目标/文件/依赖/验证标准）、输出 todo_write 格式、等待用户确认流程 |
| 模块四：多角色审查 | ~50 行 | 四角色定义（Code Reviewer/Security Auditor/Architect/User Advocate），角色切换协议，适用场景（仅在 Tier 3 复杂任务时按需启用） |
| 模块五：迭代修正 | ~50 行 | Evaluator-Optimizer 循环流程，max_iterations=3，停滞检测（连续两轮无改进立即停止），失败时的 BLOCKED 报告格式 |
| 边界情况说明 | ~30 行 | 简单任务不触发反射、单文件修改跳过规划、技术问答无需审查、上下文不足时降级处理 |


**关键设计决策**：

- `alwaysApply: false` + `provider:` 留空 = agent-requested 类型，AI 根据 description 中的关键词和场景描述自动判断是否加载
- 反射 5 维度评分体系与项目现有 AGENT.md 中的 Pydantic Reflection 模型对齐（但用 Markdown 表格重述，不引用 Python 代码）
- 迭代上限 3 轮（而非 AGENT.md 中的 5 轮），因为 CodeBuddy 单次对话的上下文成本更高
- 禁止在规则中引用文件路径或项目特定代码，确保规则可跨项目复用

#### 2. `.codebuddy/settings.json`（新建，权限硬约束）

**结构设计**：

```
{
  "permissions": {
    "deny": [
      "Bash(rm -rf *)",
      "Bash(curl:*)",
      "Bash(wget:*)",
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./secrets/**)",
      "Read(./.git/config)",
      "Edit(./.git/config)",
      "Bash(git push --force:*)",
      "Bash(git push -f:*)",
      "Bash(git reset --hard:*)",
      "Bash(shutdown:*)",
      "Bash(reboot:*)"
    ],
    "allow": [
      "Bash(npm:*)",
      "Bash(pip:*)",
      "Bash(python:*)",
      "Bash(git status:*)",
      "Bash(git diff:*)",
      "Bash(git add:*)",
      "Bash(git commit:*)",
      "Bash(git log:*)",
      "Bash(git branch:*)",
      "Bash(dir:*)",
      "Bash(ls:*)",
      "Bash(cat:*)",
      "Bash(echo:*)",
      "Bash(mkdir:*)",
      "Bash(type:*)",
      "Bash(where:*)",
      "Bash(whoami:*)"
    ],
    "ask": [
      "Bash(git push:*)",
      "Bash(git pull:*)",
      "Bash(git merge:*)",
      "Bash(git rebase:*)",
      "Bash(del:*)",
      "Bash(rm:*)",
      "Bash(move:*)",
      "Bash(ren:*)"
    ]
  },
  "defaultMode": "default"
}
```

**关键设计决策**：

- `deny` 数组放在最前面（官方文档明确 "deny 先于任何 mode 生效"），保护敏感文件 + 拦截危险命令
- `allow` 放行项目常用 Python/Node.js 栈的安全命令
- `ask` 对文件删除、Git 推送等操作需用户审批
- `defaultMode: "default"` 采用标准询问模式，不自动接受编辑

#### 3. `AGENT.md` 头部修正（修改现有文件）

在现有文件第一行（`# Agent Workflow 行为规约 v1.0` 之前）插入定位说明块：

```markdown
<!--
  定位说明：本文档是项目 Python Agent 系统（agent/ 目录）的架构设计文档和行为规约，
  定义的是自定义 Agent 系统的内部行为规则（Pydantic 模型、LangGraph 工作流等），
  而非 CodeBuddy AI 编码助手的约束规则。

  CodeBuddy AI 的行为约束请参见：.codebuddy/rules/ 和 .codebuddy/settings.json
-->
```

**设计意图**：使用 HTML 注释格式，人类可读但 LLM 可能忽略——但 CodeBuddy 官方文档说明它会加载 AGENT.md 全文入上下文，因此这个注释也会被读取，起到定位澄清作用。

### 性能与可靠性

- **Token 消耗**：agent-requested 规则仅在触发时加载正文（~300 行 ≈ 2000 Token），不触发时仅加载 description（~200 Token），相比 alwaysApply（每次 2000 Token）节省 90% 上下文开销
- **权限安全**：deny 层在工具调用前拦截，零性能开销
- **向后兼容**：三个文件均为新增或头部追加，不修改任何现有业务逻辑