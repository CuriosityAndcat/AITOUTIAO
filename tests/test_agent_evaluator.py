"""
测试 agent/agent.py — default_evaluator 评估器
"""
import pytest

from agent.agent import default_evaluator
from agent.types import Reflection


class TestDefaultEvaluator:
    """default_evaluator 规则检查测试"""

    def test_empty_draft(self):
        """空输出应被评估为不通过"""
        result = default_evaluator("", "写一篇关于AI的文章")
        assert isinstance(result, Reflection)
        assert result.is_sufficient is False
        assert result.score == 0
        assert result.missing is not None

    def test_whitespace_draft(self):
        """纯空白输出应被评估为不通过"""
        result = default_evaluator("   \n  ", "写一篇文章")
        assert result.is_sufficient is False
        assert result.score == 0

    def test_short_draft(self):
        """过短输出应被评估为不通过"""
        result = default_evaluator("短文", "写一篇关于AI发展的详细分析")
        assert result.is_sufficient is False
        assert result.score == 40
        assert "过短" in (result.missing or "")

    def test_keyword_mismatch(self):
        """输出不包含任务关键词应被评估为不通过"""
        result = default_evaluator(
            "今天天气很好，适合出去散步。" * 5,
            "写一篇关于人工智能未来发展的深度分析文章",
        )
        assert result.is_sufficient is False
        assert "关键词" in (result.missing or "")
        assert result.score == 40

    def test_passing_draft(self):
        """正常输出应通过"""
        result = default_evaluator(
            "人工智能是当今时代最重要的技术发展方向之一。" * 5,
            "人工智能 技术 发展",  # 使用简短关键词
        )
        assert result.is_sufficient is True
        assert result.score == 85
        assert result.feedback == "输出合格"

    def test_contains_keyword(self):
        """输出包含关键词时应通过"""
        result = default_evaluator(
            "深度学习是人工智能的一个分支，它利用多层神经网络来学习数据的特征表示。" * 5,
            "深度学习 技术",  # 使用简短关键词
        )
        assert result.is_sufficient is True

    def test_with_state_ignored(self):
        """_state 参数应被忽略（向后兼容）"""
        result = default_evaluator(
            "合格内容测试文本" * 10,  # 足够 50+ 字符
            "合格 内容",  # 使用简短关键词确保匹配
            _state={"extra": "should_be_ignored"},
        )
        assert result.is_sufficient is True

    def test_chinese_keyword_detection(self):
        """中文关键词检测"""
        result = default_evaluator(
            "这是一个测试。" * 10,
            "关于天气变化"
        )
        assert result.is_sufficient is False
        assert "关键词" in (result.missing or "")

    def test_no_task(self):
        """无任务描述时仅检查长度"""
        result = default_evaluator(
            "这是足够长的内容测试文本" * 5,  # 足够 50+ 字符
            "",
        )
        # 长度够、无 task 就不检查关键词 → 通过
        assert result.is_sufficient is True
