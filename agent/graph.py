"""
AgentGraph — Evaluator-Optimizer 工作流图构建器

严格对齐 LangGraph StateGraph API

对齐框架: LangGraph (https://github.com/langchain-ai/langgraph)
参考源码:
    - langgraph.graph.StateGraph — add_node / add_edge / add_conditional_edges / compile
    - langgraph.graph.message.add_messages — message reducer
    - examples/reflexion/reflexion/graph.py — Reflexion agent graph

工作流图结构:

    ┌──────────────────────────────────────────────────────┐
    │                Evaluator-Optimizer 循环               │
    │                                                      │
    │  START → search → execute → evaluate                 │
    │                   ▲           │                      │
    │                   │         ┌─┼─┐                    │
    │                   │      PASS  │  FIXABLE            │
    │                   │       │    │    │                │
    │                   │      END    │  fix               │
    │                   │            │    │                │
    │                   └────────────┘    │                │
    │                         │           │                │
    │                     BLOCKED→ END    │                │
    │                                     │                │
    │                               search (循环)           │
    └──────────────────────────────────────────────────────┘

节点函数签名: func(state: AgentState) -> dict[str, Any]
路由函数签名: router(state: AgentState) -> str
"""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, StateGraph

from agent.config import RunConfig
from agent.guardrails import (
    GuardrailPipeline,
    GuardrailResult,
    InputGuardrail,
    OutputGuardrail,
    PolicyGuardrail,
)
from agent.memory import WorkingMemory
from agent.state import AgentState
from agent.types import AgentStatus, Reflection


