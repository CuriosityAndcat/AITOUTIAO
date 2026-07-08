"""
测试 agent/llm_client.py — LLMClient

使用 mock 验证 API 调用格式，不实际发起网络请求。
"""
import pytest
from unittest.mock import patch, MagicMock

from agent.config import RunConfig


class TestLLMClient:
    """LLMClient 初始化测试"""

    def _make_mock_client(self, **kwargs):
        """创建 Mock 的 OpenAI 客户端来避免 httpx proxies 兼容性问题"""
        with patch("agent.llm_client.OpenAI") as mock_openai:
            mock_instance = MagicMock()
            mock_openai.return_value = mock_instance
            from agent.llm_client import LLMClient
            return LLMClient(**kwargs), mock_instance

    def test_basic_init(self):
        """基本初始化"""
        client, _ = self._make_mock_client(
            api_key="test-key",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
        )
        assert client.model == "deepseek-chat"
        assert client.base_url == "https://api.deepseek.com/v1"
        assert client.temperature == 0.7
        assert client.max_tokens == 2000

    def test_custom_params(self):
        """自定义参数"""
        client, _ = self._make_mock_client(
            api_key="custom-key",
            base_url="https://custom.api.com/v1",
            model="gpt-4",
            temperature=0.3,
            max_tokens=4000,
        )
        assert client.temperature == 0.3
        assert client.max_tokens == 4000
        assert client.model == "gpt-4"

    def test_missing_api_key(self):
        """缺少 API key 应抛出异常"""
        with pytest.raises(ValueError, match="api_key"):
            from agent.llm_client import LLMClient
            LLMClient(api_key="")

    def test_from_config(self, mock_env):
        """从 RunConfig 创建 LLMClient"""
        with patch("agent.llm_client.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            from agent.llm_client import LLMClient

            config = RunConfig(
                api_key="config-test-key",
                base_url="https://api.test.com/v1",
                model="test-model",
                temperature=0.5,
                max_tokens=1000,
            )
            client = LLMClient.from_config(config)
            assert client.api_key == "config-test-key"
            assert client.base_url == "https://api.test.com/v1"
            assert client.model == "test-model"
            assert client.temperature == 0.5
            assert client.max_tokens == 1000

    def test_from_config_env(self, mock_env, monkeypatch):
        """从环境变量自动填充 RunConfig"""
        monkeypatch.setenv("AI_API_KEY", "env-api-key")
        monkeypatch.setenv("AI_BASE_URL", "https://env-api.com/v1")

        with patch("agent.llm_client.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            from agent.llm_client import LLMClient

            config = RunConfig()
            client = LLMClient.from_config(config)
            assert client.api_key == "env-api-key"
            assert client.base_url == "https://env-api.com/v1"

    def test_repr(self):
        """__repr__ 测试"""
        client, _ = self._make_mock_client(
            api_key="test-key",
            model="deepseek-chat",
        )
        repr_str = repr(client)
        assert "LLMClient" in repr_str
        assert "deepseek-chat" in repr_str


class TestLLMClientGenerate:
    """LLMClient.generate() mock 测试"""

    @pytest.fixture
    def client(self):
        with patch("agent.llm_client.OpenAI") as mock_openai:
            mock_instance = MagicMock()
            mock_openai.return_value = mock_instance
            from agent.llm_client import LLMClient
            return LLMClient(
                api_key="test-key",
                base_url="https://api.test.com/v1",
                model="test-model",
            )

    def test_generate_basic(self, client):
        """基本调用测试"""
        mock_choice = MagicMock()
        mock_choice.message.content = "AI 生成的内容"
        client._client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        result = client.generate(prompt="你好", system_prompt="你是助手")

        assert result == "AI 生成的内容"
        # 验证调用参数
        call_kwargs = client._client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "test-model"
        assert call_kwargs["max_tokens"] == 2000
        assert call_kwargs["temperature"] == 0.7
        assert len(call_kwargs["messages"]) == 2
        assert call_kwargs["messages"][0]["role"] == "system"
        assert call_kwargs["messages"][0]["content"] == "你是助手"
        assert call_kwargs["messages"][1]["role"] == "user"
        assert call_kwargs["messages"][1]["content"] == "你好"

    def test_generate_no_system_prompt(self, client):
        """无 system_prompt 的调用"""
        mock_choice = MagicMock()
        mock_choice.message.content = "响应"
        client._client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        result = client.generate(prompt="问一个问题")

        assert result == "响应"
        # 只有一条 user message
        call_kwargs = client._client.chat.completions.create.call_args[1]
        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0]["role"] == "user"

    def test_generate_custom_params(self, client):
        """自定义 temperature 和 max_tokens"""
        mock_choice = MagicMock()
        mock_choice.message.content = "自定义参数响应"
        client._client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        result = client.generate(
            prompt="测试",
            temperature=0.2,
            max_tokens=500,
        )

        call_kwargs = client._client.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.2
        assert call_kwargs["max_tokens"] == 500

    def test_generate_strips_whitespace(self, client):
        """验证返回内容去除首尾空白"""
        mock_choice = MagicMock()
        mock_choice.message.content = "  \n  内容有空白  \n  "
        client._client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        result = client.generate(prompt="测试")
        assert result == "内容有空白"
        assert not result.startswith(" ")
        assert not result.endswith(" ")

    def test_generate_api_error(self, client):
        """API 调用失败应抛出 RuntimeError"""
        client._client.chat.completions.create.side_effect = Exception("API 请求失败")

        with pytest.raises(RuntimeError, match="LLM API 调用失败"):
            client.generate(prompt="测试")
