#!/usr/bin/env python3
"""
Prompt 清洗器 —— 确保 AI 生成图片干净无文字/水印。

三条清洗管道：
  1. strip_chinese_labels  — 剥离中文标签性文字（"封面图""微头条""评书风格"等）
  2. to_english_visual      — 将残留中文视觉描述转为英文
  3. append_no_text_directive — 强制追加禁止渲染文字的指令

用法:
    from prompt_sanitizer import sanitize
    clean = sanitize("今日头条军事微头条封面图，一把断裂的武士刀...")
    # → "A cinematic composition of a broken samurai sword..." + no-text directive
"""

import re
from typing import List, Tuple


# ── 中文标签模式库 ──
# 这些是常见的中文元描述/平台标签，AI 模型会误当成文字渲染到图上
_CHINESE_LABEL_PATTERNS: List[Tuple[str, str]] = [
    # 平台/频道标签
    (r'今日头条\S*封面图[，,\s]*', ''),
    (r'今日头条\S*配图[，,\s]*', ''),
    (r'今日头条\S*文章[，,\s]*', ''),
    (r'微头条\S*封面图[，,\s]*', ''),
    (r'微头条\S*配图[，,\s]*', ''),
    # 内容类型标签
    (r'评书故事风格[，,\s]*', ''),
    (r'军事深度分析[，,\s]*', ''),
    (r'军事科技[，,\s]*', ''),
    (r'新闻资讯类[，,\s]*', ''),
    (r'专业军事分析感[，,\s]*', ''),
    (r'深度分析配图风格[。，,\s]*', ''),
    # 排版/平台提示
    (r'横版\d+:\d+构图[，,\s]*', ''),
    (r'横版构图[，,\s]*', ''),
    (r'竖版构图[，,\s]*', ''),
    (r'比例\d+:\d+[，,\s]*', ''),
    (r'适合\S*封面[。，,\s]*', ''),
    (r'适合\S*配图[。，,\s]*', ''),
    (r'适合\S*内文配图[。，,\s]*', ''),
    (r'文字区域留白在\S*位置[。，,\s]*', ''),
    (r'文字区域\S*留白[。，,\s]*', ''),
    # 通用结尾标签
    (r'视觉冲击力强[，,\s]*', ''),
    (r'强烈视觉冲击力[，,\s]*', ''),
    (r'电影质感[，,\s]*', ''),
    (r'电影级质感[，,\s]*', ''),
]

# 中文标点/结构词（用于剥离中文前缀："画面主体：一把巨大的..."）
_CHINESE_STRUCTURE_WORDS = [
    r'画面主体[：:][，,\s]*',
    r'画面中心[：:][，,\s]*',
    r'画面[：:][，,\s]*',
    r'主体[：:][，,\s]*',
    r'背景[：:][，,\s]*',
    r'前景[：:][，,\s]*',
    r'光影[：:][，,\s]*',
    r'色调[：:][，,\s]*',
    r'构图[：:][，,\s]*',
    r'风格[：:][，,\s]*',
    r'配色[：:][，,\s]*',
]

# ── 禁止渲染文字的强制指令 ──
_NO_TEXT_DIRECTIVE = (
    "\n\nCRITICAL INSTRUCTION: "
    "DO NOT render any text, watermark, label, letters, characters, "
    "or typography on this image. Pure visual scene only. "
    "No Chinese characters. No English words. No UI elements. "
    "This must be a clean, text-free photograph/illustration."
)

_NO_TEXT_DIRECTIVE_CN = (
    "\n\n【关键指令】请勿在图片上渲染任何文字、水印、标签、字母、字符或排版元素。"
    "纯视觉画面。无中文汉字。无英文单词。无UI元素。必须是一张干净无文字的图像。"
)


