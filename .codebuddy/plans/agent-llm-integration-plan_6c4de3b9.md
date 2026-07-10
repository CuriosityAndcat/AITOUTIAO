---
name: agent-llm-integration-plan
overview: 按优先级从高到低执行4个任务：1) 提交当前修改到GitHub，2) 将 Agent 骨架的 _generate_draft 接入 DeepSeek LLM API，3) 将 pipeline.py 的 WriteStage 从 HTTP API 调用改为 Agent/Runner 编排，4) 编写 agent/ 模块单元测试。
todos:
  - id: git-commit-push
    content: 提交 v0.1.1 修改到 GitHub：git add 7 个已修改文件，commit 并 push 到 origin/main
    status: completed
  - id: create-llm-client
    content: 新增 agent/llm_client.py，封装 OpenAI SDK 调用 DeepSeek API；扩展 agent/config.py 的 RunConfig 新增 api_key/base_url/max_tokens 字段
    status: completed
    dependencies:
      - git-commit-push
  - id: rewrite-generate-draft
    content: 重写 agent/graph.py 的 _generate_draft 接入 LLMClient，更新 _execute_node 和 _fix_node 传递 LLM 参数；增强 agent/agent.py 的 default_evaluator 支持可选 LLM 评估
    status: completed
    dependencies:
      - create-llm-client
  - id: integrate-pipeline
    content: 修改 pipeline.py 的 WriteStage.run()，用 Agent+Runner 编排替代直接 HTTP API 调用，保持向后兼容和降级策略
    status: completed
    dependencies:
      - rewrite-generate-draft
  - id: write-unit-tests
    content: 创建 tests/test_agent_*.py 系列单元测试，覆盖 types/guardrails/evaluator/config/llm_client 核心模块
    status: completed
    dependencies:
      - rewrite-generate-draft
  - id: update-version-final
    content: 更新 agent/__init__.py 版本号到 0.2.0，更新 AGENT.md 追加 v1.1.0 版本记录，最终验证
    status: completed
    dependencies:
      - integrate-pipeline
      - write-unit-tests
---

## 用户需求

按照优先级从高到低执行4项任务，将 Agent 系统从 v0.1.1 骨架提升到 v0.2 生产可用的版本。

## 核心任务

### 1. 提交当前修改到 GitHub

7个已修改文件需要 stage、commit 并 push 到 `https://github.com/CuriosityAndcat/AITOUTIAO.git` 的 main 分支，固化 v0.1.1 修正成果。

### 2. 接入 DeepSeek LLM API

替换 `agent/graph.py` 中的 `_generate_draft` 骨架占位函数（当前返回硬编码模板文本），改为通过 OpenAI SDK 调用 DeepSeek API 生成真实内容。同时增强 `agent/agent.py` 中的 `default_evaluator`，使其支持可选的 LLM 驱动评估。

### 3. 集成 Agent/Runner 到 pipeline.py

修改 `pipeline.py` 中的 `WriteStage.run()`，将当前直接通过 HTTP 调用 `/api/generate` 的方式替换为使用 Agent + Runner 的 Evaluator-Optimizer 闭环编排。

### 4. 编写 agent 模块单元测试

为 `agent/` 模块创建测试文件，覆盖状态流转、护栏检查、评估器逻辑、Agent 配置验证、LLM 客户端等核心组件。

## 技术栈

- 语言：Python 3.9+
- LLM SDK：openai >= 1.55.0（项目已有）
- 图编排：LangGraph StateGraph
- 数据模型：Pydantic 2.x
- 环境配置：python-dotenv

## 实现方案

### 任务1：Git Commit & Push

直接执行 git add/git commit/git push 三步操作。commit message 遵循 conventional commits 规范。

### 任务2：接入 DeepSeek LLM API

**策略**：遵循 `toutiao-auto-publisher/backend/ai_writer.py` 中已有的 OpenAI SDK 调用模式，在 agent 模块内新增一个轻量级 `LLMClient` 类，统一管理 LLM 调用。

**核心改动**：

1. **新增 `agent/llm_client.py`**

- 创建 `LLMClient` 类，封装 `openai.OpenAI` 客户端
- 从 `RunConfig` 读取 `api_key`、`base_url`、`model`、`temperature`、`max_tokens`
- 提供 `generate(prompt, system_prompt)` 方法，返回文本响应
- 遵循 `AIWriter._call_ai()` 的调用模式：`client.chat.completions.create(model=..., messages=[...], max_tokens=..., temperature=...)`

2. **扩展 `agent/config.py` 的 `RunConfig`**

