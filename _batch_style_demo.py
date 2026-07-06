"""
批量风格示例生成脚本
使用统一军事话题，循环 6 种风格调用 DeepSeek API，汇编为 STYLE_OPTIONS.md
"""
import sys
import os
import time
from pathlib import Path

# 确保 backend 目录可导入
backend_dir = Path(__file__).parent / "toutiao-auto-publisher" / "backend"
sys.path.insert(0, str(backend_dir))

from models import ContentType, ContentStyle
from ai_writer import AIWriter

# ============================================================
# 统一测试话题
# ============================================================
TOPIC = """日本防卫白皮书2025：日本防卫省发布2025年版《防卫白皮书》，首次将中国定位为"前所未有的最大战略挑战"。
白皮书指出，中国在东海、南海的军事活动持续活跃，中俄联合战略巡航趋于常态化，台海局势紧张升级。
日本宣布计划在2027年前将防卫费提升至GDP的2%，重点发展"反击能力"（对敌基地攻击能力），
包括采购美制战斧巡航导弹、研发国产高超音速武器、扩建西南诸岛军事设施等。
对此，中方外交部回应称日方渲染"中国威胁"、为其军事扩张找借口，敦促日方反省侵略历史、坚持和平发展道路。"""

# ============================================================
# 风格列表及其元信息
# ============================================================
STYLES = [
    {
        "key": ContentStyle.MILITARY,
        "name": "军事深度分析型",
        "icon": "🔥",
        "benchmark": "你的专属风格",
        "desc": "七层递进法：钩子→事件→证据→博弈→后果→中方立场→互动。口语化强，'家人们'开篇，多角度拆解。",
        "temperature": "0.7",
    },
    {
        "key": ContentStyle.STORY_NARRATIVE,
        "name": "评书故事型",
        "icon": "📖",
        "benchmark": "对标「听风的蚕」",
        "desc": "评书五段法：拍案→铺陈→冲突→揭秘→留扣。河南方言韵味，'咱们''这家伙'，通俗比喻降维解读。",
        "temperature": "0.85",
    },
    {
        "key": ContentStyle.SHARP_COMMENTARY,
        "name": "冷静克制型",
        "icon": "✒️",
        "benchmark": "对标「牛弹琴」",
        "desc": "四段法：场景切入→事实铺陈→独到解读→自然收束。事实为主观点为辅，温和克制，在喧嚣中提供冷静声音。",
        "temperature": "0.6",
    },
    {
        "key": ContentStyle.DATA_LIST,
        "name": "硬核论证型",
        "icon": "📊",
        "benchmark": "对标「静思有我」",
        "desc": "论证四步法：核心问题→多维度证据→博弈透视→深度结论。数据驱动，逻辑链严密，零基础看懂全球。",
        "temperature": "0.5",
    },
    {
        "key": ContentStyle.FLASH_NEWS,
        "name": "快讯速报型",
        "icon": "⚡",
        "benchmark": "头条快讯风格",
        "desc": "三段式：发生了什么→为什么重要→关注什么。极度精炼，零铺垫，300-500字纯干货。",
        "temperature": "0.5",
    },
    {
        "key": ContentStyle.DISCUSSION,
        "name": "互动讨论型",
        "icon": "💬",
        "benchmark": "社区运营风格",
        "desc": "话题抛出→多角度展现→核心提问→互动引导。开放式提问，'你怎么看'为主轴，撩评论互动。",
        "temperature": "0.7",
    },
]


def main():
    print("=" * 60)
    print("批量风格示例生成")
    print(f"话题：日本防卫白皮书2025")
    print(f"风格数：{len(STYLES)} 种")
    print("=" * 60)

    writer = AIWriter()
    results = []

    for i, style in enumerate(STYLES, 1):
        print(f"\n[{i}/{len(STYLES)}] 生成中：{style['name']}（{style['benchmark']}）...", end=" ", flush=True)

        try:
            result = writer.generate(
                topic=TOPIC,
                content_type=ContentType.TOUTIE,
                max_chars=800,
                content_style=style["key"],
            )
            content = result["content"]
            char_count = result["char_count"]

            results.append({
                **style,
                "content": content,
                "char_count": char_count,
                "status": "success",
            })
            print(f"[OK] {char_count}字")

        except Exception as e:
            print(f"[FAIL] {e}")
            results.append({
                **style,
                "content": f"生成失败：{e}",
                "char_count": 0,
                "status": "failed",
            })

        # 避免触发 DeepSeek 限流
        if i < len(STYLES):
            time.sleep(3)

    # ============================================================
    # 汇编 Markdown 文档
    # ============================================================
    md = assemble_markdown(results)
    output_path = Path(__file__).parent / "STYLE_OPTIONS.md"
    output_path.write_text(md, encoding="utf-8")

    print(f"\n{'=' * 60}")
    print(f"[OK] 文档已输出：{output_path}")
    print(f"   成功 {sum(1 for r in results if r['status']=='success')}/{len(results)} 篇")
    print(f"{'=' * 60}")