def strip_chinese_labels(prompt: str, keep_cn_visual: bool = False) -> str:
    """
    剥离中文标签性文字。

    当 keep_cn_visual=True 时：
      仅剥离平台/频道/类型标签（"今日头条""微头条""评书故事风格"等），
      保留视觉描述正文（"画面主体""背景""光影""色调"等）作为完整中文 Prompt。

    当 keep_cn_visual=False 时（默认）：
      剥离所有中文标签和结构词前缀，输出纯英文视觉描述起点。

    将"今日头条军事微头条封面图，评书故事风格。画面主体：..." 
    在 keep_cn_visual 模式下清洗为"画面主体：..."
    在默认模式下清洗为"一把巨大的武士刀..."
    """
    result = prompt

    # 1. 剥离模式匹配的标签
    for pattern, replacement in _CHINESE_LABEL_PATTERNS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    if keep_cn_visual:
        # keep 模式：仅剥离平台标签，不剥离结构词前缀
        # 保留"画面主体""背景""光影""色调"等作为完整中文 Prompt 的段落标记
        result = result.strip('。，,;；、 \t\n')
        return result

    # 默认模式：也剥离中文结构词前缀（保留后面的视觉内容）
    for pattern in _CHINESE_STRUCTURE_WORDS:
        result = re.sub(r'^' + pattern, '', result, flags=re.IGNORECASE)

    # 3. 清理连续标点/空白
    result = result.strip('。，,;；、 \t\n')

    return result


def to_english_visual(prompt: str) -> str:
    """
    将中文视觉描述转为英文。
    如果 prompt 以中文为主，尝试提取视觉关键信息转为英文。
    纯英文 prompt 直接返回。
    """
    # 检测中文含量
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', prompt))
    total_chars = len(prompt)

    if chinese_chars == 0:
        # 纯英文，直接返回
        return prompt

    if chinese_chars > total_chars * 0.5:
        # 中文为主，需要转换
        return _translate_cn_to_en_visual(prompt)

    # 中英混合，剥离中文部分
    return _strip_chinese_segments(prompt)


def _strip_chinese_segments(prompt: str) -> str:
    """剥离中英混合 prompt 中的中文片段"""
    # 移除整段中文描述
    result = re.sub(r'[\u4e00-\u9fff][\u4e00-\u9fff，。、；：""\u2018\u2019！？\s]{5,}', ' ', prompt)
    result = re.sub(r'[\u4e00-\u9fff]+', '', result)
    # 清理多余空白
    result = re.sub(r'\s{2,}', ' ', result).strip()
    return result


def _translate_cn_to_en_visual(text: str) -> str:
    """
    中文视觉描述 → 英文 visual prompt 骨架。
    这是一个基于模式的启发式转换（不依赖翻译 API），
    提取关键视觉概念并用英文模板重组。

    增强版：使用新闻摄影/战地纪录风格前缀，保留更多视觉细节。
    """
    # 提取关键视觉元素
    keywords = _extract_visual_keywords(text)

    # 构建英文 prompt 骨架
    parts = []

    # 添加风格前缀（新闻摄影风，而非抽象编辑风）
    if keywords['lighting'] and any(l in str(keywords['lighting']) for l in ['forensic', 'harsh', 'interrogation']):
        parts.append("A forensic photojournalism photograph of")
    elif keywords['lighting'] and any(l in str(keywords['lighting']) for l in ['war-room', 'briefing', 'top-down']):
        parts.append("An overhead intelligence-briefing photograph of")
    else:
        parts.append("A news documentary photograph of")

    # 主体描述
    if keywords['subjects']:
        parts.append(", ".join(keywords['subjects']))
    else:
        parts.append("a striking documentary composition")

    # 色调
    if keywords['colors']:
        parts.append(f"with {', '.join(keywords['colors'])} color palette")

    # 光照
    if keywords['lighting']:
        parts.append(f"{', '.join(keywords['lighting'])}")

    # 背景
    if keywords['background']:
        parts.append(f"against {', '.join(keywords['background'])}")

    # 质感后缀
    parts.append("8K resolution, news wire service quality")

    prompt = ". ".join(parts)
    # 修复格式
    prompt = re.sub(r'\.\s*\.', '.', prompt)
    prompt = re.sub(r'\s{2,}', ' ', prompt).strip()

    return prompt


