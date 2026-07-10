---
name: agent-skeleton-v1-github
overview: 创建 Agent 系统骨架初版（严格对齐 OpenAI Agents SDK + LangGraph 标准源码），提交到 GitHub 作为 v1 基线，然后进入迭代优化流程。
todos:
  - id: create-agentspec
    content: 创建项目根目录 AGENT.md — Agent Workflow 行为规约（三条规则、完成协议、护栏分层、HITL规则）
    status: completed
  - id: create-types
    content: 创建 agent/types.py — 严格对齐 LangGraph Reflexion 官方的 Reflection、AnswerQuestion、ReviseAnswer Pydantic 模型
    status: completed
  - id: create-state-config
    content: 创建 agent/state.py（LangGraph TypedDict AgentState）和 agent/config.py（OpenAI RunConfig dataclass）
    status: completed
    dependencies:
      - create-types
  - id: create-agent-core
    content: 创建 agent/agent.py（OpenAI Agent dataclass）和 agent/runner.py（Runner.run_sync/run 类方法 + RunResult）
    status: completed
    dependencies:
      - create-types
  - id: create-graph
    content: 创建 agent/graph.py — AgentGraph.build() 构建 Evaluator-Optimizer StateGraph（search→execute→evaluate→条件分支）
    status: completed
    dependencies:
      - create-state-config
  - id: create-tools-guardrails-memory
    content: 创建 agent/tools.py（function_tool + ToolRegistry）、agent/guardrails.py（InputGuardrail/OutputGuardrail）、agent/memory.py（ConversationMemory + WorkingMemory）
    status: completed
  - id: create-init
    content: 创建 agent/__init__.py — 统一导出所有公开接口
    status: completed
    dependencies:
      - create-types
      - create-agent-core
      - create-graph
      - create-tools-guardrails-memory
  - id: scan-existing-tools
    content: 使用 [subagent:code-explorer] 扫描 ai_writer.py、image_reviewer.py 等现有工具函数，为后续 tools.py 注册做准备
    status: completed
  - id: git-commit-push
    content: "将所有新文件 git add、commit（message: feat: Agent系统骨架v0.1 — LangGraph+OpenAI SDK+Reflexion对齐）、push 到 origin/main"
    status: completed
    dependencies:
      - create-agentspec
      - create-init
---

## 用户需求

创建 Agent 系统骨架 v0.1 初版，将所有核心代码文件和 AGENT.md 行为规约提交到 GitHub 仓库 `https://github.com/CuriosityAndcat/AITOUTIAO.git`，作为后续逐步优化的起点。

## 核心交付物

### 1. AGENT.md 行为规约（项目根目录）

定义 AI Agent Workflow 的三条核心规则：

- 规则1：执行前搜索增强（Search-Before-Act）
- 规则2：执行后审查校验（Review-and-Decide）
- 规则3：不达标时迭代修正（Loop-Until-Pass），max_iterations=5

### 2. agent/ 模块（10个文件）

严格对齐 LangGraph StateGraph API、OpenAI Agents SDK 和 Reflexion 官方源码标准：

| 文件 | 对齐框架 | 定义内容 |
| --- | --- | --- |
| `__init__.py` | OpenAI SDK 导出风格 | 统一导出 Agent、Runner、RunResult、Reflection 等 |
| `types.py` | LangGraph Reflexion 官方 cool_classes.py | `Reflection(missing, superfluous)`、`AnswerQuestion`、`ReviseAnswer` |
| `state.py` | LangGraph StateGraph TypedDict | `AgentState` 含消息列表 add reducer、迭代计数、审查状态 |
| `agent.py` | OpenAI Agents SDK agent.py | `Agent` dataclass（name, instructions, tools, handoffs, evaluator） |
| `runner.py` | OpenAI SDK run.py | `Runner.run_sync()`/`run()`、`RunResult(final_output, status, iterations)` |
| `config.py` | OpenAI SDK RunConfig | `RunConfig` dataclass（max_iterations=5, tracing, checkpointer） |
| `graph.py` | LangGraph StateGraph API | `AgentGraph.build()`: add_node → add_edge → add_conditional_edges → compile |
| `tools.py` | OpenAI @function_tool | `function_tool` 装饰器 + `ToolRegistry` |
| `guardrails.py` | OpenAI Guardrails | `InputGuardrail`、`OutputGuardrail`、`GuardrailResult(passed, reason)` |
| `memory.py` | Reflexion 记忆设计 | `ConversationMemory`（滑动窗口）+ `WorkingMemory`（任务状态/草稿） |


工作流节点流程：`START → search → execute → evaluate → {PASS:END | FIXABLE:fix→search | BLOCKED:END}`

## 技术栈

- Python 3.9+
- Pydantic 2.x（数据模型，项目已有）
- LangGraph（StateGraph 图编排）

## 实现方案

### 核心设计：Evaluator-Optimizer Workflow 模式

每个文件严格对齐标准框架的 API 签名和模块结构：

- **LangGraph StateGraph**：节点函数签名为 `func(state: State) → dict`，路由函数签名为 `router(state: State) → str`
- **OpenAI Agents SDK**：`Agent` 用 dataclass 定义，`Runner` 用类方法 `run_sync`/`run`
- **Reflexion**：`Reflection(missing, superfluous)` Pydantic 模型字段名与官方源码完全一致

### 代码规范

- 每个文件头部注释标注对齐的框架和源码文件
- 所有公开类和方法使用 Python 类型注解
- 使用 `from __future__ import annotations` 启用延迟注解求值

### 目录结构

```
d:/AIToutiao/
├── AGENT.md                    # 新建 — Agent Workflow 行为规约
├── agent/
│   ├── __init__.py             # 新建 — 包导出
│   ├── types.py                # 新建 — Pydantic 数据模型
│   ├── state.py                # 新建 — LangGraph State 定义
│   ├── agent.py                # 新建 — Agent dataclass
│   ├── runner.py               # 新建 — Runner 执行器
│   ├── config.py               # 新建 — RunConfig 配置
│   ├── graph.py                # 新建 — StateGraph 构建
│   ├── tools.py                # 新建 — 工具系统
│   ├── guardrails.py           # 新建 — 护栏系统
│   └── memory.py               # 新建 — 记忆管理
├── .gitignore                  # 已存在 — 覆盖 python/venv/outputs
└── pipeline.py                 # 已存在 — 后续会集成 agent 模块
```

## 子 Agent

### code-explorer

- 用途：在创建 agent 文件前，快速扫描项目中已有的 Python 工具函数（如 `ai_writer.py`、`image_reviewer.py`），确保 agent/tools.py 中的 `function_tool` 能够正确引用现有函数
- 预期结果：获取现有可调用函数的签名和路径清单，供 tools.py 注册时引用