def assemble_markdown(results: list) -> str:
    """将结果汇编为 Markdown 风格选型文档"""
    lines = []

    lines.append("# 🔫 军事微头条 — 6种AI写作风格选型文档\n")
    lines.append(f"> 生成模型：DeepSeek Chat  |  测试话题：日本防卫白皮书2025  |  生成时间：{time.strftime('%Y-%m-%d %H:%M')}\n")
    lines.append("---\n")

    # ---- 快速对比表 ----
    lines.append("## 一、快速对比矩阵\n")
    lines.append("| # | 风格 | 对标灵感 | Temp | 字数 | 适合场景 |")
    lines.append("|---|------|---------|------|------|---------|")
    for r in results:
        lines.append(
            f"| {r['icon']} | **{r['name']}** | {r['benchmark']} "
            f"| {r['temperature']} | {r.get('char_count', '-')} "
            f"| {r['desc'][:30]}... |"
        )
    lines.append("")

    # ---- 风格选择建议 ----
    lines.append("## 二、风格选择建议\n")
    lines.append("| 你的目标 | 推荐风格 |")
    lines.append("|---------|---------|")
    lines.append('| 建立个人IP，强化账号识别性 | \U0001f525 军事深度分析型（你的专属风格） |')
    lines.append('| 追求差异化，打造「评书」人设 | \U0001f4d6 评书故事型（听风的蚕路线） |')
    lines.append('| 追求公信力，走专业克制路线 | \u2712\ufe0f 冷静克制型（牛弹琴路线） |')
    lines.append('| 追求深度价值，吸引高知用户 | \U0001f4ca 硬核论证型（静思有我路线） |')
    lines.append('| 抢热点速度，第一时间触达 | \u26a1 快讯速报型 |')
    lines.append('| 提升互动率，做社区粘性 | \U0001f4ac 互动讨论型 |')
    lines.append("")

    # ---- 详细风格卡片 ----
    lines.append("## 三、风格详细卡片\n")

    for i, r in enumerate(results, 1):
        lines.append(f"### 风格 {i}：{r['icon']} {r['name']}  {'✅' if r['status']=='success' else '❌'}\n")
        lines.append(f"**对标灵感**：{r['benchmark']}  \n")
        lines.append(f"**温度参数**：{r['temperature']}  \n")
        lines.append(f"**核心特征**：{r['desc']}  \n")
        lines.append(f"**生成字数**：{r.get('char_count', '-')} 字  \n")
        lines.append("**生成示例**：\n")
        lines.append("---")
        lines.append(r["content"])
        lines.append("\n---\n")

    # ---- 技术说明 ----
    lines.append("## 四、技术说明\n")
    lines.append("### Style Routing\n")
    lines.append("所有风格通过 `STYLE_ROUTER` 字典实现 O(1) 路由：\n")
    lines.append("```python")
    lines.append("STYLE_ROUTER = {")
    lines.append("    ContentStyle.MILITARY:         (SYSTEM_PROMPT_MILITARY,         MILITARY_TOUTIE_PROMPT,    0.7),")
    lines.append("    ContentStyle.STORY_NARRATIVE:  (SYSTEM_PROMPT_STORY_NARRATIVE,  STORY_NARRATIVE_PROMPT,    0.85),")
    lines.append("    ContentStyle.SHARP_COMMENTARY: (SYSTEM_PROMPT_SHARP_COMMENTARY, SHARP_COMMENTARY_PROMPT,   0.6),")
    lines.append("    ContentStyle.DATA_LIST:        (SYSTEM_PROMPT_DATA_LIST,        DATA_LIST_PROMPT,          0.5),")
    lines.append("    ContentStyle.FLASH_NEWS:       (SYSTEM_PROMPT_FLASH_NEWS,       FLASH_NEWS_PROMPT,         0.5),")
    lines.append("    ContentStyle.DISCUSSION:       (SYSTEM_PROMPT_DISCUSSION,       DISCUSSION_PROMPT,         0.7),")
    lines.append("}")
    lines.append("```\n")
    lines.append("### 共享红线\n")
    lines.append("所有军事类风格的 System Prompt 末尾统一追加 `MILITARY_RED_LINES`，")
    lines.append("包含「军事真实性红线」和「国家立场红线」，确保各风格均遵守核心底线。\n")
    lines.append("### Pipeline 调用\n")
    lines.append("在 `pipeline.py` 中修改 `content_style` 参数即可切换风格：\n")
    lines.append("```python")
    lines.append('"content_style": "military"           # 👈 改成对应值')
    lines.append("# 可选值: military / story_narrative / sharp_commentary / data_list / flash_news / discussion")
    lines.append("```\n")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