def _extract_visual_keywords(text: str) -> dict:
    """
    从中文文本中提取视觉关键词。
    返回 {'subjects': [...], 'colors': [...], 'lighting': [...], 'background': [...]}
    """
    result = {
        'subjects': [],
        'colors': [],
        'lighting': [],
        'background': [],
    }

    # 颜色映射（增强版）
    color_map = {
        '暗红': 'crimson and dark red',
        '深红': 'deep crimson red',
        '深蓝': 'deep navy blue',
        '蓝灰': 'blue-grey metallic',
        '金属': 'metallic steel',
        '暖黄': 'warm amber',
        '金黄': 'golden amber',
        '冷色': 'cool-toned',
        '暗色': 'dark and moody',
        '暗绿': 'dark forest green',
        '象牙白': 'ivory white',
        '黑白': 'monochrome',
        '暗红+深蓝': 'crimson red and deep navy blue clash',
        '深蓝+暗红': 'deep blue and dark crimson contrast',
        '炭黑': 'charcoal black',
        '红金': 'red and gold accent',
        '冷暖对冲': 'cold-warm color opposition',
        '冷白蓝红': 'cold white-blue-red triadic tension',
    }
    for cn, en in color_map.items():
        if cn in text:
            result['colors'].append(en)

    # 光照映射（增强版）
    light_map = {
        '侧光': 'dramatic side lighting from upper left',
        '聚光': 'focused single spotlight from above',
        '顶光': 'harsh top-down interrogation lamp',
        '明暗对比': 'strong chiaroscuro contrast with deep shadows',
        '电影布光': 'cinematic three-point lighting setup',
        '电影级布光': 'professional cinematic lighting with motivated light sources',
        '强烈侧光': 'intense directional side light casting long shadows',
        '右上角': 'key light from upper right quadrant',
        '聚光灯照明': 'single spotlight illumination with fall-off into darkness',
        '暗色调为主': 'low-key lighting with dominant shadows',
    }
    for cn, en in light_map.items():
        if cn in text:
            result['lighting'].append(en)

    # 主体关键词提取（增强版：覆盖更多具体视觉元素）
    subject_patterns = [
        # 武士刀/日本符号
        (r'一把(?:巨大的)?(\S+)?(?:武士刀|刀)', 'a shattered katana sword with blade fragments scattering'),
        (r'断裂的?(\S+)?(?:刀|武士刀)', 'a broken katana sword split at the center'),
        (r'日本\S*(?:旗|国旗)', 'a fading and cracked Japanese flag motif'),
        (r'刀身碎片', 'katana blade shards suspended mid-air'),
        # 芯片/电子
        (r'芯片|电子芯片|制导芯片', 'extreme macro of a missile guidance microchip, gold circuit traces'),
        (r'微型零件|电子元件|电子零部件', 'micro electronic components on inspection tray'),
        (r'电路|电路板', 'intricate printed circuit board with gold-plated pathways'),
        # 检查/拆解
        (r'放大镜', 'a forensic magnifying glass with yellow evidence markers'),
        (r'检查手套', 'a gloved hand in blue nitrile inspection gloves'),
        (r'拆解|武器残骸|残骸拆解', 'disassembled weapon wreckage with evidence tags on metal table'),
        (r'标记标签|证据标记', 'yellow evidence markers and forensic labels'),
        # 棋盘/博弈
        (r'国际象棋|棋盘|棋局', 'a chess board photographed from above with pieces in conflict'),
        (r'棋子|"马"|"后"|"车"', 'chess pieces in mid-conflict positions'),
        (r'星条旗', 'stars and stripes motif on chess pieces'),
        # 锁链/张力
        (r'锁链', 'heavy industrial chains under extreme tension'),
        (r'地图|世界地图|经纬线', 'world map projection with latitude-longitude grid overlay'),
        (r'日本地图|日本\S*剪影', 'Japan map silhouette glowing red at the edges'),
        # 无人机/导弹
        (r'无人机', 'military surveillance drone with visible camera payload'),
        (r'导弹|巡航导弹|弹道导弹', 'a cruise missile body section on inspection stand'),
        (r'无人机剪影', 'drone silhouette against turbulent storm clouds'),
        # 工厂/工业
        (r'焊接|焊接痕迹', 'industrial welding marks on metal surfaces'),
        (r'金属碎片', 'scattered metallic fragments with serial markings'),
        # 文件/报告
        (r'文件|报告|协议', 'classified document folders spread on a dimly lit desk'),
        (r'纸币|日元', 'scattered Japanese yen banknotes falling through the air'),
        # 光影背景
        (r'红色太阳|太阳.*黯淡|黯淡褪色', 'a crimson sun disc fading and cracking'),
        (r'暴风雨|云层|乌云', 'gathering storm clouds with lightning flashes'),
        (r'暗色背景|深色背景', 'deep atmospheric dark background'),
        (r'投影|经纬线', 'projected geographic grid lines'),
        (r'聚光灯|侧光|顶光', 'single dramatic spotlight from above'),
        # 手/操纵
        (r'手影|幕后操纵', 'shadowy hands hovering over a strategic map'),
        (r'幕后|阴影|操纵', 'puppet-master hands pulling strings from the darkness'),
    ]
    for pattern, english in subject_patterns:
        if re.search(pattern, text):
            result['subjects'].append(english)

    # 背景
    bg_patterns = [
        (r'暴风雨|云层|乌云', 'gathering storm clouds with atmospheric tension'),
        (r'暗色背景|深色背景', 'a deep dark atmospheric background with subtle texture'),
        (r'投影|经纬线', 'projected latitude-longitude grid lines on dark surface'),
        (r'拆解现场|残骸现场', 'weapon debris investigation site with forensic markers'),
        (r'世界地图|暗色世界地图', 'faint world map projection in the background'),
        (r'红色太阳|太阳', 'a fading crimson sun disc in the background'),
    ]
    for pattern, english in bg_patterns:
        if re.search(pattern, text):
            result['background'].append(english)

    # 如果没有任何视觉关键词被提取到，使用通用描述
    if not any(result.values()):
        result['subjects'] = ['a dynamic editorial composition']

    return result


