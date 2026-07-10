#!/usr/bin/env python3
"""
合规审查器 —— 确保 AI 图片生成 prompt 符合今日头条平台规范。

功能：
  1. 分级敏感词库（武器/暴力/政治/恐怖等类别）
  2. prompt 扫描 + 风险等级判定
  3. 安全替代建议生成
  4. 自动告警 + 可选拦截

今日头条图片审核红线（部分）：
  - 禁止武器公然展示（刀、枪、爆炸物等）
  - 禁止暴力//血腥场景（伤口、血迹、残骸）
  - 禁止敏感政治符号不当使用
  - 禁止恐怖/战争恐怖场景

用法:
    from compliance_checker import check
    result = check("a broken sword with blood on the blade")
    if not result.passed:
        print(result.warnings)
        print(result.safe_alternative)
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


# ============================================================
# 风险等级
# ============================================================

class RiskLevel(str, Enum):
    SAFE = "safe"              # 安全通过
    LOW = "low"                # 轻微风险，建议修改
    MEDIUM = "medium"          # 中等风险，需要替换
    HIGH = "high"              # 高风险，必须拦截


# ============================================================
# 敏感词分级词库
# ============================================================

# 高风险（直接拦截）
_HIGH_RISK_WORDS = [
    # 血腥暴力
    "blood", "bleeding", "gore", "mutilated", "severed",
    "corpse", "dead body", "carnage", "slaughter",
    "decapitated", "dismembered",
    # 恐怖主义
    "terrorist", "terrorism", "beheading", "execution",
    "hostage", "torture", "massacre",
    # 色情
    "nude", "naked", "porn", "sexual", "explicit",
    # 政治极端符号
    "swastika", "nazi", "ISIS", "jihadist",
]

# 中风险（需要替换）
_MEDIUM_RISK_WORDS = [
    # 武器公然展示
    "sword", "blade", "knife", "dagger", "katana",
    "gun", "rifle", "pistol", "weapon", "firearm",
    "bullet", "ammunition", "explosive", "bomb",
    "missile", "rocket launcher", "grenade",
    # 战争残骸
    "wreckage", "debris of war", "battlefield",
    "destroyed", "warship", "tank", "military vehicle",
    "troops", "soldier", "armed forces",
    # 敏感政治符号
    "flag burning", "flag torn", "flag fragment",
    "shattered flag", "broken flag",
    "leader", "president", "dictator",
    "protest", "riot",
]

# 低风险（建议优化）
_LOW_RISK_WORDS = [
    # 可能的暴力暗示
    "broken", "shattered", "cracked", "crushed",
    "fighting", "conflict", "tension",
    "aggressive", "hostile",
    # 可优化的军事相关
    "military", "war", "combat", "battle",
    "surveillance", "drone", "fighter jet",
]

# 白名单（允许通过的安全替代关键词）
_SAFE_ALTERNATIVES = {
    "sword": "historical artifact",
    "katana": "decorative art piece",
    "blade": "metal craftsmanship",
    "knife": "hand tool",
    "gun": "industrial equipment",
    "weapon": "mechanical device",
    "broken sword": "fractured art sculpture",
    "shattered sword": "abstract geometric sculpture",
    "broken katana": "abstract metallic sculpture",
    "missile": "aerodynamic object",
    "bomb": "spherical device",
    "blood": "crimson texture",
    "battlefield": "historical landscape",
    "wreckage": "industrial remains",
    "tank": "heavy machinery",
    "military": "historical",
    "war": "conflict",
    "drone": "aerial vehicle",
    "fighting": "competing forces",
    "explosive": "energetic material",
    "shattered flag": "abstract color field",
    "broken flag": "textured fabric art",
    "flag fragment": "abstract textile composition",
}

# 安全词白名单：这些科技/调查/学术中性词永远不会被标记为风险
# 确保 magnifying glass、forensic、circuit、chip、precision 等不会被误判
SAFE_NEUTRAL_WORDS = {
    "magnifying glass", "magnifying", "forensic", "document",
    "circuit", "circuit board", "microchip", "chip",
    "precision", "component", "components", "industrial",
    "inspection", "laboratory", "gold-plated", "holographic",
    "aerial", "silhouette", "photograph", "photographic",
    "editorial", "composition", "macro", "cinematic",
}


@dataclass
class ComplianceResult:
    """合规审查结果"""
    passed: bool                     # 是否通过审查
    risk_level: RiskLevel = RiskLevel.SAFE
    warnings: List[str] = field(default_factory=list)   # 警告信息
    replacements: dict = field(default_factory=dict)     # 建议替换 {旧词: 新词}
    safe_prompt: Optional[str] = None  # 清洗后的安全 prompt


def _scan_keywords(prompt: str) -> List[tuple]:
    """
    扫描 prompt 中的敏感词。
    返回 [(词, 风险等级), ...]
    """
    hits = []
    prompt_lower = prompt.lower()

    for word in _HIGH_RISK_WORDS:
        if _match_word(word, prompt_lower) and word not in SAFE_NEUTRAL_WORDS:
            hits.append((word, RiskLevel.HIGH))

    for word in _MEDIUM_RISK_WORDS:
        if _match_word(word, prompt_lower) and word not in SAFE_NEUTRAL_WORDS:
            hits.append((word, RiskLevel.MEDIUM))

    for word in _LOW_RISK_WORDS:
        if _match_word(word, prompt_lower) and word not in SAFE_NEUTRAL_WORDS:
            hits.append((word, RiskLevel.LOW))

    return hits


def _match_word(word: str, text: str) -> bool:
    """检查词汇是否在文本中出现（精确匹配）。"""
    # 构建正则：单词边界匹配
    pattern = r'\b' + re.escape(word) + r'\b'
    return bool(re.search(pattern, text))


def _get_alternative(word: str) -> Optional[str]:
    """获取敏感词的安全替代"""
    word_lower = word.lower()
    if word_lower in _SAFE_ALTERNATIVES:
        return _SAFE_ALTERNATIVES[word_lower]

    # 尝试部分匹配
    for key, value in _SAFE_ALTERNATIVES.items():
        if key in word_lower:
            return value

    return None


def _build_safe_prompt(original: str, hits: List[tuple]) -> str:
    """基于命中的敏感词，构建安全版本的 prompt"""
    result = original
    replacements_made = {}

    # 按风险等级排序，先处理高风险
    for word, level in sorted(hits, key=lambda x: [RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW].index(x[1])):
        alt = _get_alternative(word)
        if alt:
            # 使用正则实现词边界替换
            pattern = r'\b' + re.escape(word) + r'\b'
            result = re.sub(pattern, alt, result, flags=re.IGNORECASE)
            replacements_made[word] = alt

    return result, replacements_made


def check(prompt: str, auto_fix: bool = True) -> ComplianceResult:
    """
    对 prompt 进行合规审查。

    Args:
        prompt: 待审查的 prompt 文本
        auto_fix: 是否自动生成安全替代版本

    Returns:
        ComplianceResult 包含风险等级、警告、安全 prompt 等
    """
    hits = _scan_keywords(prompt)

    if not hits:
        return ComplianceResult(
            passed=True,
            risk_level=RiskLevel.SAFE,
            warnings=[],
        )

    # 按最高风险等级归类
    high_hits = [w for w, l in hits if l == RiskLevel.HIGH]
    medium_hits = [w for w, l in hits if l == RiskLevel.MEDIUM]
    low_hits = [w for w, l in hits if l == RiskLevel.LOW]

    warnings = []
    max_level = RiskLevel.SAFE

    if high_hits:
        max_level = RiskLevel.HIGH
        warnings.append(f"🚫 高风险词: {', '.join(high_hits)} — 必须移除")
    if medium_hits:
        if max_level.value < RiskLevel.MEDIUM.value:
            max_level = RiskLevel.MEDIUM
        warnings.append(f"⚠️ 中风险词: {', '.join(medium_hits)} — 建议替换")
    if low_hits:
        if max_level == RiskLevel.SAFE:
            max_level = RiskLevel.LOW
        warnings.append(f"💡 低风险词: {', '.join(low_hits)} — 可优化")

    result = ComplianceResult(
        passed=(max_level != RiskLevel.HIGH),
        risk_level=max_level,
        warnings=warnings,
    )

    # 自动生成安全版本
    if auto_fix and not (high_hits and not all(_get_alternative(w) for w in high_hits)):
        safe_prompt, replacements = _build_safe_prompt(prompt, hits)
        result.safe_prompt = safe_prompt
        result.replacements = replacements

        if replacements:
            result.warnings.append(f"✅ 自动替换: {replacements}")

    return result


def is_safe(prompt: str) -> bool:
    """快速检查：prompt 是否安全可生成"""
    return check(prompt, auto_fix=False).passed


def check_and_fix(prompt: str) -> tuple:
    """
    审查并自动修复。返回 (safe_prompt, warnings)。
    如果有高风险词且无法替换，返回 (None, warnings)。
    """
    result = check(prompt, auto_fix=True)

    if result.passed:
        if result.safe_prompt:
            return result.safe_prompt, result.warnings
        return prompt, []

    # 高风险且无法自动修复
    return None, result.warnings


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
    else:
        # 默认测试
        test_prompts = [
            "A broken katana sword on dark background, cinematic lighting",
            "Blood splattered battlefield scene with dead bodies",
            "A peaceful landscape with cherry blossoms, no weapons",
            "Military tank wreckage in war zone with explosions",
        ]
        for p in test_prompts:
            print(f"\n{'='*60}")
            print(f"[Input]  {p[:100]}")
            result = check(p)
            print(f"[Level]  {result.risk_level.value}")
            if result.warnings:
                for w in result.warnings:
                    print(f"  {w}")
            if result.safe_prompt:
                print(f"[Fixed]  {result.safe_prompt[:120]}...")
            print()
        sys.exit(0)

    result = check(prompt)
    print(f"Risk Level: {result.risk_level.value}")
    for w in result.warnings:
        print(w)
    if result.safe_prompt:
        print(f"\nSafe version:\n{result.safe_prompt}")
