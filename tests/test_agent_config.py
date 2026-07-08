"""
测试 agent/config.py — RunConfig 和 agent/agent.py — Agent
"""
import pytest

from agent.config import RunConfig
from agent.agent import Agent


class TestRunConfig:
    """RunConfig 配置测试"""

    def test_default_values(self):
        """测试默认值"""
        config = RunConfig()
        assert config.max_iterations == 5
        assert config.temperature == 0.7
        assert config.model == "deepseek-chat"
        assert config.max_tokens == 2000
        assert config.base_url == "https://api.deepseek.com/v1"
        assert config.tracing_enabled is True

    def test_custom_values(self):
        """测试自定义值"""
        config = RunConfig(
            max_iterations=3,
            temperature=0.3,
            model="gpt-4",
            api_key="custom-key",
            base_url="https://api.openai.com/v1",
            max_tokens=4000,
        )
        assert config.max_iterations == 3
        assert config.temperature == 0.3
        assert config.model == "gpt-4"
        assert config.api_key == "custom-key"
        assert config.base_url == "https://api.openai.com/v1"
        assert config.max_tokens == 4000

    def test_env_var_loading(self, monkeypatch):
        """测试从环境变量自动填充"""
        monkeypatch.setenv("AI_API_KEY", "env-test-key")
        monkeypatch.setenv("AI_BASE_URL", "https://env-api.example.com/v1")

        config = RunConfig()
        # __post_init__ 自动读取环境变量
        assert config.api_key == "env-test-key"
        assert config.base_url == "https://env-api.example.com/v1"

    def test_explicit_api_key_overrides_env(self, monkeypatch):
        """显式传入的 api_key 应覆盖环境变量"""
        monkeypatch.setenv("AI_API_KEY", "env-key")

        config = RunConfig(api_key="explicit-key")
        assert config.api_key == "explicit-key"

    def test_no_env_var_defaults(self):
        """无环境变量时使用默认值"""
        # api_key 默认为空字符串
        config = RunConfig()
        # 在没有设置 AI_API_KEY 环境变量的情况下，应为空字符串
        # （取决于运行环境，这里只验证类型）
        assert isinstance(config.api_key, str)

    def test_trace_id(self):
        """trace_id 测试"""
        config = RunConfig(trace_id="test-trace-123")
        assert config.trace_id == "test-trace-123"

    def test_callbacks(self):
        """callbacks 测试"""
        cb_calls = []

        def dummy_cb(event_type, state):
            cb_calls.append(event_type)

        config = RunConfig(callbacks=[dummy_cb])
        assert len(config.callbacks) == 1

        config.callbacks[0]("test_event", {})
        assert cb_calls == ["test_event"]

    def test_metadata(self):
        """metadata 测试"""
        config = RunConfig(metadata={"source": "test", "version": "0.1"})
        assert config.metadata["source"] == "test"


class TestAgent:
    """Agent 实例化测试"""

    def test_minimal_agent(self):
        """最小化 Agent 创建"""
        agent = Agent(
            name="TestAgent",
            instructions="你是一个测试助手",
        )
        assert agent.name == "TestAgent"
        assert agent.instructions == "你是一个测试助手"
        assert agent.description == ""
        assert agent.tools == []
        assert agent.handoffs == []
        assert agent.evaluator is None
        assert agent.search_provider is None
        assert agent.fixer is None

    def test_full_agent(self):
        """完整 Agent 创建"""

        def dummy_tool():
            return "tool_result"

        def dummy_evaluator(draft, task, state):
            from agent.types import Reflection
            return Reflection(is_sufficient=True, score=90)

        agent = Agent(
            name="FullAgent",
            instructions="你是完整配置的助手",
            description="完整的测试 Agent",
            tools=[dummy_tool],
            evaluator=dummy_evaluator,
        )
        assert agent.name == "FullAgent"
        assert len(agent.tools) == 1
        assert agent.evaluator is not None
        assert agent.description == "完整的测试 Agent"

    def test_empty_name_raises(self):
        """空名称应抛出 ValueError"""
        with pytest.raises(ValueError, match="name"):
            Agent(name="", instructions="指令")

        with pytest.raises(ValueError, match="name"):
            Agent(name="   ", instructions="指令")

    def test_empty_instructions_raises(self):
        """空指令应抛出 ValueError"""
        with pytest.raises(ValueError, match="instructions"):
            Agent(name="Agent", instructions="")

        with pytest.raises(ValueError, match="instructions"):
            Agent(name="Agent", instructions="   ")

    def test_default_config(self):
        """default_config 默认值"""
        agent = Agent(name="Test", instructions="test")
        assert agent.default_config.max_iterations == 5

    def test_custom_default_config(self):
        """自定义 default_config"""
        custom_config = RunConfig(max_iterations=3, temperature=0.5)
        agent = Agent(
            name="Test",
            instructions="test",
            default_config=custom_config,
        )
        assert agent.default_config.max_iterations == 3
        assert agent.default_config.temperature == 0.5

    def test_agent_with_handoffs(self):
        """多 Agent 移交测试"""
        child = Agent(name="Child", instructions="子 Agent")
        parent = Agent(
            name="Parent",
            instructions="父 Agent",
            handoffs=[child],
        )
        assert len(parent.handoffs) == 1
        assert parent.handoffs[0].name == "Child"

    def test_agent_with_search_provider(self):
        """搜索提供器测试"""

        def search_provider(task, state):
            from agent.types import SearchResult
            return [SearchResult(queries=[], findings="搜索结果")]

        agent = Agent(
            name="SearchAgent",
            instructions="有搜索能力的 Agent",
            search_provider=search_provider,
        )
        assert agent.search_provider is not None

    def test_agent_with_fixer(self):
        """修正器测试"""

        def fixer(draft, reflection, state):
            return "修正后的内容"

        agent = Agent(
            name="FixAgent",
            instructions="有修正能力的 Agent",
            fixer=fixer,
        )
        assert agent.fixer is not None
