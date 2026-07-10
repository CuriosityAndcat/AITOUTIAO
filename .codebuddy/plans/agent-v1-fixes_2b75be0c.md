---
name: agent-v1-fixes
overview: 修复 Agent 骨架 v0.1 中 5 个代码质量问题：补充 PolicyGuardrail、消除 graph.py 与 agent.py 重复评估器、接入 GuardrailPipeline 和 WorkingMemory 到工作流、更新 AGENT.md 版本记录。
todos:
  - id: add-policy-guardrail
    content: 在 agent/guardrails.py 中新增 PolicyGuardrail 类，继承 BaseGuardrail，实现内容审核和版权检查规则
    status: completed
  - id: enhance-evaluator
    content: 增强 agent/agent.py 中 default_evaluator，添加 task 关键词相关性检查且通过分改为 85
    status: completed
  - id: fix-graph-dedup
    content: 修正 agent/graph.py：删除 _default_llm_evaluator 和 _calculate_score 重复函数，统一引用 agent.py 的 default_evaluator；在 _search_node 和 _execute_node 中接入 GuardrailPipeline 护栏检查；在 _search_node 和 _fix_node 中维护 WorkingMemory 状态
    status: completed
    dependencies:
      - add-policy-guardrail
      - enhance-evaluator
  - id: extend-state-and-runner
    content: 扩展 agent/state.py 新增 working_memory 字段；修正 agent/runner.py 在 run_sync 中初始化 WorkingMemory 实例并注入到 AgentState 初始字典
    status: completed
  - id: update-init-and-agentspec
    content: 更新 agent/__init__.py 新增 PolicyGuardrail 导出并升版本号到 0.1.1；更新 AGENT.md 追加 v1.0.1 版本变更记录
    status: completed
    dependencies:
      - add-policy-guardrail
---

## 背景

Agent 系统骨架 v0.1 已完成 10 个核心文件的编码并提交到 GitHub，但经过全面代码质量审核发现 5 个需要修正的问题，涉及代码重复、运行时未接入、功能缺失等。

## 修正清单

- **P1 补充 PolicyGuardrail**：AGENT.md 定义了三层护栏（InputGuardrail / PolicyGuardrail / OutputGuardrail），但 guardrails.py 只实现了 Layer 1 和 Layer 3，缺少 Layer 2 的策略合规护栏（内容审核、版权检查）。
- **P2 消除评估器重复**：graph.py 和 agent.py 各自定义了一个默认评估器函数，逻辑不一致。graph.py 版本额外检查 task 是否在 draft 中且通过分 85，agent.py 版本只检查长度且通过分 80。需要统一到 agent.py 并补充缺失的 task 相关性检查。
- **P3 接入 GuardrailPipeline**：GuardrailPipeline 和 GuardrailResult 已在 graph.py 导入但从未在任何节点函数中调用。需要在 search 节点接入 InputGuardrail，在 execute 节点生成 draft 后接入 OutputGuardrail。
- **P4 接入 WorkingMemory**：WorkingMemory 已在 memory.py 定义且 graph.py 导入，但在 runner.py 未初始化、graph.py 未维护。需要让 runner.py 创建实例并注入 AgentState，graph.py 在各节点同步更新 search_context。
- **P5 更新版本记录**：AGENT.md 当前版本为 v1.0，需要追加 v1.0.1 (2026-07-08) 变更记录，标注此次质量修正。

## 技术栈

- Python 3.9+
- Pydantic 2.x
- LangGraph StateGraph API

## 修改策略

所有修改严格遵循 AGENT.md 行为规约，不改变已定义的模块间 API 契约，只做增量补充和消歧。

## 各文件修改要点

### 1. agent/guardrails.py — 新增 PolicyGuardrail

- 在 OutputGuardrail 类之后、GuardrailPipeline 之前，插入 `PolicyGuardrail` 类
- 继承 `BaseGuardrail`，实现 `check()` 方法
- 包含基础规则：内容合规关键词检测（涉政、涉黄、涉暴敏感词示例）、版权声明检测（禁止全文引用未授权内容）
- 更新顶部 docstring 三层护栏说明已完整

### 2. agent/agent.py — 增强 default_evaluator

- 在现有关注项列表中新增 task 相关性检查：如果 `task` 中的关键词不在 `draft` 中出现至少一个，则追加遗漏项
- 通过分从 80 提升为 85（与 graph.py 原逻辑一致）
- 保持函数签名不变（draft, task, _state）

### 3. agent/graph.py — 核心修正（三合一）

- **删除重复代码**：移除 `_default_llm_evaluator` 函数（第 330-368 行）和 `_calculate_score` 函数（第 371-381 行）
- **统一评估器引用**：`_evaluate_node` 中将局部导入改为 `from agent.agent import default_evaluator`
- **接入护栏管线**：在 `_search_node` 中，对 task 执行 InputGuardrail 检查；在 `_execute_node` 生成 draft 后执行 OutputGuardrail 检查。不通过时设置 next_action="BLOCKED" 和相应 error。
- **接入 WorkingMemory**：在 `_search_node` 中从 state 提取 working_memory（需先在 runner.py 注入），将 search_results 的 findings 拼接到 working_memory.search_context；在 `_fix_node` 中将 reflection.feedback 追加到 working_memory.reflections。

### 4. agent/runner.py — 初始化 WorkingMemory

- 在 `run_sync` 的 state 初始化字典中，新增 `"working_memory": WorkingMemory(task=task, max_iterations=cfg.max_iterations)` 字段
- 在 `run_sync` 开头添加 `from agent.memory import WorkingMemory` 导入

### 5. agent/state.py — 扩展 AgentState

- 在 AgentState TypedDict 中新增 `working_memory: WorkingMemory` 字段（放在 search_results 之后），用于工作流图中传递 WorkingMemory 实例

### 6. agent/**init**.py — 更新导出

- 在 guardrails 导入段新增 `PolicyGuardrail`
- 在 `__all__` 列表新增 `"PolicyGuardrail"`
- 更新 `__version__` 为 `"0.1.1"`

### 7. AGENT.md — 追加版本记录

- 在版本历史表格中追加一行：v1.0.1 / 2026-07-08 / 代码质量修正：补充 PolicyGuardrail、消除评估器重复、接入护栏管线与工作记忆