class AgentGraph:
    """
    Evaluator-Optimizer 图构建器

    使用 LangGraph StateGraph API 构建完整的 Agent 工作流：
    add_node → add_edge → add_conditional_edges → compile

    使用示例:
        graph = AgentGraph.build(agent, config)
        result = graph.invoke(initial_state)
    """

    # ─── 公开 API: build ───────────────────────────────────────

    @staticmethod
    def build(agent, config: RunConfig) -> StateGraph:
        """
        构建并编译 Evaluator-Optimizer 工作流图。

        Args:
            agent: Agent 实例（来自 agent.agent.Agent）
            config: 运行配置

        Returns:
            编译后的 StateGraph 实例，可直接 invoke
        """
        builder = StateGraph(AgentState)

        # —— 注册节点 ——
        # 使用 functools.partial 绑定 agent + config
        import functools

        search_node = functools.partial(AgentGraph._search_node, agent=agent, config=config)
        execute_node = functools.partial(AgentGraph._execute_node, agent=agent, config=config)
        evaluate_node = functools.partial(AgentGraph._evaluate_node, agent=agent, config=config)
        fix_node = functools.partial(AgentGraph._fix_node, agent=agent, config=config)

        builder.add_node("search", search_node)       # type: ignore[arg-type]
        builder.add_node("execute", execute_node)     # type: ignore[arg-type]
        builder.add_node("evaluate", evaluate_node)   # type: ignore[arg-type]
        builder.add_node("fix", fix_node)             # type: ignore[arg-type]

        # —— 注册边 ——
        builder.set_entry_point("search")             # START → search
        builder.add_edge("search", "execute")         # search → execute
        builder.add_edge("execute", "evaluate")       # execute → evaluate
        builder.add_edge("fix", "search")             # fix → search（回到循环起点）

        # —— 条件分支 ——
        builder.add_conditional_edges(
            "evaluate",
            AgentGraph._router,                 # type: ignore[arg-type]
            {
                "PASS": END,
                "FIXABLE": "fix",
                "BLOCKED": END,
            },
        )

        return builder.compile()

    # ─── 路由函数 ───────────────────────────────────────────────

    @staticmethod
    def _router(state: AgentState) -> Literal["PASS", "FIXABLE", "BLOCKED"]:
        """
        条件路由函数 — 对齐 LangGraph add_conditional_edges

        根据 evaluate 节点的审查结果决定下一步。

        路由规则:
            - 迭代次数达到上限且未通过 → PASS（强制结束）
            - reflection.is_sufficient → PASS
            - 无具体反馈 → BLOCKED
            - 否则 → FIXABLE
        """
        iteration = state.get("iteration", 0)
        max_iter = state.get("max_iterations", 5)
        reflection = state.get("reflection")
        next_action = state.get("next_action", "")

        # 强制结束：达到迭代上限
        if iteration >= max_iter:
            return "PASS"

        # 审查通过
        if reflection and reflection.is_sufficient:
            return "PASS"

        # 显式阻塞信号
        if next_action == "BLOCKED":
            return "BLOCKED"

        # 无反射对象且无明确信号 → 阻塞
        if reflection is None:
            return "BLOCKED"

        # 有具体遗漏 → 可修复
        if reflection.missing:
            return "FIXABLE"

        # 默认阻塞
        return "BLOCKED"

    # ─── 节点函数 ───────────────────────────────────────────────

    @staticmethod
    def _search_node(state: AgentState, agent, config: RunConfig) -> dict[str, Any]:
        """
        搜索增强节点 — Search-Before-Act

        在执行前进行信息检索，增强上下文。
        同时执行 InputGuardrail 输入校验。
        """
        task = state.get("task", "")
        iteration = state.get("iteration", 0)
        wm = state.get("working_memory")
        search_results = list(state.get("search_results", []))

        # ── 输入护栏检查 ──
        input_pipeline = GuardrailPipeline(
            guardrails=[InputGuardrail(), PolicyGuardrail()],
            fail_fast=True,
        )
        guard_results = input_pipeline.run(task)
        if not input_pipeline.is_all_passed(guard_results):
            failed = next((r for r in guard_results if not r.passed), None)
            return {
                "search_results": search_results,
                "iteration": iteration,
                "next_action": "BLOCKED",
                "error": f"输入护栏拦截: {failed.reason if failed else '未知原因'}",
                "status": AgentStatus.BLOCKED,
            }

        # 如果有自定义 search_provider，使用它
        if agent.search_provider:
            try:
                from agent.types import SearchResult
                results = agent.search_provider(task, dict(state))
                search_results.extend(results)
            except Exception:
                pass

        # ── 同步 WorkingMemory ──
        if wm is not None:
            findings_text = "; ".join(
                getattr(r, "findings", "") for r in search_results
                if hasattr(r, "findings") and getattr(r, "findings", "")
            )
            if findings_text:
                wm.search_context = f"{wm.search_context}; {findings_text}".strip("; ")

        return {
            "search_results": search_results,
            "iteration": iteration,  # 搜索不消耗迭代计数
            "working_memory": wm,
        }

    @staticmethod
    def _execute_node(state: AgentState, agent, config: RunConfig) -> dict[str, Any]:
        """
        执行节点 — 生成/执行任务

        这里是 LLM 调用的核心位置。
        当前是骨架版本，使用简单的模板填充，
        后续迭代接入 LLM API。

        生成 draft 后执行 OutputGuardrail 输出校验。
        """
        task = state.get("task", "")
        search_results = state.get("search_results", [])

        # 构造增强的上下文
        context_parts = [task]
        if search_results:
            findings = "\n".join(
                r.findings for r in search_results if hasattr(r, "findings")
            )
            if findings:
                context_parts.append(f"\n搜索增强上下文：\n{findings}")

        # 使用 agent 的 instructions 作为 system prompt
        # 此处是骨架版本，实际执行会调用 LLM
        draft = _generate_draft(
            task=task,
            instructions=agent.instructions,
            search_context=search_results,
        )

        # ── 输出护栏检查 ──
        output_pipeline = GuardrailPipeline(
            guardrails=[OutputGuardrail(), PolicyGuardrail()],
            fail_fast=True,
        )
        guard_results = output_pipeline.run(draft)
        if not output_pipeline.is_all_passed(guard_results):
            failed = next((r for r in guard_results if not r.passed), None)
            return {
                "draft": draft,
                "next_action": "BLOCKED",
                "status": AgentStatus.BLOCKED,
                "error": f"输出护栏拦截: {failed.reason if failed else '未知原因'}",
            }

        return {
            "draft": draft,
        }

    @staticmethod
    def _evaluate_node(state: AgentState, agent, config: RunConfig) -> dict[str, Any]:
        """
        评估节点 — Review-and-Decide

        使用评估器（自定义或默认）审查 execute 节点的输出。
        """
        from agent.agent import default_evaluator

        draft = state.get("draft", "")
        task = state.get("task", "")
        iteration = state.get("iteration", 0) + 1
        reflections = list(state.get("reflections", []))

        # 使用自定义评估器或默认评估器（统一来自 agent.py）
        evaluator = agent.evaluator or default_evaluator
        reflection = evaluator(draft, task, dict(state))

        # 确保分数存在（默认评估器已设置，自定义评估器可能未设置）
        if reflection.score is None:
            score = 80
            if reflection.missing:
                score -= min(30, len(reflection.missing) // 10)
            if reflection.superfluous:
                score -= min(20, len(reflection.superfluous) // 10)
            reflection.score = max(0, min(100, score))

        reflections.append(reflection)

        status = AgentStatus.DONE
        next_action = "PASS"
        error = ""

        if reflection.is_sufficient:
            status = AgentStatus.DONE if reflection.score >= 80 else AgentStatus.DONE_WITH_CONCERNS
            next_action = "PASS"
        elif iteration >= config.max_iterations:
            status = AgentStatus.DONE_WITH_CONCERNS
            next_action = "PASS"  # 达到上限，强制结束
            error = f"达到最大迭代次数 {config.max_iterations}，停止修正"
        elif reflection.missing:
            status = ""
            next_action = "FIXABLE"
        else:
            status = AgentStatus.BLOCKED
            next_action = "BLOCKED"
            error = reflection.feedback or "审查未通过但无明确修正建议"

        return {
            "reflection": reflection,
            "reflections": reflections,
            "iteration": iteration,
            "next_action": next_action,
            "status": status if status else state.get("status", ""),
            "final_output": draft if status else "",
            "error": error,
        }

    @staticmethod
    def _fix_node(state: AgentState, agent, config: RunConfig) -> dict[str, Any]:
        """
        修正节点 — Loop-Until-Pass 中的修正步骤

        根据审查反馈修改草稿，然后回到 search 节点重新增强。
        """
        draft = state.get("draft", "")
        reflection = state.get("reflection")
        wm = state.get("working_memory")

        if reflection is None:
            return {"draft": draft}

        # ── 同步 WorkingMemory 反思记录 ──
        if wm is not None and reflection.feedback:
            wm.add_reflection(reflection.feedback)

        # 构造修正 prompt
        fix_prompt = f"""根据以下反馈修正草稿：

原始草稿：
{draft}

审查反馈：
- 缺失内容：{reflection.missing or '无'}
- 多余内容：{reflection.superfluous or '无'}
- 改进建议：{reflection.feedback or '无'}

请修正草稿，补充缺失内容，移除多余部分。"""

        # 此处是骨架版本，实际修正会调用 LLM
        revised = _generate_draft(
            task=state.get("task", ""),
            instructions=fix_prompt,
            search_context=state.get("search_results", []),
        )

        return {
            "draft": revised,
            "working_memory": wm,
        }


# ─── 辅助函数 ───────────────────────────────────────────────────


def _generate_draft(
    task: str,
    instructions: str,
    search_context: list | None = None,
) -> str:
    """
    生成草稿（骨架版）。

    后续迭代中替换为实际 LLM API 调用。
    """
    context_str = ""
    if search_context:
        from agent.types import SearchResult
        findings = (
            r.findings for r in search_context
            if isinstance(r, SearchResult) and r.findings
        )
        context_str = "; ".join(findings)

    return (
        f"[Agent 生成草稿]\n"
        f"任务: {task}\n"
        f"指令: {instructions[:200]}...\n"
        + (f"搜索上下文: {context_str}\n" if context_str else "")
        + f"\n--- 此处为骨架版输出，后续接入 LLM API ---"
    )
