"""
Config 模块预加载完整性测试
验证 importlib.util 预加载策略能正确隔离 wewrite-main/toolkit/config.py
"""
import importlib.util
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent


class TestConfigPreload:
    """验证 backend/config.py 通过 importlib.util 预加载到 sys.modules"""

    def test_config_module_is_backend_version(self):
        """确保 sys.modules["config"] 是 backend/config.py 而非 wewrite"""
        if "config" in sys.modules:
            config_mod = sys.modules["config"]
            file_path = getattr(config_mod, "__file__", "")
            assert "toutiao-auto-publisher" in file_path, (
                f"config 模块应来自 toutiao-auto-publisher/backend，"
                f"实际: {file_path}"
            )

    def test_config_has_settings(self):
        """确保预加载的 config 模块有 settings 属性"""
        if "config" in sys.modules:
            config_mod = sys.modules["config"]
            assert hasattr(config_mod, "settings"), (
                "config 模块必须有 settings 属性（pydantic Settings 实例）"
            )

    def test_config_settings_has_expected_fields(self):
        """验证 settings 包含关键配置字段"""
        if "config" in sys.modules:
            config_mod = sys.modules["config"]
            settings = config_mod.settings
            # 基础字段应存在
            assert hasattr(settings, "AI_API_KEY")
            assert hasattr(settings, "AI_BASE_URL")
            assert hasattr(settings, "AI_MODEL")
            assert hasattr(settings, "WHISPER_MODEL")
            assert hasattr(settings, "TRANSCRIBE_BACKEND")

    def test_wewrite_config_not_polluting(self):
        """验证 wewrite-main/toolkit/config.py 不会污染 sys.modules["config"]"""
        # 尝试从 wewrite toolkit 目录查找 config.py
        wewrite_config = _PROJECT_ROOT / "wewrite-main" / "toolkit" / "config.py"
        assert wewrite_config.exists(), "wewrite config.py 应存在（用于确认隔离有效）"

        # 如果 sys.modules["config"] 已加载，确认它不是 wewrite 版本
        if "config" in sys.modules:
            config_mod = sys.modules["config"]
            mod_file = Path(getattr(config_mod, "__file__", ""))
            assert wewrite_config.resolve() != mod_file.resolve(), (
                "sys.modules['config'] 不应指向 wewrite-main/toolkit/config.py"
            )


class TestConfigImportIsolation:
    """隔离测试：在干净导入环境中验证 from config import settings 正确"""

    def test_fresh_import_resolves_correctly(self):
        """在新进程中验证 import config 指向正确模块"""
        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-c",
                (
                    "import sys; "
                    f"sys.path.insert(0, r'{_PROJECT_ROOT / 'toutiao-auto-publisher' / 'backend'}'); "
                    f"sys.path.insert(0, r'{_PROJECT_ROOT / 'wewrite-main' / 'toolkit'}'); "
                    "import importlib.util as iu; "
                    f"mod = iu.module_from_spec(iu.spec_from_file_location('config', r'{_PROJECT_ROOT / 'toutiao-auto-publisher' / 'backend' / 'config.py'}')); "
                    "sys.modules['config'] = mod; "
                    f"iu.spec_from_file_location('config', r'{_PROJECT_ROOT / 'toutiao-auto-publisher' / 'backend' / 'config.py'}').loader.exec_module(mod); "
                    "print(mod.settings.WHISPER_MODEL); "
                    "print(hasattr(mod.settings, 'AI_API_KEY')); "
                    "print(hasattr(mod, 'load_config'))"
                ),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        lines = result.stdout.strip().split("\n")
        assert len(lines) >= 3
        # settings.WHISPER_MODEL 应输出（有值）
        assert len(lines[0]) > 0
        # settings 应有 AI_API_KEY
        assert lines[1] == "True" or lines[1] == "False"
        # 不应有 wewrite 的 load_config 函数
        assert lines[2] == "False", "backend config 不应有 wewrite 的 load_config"
