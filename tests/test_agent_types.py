"""
测试 agent/types.py — 数据模型验证
"""
import pytest

from agent.types import (
    AgentStatus,
    Reflection,
    AnswerQuestion,
    ReviseAnswer,
    ResearchQuery,
    SearchResult,
    TaskResult,
)


class TestAgentStatus:
    """AgentStatus 常量测试"""

    def test_valid_statuses(self):
        """验证所有合法状态常量存在"""
        assert AgentStatus.DONE == "DONE"
        assert AgentStatus.DONE_WITH_CONCERNS == "DONE_WITH_CONCERNS"
        assert AgentStatus.BLOCKED == "BLOCKED"
        assert AgentStatus.NEEDS_CONTEXT == "NEEDS_CONTEXT"

    def test_valid_statuses_set(self):
        """验证 VALID_STATUSES 包含所有状态"""
        expected = {"DONE", "DONE_WITH_CONCERNS", "BLOCKED", "NEEDS_CONTEXT"}
        assert AgentStatus.VALID_STATUSES == expected


class TestReflection:
    """Reflection 模型测试"""

    def test_default_values(self):
        """测试默认值"""
        r = Reflection()
        assert r.missing is None
        assert r.superfluous is None
        assert r.score is None
        assert r.is_sufficient is False
        assert r.feedback is None

    def test_passed_reflection(self):
        """测试通过的审查结果"""
        r = Reflection(
            is_sufficient=True,
            score=90,
            feedback="输出合格",
        )
        assert r.is_sufficient is True
        assert r.score == 90
        assert r.missing is None

    def test_failed_reflection(self):
        """测试未通过的审查结果"""
        r = Reflection(
            missing="缺少关键论据",
            superfluous="多余废话",
            is_sufficient=False,
            score=40,
            feedback="需要补充论据",
        )
        assert r.is_sufficient is False
        assert r.missing == "缺少关键论据"
        assert r.superfluous == "多余废话"
        assert r.score == 40

    def test_score_range_validation(self):
        """测试分值范围验证"""
        # Pydantic 应校验 ge=0, le=100
        with pytest.raises(Exception):
            Reflection(score=-1, is_sufficient=False)

        with pytest.raises(Exception):
            Reflection(score=101, is_sufficient=False)


class TestAnswerQuestion:
    """AnswerQuestion 模型测试"""

    def test_basic(self):
        aq = AnswerQuestion(
            answer="这是答案",
            reasoning="这是推理过程",
        )
        assert aq.answer == "这是答案"
        assert aq.reasoning == "这是推理过程"
        assert aq.research_queries is None

    def test_with_followup(self):
        """带后续研究查询的测试"""
        aq = AnswerQuestion(
            answer="部分确定的答案",
            reasoning="需要进一步验证",
            research_queries=[
                ResearchQuery(query="补充查询", rationale="需要更多数据"),
            ],
        )
        assert len(aq.research_queries) == 1
        assert aq.research_queries[0].query == "补充查询"


class TestReviseAnswer:
    """ReviseAnswer 模型测试"""

    def test_basic(self):
        ra = ReviseAnswer(
            revised_answer="修正后的回答",
            changes_made=["补充了数据来源", "修正了错误表述"],
        )
        assert ra.revised_answer == "修正后的回答"
        assert len(ra.changes_made) == 2
        assert ra.reflection_incorporated is True

    def test_reflection_not_incorporated(self):
        """反思未纳入时的情况"""
        ra = ReviseAnswer(
            revised_answer="未修改的回答",
            changes_made=[],
            reflection_incorporated=False,
        )
        assert ra.reflection_incorporated is False
        assert ra.changes_made == []


class TestSearchResult:
    """SearchResult 模型测试"""

    def test_basic(self):
        sr = SearchResult(
            queries=["搜索关键词"],
            findings="搜索结果摘要",
            confidence=0.8,
        )
        assert sr.queries == ["搜索关键词"]
        assert sr.findings == "搜索结果摘要"
        assert sr.confidence == 0.8
        assert sr.sources == []

    def test_with_sources(self):
        sr = SearchResult(
            queries=["q1", "q2"],
            findings="综合搜索结果",
            sources=["source1.com", "source2.com"],
            confidence=0.9,
        )
        assert len(sr.sources) == 2


class TestTaskResult:
    """TaskResult 模型测试"""

    def test_success_result(self):
        tr = TaskResult(
            status=AgentStatus.DONE,
            output="成功完成的内容",
            iterations=2,
        )
        assert tr.status == "DONE"
        assert tr.output == "成功完成的内容"
        assert tr.iterations == 2
        assert tr.reflections == []
        assert tr.error is None

    def test_failed_result(self):
        tr = TaskResult(
            status=AgentStatus.BLOCKED,
            output="",
            iterations=1,
            error="护栏拦截：包含敏感内容",
        )
        assert tr.status == "BLOCKED"
        assert tr.error == "护栏拦截：包含敏感内容"


class TestResearchQuery:
    """ResearchQuery 模型测试"""

    def test_basic(self):
        rq = ResearchQuery(
            query="人工智能发展趋势",
            rationale="需要了解最新技术动向",
        )
        assert rq.query == "人工智能发展趋势"
        assert rq.rationale == "需要了解最新技术动向"
