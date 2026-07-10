#!/usr/bin/env python3
"""
封面 & 内文配图 Prompt 构建器。

功能：
  1. 从文章标题提取视觉隐喻 → 构建封面 prompt
  2. 从叙事段落提取关键节点 → 构建内文配图 prompt
  3. 串联 Sanitizer + ComplianceChecker 确保输出干净合规
  4. 严格遵循 cover-prompts.md 规范：英文 prompt、不写文字、禁止紫色

用法:
    from cover_prompt_builder import CoverPromptBuilder
    builder = CoverPromptBuilder()
    cover_prompt = builder.build_cover(title, summary, style="story_narrative")
    inline_prompts = builder.build_inline_prompts(content, num_images=3)
"""

import re
from typing import Dict, List, Optional, Tuple

from prompt_sanitizer import sanitize
from compliance_checker import check as compliance_check, check_and_fix


# ============================================================
# 视觉隐喻映射表
# ============================================================

# 中文关键词 → 英文具体视觉场景（新闻摄影/战地纪录风格，而非抽象编辑隐喻）
_VISUAL_METAPHOR_MAP: Dict[str, str] = {
    # 地缘/国际关系 — 具体国家符号 + 新闻场景
    "日本": "a cracked and fading red circle (Japanese flag motif) against a dark stormy sky, symbolic of national dilemma, news documentary style",
    "美国": "the stars and stripes flag fabric rippling with dramatic shadows, power and uncertainty, photojournalism composition",
    "中国": "a majestic red and gold dragon-scale textured surface under spotlight, ancient and modern fusion, dramatic editorial photography",
    "俄罗斯": "a frozen industrial landscape with smokestacks and pipelines stretching into snow-covered horizon, cold blue tones",
    "乌克兰": "a field of sunflowers under gathering storm clouds with blue-yellow color accents in the sky, resilience symbolism",
    "博弈": "overhead shot of a chess board with dramatic long shadows, world map projected underneath, pieces in mid-conflict, war-room lighting",
    "制裁": "thick iron chains wrapped around cargo containers and industrial parts, one chain link cracking under pressure, dramatic industrial lighting",
    "合作": "two hands from opposing sides reaching across a negotiating table, handshake mid-motion, background maps and documents, UN-chamber lighting",
    "冲突": "two massive waves of opposing colors (dark blue vs crimson red) colliding at center, spray frozen in motion, storm lighting",
    "战争": "a devastated landscape: destroyed buildings silhouette at dawn, smoke columns rising, single ray of light breaking through, documentary war photography aesthetic",
    # 军事/科技 — 具体设备/零件/武器残骸
    "武器": "weapon components laid out on a military inspection table under harsh fluorescent lighting, evidence tags visible, forensic photography style",
    "芯片": "extreme macro close-up of a microchip silicon die, gold circuit traces and transistor gates visible, magnifying lens overlay, industrial espionage aesthetic",
    "无人机": "a military reconnaissance drone viewed from below against turbulent cloudy sky, camera lens and payload visible, defense photography",
    "导弹": "a cruise missile body section on an inspection stand, aerodynamic casing with serial markings, hangar lighting, military hardware catalog style",
    "军工": "heavy factory machinery casting dramatic shadows, assembly line for military equipment parts, industrial welding sparks, dark moody factory interior",
    "供应链": "cargo ships and containers at a foggy port terminal, shipping routes marked on overlay, global trade logistics visual, documentary style",
    # 叙事/情感
    "偷鸡不成蚀把米": "a red fox with its paw caught in a steel trap, surrounded by scattered grain, dramatic wilderness lighting, National Geographic documentary style",
    "反转": "a playing card being flipped mid-air showing two sides — one king, one joker — dramatic spotlight, casino table background",
    "尴尬": "a corporate figure in suit caught between two massive closing concrete walls, tight composition, overhead harsh lighting, photojournalism",
    "困境": "a lone building structure at center besieged by approaching storm clouds from all directions, lightning striking nearby, diegetic documentary lighting",
    "揭秘": "a heavy bank vault door swinging open, blinding light pouring through the crack illuminating a dark room, cinematic reveal",
    "曝光": "a classified document folder being illuminated by a single desk lamp beam in a dark archive room, dramatic chiaroscuro",
    # 证据/细节（index=0 配图优先命中）
    "报告": "a classified intelligence report folder open on a desk, top-secret stamp visible, magnifying glass over key paragraphs, evidence markers, war-room lighting",
    "拆解": "disassembled military hardware components tagged with yellow evidence markers on a metal workbench, tools scattered, investigative journalism photography",
    "证据": "crime investigation evidence board with photographs connected by red string, documents pinned, single overhead interrogation lamp, detective noir style",
    "数据": "multiple holographic data screens floating in a dark mission control room, charts and satellite imagery visible, blue-cyan tech aesthetic",
    "电子": "extreme close-up of a circuit board with golden traces, capacitors and resistors in sharp focus under macro lens, electronic forensics",
    "零件": "various mechanical parts — gears, springs, bolts — scattered on a forensic inspection tray under a bright task lamp, evidence catalog photography",
    "检": "a magnifying glass held by gloved hand hovering over deconstructed industrial components, evidence markers, forensic lab table",
    # 张力/对峙（index=1 配图优先命中）
    "对峙": "two opposing chess pieces (black knight vs white queen) face to face across a board split by a crack of light, dramatic side lighting, tension-filled composition",
    "两难": "a lone figure standing at a dirt crossroads under approaching storm clouds from both directions, one path blocked by fire, the other by flood, cinematic wide shot",
    "进退": "thick metallic chains pulling a fractured national emblem in opposite directions, sparks flying from the strain, industrial warehouse background, dynamic tension",
    "矛盾": "a large mirror cracked diagonally showing two different realities: one side calm and order, the other chaos and fire, editorial photography",
    "拉扯": "heavy rusted chains stretching taut between two industrial anchors, center link deforming under extreme tension, dramatic spotlight, warehouse setting",
    "陷入": "a corporate document folder sinking into dark quicksand with bubbles, handprints on the surface trying to pull it out, cinematic doom aesthetic",
    # 策略/博弈（index=2 配图优先命中）
    "幕后": "shadowy hands hovering over a large strategic map spread across a dimly lit conference table, red pins marking locations, intelligence briefing room aesthetic",
    "棋局": "aerial top-down view of a chess board mid-game with several black pieces knocked over, white queen dominating, dramatic coffee-stain rings on the board, war-room",
    "操纵": "marionette cross-bar with strings descending to wooden puppet figurines arranged like chess pieces, spotlight from above, puppet theater noir",
    "收尾": "a single black king chess piece tipping over in slow-motion toward the edge of a polished table, dramatic lighting, symbolic closure",
    "引爆": "a single lit match held inches away from a fuse leading toward a black powder trail, shallow depth of field, intense amber light, suspense photography",
    "说客": "a silhouetted figure whispering into another silhouetted figure's ear through a velvet curtain, dramatic backlighting, political intrigue noir",
    # 抽象概念
    "野心": "a hand reaching out from darkness toward a glowing unreachable star hanging in void, fingers just inches away, aspiration and frustration, cinematic",
    "失败": "a grand stone monument crumbling and collapsing in slow motion, dust clouds rising, pigeons scattering, documentary disaster photography",
    "平衡": "a brass justice scale with one side heavily weighed down by gold bars, the other side floating empty, dramatic courtroom lighting",
    "权力": "an empty ornate throne chair in a vast dark hall, single beam of light from above, dust particles dancing in the light, power aesthetics",
    "背后操纵": "bird's-eye view of a chess board on a dark table, multiple sets of hands reaching in from the edges moving pieces, puppet-master lighting",
}

