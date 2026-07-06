"""
URL 提取逻辑完整性测试
测试 extract_douyin_url 的所有场景：纯 URL、分享文本、无效输入、边界情况
"""
import re
import sys
from pathlib import Path

import pytest

# ── 直接从 streamlit_app 导入或用内置函数 ──
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from streamlit_app import extract_douyin_url
except ImportError:
    # 如果 streamlit 不可用，内联测试函数
    def extract_douyin_url(raw_text: str):
        raw_text = raw_text.strip()
        if re.match(r'^https?://', raw_text):
            m = re.match(r'^(https?://[^\s]+)', raw_text)
            if m:
                url = m.group(1).rstrip('.,;:!?。，；：！？')
                return url
            return raw_text
        url_patterns = [
            r'https?://v\.douyin\.com/[^\s]+',
            r'https?://www\.douyin\.com/video/[^\s]+',
            r'https?://www\.douyin\.com/user/[^\s]+',
            r'https?://www\.iesdouyin\.com/[^\s]+',
            r'https?://[^\s]*douyin[^\s]*',
            r'https?://[^\s]+',
        ]
        for pattern in url_patterns:
            m = re.search(pattern, raw_text)
            if m:
                url = m.group(0).rstrip('.,;:!?。，；：！？')
                if len(url) > 15 and ('douyin.com' in url or 'iesdouyin.com' in url):
                    return url
                elif len(url) > 15:
                    return url
        return None


class TestPureURL:
    """测试纯 URL 输入"""

    def test_douyin_short_link(self):
        url = "https://v.douyin.com/wPI_y-7jkO4/"
        assert extract_douyin_url(url) == url

    def test_douyin_full_video_link(self):
        url = "https://www.douyin.com/video/7656760597240958214"
        assert extract_douyin_url(url) == url

    def test_iesdouyin_link(self):
        url = "https://www.iesdouyin.com/share/video/7656760597240958214/"
        assert extract_douyin_url(url) == url

    def test_url_with_trailing_punctuation(self):
        result = extract_douyin_url("https://v.douyin.com/abc123/。")
        assert result == "https://v.douyin.com/abc123/"

    def test_url_with_trailing_comma(self):
        result = extract_douyin_url("https://v.douyin.com/abc123/，")
        assert result == "https://v.douyin.com/abc123/"


class TestShareTextExtraction:
    """测试从抖音分享文本中提取 URL"""

    def test_typical_share_text(self):
        text = '1.74 aAG:/ :3pm 抖音独家 | 普京急了  https://v.douyin.com/i_WuLosoDww/ 复制此链接，打开Dou音搜索，直接观看视频！'
        result = extract_douyin_url(text)
        assert result == "https://v.douyin.com/i_WuLosoDww/"

    def test_share_text_with_special_chars(self):
        text = '# 零基础看懂全球 # 全球创作者计划  https://v.douyin.com/abc123def/ 复制此链接'
        result = extract_douyin_url(text)
        assert result == "https://v.douyin.com/abc123def/"

    def test_share_text_with_chinese_quotes(self):
        text = '\u201c\u201d 链接 https://v.douyin.com/test456/ 打开'
        result = extract_douyin_url(text)
        assert result == "https://v.douyin.com/test456/"


class TestEdgeCases:
    """边界和异常情况"""

    def test_empty_string(self):
        assert extract_douyin_url("") is None
        assert extract_douyin_url("   ") is None

    def test_no_url_text(self):
        assert extract_douyin_url("这是一段没有链接的文本") is None

    def test_short_garbage(self):
        assert extract_douyin_url("abc") is None

    def test_non_douyin_url(self):
        result = extract_douyin_url("https://www.bilibili.com/video/av123456")
        assert result == "https://www.bilibili.com/video/av123456"


class TestMultiLineText:
    """多行文本场景"""

    def test_url_in_middle_of_text(self):
        text = "普京最新表态\nhttps://v.douyin.com/putin-special/\n详细解读"
        result = extract_douyin_url(text)
        assert result == "https://v.douyin.com/putin-special/"

    def test_multiple_urls_pick_first_douyin(self):
        text = "看视频：https://v.douyin.com/xyz789/ 原文：https://www.baidu.com/abc"
        result = extract_douyin_url(text)
        assert "douyin.com" in result
