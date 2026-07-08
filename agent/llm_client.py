"""
LLM 客户端 — 封装 OpenAI SDK 调用 DeepSeek API

对齐 toutiao-auto-publisher/backend/ai_writer.py 的 AIWriter._call_ai() 模式。
使用 openai SDK 通过 OpenAI 兼容接口调用 DeepSeek API。

参考: toutiao-auto-publisher/backend/ai_writer.py (第845-882行)
"""

from __future__ import annotations

from typing import Any

from openai import OpenAI


class LLMClient:
    """
    LLM 调用客户端，封装 OpenAI 兼容 API 调用。

    与 AIWriter._call_ai() 保持一致的调用模式：
        client.chat.completions.create(
            model=model,
            messages=[{"role": "system", ...}, {"role": "user", ...}],
            max_tokens=max_tokens,
            temperature=temperature,
        )

    使用示例:
        client = LLMClient(
            api_key="sk-...",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
        )
        text = client.generate(prompt="你好", system_prompt="你是助手")
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ):
        """
        初始化 LLM 客户端。

        Args:
            api_key: API 密钥（DeepSeek API key）。
            base_url: API 端点 URL。
            model: 模型名称。
            temperature: LLM 温度参数。
            max_tokens: 最大输出 token 数。
        """
        if not api_key:
            raise ValueError(
                "LLMClient 需要 api_key。请设置环境变量 AI_API_KEY 或直接传入。"
            )

        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        # 初始化 OpenAI 客户端（指向 DeepSeek 兼容接口）
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """
        调用 LLM 生成文本。

        对齐 AIWriter._call_ai() 的调用模式。

        Args:
            prompt: 用户提示词（必填）。
            system_prompt: 系统提示词（可选，作为 system message）。
            temperature: 温度参数，不传则使用实例默认值。
            max_tokens: 最大 token 数，不传则使用实例默认值。

        Returns:
            LLM 返回的文本内容。

        Raises:
            RuntimeError: 当 API 调用失败时抛出。
        """
        # 构造消息列表
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens or self.max_tokens,
                temperature=(
                    temperature
                    if temperature is not None
                    else self.temperature
                ),
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            raise RuntimeError(f"LLM API 调用失败: {e}") from e

    @classmethod
    def from_config(cls, config: Any) -> "LLMClient":
        """
        从 RunConfig 实例创建 LLMClient。

        Args:
            config: RunConfig 实例（来自 agent.config）。

        Returns:
            LLMClient 实例。
        """
        return cls(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

    def __repr__(self) -> str:
        return (
            f"LLMClient(model={self.model}, "
            f"base_url={self.base_url}, "
            f"temperature={self.temperature}, "
            f"max_tokens={self.max_tokens})"
        )