# ============================================================
# 中文 Prompt 模板 — 军事视觉隐喻风格（推荐）
# 严格复刻 fresh_test_story_narrative 的视觉语言：
#   暗色基底 + 红金点缀 + 冷暖对冲色调
#   电影级侧光/聚光 + 强明暗对比
#   具体国家符号（断裂武士刀、国旗色锁链、棋子推倒）
#   层叠复合构图（主体+背景+前景+光影+色调+留白）
# ============================================================

# 中文视觉风格指南常量（所有中文 Prompt 共用）
_VISUAL_GUIDE_CN = (
    "暗色基底色调，深蓝+暗红+红金点缀冷暖对冲。"
    "电影级侧光与聚光照明，强明暗对比避免平光。"
    "金属科技质感，战争遗迹美学，忌卡通化扁平化。"
    "横版构图，视觉重心居中偏左为文字留右侧空间。"
)

# 中文封面模板（故事性叙事 + 多层融合构图法）
_STYLE_TEMPLATES_CN = {
    "story_narrative": (
        "今日头条军事微头条封面图，评书故事风格，多层复合构图。"
        "【前景主体】{foreground}"
        "【中景层】画面中心：{midground}"
        "【背景层】画面深远背景：{background}"
        "【整体画面氛围】画面统一在一个完整的戏剧性空间中——暗色基调的电影级布光，"
        "一道强烈侧光从右上角打下来照亮核心主体区域，呈递进式景深从前景延伸至背景。"
        "色调为深蓝+暗红+暖金三色对冲，金属质感的战争遗迹美学。"
        "构图上部为文字留白区域。比例16:9，横版封面，视觉冲击力强。所有元素应融合为一张完整的单一画面，非拼接蒙太奇。"
    ),
    "story_narrative_single": (
        # 回退模板：当文章只涉及单一核心实体时使用
        "今日头条军事微头条封面图，评书故事风格。"
        "画面主体：{visual_metaphor}。"
        "背景暗色世界地图投影与暴风雨云层。"
        "前景散落电子芯片与微型零件。"
        "光影：暗色调为主，一道强烈侧光从右上角打下来照亮核心主体。"
        "色调：深蓝+暗红对冲，电影级质感，冷暖色调碰撞。"
        "文字区域留白在画面中上位置。比例16:9，横版封面，视觉冲击力强。"
    ),
    "military": (
        "今日头条军事深度分析封面图。"
        "画面主体：{visual_metaphor}。"
        "背景为暗色军事地图与战略投影。"
        "光影：一道硬质顶光从正上方打下，制造强烈的明暗对比与戏剧性阴影。"
        "色调：深蓝+暗红基调，金属质感，8K超清。"
        "比例16:9，横版封面，专业军事分析感。"
    ),
    "general": (
        "今日头条新闻封面图。"
        "画面主体：{visual_metaphor}。"
        "背景暗色氛围与新闻事件相关元素投影。"
        "光影：聚光灯效果，主体明亮背景暗化。"
        "色调：深色基底+暖色点缀，新闻纪实感。"
        "比例16:9，横版封面。"
    ),
}

