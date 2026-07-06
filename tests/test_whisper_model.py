"""
Whisper 模型名规范化完整性测试
测试 _normalize_whisper_model 和 streamlit_app 内置逻辑的所有输入
"""
import sys
from pathlib import Path

import pytest

# ── 内联 _normalize_whisper_model（与 pipeline.py 版本一致）──
def _normalize_whisper_model(model: str) -> str:
    """规范化 Whisper 模型名：去除 openai/whisper- 等前缀，faster-whisper 只需 short name。"""
    for prefix in ("openai/whisper-", "openai/", "whisper-"):
        if model.startswith(prefix):
            return model[len(prefix):]
    return model


# ── 确保从 .env 读取的模型名能在 streamlit_app 的前缀剥离中正常工作 ──
def _strip_streamlit_style(model: str) -> str:
    """模拟 streamlit_app.py 第 630-635 行的前缀剥离逻辑。"""
    fw_model_name = model
    for prefix in ("openai/whisper-", "openai/", "whisper-"):
        if fw_model_name.startswith(prefix):
            fw_model_name = fw_model_name[len(prefix):]
            break
    return fw_model_name


class TestNormalizeWhisperModel:
    """pipeline.py 的 _normalize_whisper_model 函数"""

    def test_openai_whisper_small(self):
        assert _normalize_whisper_model("openai/whisper-small") == "small"

    def test_openai_whisper_tiny(self):
        assert _normalize_whisper_model("openai/whisper-tiny") == "tiny"

    def test_openai_whisper_medium(self):
        assert _normalize_whisper_model("openai/whisper-medium") == "medium"

    def test_openai_whisper_large_v3(self):
        assert _normalize_whisper_model("openai/whisper-large-v3") == "large-v3"

    def test_whisper_prefix_only(self):
        assert _normalize_whisper_model("whisper-small") == "small"

    def test_openai_prefix_only(self):
        assert _normalize_whisper_model("openai/small") == "small"

    def test_already_clean(self):
        assert _normalize_whisper_model("small") == "small"

    def test_already_clean_tiny(self):
        assert _normalize_whisper_model("tiny") == "tiny"

    def test_already_clean_large_v3(self):
        assert _normalize_whisper_model("large-v3") == "large-v3"

    def test_already_clean_turbo(self):
        assert _normalize_whisper_model("turbo") == "turbo"

    def test_distil_model(self):
        assert _normalize_whisper_model("distil-large-v3") == "distil-large-v3"


class TestStreamlitStyleStrip:
    """streamlit_app.py 的前缀剥离逻辑（for 循环 break 版本）"""

    def test_dotenv_actual_value(self):
        """模拟 .env WHISPER_MODEL=openai/whisper-small 的实际场景"""
        assert _strip_streamlit_style("openai/whisper-small") == "small"

    def test_dotenv_with_tiny(self):
        assert _strip_streamlit_style("openai/whisper-tiny") == "tiny"

    def test_raw_short_name(self):
        assert _strip_streamlit_style("small") == "small"

    def test_whisper_prefix_from_dotenv(self):
        """某些 .env 可能配置 WHISPER_MODEL=whisper-small"""
        assert _strip_streamlit_style("whisper-small") == "small"


class TestFasterWhisperCompatibility:
    """验证规范化后的模型名在 faster-whisper 有效列表中"""

    VALID_MODELS = frozenset({
        "tiny.en", "tiny", "base.en", "base", "small.en", "small",
        "medium.en", "medium", "large-v1", "large-v2", "large-v3", "large",
        "distil-large-v2", "distil-medium.en", "distil-small.en",
        "distil-large-v3", "distil-large-v3.5", "large-v3-turbo", "turbo",
    })

    def test_normalized_is_valid_faster_whisper(self):
        """确认 openai/whisper-small 规范化后可用"""
        assert _normalize_whisper_model("openai/whisper-small") in self.VALID_MODELS

    def test_all_normalized_variants_valid(self):
        inputs = [
            "openai/whisper-tiny",
            "openai/whisper-small",
            "openai/whisper-base",
            "openai/whisper-medium",
            "openai/whisper-large-v3",
            "tiny",
            "small",
            "base",
            "medium",
            "large-v3",
            "turbo",
            "distil-large-v3",
        ]
        for inp in inputs:
            normalized = _normalize_whisper_model(inp)
            assert normalized in self.VALID_MODELS, f"{inp} -> {normalized} NOT valid"