def append_no_text_directive(prompt: str, use_cn: bool = False) -> str:
    """
    追加禁止渲染文字的强制指令。
    如果 prompt 中已包含类似指令则跳过。

    Args:
        prompt: 原始 prompt
        use_cn: 是否使用中文指令（用于中文 Prompt 模式）
    """
    if re.search(r'NO\s+TEXT|no\s+text|DO NOT render.*text|请勿.*文字|纯视觉', prompt, re.IGNORECASE):
        return prompt
    directive = _NO_TEXT_DIRECTIVE_CN if use_cn else _NO_TEXT_DIRECTIVE
    return prompt + directive


def sanitize(prompt: str, target_lang: str = "en") -> str:
    """
    完整清洗管道。

    Args:
        prompt: 原始 prompt（可能包含中文标签、文字描述）
        target_lang: 目标语言
            - 'en': 转为英文（默认）
            - 'cn': 保留中文视觉描述，仅剥离平台标签
            - 'keep': 保留原始语言（不转换）

    Returns:
        清洗后的 prompt，保证不会在图片上渲染文字
    """
    # 判断是否需要保留中文
    keep_cn = target_lang in ("cn", "keep")

    # 第一层：剥离中文标签
    cleaned = strip_chinese_labels(prompt, keep_cn_visual=keep_cn)

    if not cleaned:
        return append_no_text_directive(
            "A cinematic editorial photograph" if not keep_cn else "电影级新闻纪实摄影画面"
        )

    # 第二层：语言转换
    if target_lang == "en":
        cleaned = to_english_visual(cleaned)
    # target_lang='cn' 或 'keep' 时：保留中文，不做翻译

    if not cleaned or len(cleaned) < 10:
        return append_no_text_directive(
            "A cinematic editorial photograph" if not keep_cn else "电影级新闻纪实摄影画面",
            use_cn=keep_cn,
        )

    # 第三层：追加禁止渲染文字指令
    cleaned = append_no_text_directive(cleaned, use_cn=keep_cn)

    return cleaned


def sanitize_batch(prompts: List[str], target_lang: str = "en") -> List[str]:
    """批量清洗 prompt 列表"""
    return [sanitize(p, target_lang) for p in prompts]


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import sys

    # 示例测试
    test_prompts = [
        "今日头条军事微头条封面图，评书故事风格。画面主体：一把巨大的武士刀从中间断裂，刀身碎片散落。背景左侧是日本国旗的红色太阳正在黯淡褪色。",
        "军事科技微距特写图：一只手戴着检查手套，手持放大镜对准一块被拆解开的导弹制导芯片。适合今日头条军事分析文章内文配图。",
        "A cinematic wide shot of a stormy ocean with a lone ship, dramatic lighting, 8K quality",
    ]

    for i, p in enumerate(test_prompts):
        print(f"\n{'='*60}")
        print(f"[Test {i+1}] Original ({len(p)} chars):")
        print(f"  {p[:120]}...")
        cleaned = sanitize(p)
        print(f"[After] Cleaned ({len(cleaned)} chars):")
        print(f"  {cleaned[:200]}...")