# 中文内文配图模板（三级差异化，对应叙事功能）
_INLINE_TEMPLATES_CN = [
    # index=0: 证据特写型 — 微距/拆解/放大镜/检查台
    (
        "军事科技微距特写图：{scene}。"
        "背景是武器残骸拆解现场的模糊场景——金属碎片、焊接痕迹、标记标签。"
        "冷色调，蓝灰色金属质感为主，核心区域有一丝暖黄光晕。"
        "景深浅，焦点在细节核心处。横版3:2构图，专业军事分析感，今日头条军事类配图风格。"
    ),
    # index=1: 张力对峙型 — 锁链拉扯/国旗色对冲/风暴对抗/宽镜头
    (
        "地缘政治概念图：{scene}。"
        "背景是暗色世界地图的模糊投影，空中飘落着破碎的协议文件与货币符号。"
        "电影级布光，冷暖对冲，强明暗对比制造戏剧性张力，对称或撕裂感构图。"
        "横版构图，适合今日头条军事分析文章内文配图。"
    ),
    # index=2: 策略博弈型 — 俯拍/棋盘/手影操纵/战情室
    (
        "战略博弈概念图：{scene}。"
        "深色背景，棋盘格为暗绿+象牙白，上方聚光灯照明制造舞台效果。"
        "棋盘边缘有模糊的多只手影在移动棋子，暗示幕后操纵。"
        "电影质感，冷峻的权谋美学，今日头条军事深度分析配图风格。"
    ),
]

# ============================================================
# 英文 Prompt 模板 — 新闻摄影/战地纪录风格
# ============================================================

# 风格模板（新闻摄影/战地纪录风格，非抽象编辑杂志风）
_STYLE_TEMPLATES = {
    "military": (
        "A photojournalism documentary photograph of {visual_metaphor}. "
        "Deep blue and crimson amber color palette, harsh directional key light from upper left "
        "creating strong contrast with deep shadows, metallic military industrial textures, "
        "ultra realistic, 8K resolution, news wire service quality"
    ),
    "story_narrative": (
        "A dramatic news documentary photograph of {visual_metaphor}. "
        "Warm amber and deep teal color tones, theatrical spotlight with strong chiaroscuro, "
        "storytelling visual narrative with tension and anticipation, "
        "rich cinematic textures with film grain, 8K, war correspondence photo quality"
    ),
    "sharp_commentary": (
        "A sleek documentary photograph of {visual_metaphor}. "
        "Cool-toned sophisticated palette, clean geometric composition with negative space, "
        "financial district glass-and-steel aesthetic, 8K, business wire photo quality"
    ),
    "data_list": (
        "A precision-focused technical photograph of {visual_metaphor}. "
        "Technical schematic aesthetic with clean lines, data visualization subtly integrated, "
        "blue and white professional palette, 8K, scientific journal quality"
    ),
    "flash_news": (
        "A bold breaking-news photograph of {visual_metaphor}. "
        "Crushed blacks with high contrast, urgent and immediate feel, breaking news wire service energy, "
        "vibrant red accent on neutral background, 8K, news bulletin front-page quality"
    ),
    "discussion": (
        "An engaging documentary photograph of {visual_metaphor}. "
        "Warm inviting tones, people-scale perspective, relatable social documentary aesthetic, "
        "golden hour natural lighting, 8K, feature story quality"
    ),
    "general": (
        "A professional news photograph of {visual_metaphor}. "
        "Balanced composition, natural photojournalism lighting, clean documentary aesthetic, "
        "8K resolution, versatile news wire quality"
    ),
}

# 内文配图模板（三级差异化，新闻摄影/战地纪录风格）
_INLINE_TEMPLATES = [
    # index=0: 证据特写型 — 法证/微距/拆解现场/检查台
    (
        "A forensic photojournalism close-up of {scene}. "
        "Harsh key light from above casting sharp shadows, evidence-marker labels and yellow tags visible, "
        "metallic surfaces with wear marks and scratches, high contrast news documentary style, 8K"
    ),
    # index=1: 张力对峙型 — 冲突/拉扯/戏剧性对抗/宽镜头
    (
        "A dramatic news wire photograph of {scene}. "
        "Strong directional lighting casting long dramatic shadows, "
        "tension and conflict visible in the composition, "
        "photojournalism color grading with crushed blacks and desaturated midtones, 8K"
    ),
    # index=2: 策略博弈型 — 战情室/棋盘/俯瞰/幕后
    (
        "An overhead intelligence-briefing photograph of {scene}. "
        "Top-down documentary angle with strategic arrangement, "
        "dim atmospheric war-room lighting with selective spot illumination on key elements, "
        "dark elegant tones with subtle amber accents, 8K"
    ),
]

# 分类关键词：按位置（index）指定优先匹配的关键词组
# 确保每张图在对应的叙事功能中搜索最相关的视觉概念
_CATEGORY_KEYWORDS = {
    0: ["报告", "拆解", "证据", "数据", "电子", "零件", "芯片", "曝光", "揭秘", "检"],
    1: ["对峙", "两难", "进退", "矛盾", "困境", "冲突", "尴尬", "制裁", "拉扯", "陷入"],
    2: ["幕后", "棋局", "操纵", "收尾", "博弈", "权力", "背后操纵", "野心", "引爆", "说客"],
}

# 分类默认回退场景：当对应类别关键词全部未命中时使用
_FALLBACK_SCENES = [
    "a forensic magnifying glass over precision components on a dark inspection table",
    "two massive forces represented by storms converging over a divided landscape",
    "a strategic chess board photographed from above with key pieces dramatically lit",
]


# ============================================================
# Prompt 构建器
# ============================================================

