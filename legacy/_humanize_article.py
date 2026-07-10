#!/usr/bin/env python3
"""
人工化改写脚本 — 去除 AI 味，输出真人手笔
============================================

功能：
    将 AI 生成或初稿文本改写为适合今日头条微头条发布的版本，
    彻底消除机器腔，注入口语化表达和真人写作特征。

用法：
    # 从文件读取，输出到终端
    python _humanize_article.py article.md

    # 从文件读取，保存到文件
    python _humanize_article.py article.md -o output.md

    # 直接传入文本
    python _humanize_article.py --text "这是一段AI生成的文章..."

    # 对比模式：显示改写前后的对比
    python _humanize_article.py article.md --diff

    # 干跑模式：只检测 AI 味特征，不调用 API
    python _humanize_article.py article.md --dry-run

依赖：
    - toutiao-auto-publisher/backend/ 目录下的 config.py 和 ai_writer.py
    - .env 文件中的 DeepSeek API 配置

作者：AIToutiao 项目
"""

import argparse
import io
import re
import sys
import textwrap
from pathlib import Path

# ── 修复 Windows GBK 编码问题 ──
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── 路径设置 ─────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
BACKEND_DIR = PROJECT_ROOT / "toutiao-auto-publisher" / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from ai_writer import AIWriter


# ═══════════════════════════════════════════════════════════════
# AI 味检测规则
# ═══════════════════════════════════════════════════════════════

AI_PATTERNS = {
    "结构套路": [
        (r"首先[,，].*其次[,，].*(最后|再次)", "首先其次最后"),
        (r"综上所述[,，]", "综上所述"),
        (r"总而言之[,，]", "总而言之"),
        (r"值得注意的是[,，]", "值得注意的是"),
        (r"需要指出的是[,，]", "需要指出的是"),
    ],
    "书面语过度": [
        (r"\b(进行|实施|呈现|展现|体现)\b", "书面动词"),
        (r"\b(此外|另外|与此同时|另一方面|换言之)\b", "连接词"),
        (r"\b(基于|鉴于|针对|对于|关于)\b.{0,20}(?:而言|来说)", "嵌套介词"),
    ],
    "结构对称": [
        (r"不仅.{3,20}而且.{3,20}", "不仅而且"),
        (r"既.{3,15}又.{3,15}", "既又"),
        (r"一方面.{3,20}另一方面.{3,20}", "一方面另一方面"),
    ],
    "无语气词": [
        # 反向检测：如果全篇零语气词，很可能是 AI
    ],
}


def detect_ai_patterns(text: str) -> list[dict]:
    """检测文本中的 AI 味特征，返回特征列表"""
    findings = []
    for category, patterns in AI_PATTERNS.items():
        for pattern, label in patterns:
            matches = re.findall(pattern, text)
            if matches:
                findings.append({
                    "category": category,
                    "label": label,
                    "count": len(matches),
                    "sample": matches[0] if isinstance(matches[0], str) else str(matches[0]),
                })
    return findings


def has_no_tone_words(text: str) -> bool:
    """检测是否缺少语气词"""
    tone_words = r"[啊呢吧嘛哈咯呗罢了呀哦嗯]"
    return len(re.findall(tone_words, text)) == 0


# ═══════════════════════════════════════════════════════════════
# 核心改写逻辑
# ═══════════════════════════════════════════════════════════════

def humanize_text(text: str, writer: AIWriter) -> dict:
    """
    调用 DeepSeek API 进行人工化改写。

    Args:
        text: 原始文本
        writer: AIWriter 实例

    Returns:
        dict: {"content": str, "char_count": int}
    """
    if not text or not text.strip():
        raise ValueError("输入文本为空")

    result = writer.humanize(text)
    return result


# ═══════════════════════════════════════════════════════════════
# CLI 界面
# ═══════════════════════════════════════════════════════════════

def read_input(args: argparse.Namespace) -> str:
    """根据命令行参数读取输入文本"""
    if args.text:
        return args.text

    if args.file:
        filepath = Path(args.file)
        if not filepath.exists():
            print(f"❌ 文件不存在: {args.file}", file=sys.stderr)
            sys.exit(1)
        text = filepath.read_text(encoding="utf-8")
        # 如果是 .md 文件，尝试提取正文（跳过 front matter 和元信息）
        text = extract_body_from_markdown(text)
        return text

    # 从标准输入读取
    if not sys.stdin.isatty():
        return sys.stdin.read()

    print("❌ 请提供输入：--text 或 --file 或 管道输入", file=sys.stderr)
    sys.exit(1)


def extract_body_from_markdown(md_text: str) -> str:
    """从 Markdown 文件中提取正文（跳过 YAML front matter 和以 ## 开头的元信息行）"""
    # 跳过 YAML front matter
    lines = md_text.split("\n")
    start = 0
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                start = i + 1
                break

    body = "\n".join(lines[start:]).strip()
    return body


