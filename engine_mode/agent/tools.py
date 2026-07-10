"""
工具系统 — 严格对齐 OpenAI function_tool 装饰器模式

对齐框架: OpenAI Agents SDK (https://github.com/openai/openai-agents-python)
参考源码: src/agents/function_tool.py — function_tool 装饰器 + FunctionTool

function_tool 将普通 Python 函数包装为 Agent 可调用的工具。
ToolRegistry 提供工具的统一注册和查找。
"""

from __future__ import annotations

import functools
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class FunctionTool:
    """
    函数工具包装 — 对齐 OpenAI FunctionTool

    将一个 Python 可调用对象包装为 Agent 可用工具，
    自动提取函数签名、文档字符串和参数 schema。
    """

    name: str
    """工具名称，用于 LLM function calling。"""

    description: str
    """工具描述，LLM 据此判断何时调用。"""

    func: Callable
    """包装的原始函数。"""

    params_schema: dict[str, Any] = field(default_factory=dict)
    """参数 JSON Schema，自动从函数签名提取。"""

    # ─── 对齐 OpenAI FunctionTool 的关键属性 ───
    strict: bool = False
    """是否启用严格模式参数校验（OpenAI structured output）。"""

    require_confirmation: bool = False
    """调用前是否需要用户确认（高风险操作）。"""

    def __call__(self, **kwargs) -> Any:
        """执行工具调用"""
        return self.func(**kwargs)

    def to_openai_schema(self) -> dict[str, Any]:
        """转换为 OpenAI function calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.params_schema,
                "strict": self.strict,
            },
        }


def function_tool(
    name: str | None = None,
    description: str | None = None,
    strict: bool = False,
    require_confirmation: bool = False,
) -> Callable:
    """
    function_tool 装饰器 — 对齐 OpenAI @function_tool

    将普通函数注册为 Agent 可调用的工具。

    使用示例:
        @function_tool(name="search_web", description="搜索互联网获取最新信息")
        def search_web(query: str) -> str:
            ...

        # 或直接使用函数名
        @function_tool
        def get_weather(city: str) -> str:
            ...
    """

    def decorator(func: Callable) -> FunctionTool:
        tool_name = name or func.__name__
        tool_desc = description or func.__doc__ or ""

        # 自动提取参数 schema
        params = _extract_params_schema(func)

        tool = FunctionTool(
            name=tool_name,
            description=tool_desc.strip(),
            func=func,
            params_schema=params,
            strict=strict,
            require_confirmation=require_confirmation,
        )

        # 保持被装饰函数的元数据
        functools.update_wrapper(tool, func)
        return tool

    return decorator


def _extract_params_schema(func: Callable) -> dict[str, Any]:
    """从函数签名自动提取参数 JSON Schema"""
    sig = inspect.signature(func)
    properties = {}
    required = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue

        param_type = "string"
        if param.annotation is not inspect.Parameter.empty:
            anno = param.annotation
            if anno is int:
                param_type = "integer"
            elif anno is float:
                param_type = "number"
            elif anno is bool:
                param_type = "boolean"
            elif anno is list:
                param_type = "array"

        properties[param_name] = {"type": param_type}

        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


# ─── ToolRegistry ─────────────────────────────────────────────────


@dataclass
class ToolRegistry:
    """
    工具注册表 — 管理一组工具的注册与查找

    使用示例:
        registry = ToolRegistry()
        registry.register(search_tool)
        registry.register(write_tool)
        tools = registry.to_openai_schemas()
    """

    tools: dict[str, FunctionTool] = field(default_factory=dict)
    """按名称索引的工具字典。"""

    def register(self, tool: FunctionTool) -> None:
        """注册一个工具"""
        if tool.name in self.tools:
            raise ValueError(f"工具名称冲突: {tool.name}")
        self.tools[tool.name] = tool

    def register_func(
        self,
        func: Callable,
        name: str | None = None,
        description: str | None = None,
        **kwargs,
    ) -> FunctionTool:
        """注册一个普通函数为工具"""
        tool = function_tool(name=name, description=description, **kwargs)(func)
        self.register(tool)
        return tool

    def get(self, name: str) -> FunctionTool | None:
        """按名称查找工具"""
        return self.tools.get(name)

    def list_all(self) -> list[FunctionTool]:
        """列出所有已注册工具"""
        return list(self.tools.values())

    def to_openai_schemas(self) -> list[dict[str, Any]]:
        """导出所有工具为 OpenAI function calling 格式"""
        return [tool.to_openai_schema() for tool in self.tools.values()]

    def __len__(self) -> int:
        return len(self.tools)

    def __contains__(self, name: str) -> bool:
        return name in self.tools