- 新增字段：`api_key: str`（从环境变量 `AI_API_KEY` 读取）、`base_url: str`（从 `AI_BASE_URL` 读取，默认 `https://api.deepseek.com/v1`）、`max_tokens: int = 2000`
- 保持与现有 `.env` 配置对齐

3. **重写 `agent/graph.py` 的 `_generate_draft`**

- 接收 `LLMClient` 实例和 `RunConfig`
- 构造 system prompt = agent.instructions + search_context
- 调用 `llm_client.generate(prompt=task, system_prompt=system_prompt)`
- 添加错误处理：LLM 调用失败时 fallback 返回带错误标记的文本

4. **增强 `agent/agent.py` 的 `default_evaluator`**

- 新增可选参数 `llm_client: LLMClient | None = None`
- 当提供 `llm_client` 时，构造评估 prompt 让 LLM 判断输出质量（使用结构化输出格式）
- 当不提供时，保持规则检查作为 fallback

5. **更新 `agent/__init__.py`**

- 导出 `LLMClient`

**性能考虑**：LLMClient 在 RunConfig 级别单例化，避免每次节点调用重复初始化 OpenAI 客户端。

### 任务3：集成 Agent/Runner 到 pipeline.py

**策略**：在 `WriteStage.run()` 中构造 Agent 实例并通过 Runner.run_sync() 执行，替代当前直接 HTTP 调用。

**核心改动**：

1. **修改 `WriteStage.run()`**

- 加载转录文本后，构造 `Agent` 实例（name="ContentWriter", instructions 指定生成微头条/文章的任务描述和输出格式）
- 创建 `RunConfig` 并注入 `LLMClient`
- 调用 `Runner.run_sync(agent, task, config=config)`
- 从 `RunResult.final_output` 解析 title 和 content
- 保存输出文件（复用现有逻辑）
- 保留人工化改写（`enable_humanize`）兼容

2. **Agent 输出格式约定**

- 在 `instructions` 中规定 LLM 输出 JSON 格式：`{"title": "...", "content": "..."}`
- 在 Runner 返回后解析 JSON，fallback 时使用全文作为 content

3. **向后兼容**

- 当 LLM 调用失败时，降级回原有的 HTTP API 调用方式
- 保持 `state.outputs` 数据结构不变，确保 PublishStage 和 ImageGenStage 正常工作

### 任务4：编写单元测试

**策略**：创建 `tests/test_agent_*.py` 系列测试文件。

**测试清单**：

| 测试文件 | 覆盖范围 |
| --- | --- |
| `tests/test_agent_types.py` | Reflection/AnswerQuestion/ReviseAnswer 模型验证，AgentStatus 常量 |
| `tests/test_agent_guardrails.py` | InputGuardrail/OutputGuardrail/PolicyGuardrail 检查逻辑，GuardrailPipeline 管线执行 |
| `tests/test_agent_evaluator.py` | default_evaluator 规则检查（空输出、短输出、关键词缺失、通过） |
| `tests/test_agent_config.py` | Agent 实例化验证、RunConfig 默认值 |
| `tests/test_agent_llm_client.py` | LLMClient 初始化、环境变量读取、API 调用格式（使用 mock） |


## 目录结构

```
d:/AIToutiao/
├── agent/
│   ├── __init__.py          # [MODIFY] 新增 LLMClient 导出，升版本到 0.2.0
│   ├── config.py            # [MODIFY] RunConfig 新增 api_key/base_url/max_tokens 字段
│   ├── agent.py             # [MODIFY] default_evaluator 新增 llm_client 可选参数
│   ├── graph.py             # [MODIFY] 重写 _generate_draft 接入 LLMClient，更新 _execute_node/_fix_node 传递 LLM 参数
│   ├── llm_client.py        # [NEW] LLMClient 类，封装 OpenAI SDK 调用 DeepSeek API
│   ├── runner.py            # [MODIFY] run_sync 传递 LLMClient 给 graph 构建
│   ├── state.py             # [MODIFY] 无需改动（LLMClient 通过 config 传递）
│   └── guardrails.py        # [MODIFY] 无需改动（v0.1.1 已完成）
├── pipeline.py              # [MODIFY] WriteStage.run() 改用 Agent+Runner 编排
├── AGENT.md                 # [MODIFY] 追加 v1.1.0 版本记录
└── tests/
    ├── test_agent_types.py      # [NEW] 类型模型测试
    ├── test_agent_guardrails.py # [NEW] 护栏系统测试
    ├── test_agent_evaluator.py  # [NEW] 评估器测试
    ├── test_agent_config.py     # [NEW] Agent 配置测试
    └── test_agent_llm_client.py # [NEW] LLM 客户端测试（含 mock）
```