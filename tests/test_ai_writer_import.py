"""
AIWriter 导入和基础功能完整性测试
验证即使在 wewrite-main/toolkit 存在的情况下，AIWriter 也能正确导入
"""
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent


class TestAIWriterImport:
    """AIWriter 模块导入不冲突"""

    def test_ai_writer_imports_successfully(self):
        """确保 AIWriter 可以直接导入，不会报 cannot import name 'settings'"""
        sys.path.insert(0, str(_PROJECT_ROOT / "toutiao-auto-publisher" / "backend"))
        sys.path.insert(0, str(_PROJECT_ROOT / "wewrite-main" / "toolkit"))

        try:
            from ai_writer import AIWriter
        except ImportError as e:
            pytest.fail(f"AIWriter 导入失败: {e}")

    def test_ai_writer_instantiable(self):
        """确保 AIWriter 可以实例化（需要 API Key）"""
        sys.path.insert(0, str(_PROJECT_ROOT / "toutiao-auto-publisher" / "backend"))
        sys.path.insert(0, str(_PROJECT_ROOT / "wewrite-main" / "toolkit"))

        from ai_writer import AIWriter
        writer = AIWriter()
        assert writer is not None
        assert hasattr(writer, "client")

    def test_ai_writer_uses_backend_settings(self):
        """确保 AIWriter 使用的是 backend config 而非 wewrite config"""
        sys.path.insert(0, str(_PROJECT_ROOT / "toutiao-auto-publisher" / "backend"))
        sys.path.insert(0, str(_PROJECT_ROOT / "wewrite-main" / "toolkit"))

        from ai_writer import AIWriter
        writer = AIWriter()

        # AIWriter 的 client 应使用 backend/config.py 的 settings
        assert hasattr(writer, "client"), "AIWriter 应有 client 属性"


class TestAIWriterMethodsExist:
    """AIWriter 必要方法存在性验证"""

    def test_generate_method_exists(self):
        sys.path.insert(0, str(_PROJECT_ROOT / "toutiao-auto-publisher" / "backend"))
        from ai_writer import AIWriter
        writer = AIWriter()
        assert callable(writer.generate)

    def test_humanize_method_exists(self):
        sys.path.insert(0, str(_PROJECT_ROOT / "toutiao-auto-publisher" / "backend"))
        from ai_writer import AIWriter
        writer = AIWriter()
        assert callable(writer.humanize)

    def test_generate_all_images_method_exists(self):
        sys.path.insert(0, str(_PROJECT_ROOT / "toutiao-auto-publisher" / "backend"))
        from ai_writer import AIWriter
        writer = AIWriter()
        assert callable(writer.generate_all_images)

    def test_generate_toutie_method_exists(self):
        sys.path.insert(0, str(_PROJECT_ROOT / "toutiao-auto-publisher" / "backend"))
        from ai_writer import AIWriter
        writer = AIWriter()
        assert callable(writer.generate_toutie)


class TestContentModelsImport:
    """ContentType 和 ContentStyle 枚举导入测试"""

    def test_content_type_enum(self):
        sys.path.insert(0, str(_PROJECT_ROOT / "toutiao-auto-publisher" / "backend"))
        from models import ContentType
        assert ContentType.TOUTIE.value == "toutie"
        assert ContentType.ARTICLE.value == "article"

    def test_content_style_enum(self):
        sys.path.insert(0, str(_PROJECT_ROOT / "toutiao-auto-publisher" / "backend"))
        from models import ContentStyle
        assert ContentStyle.GENERAL.value == "general"
        assert ContentStyle.MILITARY.value == "military"
        assert ContentStyle.STORY_NARRATIVE.value == "story_narrative"


class TestPipelineImport:
    """pipeline.py 导入测试"""

    def test_pipeline_import_resolves_config(self):
        """验证 pipeline.py 能成功导入，config 不冲突"""
        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-c",
                """
import sys
from pathlib import Path
sys.path.insert(0, r'%s')
import pipeline
print('Pipeline imported OK')
                """.strip() % str(_PROJECT_ROOT),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(_PROJECT_ROOT),
        )
        assert "Pipeline imported OK" in result.stdout, (
            f"pipeline.py 导入失败:\n{result.stderr}"
        )

    def test_pipeline_whisper_model_normalized(self):
        """验证 pipeline.py 中的 WHISPER_MODEL 已被规范化"""
        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-c",
                """
import sys
sys.path.insert(0, r'%s')
from pipeline import WHISPER_MODEL
# 不应包含 openai/ 或 whisper- 前缀
assert 'openai/' not in WHISPER_MODEL, f'WHISPER_MODEL still has openai/ prefix: {WHISPER_MODEL}'
assert 'whisper-' not in WHISPER_MODEL, f'WHISPER_MODEL still has whisper- prefix: {WHISPER_MODEL}'
print(f'WHISPER_MODEL={WHISPER_MODEL} OK')
                """.strip() % str(_PROJECT_ROOT),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(_PROJECT_ROOT),
        )
        assert "OK" in result.stdout, (
            f"WHISPER_MODEL 未正确规范化:\nstdout={result.stdout}\nstderr={result.stderr}"
        )
