"""
Agent 定义 — 严格对齐 OpenAI Agents SDK agent.py

对齐框架: OpenAI Agents SDK (https://github.com/openai/openai-agents-python)
参考源码: src/agents/agent.py — Agent dataclass

Agent 是核心抽象：封装了 LLM 指令、可用工具、护栏和移交规则。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from agent.config import RunConfig
from agent.types import AgentStatus, Reflection


@dataclass
class Agent:
    """
    AI Agent 核心定义 — 对齐 OpenAI Agents SDK Agent dataclass

    参考: https://github.com/openai/openai-agents-python/blob/main/src/agents/agent.py

    Agent 封装了一个完整的自动化执行单元：
    - name + instructions 定义行为和目标
    - tools 提供可调用的外部能力
    - handoffs 支持多 Agent 协作
    - guards 确保安全合规
    - evaluator 实现自我审查（Reflexion 模式）

    使用示例:
        agent = Agent(
            name="ContentWriter",
            instructions="你是一个文章写作助手，按用户要求生成内容。",
            tools=[search_tool, write_tool],
        )
        result = Runner.run_sync(agent, "写一篇关于AI的文章", config=RunConfig())
    """

    # ── 身份与指令 ──
    name: str
    """Agent 唯一名称，用于日志和追踪。"""

    instructions: str
    """Agent 的行为指令（System Prompt）。"""

    description: str = ""
    """Agent 功能的简短描述，用于多 Agent 场景中的路由。"""

    # ── 能力定义 ──
    tools: list[Callable] = field(default_factory=list)
    """
    Agent 可调用的工具函数列表。
    每个工具应是 @function_tool 装饰的函数或 FunctionTool 实例。
    """

    handoffs: list[Agent] = field(default_factory=list)
    """
    可移交的子 Agent 列表。
    当 Agent 判断自身无法处理时，可将任务移交给子 Agent。
    """

    # ── 护栏 ──
    input_guardrails: list[Callable] = field(default_factory=list)
    """输入护栏列表，在执行前校验用户输入。"""

    output_guardrails: list[Callable] = field(default_factory=list)
    """输出护栏列表，在返回结果前校验 Agent 输出。"""

    # ── 评估 ──
    evaluator: Callable | None = None
    """
    评估函数，用于 Reflexion 自我审查模式。
    签名: evaluator(draft: str, task: str, state: dict) -> Reflection
    
    如果为 None，则使用默认的 LLM 评估器。
    """

    # ── 搜索增强 ──
    search_provider: Callable | None = None
    """
    搜索提供函数，在 execute 前调用。
    签名: search_provider(task: str, state: dict) -> list[SearchResult]
    """

    # ── 修正器 ──
    fixer: Callable | None = None
    """
    修正函数，在评估不通过时修复草稿。
    签名: fixer(draft: str, reflection: Reflection, state: dict) -> str
    
    如果为 None，则使用 LLM 驱动的默认修正器。
    """

    # ── 运行时配置 ──
    default_config: RunConfig = field(default_factory=RunConfig)
    """默认运行配置，可在 Runner 调用时覆盖。"""

    def __post_init__(self):
        """验证 Agent 配置的有效性"""
        if not self.name.strip():
            raise ValueError("Agent name 不能为空")
        if not self.instructions.strip():
            raise ValueError("Agent instructions 不能为空")


# ─── 内置评估器（默认 LLM 评估） ────────────────────────────────


def default_evaluator(
    draft: str,
    task: str,
    _state: dict | None = None,
    llm_client: Any = None,
) -> Reflection:
    """
    默认评估器 — 优先使用 LLM 驱动评估，不可用时降级为规则检查。

    当提供 llm_client 时，使用 LLM 对输出进行结构化评估；
    否则使用基于规则的简化评估器。

    检查维度：
    1. 输出非空
    2. 输出长度 ≥ 50 字符
    3. 任务关键词相关性（至少一个 task 关键词出现在 draft 中）
    4. 如果使用 LLM 评估，额外检查内容完整性、逻辑连贯性
    """
    # ── LLM 驱动评估（优先） ──
    if llm_client is not None:
        try:
            eval_prompt = f"""请评估以下内容是否满足任务要求。

任务描述：
{task}

生成内容：
{draft}

请从以下维度评估（用 JSON 格式回复）：
1. 内容是否完整覆盖了任务要求的关键点
2. 逻辑是否连贯清晰
3. 是否有多余或不相关的废话
4. 综合评分（0-100）
5. 是否需要修正（true/false）

请以 JSON 格式回复：
{{
  "is_sufficient": true/false,
  "score": 0-100,
  "missing": "缺失的关键内容（无则填null）",
  "superfluous": "多余的无关内容（无则填null）",
  "feedback": "改进建议"
}}"""

            response = llm_client.generate(
                prompt=eval_prompt,
                system_prompt="你是一个专业的内容质量评审专家。请严格、客观地评估。",
                temperature=0.3,  # 评估使用低温度确保一致性
            )

            # 尝试解析 JSON
            import json
            import re

            # 提取 JSON 部分（处理 LLM 可能在 JSON 外添加说明的情况）
            json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
            if json_match:
                eval_data = json.loads(json_match.group())
                return Reflection(
                    missing=eval_data.get("missing"),
                    superfluous=eval_data.get("superfluous"),
                    score=eval_data.get("score", 80),
                    is_sufficient=eval_data.get("is_sufficient", True),
                    feedback=eval_data.get("feedback"),
                )

            # JSON 解析失败，降级到规则检查
            logger = __import__("logging").getLogger(__name__)
            logger.warning("LLM 评估器 JSON 解析失败，降级到规则检查")

        except Exception as e:
            logger = __import__("logging").getLogger(__name__)
            logger.warning("LLM 评估器调用失败: %s，降级到规则检查", e)

    # ── 规则检查（Fallback） ──
    if not draft or not draft.strip():
        return Reflection(
            missing="输出为空",
            is_sufficient=False,
            score=0,
            feedback="需要生成非空输出",
        )

    # 基础检查
    concerns: list[str] = []
    if len(draft) < 50:
        concerns.append("输出过短，可能不完整")

    # 任务关键词相关性检查：task 中至少一个下划线/中文关键词出现在 draft 中
    if task:
        import re
        task_keywords = re.findall(r"[\u4e00-\u9fff\w]{2,}", task)
        if task_keywords:
            found = any(kw in draft for kw in task_keywords)
            if not found:
                concerns.append(f"输出未涉及任务关键词: {', '.join(task_keywords[:3])}")

    if concerns:
        return Reflection(
            missing="; ".join(concerns),
            is_sufficient=False,
            score=40,
            feedback="补充缺失内容后重试",
        )

    return Reflection(
        is_sufficient=True,
        score=85,
        feedback="输出合格",
    )
