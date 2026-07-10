"""快速流水线集成测试 - 用已有数据模拟端到端流程"""
import sys, json
from pathlib import Path
from datetime import datetime

# 模拟一个已完成的下载+转录状态
run_id = f"20260704_test_{datetime.now().strftime('%H%M%S')}"
run_dir = Path("d:/AIToutiao/outputs/20260704") / run_id
run_dir.mkdir(parents=True, exist_ok=True)

# 创建转录文件
transcript_text = Path("d:/AIToutiao/outputs/2026-06-30/transcripts/视频1_伊朗真有可能在霍尔木兹海峡收费吗.md").read_text(encoding="utf-8")
transcript_file = run_dir / "transcript.txt"
transcript_file.write_text(transcript_text, encoding="utf-8")

# 创建 pipeline_state.json
state = {
    "run_id": run_id,
    "mode": "write",
    "input_url": "测试_伊朗霍尔木兹海峡",
    "content_type": "toutie",
    "completed_stages": ["download", "transcribe"],
    "outputs": {
        "transcript_files": [str(transcript_file)],
    },
    "created_at": datetime.now().isoformat(),
    "updated_at": datetime.now().isoformat(),
}
(run_dir / "pipeline_state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"Test run created: {run_id}")
print(f"Run dir: {run_dir}")
print(f"Now run: python pipeline.py --resume {run_id}")