class CoverPromptBuilder:
    """
    封面 & 内文配图 Prompt 构建器。

    内部集成：
      - 视觉隐喻提取（中文标题 → 英文视觉概念或中文视觉场景）
      - 风格模板选择（中文或英文）
      - Sanitizer 清洗（去标签、转英文、禁文字）
      - ComplianceChecker 审查（敏感词扫描、安全替代）

    支持两种 Prompt 语言模式（通过 prompt_lang 参数控制）：
      - 'cn': 中文军事视觉隐喻风格（推荐，具体国家符号+层叠复合构图）
      - 'en': 英文新闻纪录摄影风格（抽象概念+单一场景）
    """

    def __init__(self, style: str = "story_narrative", prompt_lang: str = "cn"):
        """
        Args:
            style: 内容风格，决定视觉模板
                  可选: military / story_narrative / sharp_commentary / data_list
                        flash_news / discussion / general
            prompt_lang: Prompt 语言模式
                        'cn': 中文军事视觉隐喻（推荐，默认）
                        'en': 英文新闻摄影风
        """
        self.style = style
        self.prompt_lang = prompt_lang

        if prompt_lang == "cn":
            # 中文模式：使用中文模板
            self.template = _STYLE_TEMPLATES_CN.get(style, _STYLE_TEMPLATES_CN.get("general", _STYLE_TEMPLATES_CN.get("story_narrative", "")))
            self.inline_templates = _INLINE_TEMPLATES_CN
        else:
            # 英文模式：使用英文模板
            self.template = _STYLE_TEMPLATES.get(style, _STYLE_TEMPLATES["general"])
            self.inline_templates = _INLINE_TEMPLATES

    def _extract_visual_metaphor_for_lang(self, title: str, summary: str = "") -> str:
        """
        按 prompt_lang 选择中/英文视觉隐喻提取方式。
        """
        if self.prompt_lang == "cn":
            return self._extract_cn_cover_metaphor(title, summary)
        else:
            return self.extract_visual_metaphor(title, summary)

    def _extract_cn_cover_metaphor(self, title: str, summary: str = "") -> str:
        """
        从标题+摘要提取中文视觉隐喻（用于 CN 模式封面）。

        优先收集全部匹配的国家/军事/叙事实体，按前景/中景/背景三层融合；
        仅涉及单一实体时使用传统单元素模板。
        """
        full_text = title + (summary[:300] if summary else "")

        # 1. 收集全部匹配的实体（带分类和去重）
        matched = self._collect_all_entities(full_text)

        # 2. 判断：多元素 vs 单元素
        if len(matched) >= 2:
            return self._fuse_multi_element_metaphor(matched)

        # 3. 单元素：使用原有逻辑
        if len(matched) == 1:
            return list(matched.values())[0]

        # 4. 从标题提取核心主题词组合
        core_topics = self._extract_core_topics(title)
        if core_topics:
            return "与".join(core_topics) + "的戏剧性画面——深蓝暗红对冲色调，电影级布光"

        # 5. 通用回退
        return "地缘政治博弈的戏剧性画面——深蓝暗红对冲色调，电影级布光，强明暗对比"

    def _collect_all_entities(self, full_text: str) -> Dict[str, str]:
        """
        扫描全文，收集全部匹配的实体关键词及其视觉描述。
        按实体语义类别分组排序：国家 > 军事科技 > 叙事情感。

        Returns:
            {keyword: visual_description} 字典（按类别排序）
        """
        # 分类优先级定义
        CATEGORY_ORDER = {
            "日本": 0, "美国": 0, "中国": 0, "俄罗斯": 0, "乌克兰": 0,  # 国家类
            "芯片": 1, "无人机": 1, "导弹": 1, "武器": 1, "军工": 1,   # 军事科技
            "供应链": 1, "零件": 1, "证据": 1, "报告": 1,
            "博弈": 2, "制裁": 2, "冲突": 2, "对峙": 2, "棋局": 2,    # 地缘张力
            "两难": 2, "困境": 2,
            "偷鸡不成蚀把米": 3, "反转": 3, "揭秘": 3, "曝光": 3,      # 叙事
            "野心": 3, "失败": 3,
        }

        # 收集匹配
        raw_matches = []
        seen_keywords = set()
        for keyword, metaphor in _CN_COVER_VISUAL_MAP.items():
            if keyword in full_text and keyword not in seen_keywords:
                raw_matches.append((keyword, metaphor))
                seen_keywords.add(keyword)

        # 按类别排序
        raw_matches.sort(key=lambda x: CATEGORY_ORDER.get(x[0], 99))

        # 限制数量，优先保留不同类别的
        result = {}
        categories_used = set()
        for keyword, metaphor in raw_matches:
            cat = CATEGORY_ORDER.get(keyword, 99)
            if cat not in categories_used or len(result) < 3:
                result[keyword] = metaphor
                categories_used.add(cat)
            if len(result) >= 4:
                break

        return result

    def _fuse_multi_element_metaphor(self, entities: Dict[str, str]) -> str:
        """
        将多个实体按前景/中景/背景三层空间融合为一幅完整画面。

        - 如果刚好1个国家 + 1个军事科技 + 1个地缘概念 → 标准三层
        - 如果多个国家 → 中景层融合多个国家符号形成对峙/博弈
        - 否则按类别分配到三层

        Returns:
            形如 "【前景】...【中景】...【背景】..." 的结构化隐喻文本。
            实际使用时由模板拆分为 foreground/midground/background 三个占位符。
        """
        entity_list = list(entities.values())
        keywords = list(entities.keys())

        # 分类分配
        countries = [k for k in keywords if k in ("日本", "美国", "中国", "俄罗斯", "乌克兰")]
        military = [k for k in keywords if k in ("芯片", "无人机", "导弹", "武器", "军工", "零件", "证据", "报告", "供应链")]
        geo = [k for k in keywords if k in ("博弈", "制裁", "冲突", "对峙", "棋局", "两难", "困境")]
        narrative = [k for k in keywords if k in ("偷鸡不成蚀把米", "反转", "揭秘", "曝光", "野心", "失败")]

        # ── 构建三层 ──
        # 前景：取最具体的单个主体符号（叙事类或第一个国家/军事）
        foreground_candidates = narrative + countries[:1] + military[:1]
        foreground_kw = foreground_candidates[0] if foreground_candidates else keywords[0]
        foreground = entities.get(foreground_kw, "暗色调的金属质感精密机械部件")

        # 中景：融合多国符号或军事科技元素
        if len(countries) >= 2:
            # 多国对峙：两侧形成冷暖对峙
            mid_parts = []
            for i, c in enumerate(countries[:3]):
                short = entities[c].split("，")[0].split("。")[0][:40]
                mid_parts.append(short)
            midground = "画面左右两侧分别呈现" + "与".join(mid_parts[:2])
            if len(mid_parts) > 2:
                midground += "，" + mid_parts[2] + "位于中央"
            midground += "，形成多极对峙格局"
        elif military:
            mid_parts = [entities[k].split("，")[0].split("。")[0] for k in military[:2]]
            midground = "与".join(mid_parts) + "——精密科技产品的拆解展示"
        elif geo:
            midground = entities[geo[0]].split("，")[0].split("。")[0]
        else:
            midground = entities.get(keywords[min(1, len(keywords)-1)], foreground).split("，")[0].split("。")[0]

        # 背景：取地缘概念或世界地图投影
        if geo:
            background = entities[geo[0]].split("，")[0].split("。")[0] + "的暗色世界地图投影"
        else:
            background = "暗色世界地图经纬线投影，暴风雨云层密布，远方的火力与烟尘点缀地平线"

        # 构建结构化隐喻（模板用 {foreground}/{midground}/{background} 解构）
        return f"【前景主体】{foreground}【中景层】{midground}【背景层】{background}"

    def _parse_fused_parts(self, metaphor: str) -> Dict[str, str]:
        """
        从 _fuse_multi_element_metaphor 的输出中解析出前景/中景/背景三个部分。

        Args:
            metaphor: 带标记的结构化隐喻文本

        Returns:
            {"foreground": str, "midground": str, "background": str}
        """
        import re
        result = {"foreground": "", "midground": "", "background": ""}
        for key in ["前景主体", "中景层", "背景层"]:
            pattern = rf"【{key}】(.*?)(?=【|$)"
            m = re.search(pattern, metaphor)
            if m:
                en_key = {"前景主体": "foreground", "中景层": "midground", "背景层": "background"}[key]
                result[en_key] = m.group(1).strip()
        return result

    def extract_visual_metaphor(self, title: str, summary: str = "") -> str:
        """
        从标题提取视觉隐喻。

        优先级：
          1. 精确匹配 _VISUAL_METAPHOR_MAP
          2. 模糊关键词匹配
          3. 回退：从标题提取核心名词构建隐喻
        """
        # 1. 精确匹配
        for keyword, metaphor in _VISUAL_METAPHOR_MAP.items():
            if keyword in title:
                return metaphor

        # 2. 在摘要中也搜索
        full_text = title + summary[:200] if summary else title
        for keyword, metaphor in _VISUAL_METAPHOR_MAP.items():
            if keyword in full_text:
                return metaphor

        # 3. 从标题提取核心主题词
        core_topics = self._extract_core_topics(title)
        if core_topics:
            topics_str = ", ".join(core_topics)
            return f"a conceptual representation of {topics_str}"

        # 最终回退
        return "a dramatic editorial scene with geopolitical tension"

    def _extract_core_topics(self, title: str) -> List[str]:
        """从标题提取 1-3 个核心主题词"""
        # 移除常见停用词
        stop_words = {'这', '那', '的', '了', '是', '在', '和', '也', '都', '就',
                      '着', '之', '与', '及', '或', '对', '等', '吗', '呢', '吧',
                      '啊', '但', '而', '所', '被', '从', '到', '把', '向', '让',
                      '这个', '那个', '什么', '怎么', '如何', '为什么'}

        topics = []
        # 按分隔符拆分
        parts = re.split(r'[！!？?。，,、；;：:（）()【】[\]""\u2018\u2019\s]+', title)

        for part in parts:
            if len(part) >= 2 and part not in stop_words:
                # 去除标点和数字
                clean = re.sub(r'[^\u4e00-\u9fff]', '', part)
                if len(clean) >= 2:
                    topics.append(clean)

        # 最多取 3 个
        return topics[:3]

    def build_cover(
        self,
        title: str,
        summary: str = "",
        custom_metaphor: Optional[str] = None,
    ) -> dict:
        """
        构建封面 prompt。

        Args:
            title: 文章标题
            summary: 文章摘要/内容前200字
            custom_metaphor: 自定义视觉隐喻（可选，覆盖自动提取）

        Returns:
            {
                "prompt": 清洗后的最终 prompt,
                "visual_metaphor": 使用的视觉隐喻,
                "style": 风格,
                "prompt_lang": 语言模式,
                "compliance": 合规审查结果字典,
            }
        """
        # 1. 提取视觉隐喻
        visual_metaphor = custom_metaphor or self._extract_visual_metaphor_for_lang(title, summary)


        # 2. 构建原始 prompt（中文模式区分多元素融合 vs 单元素）
        if self.prompt_lang == "cn":
            # 检测是否为多元素融合隐喻（带【前景主体】【中景层】【背景层】标记）
            if "【前景主体】" in visual_metaphor:
                parts = self._parse_fused_parts(visual_metaphor)
                # 使用多元素融合模板（story_narrative 已更新为三层模板）
                multi_template = _STYLE_TEMPLATES_CN.get("story_narrative", self.template)
                raw_prompt = multi_template.format(
                    foreground=parts.get("foreground", ""),
                    midground=parts.get("midground", ""),
                    background=parts.get("background", ""),
                )
            else:
                # 单元素：使用传统回退模板
                single_template = _STYLE_TEMPLATES_CN.get("story_narrative_single", self.template)
                raw_prompt = single_template.format(visual_metaphor=visual_metaphor)
        else:
            # 英文模式：visual_metaphor 是英文场景描述
            raw_prompt = self.template.format(visual_metaphor=visual_metaphor)

        # 3. 清洗 + 去标签 + 禁文字
        # 中文模式下 target_lang='cn' 保留中文内容
        sanitize_lang = "cn" if self.prompt_lang == "cn" else "en"
        cleaned = sanitize(raw_prompt, target_lang=sanitize_lang)

        # 4. 合规审查 + 自动修复
        safe_prompt, warnings = check_and_fix(cleaned)
        if safe_prompt is None:
            # 有无法自动修复的高风险词，强制使用安全回退
            if self.prompt_lang == "cn":
                safe_prompt = (
                    "电影级新闻纪实摄影画面：抽象几何形态表现战略张力，"
                    "深蓝与琥珀色调，专业干净构图，8K画质"
                )
            else:
                safe_prompt = (
                    "A cinematic editorial photograph of abstract geometric forms "
                    "representing strategic tension, deep blue and amber tones, "
                    "professional clean composition, 8K quality"
                )
            warnings.append("🚫 原 prompt 含无法修复的高风险词，已使用安全回退 prompt")

        # 再次追加禁文字指令（确保合规修复后仍有）
        safe_prompt = sanitize(safe_prompt, target_lang=sanitize_lang)

        return {
            "prompt": safe_prompt,
            "visual_metaphor": visual_metaphor,
            "style": self.style,
            "prompt_lang": self.prompt_lang,
            "expected_elements": self._extract_expected_elements(title, summary),
            "compliance": {
                "warnings": warnings,
                "used_fallback": (safe_prompt != cleaned),
            },
        }

    def _extract_expected_elements(self, title: str, summary: str = "") -> List[str]:
        """
        从标题和摘要中提取期望出现在封面图中的核心元素列表。
        用于后续的图片审核校验。
        """
        full_text = title + (summary[:300] if summary else "")
        elements = []
        for keyword in _CN_COVER_VISUAL_MAP:
            if keyword in full_text and len(keyword) >= 2:
                elements.append(keyword)
        # 去重 + 限制数量
        return list(dict.fromkeys(elements))[:6]

    def build_inline_prompts(
        self,
        content: str,
        num_images: int = 3,
    ) -> List[dict]:
        """
        从内容中提取叙事节点，构建内文配图 prompt 列表。

        Args:
            content: 完整文章正文
            num_images: 需要生成的配图数量

        Returns:
            [{"prompt": ..., "narrative_point": ..., "index": 0, "prompt_lang": "cn"}, ...]
        """
        # 1. 提取叙事节点（每段取核心句）
        narrative_points = self._extract_narrative_nodes(content, num_images)

        # 2. 为每个叙事节点构建 prompt
        results = []
        sanitize_lang = "cn" if self.prompt_lang == "cn" else "en"

        for idx, point in enumerate(narrative_points):
            # 按位置选择视觉上下文
            visual_context = self._build_inline_visual_context_for_lang(point, idx)

            # 按位置选择对应的差异化模板
            template = self.inline_templates[idx % len(self.inline_templates)]
            raw_prompt = template.format(scene=visual_context)

            # 清洗
            cleaned = sanitize(raw_prompt, target_lang=sanitize_lang)

            # 合规审查
            safe_prompt, warnings = check_and_fix(cleaned)
            if safe_prompt is None:
                if self.prompt_lang == "cn":
                    fallbacks_cn = [
                        "一只戴手套的手持放大镜检查精密电子元件的微距特写画面",
                        "两股巨大风暴力量在分裂地貌上空汇聚对峙的戏剧性场面",
                        "俯视视角的战略棋盘上关键棋子被聚光灯照亮的博弈画面",
                    ]
                    safe_prompt = fallbacks_cn[idx % len(fallbacks_cn)]
                else:
                    safe_prompt = _FALLBACK_SCENES[idx % len(_FALLBACK_SCENES)]
                warnings.append("已使用安全回退 prompt")

            results.append({
                "prompt": sanitize(safe_prompt, target_lang=sanitize_lang),
                "narrative_point": point[:100],
                "index": idx,
                "prompt_lang": self.prompt_lang,
                "warnings": warnings,
            })

        return results

    def _build_inline_visual_context(self, narrative_text: str, index: int) -> str:
        """
        从叙事文本构建英文视觉上下文，按图片位置选择不同视觉焦点。

        核心改进：取最高优先级分类下的最长隐喻作为**单一完整场景**，
        不再拼接多个碎片概念。AI 模型对单一连贯场景的渲染质量远高于碎片拼接。

        Args:
            narrative_text: 叙事段落文本（中文）
            index: 图片位置索引（0=证据特写, 1=张力对峙, 2=策略博弈）

        Returns:
            英文视觉场景描述字符串（单一完整场景）
        """
        # 1. 按 index 选择优先类别，在该类别中搜索关键词
        category = _CATEGORY_KEYWORDS.get(index, _CATEGORY_KEYWORDS[0])
        best_metaphor = ""  # 取最长的完整隐喻（更具体）
        best_keyword_len = 0

        for keyword in category:
            if keyword in narrative_text:
                metaphor = _VISUAL_METAPHOR_MAP.get(keyword, "")
                if metaphor and len(metaphor) > len(best_metaphor):
                    best_metaphor = metaphor
                    best_keyword_len = len(keyword)

        # 2. 如果该类别命中，直接返回最长隐喻作为单一场景
        if best_metaphor:
            return best_metaphor

        # 3. 该类别无命中 → 降级搜索全量映射表，同样取最长隐喻
        for keyword, metaphor in _VISUAL_METAPHOR_MAP.items():
            if keyword in narrative_text and keyword not in category:
                if len(metaphor) > len(best_metaphor):
                    best_metaphor = metaphor

        if best_metaphor:
            return best_metaphor

        # 4. 最终回退：按 index 返回固定的差异化默认场景
        return _FALLBACK_SCENES[index % len(_FALLBACK_SCENES)]

    def _build_inline_visual_context_for_lang(self, narrative_text: str, index: int) -> str:
        """
        按 prompt_lang 分发到中文或英文视觉上下文构建。

        中文模式：使用具体的中文视觉场景描述（适合插入中文模板）。
        英文模式：使用英文视觉隐喻映射表。
        """
        if self.prompt_lang == "cn":
            return self._build_inline_visual_context_cn(narrative_text, index)
        else:
            return self._build_inline_visual_context(narrative_text, index)

    def _build_inline_visual_context_cn(self, narrative_text: str, index: int) -> str:
        """
        构建中文视觉场景描述，严格复刻 fresh_test_story_narrative 的视觉语言。

        每种 index 有明确的视觉范式：
          - index=0: 微距特写/拆解/放大镜/检查台
          - index=1: 锁链拉扯/国旗色对冲/风暴对抗/撕裂张力
          - index=2: 俯拍棋盘/手影操纵/棋子推倒/战情室
        """
        # 场景范式表（与 index 强绑定而非关键词匹配）
        _CN_SCENE_TEMPLATES = {
            0: [
                "一只手戴着检查手套，手持放大镜对准一块被拆解开的导弹制导芯片。" +
                "芯片表面印有模糊的标识符号，电路纹理在放大镜下清晰可见",
                "武器残骸部件拆解后的精密零件特写——齿轮、弹簧、螺栓散落在法医检测托盘上，" +
                "黄色证据标记标签贴在关键部位，强光任务灯照射",
                "机密文件在暗室中被单束台灯光束照亮的特写，" +
                "放大镜下关键段落清晰可见，证据标记标签散落桌面",
            ],
            1: [
                "画面中心是一个被两条粗大锁链向左右两侧拉扯的地图剪影（红色发光轮廓）。" +
                "左侧锁链末端是对立势力的蓝色光芒，右侧锁链末端是另一方的冷白蓝红光芒，" +
                "两个方向的力量形成对称撕裂感",
                "两股巨大的风暴前哨（深蓝与暗红色）在分裂的地貌上空汇聚，" +
                "城市建筑剪影被困在交火中心，闪电劈裂天空",
                "一个孤立的建筑结构矗立于中央，四面八方的暴风云汇聚逼近，" +
                "闪电击中附近地面，强烈的定向侧光投下长影",
            ],
            2: [
                "俯视视角的国际象棋棋盘，棋盘上用投影标注世界地图经纬线。" +
                "棋盘中心一枚关键棋子正在被推倒，棋子底座隐约是国家标志图案。" +
                "棋盘两端——一端的强力棋子稳居后方，另一端的棋子正在推进",
                "战略地图平铺在昏暗的会议桌上，多只阴影之手从桌边伸入移动图钉和标记，" +
                "红色图钉标注关键位置，军情简报室氛围",
                "棋盘上多枚黑色棋子已被击倒，白色皇后占据主导地位，" +
                "棋盘上有咖啡渍环痕，战情室俯拍视角",
            ],
        }

        # 按 index 选择模板
        templates = _CN_SCENE_TEMPLATES.get(index, _CN_SCENE_TEMPLATES[0])

        # 按叙事文本长度选择模板变体（长文本用更丰富的描述）
        idx_offset = min(len(narrative_text) // 100, len(templates) - 1)
        return templates[idx_offset]

    def _extract_narrative_nodes(self, content: str, count: int) -> List[str]:
        """
        从文章中提取叙事关键节点。
        按段落分割，取信息密度最高的段落。
        """
        # 按段落/换行分割
        paragraphs = [p.strip() for p in content.split('\n') if p.strip()]

        if not paragraphs:
            return ["The central theme of the article"]

        # 按长度和信息密度排序
        scored = []
        for p in paragraphs:
            score = len(p)  # 长度
            # 加分：包含疑问/设问的段落（评书风格特征）
            if any(kw in p for kw in ['您猜', '说到这儿', '咱', '？', '！', '注意']):
                score *= 1.5
            scored.append((score, p))

        scored.sort(reverse=True)

        # 均匀采样（避免全部集中在开头或结尾）
        if len(scored) <= count:
            nodes = [p for _, p in scored]
        else:
            step = len(scored) / count
            indices = [int(i * step) for i in range(count)]
            nodes = [scored[idx][1] for idx in indices]

        return nodes[:count]

    def _extract_visual_keywords_from_text(self, text: str) -> List[str]:
        """从段落中提取视觉关键词"""
        keywords = []
        # 匹配 VISUAL_METAPHOR_MAP 中的词汇
        for keyword in _VISUAL_METAPHOR_MAP:
            if keyword in text:
                keywords.append(keyword)
        # 去重并限制
        return list(dict.fromkeys(keywords))[:3]

    def build_all(
        self,
        title: str,
        content: str,
        summary: str = "",
        num_inline: int = 3,
    ) -> dict:
        """
        一次性构建封面 + 内文配图的全部 prompt。

        Returns:
            {
                "cover": {...},         # 封面 prompt 字典
                "inline": [{...}, ...], # 内文配图 prompt 列表
                "style": str,
                "prompt_lang": str,
            }
        """
        # summary 为空时用 content 作为封面构建素材
        cover = self.build_cover(title, summary if summary else content)
        inline = self.build_inline_prompts(content, num_inline)

        return {
            "cover": cover,
            "inline": inline,
            "style": self.style,
            "prompt_lang": self.prompt_lang,
        }


# ============================================================
# 中文封面视觉隐喻映射表
# 用于 CN 模式下从标题关键词生成中文视觉主体描述
# ============================================================
_CN_COVER_VISUAL_MAP: Dict[str, str] = {
    # 国家/地区实体
    "日本": "一把巨大的武士刀从中间断裂，刀身碎片在空中散落，刀锋折射出冷冽的寒光",
    "美国": "星条旗织物在阴影中剧烈飘动，权力的象征在不确定中摇摆",
    "中国": "红色与金色龙鳞纹理表面在聚光灯下闪耀，古老与现代融合的戏剧性画面",
    "俄罗斯": "冰雪覆盖的工业景观，烟囱和管道延伸至地平线，冷蓝灰色调",
    "乌克兰": "暴风雨聚集云层下的向日葵田，天空中蓝黄色彩交织",
    # 军事/科技实体
    "博弈": "国际象棋棋盘俯视图，关键棋子在中局交锋，棋盘下方投影世界地图经纬线",
    "制裁": "粗大铁链缠绕货运集装箱与工业零件，一节链环在压力下开裂，金属碎片飞溅",
    "冲突": "深蓝与暗红两股巨浪在中点碰撞，水花冻结在空气中",
    "武器": "武器零部件排列在军事检查台上，黄色证据标签贴在关键部位",
    "芯片": "导弹制导芯片超微距特写，金色电路走线与晶体管门在放大镜下清晰可见，冷峻科技感",
    "无人机": "军用侦察无人机从暴风雨云层下方仰拍视角，摄像头与载荷轮廓可见，天空阴沉",
    "导弹": "一枚巡航导弹弹体截面特写，金属外壳上模糊的序列编号，精密机械内部结构",
    "供应链": "全球货运航线投影地图上，集装箱与芯片散落，钢铁锁链连接各节点",
    "军工": "重型工厂内部焊接火花飞溅，暗色铁灰工业氛围，军事装备零件组装线",
    "证据": "法医调查证据板上的照片用红线连接，文件钉在板上，单一审讯灯从上方照射",
    "报告": "机密情报报告文件夹在桌面上打开，放大镜对准关键段落，证据标记散落",
    "零件": "各种机械零件——齿轮、弹簧、螺栓散落在法医检测托盘上，强光任务灯照射",
    # 叙事/情感
    "偷鸡不成蚀把米": "一把断裂的武士刀从中间折断，刀身碎片散落，日本国旗红日在背景中褪色黯淡",
    "反转": "一张扑克牌在半空中翻转展现两面——一面国王一面小丑，戏剧性聚光",
    "揭秘": "沉重的银行金库大门打开一条缝，刺目的光线涌出照亮暗室",
    "曝光": "一份机密文件在暗档案室中被单束台灯光束照亮",
    "困境": "一个建筑结构被四方风暴云围困，闪电劈中附近地面",
    "野心": "一只从黑暗中伸向虚空悬挂的发光星辰的手，指尖仅差几英寸",
    "失败": "宏伟石碑在慢动作中崩塌，尘埃云升腾，鸽子惊飞",
    # 张力/对峙
    "对峙": "两股相对的力量在空间中对撞，暗蓝与暗红光带交错，中央一道闪电劈裂",
    "两难": "一个孤立的建筑结构矗立于中央，左右两侧分别是烈火与洪水的极端环境",
    "棋局": "俯瞰视角的国际棋盘，中心区域棋子正在被推倒，多只阴影之手从边缘伸入",
}


# ============================================================
# CLI 测试
# ============================================================

if __name__ == "__main__":
    builder = CoverPromptBuilder(style="story_narrative")

    title = "日本这回真偷鸡不成蚀把米！拆解援乌武器爆出中国零件，反手被中方制裁"
    summary = "日本前脚刚跟乌克兰签了造无人机的协议，后脚就被乌克兰联合中国制裁了。"

    print("=" * 60)
    print("封面 Prompt 构建测试")
    print("=" * 60)

    result = builder.build_cover(title, summary)
    print(f"\n视觉隐喻: {result['visual_metaphor']}")
    print(f"风格: {result['style']}")
    print(f"\nFinal Prompt:\n{result['prompt']}")
    if result['compliance']['warnings']:
        print(f"\n⚠️ 合规警告:")
        for w in result['compliance']['warnings']:
            print(f"  {w}")

    print("\n" + "=" * 60)
    print("内文配图 Prompt 构建测试")
    print("=" * 60)

    sample_content = (
        "家人们，您猜怎么着，日本这回可真是偷鸡不成蚀把米！\n"
        "您猜报告里说了啥？俄军现在用的巡航导弹，里面九成的核心电子零部件，全是日本厂商供的货！\n"
        "说到这儿，您可能问了：这些零件不是军用的吧？\n"
        "乌克兰这一手，直接把日本架在火上烤。"
    )

    inline_results = builder.build_inline_prompts(sample_content, 3)
    for i, r in enumerate(inline_results):
        print(f"\n[配图 {i+1}] 叙事节点: {r['narrative_point']}")
        print(f"  Prompt: {r['prompt'][:150]}...")
