"""
共享 pytest fixtures — 测试基础设施
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

# ── 确保项目根目录在 sys.path ──
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ── 预加载 backend/config 防止冲突（与 streamlit_app.py 一致）──
import importlib.util as _iu
_backend_cfg = _PROJECT_ROOT / "toutiao-auto-publisher" / "backend" / "config.py"
if "config" not in sys.modules:
    _cfg_spec = _iu.spec_from_file_location("config", str(_backend_cfg))
    _cfg_mod = _iu.module_from_spec(_cfg_spec)
    sys.modules["config"] = _cfg_mod
    _cfg_spec.loader.exec_module(_cfg_mod)


@pytest.fixture
def temp_output_dir():
    """创建临时输出目录并在测试后清理。"""
    with tempfile.TemporaryDirectory(prefix="aitoutiao_test_") as tmp:
        yield Path(tmp)


@pytest.fixture
def mock_env(monkeypatch):
    """设置最小化的环境变量，避免依赖 .env 文件。"""
    monkeypatch.setenv("AI_API_KEY", "test-key-123456")
    monkeypatch.setenv("AI_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("AI_MODEL", "deepseek-chat")
    monkeypatch.setenv("WHISPER_MODEL", "small")
    monkeypatch.setenv("WHISPER_DEVICE", "cpu")
    monkeypatch.setenv("WHISPER_COMPUTE_TYPE", "int8")


@pytest.fixture
def clean_sys_modules():
    """清理 sys.modules 中的测试污染，每次测试前后自动恢复。"""
    before = set(sys.modules.keys())
    yield
    after = set(sys.modules.keys())
    for mod in after - before:
        if mod.startswith("test_") or mod in ("config",):
            continue
        if mod not in ("pipeline", "streamlit_app", "transcribe"):
            try:
                del sys.modules[mod]
            except KeyError:
                pass
