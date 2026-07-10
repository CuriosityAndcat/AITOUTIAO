"""
端到端测试：转录文本 → AI 生成 → 人工化改写
支持切换不同风格，修改 STYLE 变量即可
"""
import io
import sys
from pathlib import Path

# ── 修复 Windows GBK 编码 ──
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── 准备工作 ──
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT / "toutiao-auto-publisher" / "backend"))

from ai_writer import AIWriter
from models import ContentStyle

# 🔧 在这里切换风格
STYLE = ContentStyle.STORY_NARRATIVE  # 评书故事型（对标听风的蚕）
STYLE_NAME = "story_narrative"

# ── 读取转录文本 ──
transcript_path = PROJECT_ROOT / "outputs" / "20260704" / "20260704_134932" / "transcript.txt"
transcript = transcript_path.read_text(encoding="utf-8")
print(f"[转录] {len(transcript)} 字符")
print(f"[预览] {transcript[:160]}...\n")

writer = AIWriter()

# ════════════════════════════════════════════════════════
# 第1步: AI 生成
# ════════════════════════════════════════════════════════
print("=" * 60)
print(f"[step 1/2] AI 生成 ({STYLE_NAME}) ...")
print("=" * 60)

result = writer.generate_toutie(
    topic=transcript,
    max_chars=800,
    content_style=STYLE,
)
raw_content = result["content"]
print(f"[OK] 生成完成: {result['char_count']} 字符\n")
print(raw_content)
print()

# ════════════════════════════════════════════════════════
# 第2步: 人工化改写（去 AI 味）
# ════════════════════════════════════════════════════════
print("=" * 60)
print("[step 2/2] 人工化改写 (humanize) ...")
print("=" * 60)

hresult = writer.humanize(raw_content)
humanized = hresult["content"]
print(f"[OK] 人工化完成: {hresult['char_count']} 字符\n")
print(humanized)
print()

# ════════════════════════════════════════════════════════
# 保存结果
# ════════════════════════════════════════════════════════
output_dir = PROJECT_ROOT / "outputs" / "20260704" / f"fresh_test_{STYLE_NAME}"
output_dir.mkdir(parents=True, exist_ok=True)

raw_file = output_dir / "01_ai_raw.md"
human_file = output_dir / "02_humanized.md"
report_file = output_dir / "report.md"

raw_file.write_text(
    f"# AI 原始生成\n\n{raw_content}\n\n---\n*AI 直出，未人工化*",
    encoding="utf-8",
)
human_file.write_text(
    f"# 人工化改写后\n\n{humanized}\n\n---\n*去 AI 味处理后*",
    encoding="utf-8",
)

report = (
    f"# 微头条生成对比报告\n\n"
    f"## 源视频\n- 来源: 大话观察 (抖音)\n- 转录字数: {len(transcript)}\n\n"
    f"## AI 原始生成\n- 字数: {len(raw_content)}\n- 风格: {STYLE_NAME}\n\n"
    f"## 人工化后\n- 字数: {len(humanized)}\n\n"
    f"## 对比\n"
    f"| 维度 | AI 原始 | 人工化后 |\n"
    f"|------|---------|----------|\n"
    f"| 字数 | {len(raw_content)} | {len(humanized)} |\n"
)
report_file.write_text(report, encoding="utf-8")

print("=" * 60)
print(f"[done] 结果已保存: {output_dir}")
print(f"  AI 原始   -> {raw_file.name}")
print(f"  人工化后  -> {human_file.name}")
print(f"  对比报告  -> {report_file.name}")
