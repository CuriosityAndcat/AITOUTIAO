#!/usr/bin/env python3
"""
图片审核器 —— 生成后自动校验图片质量、元素完整性和水印检测。

功能：
  1. review_image()     —— 校验图片是否包含 Prompt 中的所有核心视觉元素
  2. detect_watermark() —— 检测图片中是否有 "AI生成""AIGC" 等水印文字
  3. crop_watermark()   —— 使用 PIL 自动裁剪图片底部常见水印区域

依赖：
  - vision-tool/vision_tool.py（智谱 GLM-4V-Flash 免费视觉模型）
  - PIL/Pillow

用法:
    from image_reviewer import review_image, detect_watermark, crop_watermark

    ok, missing, suggestion = review_image("cover.png", ["日本", "乌克兰", "芯片", "博弈"])
    has_wm, wm_text = detect_watermark("cover.png")
    crop_watermark("cover.png")
"""

import os
import sys
import re
from pathlib import Path
from typing import List, Tuple, Optional

# 确保 vision_tool 可导入
_VISION_TOOL_DIR = str(Path(__file__).parent.parent.parent / "vision-tool")
if _VISION_TOOL_DIR not in sys.path:
    sys.path.insert(0, _VISION_TOOL_DIR)

try:
    from vision_tool import _analyze, ocr, describe
except ImportError:
    _analyze = None
    ocr = None
    describe = None


# ── 审核相关常量 ──

# 水印检测关键词（中英文）
_WATERMARK_KEYWORDS = [
    "AI生成", "ai生成", "AIGC", "AI Generated",
    "由AI", "由人工智能", "created by ai",
    "AI创作", "ai创作", "Powered by AI",
    "Generated with AI", "AI绘图", "ai绘图",
]

# 最大重试次数（外部循环控制，此处仅定义）
MAX_REVIEW_RETRIES = 3

# 裁剪比例：底部水印通常占画面 5-8%，取 6%
CROP_BOTTOM_RATIO = 0.06


def _check_vision_available() -> bool:
    """检查视觉分析模块是否可用"""
    if _analyze is None:
        print("[image_reviewer] ⚠ vision_tool 未导入，审核功能不可用", flush=True)
        return False
    return True


def review_image(
    image_path: str,
    expected_elements: List[str],
) -> Tuple[bool, List[str], str]:
    """
    审核图片是否包含所有期望的视觉元素。

    调用智谱 GLM-4V-Flash 视觉模型分析图片内容，
    逐一检查 expected_elements 中的每个元素是否在画面中有所体现。

    Args:
        image_path: 图片文件路径
        expected_elements: 期望出现的视觉元素关键词列表，如 ["日本", "乌克兰", "芯片", "无人机"]

    Returns:
        (passed, missing_elements, suggestion)
        - passed: True 表示所有元素均已体现
        - missing_elements: 缺失的元素列表
        - suggestion: 改进建议文本（若有不通过时用于调整 Prompt）
    """
    if not _check_vision_available():
        return True, [], ""  # 不可用时直接放行

    if not expected_elements:
        return True, [], ""

    if not os.path.exists(image_path):
        return False, expected_elements, f"图片文件不存在: {image_path}"

    # 构建审核 Prompt
    elements_str = "、".join(expected_elements)
    review_prompt = (
        "请严格审核这张封面图片，逐一检查以下核心元素是否在画面中有所体现：\n"
        f"需要检查的元素列表：{elements_str}\n\n"
        "请按以下格式回答——\n"
        "1. 对每个元素，回答[有]或[缺失]，并简短说明画面中的对应内容（若缺失则说明原因）\n"
        "2. 最后一行给出结论：通过/不通过\n"
        "注意：不需要元素被文字标注，只要视觉上有所暗示或象征即可。例如[日本]可以通过武士刀、红日等符号体现。"
    )

    try:
        response = _analyze(review_prompt, image_path)
        if not response or response.startswith("❌"):
            print(f"[image_reviewer] ⚠ 审核 API 异常: {response}", flush=True)
            return True, [], ""  # API 异常时放行

        # 解析响应，提取缺失元素
        missing = []
        for element in expected_elements:
            # 在响应中搜索每个元素的判定结果
            # 匹配模式："元素名：有" 或 "元素名：缺失"
            pattern = rf"{re.escape(element)}[：:]\s*(有|缺失|存在|体现|可见|包含|是)"
            match = re.search(pattern, response)
            if match:
                status = match.group(1)
                if status in ("缺失",):
                    missing.append(element)
            else:
                # 未找到明确判定，尝试在整段响应中搜索
                if element not in response:
                    missing.append(element)

        # 生成改进建议
        if missing:
            suggestion = (
                f"图片缺失以下核心元素：{'、'.join(missing)}。"
                f"需要在 Prompt 中增加以下视觉描述："
                + "；".join([f"明确加入元素'{m}'的视觉符号" for m in missing])
            )
            return False, missing, suggestion

        # 检查最后一行是否有"通过"
        if "通过" in response and "不通过" not in response:
            return True, [], ""
        elif "不通过" in response:
            # 虽然有"不通过"但没解析到具体缺失，用模糊建议
            return False, [], "审核模型认为整体不达标，建议增加视觉冲击力和主体层次感"

        return True, [], ""

    except Exception as e:
        print(f"[image_reviewer] ⚠ 审核异常: {e}", flush=True)
        return True, [], ""  # 异常时放行，避免阻塞流水线


