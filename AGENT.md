<!--
  定位说明：本文档是项目 Python Agent 系统（agent/ 目录）的架构设计文档和行为规约，
  定义的是自定义 Agent 系统的内部行为规则（Pydantic 模型、LangGraph 工作流等），
  而非 CodeBuddy AI 编码助手的约束规则。

  CodeBuddy AI 的行为约束请参见：.codebuddy/rules/ 和 .codebuddy/settings.json
-->

# Agent Workflow 行为规约 v1.0

> **规约性质**：本文档定义 AI Agent 在代码编辑、内容生成、系统操作等任务中的**强制行为规则**。
> 所有 Agent 实例（含交互式、自动化、Pipeline 驱动）均须遵守本规约。

---

## 一、核心工作流规则（三条铁律）

### 规则 1：执行前搜索增强（Search-Before-Act）

**强制要求**：在执行任何非平凡操作之前，Agent 必须先执行搜索/检索以获取充分上下文。

| 操作类型 | 搜索要求 | 工具 |
|---------|---------|------|
| 代码修改 | 搜索项目中的相关代码、依赖引用、测试覆盖 | `search_content`, `search_file`, `read_file` |
| 技术决策 | 搜索官方文档、最新 API 变更、已知问题 | `web_search`, `web_fetch` |
| 领域知识 | 检索知识库获取回答 | `RAG_search` |
| 数据分析 | 读取输入文件完整内容 | `read_file` |

**禁止行为**：
- 基于假设或过时知识直接生成代码
- 在未确认文件内容前执行 `replace_in_file`

---

### 规则 2：执行后审查校验（Review-and-Decide）

**强制要求**：执行任何代码写入/修改后，必须进行结构化审查，产生明确的审查结论。

审查使用 Pydantic `Reflection` 模型：

```python
class Reflection(BaseModel):
    """审查结果 - 对齐 LangGraph Reflexion 官方 cool_classes.py"""
    missing: str | None   # 输出中缺少的必要内容
    superfluous: str | None  # 输出中多余/不相关的内容
    score: int | None     # 0-100 综合评分
    is_sufficient: bool   # 输出是否达标
```

审查后**必须**明确判断状态：
- **PASS** — 输出达标，任务完成
- **FIXABLE** — 存在具体问题，可通过修改修复
- **BLOCKED** — 存在不可逾越的障碍（缺少权限、数据不可用等）

---

### 规则 3：不达标时迭代修正（Loop-Until-Pass）

**强制要求**：当审查结果为 FIXABLE 时，自动进入修正循环。

```
┌─────────────────────────────────────────────────┐
│              Evaluator-Optimizer 循环             │
│                                                  │
│  search → execute → evaluate ──PASS──→ END       │
│                       │                          │
│                       FIXABLE                    │
│                       │                          │
│                       ▼                          │
│                      fix → search ──→ (循环)      │
│                       │                          │
│                      BLOCKED → END (报告原因)      │
└─────────────────────────────────────────────────┘
```

**关键约束**：
- **max_iterations = 5**：最多 5 轮迭代，超过则停止并报告
- **每轮必须有改进**：停滞迭代（连续两轮无改进）立即停止
- **反思必须结构化**：每轮生成 `Reflection` 对象，包含具体 `missing` 和 `superfluous`
- **失败报告**：最终无法达标时，必须输出明确的失败原因和建议

---

## 二、完成协议

Agent 完成任务后，必须返回以下四种状态之一：

| 状态 | 含义 | 触发条件 |
|------|------|---------|
| `DONE` | 任务成功完成，所有标准满足 | 审查评分 ≥ 80，无缺失项 |
| `DONE_WITH_CONCERNS` | 任务完成但存在已知风险 | 审查通过但有 `missing` 非关键项 |
| `BLOCKED` | 任务无法完成，有明确阻塞原因 | 缺少权限/数据/API 不可用 |
| `NEEDS_CONTEXT` | 需要补充信息才能继续 | 用户输入不足，需要澄清 |

---

## 三、护栏分层架构

```
Layer 1: InputGuardrail  — 输入校验（过滤恶意/违规请求）
Layer 2: PolicyGuardrail — 策略合规（内容审核、版权检查）
Layer 3: OutputGuardrail — 输出校验（格式验证、安全检查）
```

### HITL（人机回环）触发条件

以下情况**必须**停止并请求人工介入：

1. **高风险操作**：删除文件、修改 `.git/config`、执行 `git push --force`
2. **不确定决策**：存在多种合理方案且判断标准不明确
3. **护栏拦截**：输入/输出被护栏标记为高风险
4. **连续失败**：同一操作 3 次修正仍不通过

---

## 四、工具权限声明

| 权限级别 | 工具范围 | 使用条件 |
|---------|---------|---------|
| **READ** | `read_file`, `search_content`, `search_file` 等 | 无需确认 |
| **WRITE** | `write_to_file`, `replace_in_file` | 无需确认 |
| **DELETE** | `delete_file` | 需用户确认 |
| **EXEC** | `execute_command`（`git push`, `force` 等） | 需用户确认 |
| **EXEC_WORKSPACE** | `execute_command`（workspace 内安全命令） | 无需确认 |

---

## 五、可观测性要求

所有 Agent 运行实例应产生以下可观测输出：

- **Trace ID**：每次运行的唯一标识
- **迭代日志**：每轮 search/execute/evaluate 的输入输出
- **审查记录**：每轮 `Reflection` 对象快照
- **错误详情**：异常堆栈 + 上下文快照
- **性能指标**：各阶段耗时、Token 消耗

---

## 六、版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.1.0 | 2026-07-08 | Agent v0.2.0：接入 DeepSeek LLM API（新增 LLMClient），重写 _generate_draft 从骨架到生产，增强 default_evaluator 支持 LLM 驱动评估，集成 Agent/Runner 到 pipeline.py WriteStage，新增 74 个单元测试（types/guardrails/evaluator/config/llm_client） |
| v1.0.1 | 2026-07-08 | 代码质量修正：补充 PolicyGuardrail 三层护栏完整化、消除 graph.py 与 agent.py 评估器重复、接入护栏管线与工作记忆到工作流 |
| v1.0 | 2026-07-08 | 初始版本，定义三条核心规则、完成协议、护栏分层 |
