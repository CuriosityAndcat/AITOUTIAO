"""
PipelineState 完整性测试
测试保存/加载/断点续跑/已存在查找/标记完成
"""
import json
import sys
import tempfile
from pathlib import Path

import pytest

# ── 确保导入项目模块 ──
sys.path.insert(0, str(Path(__file__).parent.parent))

# 使用 streamlit_app 的 PipelineState（Streamlit 版本）
from streamlit_app import PipelineState, OUTPUTS_DIR


class TestPipelineStateInit:
    """状态初始化"""

    def test_default_init(self):
        state = PipelineState(input_url="https://v.douyin.com/test/")
        assert state.run_id  # 自动生成
        assert len(state.run_id) == 15  # YYYYMMDD_HHMMSS
        assert state.input_url == "https://v.douyin.com/test/"
        assert state.content_type == "toutie"
        assert state.content_style == "story_narrative"
        assert state.enable_humanize is False
        assert state.with_images is False
        assert state.completed_stages == []
        assert state.outputs == {}

    def test_full_init(self):
        state = PipelineState(
            run_id="20260705_120000",
            input_url="https://v.douyin.com/test/",
            content_type="article",
            content_style="military",
            enable_humanize=True,
            with_images=True,
            completed_stages=["download", "transcribe"],
            outputs={"generated_title": "测试标题"},
        )
        assert state.run_id == "20260705_120000"
        assert state.content_type == "article"
        assert state.enable_humanize is True
        assert state.is_done("download") is True
        assert state.is_done("write") is False

    def test_run_dir_path(self):
        state = PipelineState(
            run_id="20260705_120000",
            input_url="https://v.douyin.com/test/",
        )
        assert state.run_dir == OUTPUTS_DIR / "20260705" / "20260705_120000"
        assert state.state_file == state.run_dir / "pipeline_state.json"


class TestPipelineStateSaveLoad:
    """保存和加载"""

    def test_save_and_load(self, temp_output_dir, monkeypatch):
        monkeypatch.setattr("streamlit_app.OUTPUTS_DIR", temp_output_dir)

        state = PipelineState(
            run_id="20260705_120000",
            input_url="https://v.douyin.com/test123/",
            content_type="toutie",
            content_style="story_narrative",
            completed_stages=["download", "transcribe"],
            outputs={"transcript_text": "测试转录内容"},
        )
        state.save()

        # 验证文件存在
        assert state.state_file.exists()

        # 加载验证
        loaded = PipelineState.load("20260705_120000")
        assert loaded is not None
        assert loaded.input_url == "https://v.douyin.com/test123/"
        assert loaded.is_done("download") is True
        assert loaded.is_done("transcribe") is True
        assert loaded.is_done("write") is False
        assert loaded.outputs["transcript_text"] == "测试转录内容"

    def test_load_nonexistent(self):
        result = PipelineState.load("99990101_000000")
        assert result is None


class TestMarkDone:
    """标记阶段完成"""

    def test_mark_single_stage(self):
        state = PipelineState(input_url="https://v.douyin.com/test/")
        state.mark_done("download")
        assert state.is_done("download") is True
        assert "download" in state.completed_stages

    def test_mark_duplicate_no_double_add(self):
        state = PipelineState(input_url="https://v.douyin.com/test/")
        state.mark_done("download")
        state.mark_done("download")
        assert state.completed_stages.count("download") == 1

    def test_mark_all_stages(self):
        state = PipelineState(input_url="https://v.douyin.com/test/")
        stages = ["download", "transcribe", "write", "humanize", "generate_images", "assemble"]
        for s in stages:
            state.mark_done(s)
        assert all(state.is_done(s) for s in stages)
        assert len(state.completed_stages) == 6


class TestFindExisting:
    """查找已存在的运行记录"""

    def test_find_existing_same_url(self, temp_output_dir, monkeypatch):
        monkeypatch.setattr("streamlit_app.OUTPUTS_DIR", temp_output_dir)

        state = PipelineState(
            run_id="20260705_120000",
            input_url="https://v.douyin.com/unique-find-test/",
        )
        state.save()

        found = PipelineState.find_existing("https://v.douyin.com/unique-find-test/")
        assert found is not None
        assert found.run_id == "20260705_120000"

    def test_find_no_match(self):
        found = PipelineState.find_existing("https://v.douyin.com/nonexistent-url-xyz999/")
        assert found is None

    def test_find_multiple_returns_latest(self, temp_output_dir, monkeypatch):
        monkeypatch.setattr("streamlit_app.OUTPUTS_DIR", temp_output_dir)

        url = "https://v.douyin.com/latest-test/"
        s1 = PipelineState(run_id="20260705_100000", input_url=url)
        s1.save()
        s2 = PipelineState(run_id="20260705_120000", input_url=url)
        s2.save()

        found = PipelineState.find_existing(url)
        # 应返回最新的（按日期+时间排序）
        assert found.run_id == "20260705_120000"


class TestSaveJsonIntegrity:
    """JSON 序列化完整性"""

    def test_save_produces_valid_json(self, temp_output_dir, monkeypatch):
        monkeypatch.setattr("streamlit_app.OUTPUTS_DIR", temp_output_dir)

        state = PipelineState(
            run_id="20260705_120000",
            input_url="https://v.douyin.com/json-test/",
            outputs={"nested": {"key": [1, 2, 3]}, "unicode": "中文测试"},
        )
        state.save()

        # 确保是有效 JSON
        data = json.loads(state.state_file.read_text(encoding="utf-8"))
        assert data["run_id"] == "20260705_120000"
        assert data["outputs"]["nested"]["key"] == [1, 2, 3]


class TestCorruptedStateFile:
    """损坏的状态文件处理"""

    def test_find_existing_skips_corrupted(self, temp_output_dir, monkeypatch):
        monkeypatch.setattr("streamlit_app.OUTPUTS_DIR", temp_output_dir)

        url = "https://v.douyin.com/corrupt-test/"
        state = PipelineState(run_id="20260705_120000", input_url=url)
        state.save()
        # 破坏 JSON 文件
        state.state_file.write_text("{not valid json", encoding="utf-8")

        # find_existing 应跳过损坏文件，下次创建新的
        found = PipelineState.find_existing(url)
        assert found is None  # 损坏文件被跳过