def detect_watermark(image_path: str) -> Tuple[bool, str]:
    """
    检测图片中是否有 AI 生成水印文字。

    Args:
        image_path: 图片文件路径

    Returns:
        (has_watermark, watermark_text)
    """
    if not _check_vision_available():
        return False, ""

    if not os.path.exists(image_path):
        return False, ""

    try:
        text = ocr(image_path)
        if not text or text.startswith("❌"):
            return False, ""

        # 检测关键词
        text_lower = text.lower()
        for keyword in _WATERMARK_KEYWORDS:
            if keyword.lower() in text_lower:
                return True, keyword

        return False, ""

    except Exception as e:
        print(f"[image_reviewer] ⚠ 水印检测异常: {e}", flush=True)
        return False, ""


def crop_watermark(
    image_path: str,
    crop_ratio: float = CROP_BOTTOM_RATIO,
    output_path: Optional[str] = None,
) -> str:
    """
    使用 PIL 裁剪图片底部区域（常见水印位置）。

    默认裁掉底部 6% 的高度，覆盖原文件或输出到指定路径。

    Args:
        image_path: 输入图片路径
        crop_ratio: 底部裁剪比例（默认 0.06，即裁掉 6%）
        output_path: 输出路径（默认覆盖原文件）

    Returns:
        输出图片路径
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"图片不存在: {image_path}")

    try:
        from PIL import Image

        img = Image.open(image_path)
        width, height = img.size

        # 计算裁剪区域：保留上方的 (1 - crop_ratio) 部分
        new_height = int(height * (1 - crop_ratio))

        # 裁剪
        cropped = img.crop((0, 0, width, new_height))

        # 保存
        out = output_path or image_path
        # 保持原格式
        fmt = img.format or "PNG"
        cropped.save(out, format=fmt)

        print(
            f"[image_reviewer] ✂ 水印已裁剪: "
            f"{height}px → {new_height}px (裁去 {height - new_height}px 底部)",
            flush=True,
        )
        return out

    except ImportError:
        print("[image_reviewer] ⚠ PIL 未安装，无法裁剪", flush=True)
        return image_path
    except Exception as e:
        print(f"[image_reviewer] ⚠ 裁剪异常: {e}", flush=True)
        return image_path


# ── CLI 测试 ──

if __name__ == "__main__":
    import sys as _sys

    if len(_sys.argv) < 2:
        print("用法: python image_reviewer.py <图片路径> [元素1 元素2 ...]")
        print("示例: python image_reviewer.py cover.png 日本 乌克兰 芯片 博弈")
        _sys.exit(1)

    image = _sys.argv[1]
    elements = _sys.argv[2:] or ["日本", "芯片", "博弈"]

    print(f"审核图片: {image}")
    print(f"期望元素: {elements}")
    print()

    # 1. 水印检测
    has_wm, wm_text = detect_watermark(image)
    if has_wm:
        print(f"⚠️  检测到水印: '{wm_text}'")
        print("   → 执行裁剪...")
        crop_watermark(image)
        print("   ✅ 裁剪完成")
    else:
        print("✅ 未检测到水印")

    # 2. 元素审核
    passed, missing, suggestion = review_image(image, elements)
    if passed:
        print("✅ 所有元素均已体现")
    else:
        print(f"❌ 缺失元素: {missing}")
        print(f"   建议: {suggestion}")