def print_diff(original: str, humanized: str, max_lines: int = 60):
    """打印改写前后的对比"""
    orig_lines = original.split("\n")
    hum_lines = humanized.split("\n")

    print("\n" + "=" * 70)
    print("  📝  改写前（AI 痕迹）")
    print("=" * 70)
    for line in orig_lines[:max_lines]:
        print(f"  {line}")
    if len(orig_lines) > max_lines:
        print(f"  ... (共 {len(orig_lines)} 行，已截断)")

    print("\n" + "=" * 70)
    print("  ✨  改写后（真人手笔）")
    print("=" * 70)
    for line in hum_lines[:max_lines]:
        print(f"  {line}")
    if len(hum_lines) > max_lines:
        print(f"  ... (共 {len(hum_lines)} 行，已截断)")
    print("=" * 70)


def print_ai_detection(text: str):
    """打印 AI 味检测结果"""
    print("\n" + "─" * 50)
    print("  🔍  AI 味检测")
    print("─" * 50)

    findings = detect_ai_patterns(text)

    if not findings and not has_no_tone_words(text):
        print("  ✅ 未检测到明显的 AI 味特征")
    else:
        summary = {}
        for f in findings:
            cat = f["category"]
            if cat not in summary:
                summary[cat] = []
            summary[cat].append(f)

        for cat, items in summary.items():
            labels = ", ".join(f"{i['label']}(×{i['count']})" for i in items)
            print(f"  ⚠️  {cat}: {labels}")

        if has_no_tone_words(text):
            print("  ⚠️  无语气词：全篇没有出现「啊呢吧嘛哈咯」等口语语气词")

    print(f"  📊 文本长度: {len(text)} 字符")
    print("─" * 50)


# ═══════════════════════════════════════════════════════════════
# 合规自检
# ═══════════════════════════════════════════════════════════════

COMPLIANCE_KEYWORDS = {
    "色情低俗": ["色情", "裸", "性爱", "淫", "嫖", "娼"],
    "暴力恐怖": ["恐怖分子", "暴恐", "ISIS", "圣战"],
    "违法信息": ["赌博", "毒品", "枪支买卖", "假钞"],
    "政治敏感": [],  # 留空，由 AI 的 System Prompt 处理
}


def quick_compliance_check(text: str) -> list[str]:
    """快速合规关键词扫描"""
    hits = []
    for category, keywords in COMPLIANCE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                hits.append(f"⚠️  {category} 关键词: '{kw}'")
    return hits


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="人工化改写 — 去除 AI 味，输出真人手笔的微头条",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            示例:
              python _humanize_article.py article.md
              python _humanize_article.py article.md -o result.md
              python _humanize_article.py --text "AI生成的内容..."
              python _humanize_article.py article.md --diff
              python _humanize_article.py article.md --dry-run
              cat article.md | python _humanize_article.py
        """),
    )

    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument("file", nargs="?", help="输入文件路径 (.md / .txt)")
    input_group.add_argument("--text", "-t", help="直接传入文本")
    parser.add_argument("--output", "-o", help="输出文件路径（不指定则输出到终端）")
    parser.add_argument("--diff", "-d", action="store_true", help="显示改写前后对比")
    parser.add_argument("--dry-run", "-n", action="store_true", help="干跑模式：只检测 AI 味，不改写")

    args = parser.parse_args()

    # ── 读取输入 ──
    text = read_input(args)

    if not text or not text.strip():
        print("❌ 输入文本为空", file=sys.stderr)
        sys.exit(1)

    # ── 合规扫描 ──
    compliance_hits = quick_compliance_check(text)
    if compliance_hits:
        print("\n⚠️  合规警告：")
        for hit in compliance_hits:
            print(f"  {hit}")
        print()

    # ── 干跑模式：只检测 ──
    if args.dry_run:
        print_ai_detection(text)
        sys.exit(0)

    # ── 执行改写 ──
    print(f"📖 原文: {len(text)} 字符")
    print("🔄 正在调用 DeepSeek API 进行人工化改写...", end=" ", flush=True)

    try:
        writer = AIWriter()
        result = humanize_text(text, writer)
    except Exception as e:
        print(f"\n❌ 改写失败: {e}", file=sys.stderr)
        sys.exit(1)

    humanized = result["content"]
    print(f"✅ {result['char_count']} 字符")

    # ── 输出 ──
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(humanized, encoding="utf-8")
        print(f"💾 已保存: {output_path}")
    else:
        print("\n" + "─" * 60)
        print(humanized)
        print("─" * 60)

    # ── 对比模式 ──
    if args.diff:
        print_diff(text, humanized)

    # ── AI 味检测 ──
    print_ai_detection(humanized)


if __name__ == "__main__":
    main()
