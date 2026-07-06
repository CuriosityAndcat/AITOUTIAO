#!/usr/bin/env python3
"""
依赖检测脚本
自动检测 ffmpeg、faster-whisper、OpenCC 等关键依赖是否安装就绪，
给出缺失提示和安装命令。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import os
from pathlib import Path
from typing import NamedTuple

# 修复 Windows GBK 编码问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class DepStatus(NamedTuple):
    name: str
    installed: bool
    version: str
    hint: str  # 安装指引


def check_ffmpeg() -> DepStatus:
    """检测 ffmpeg 是否可用"""
    path = shutil.which("ffmpeg")
    if not path:
        return DepStatus(
            name="ffmpeg",
            installed=False,
            version="",
            hint="下载并安装 ffmpeg: https://ffmpeg.org/download.html\n"
                 "  - Windows: 推荐使用 winget install ffmpeg 或 choco install ffmpeg\n"
                 "  - 手动: 下载后将 bin 目录加入 PATH 环境变量",
        )
    try:
        result = subprocess.run(
            [path, "-version"], capture_output=True, text=True, timeout=10
        )
        first_line = result.stdout.split("\n")[0] if result.stdout else "unknown"
        return DepStatus(
            name="ffmpeg",
            installed=True,
            version=first_line.strip(),
            hint="",
        )
    except Exception:
        return DepStatus(
            name="ffmpeg",
            installed=True,
            version=f"found at {path}",
            hint="",
        )


def check_faster_whisper() -> DepStatus:
    """检测 faster-whisper 是否可用"""
    try:
        import faster_whisper  # noqa: F401
        # 尝试获取版本
        if hasattr(faster_whisper, "__version__"):
            ver = faster_whisper.__version__
        else:
            ver = "installed"
        return DepStatus(
            name="faster-whisper",
            installed=True,
            version=ver,
            hint="",
        )
    except ImportError:
        return DepStatus(
            name="faster-whisper",
            installed=False,
            version="",
            hint="pip install faster-whisper",
        )


def check_opencc() -> DepStatus:
    """检测 OpenCC（繁体转简体）是否可用"""
    try:
        import opencc  # noqa: F401
        ver = getattr(opencc, "__version__", "installed")
        return DepStatus(
            name="opencc",
            installed=True,
            version=ver,
            hint="",
        )
    except ImportError:
        return DepStatus(
            name="opencc-python-reimplemented",
            installed=False,
            version="",
            hint="pip install opencc-python-reimplemented",
        )


def check_playwright() -> DepStatus:
    """检测 Playwright（Node.js 侧用）是否可用"""
    # 检测 Node.js 侧
    npm_playwright = False
    try:
        result = subprocess.run(
            ["npx", "playwright", "--version"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            npm_playwright = True
            ver = result.stdout.strip()
            return DepStatus(
                name="playwright (Node.js)",
                installed=True,
                version=ver,
                hint="",
            )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return DepStatus(
        name="playwright (Node.js)",
        installed=False,
        version="",
        hint="cd video-batch-download-main && npm install && npx playwright install chromium",
    )


def check_node() -> DepStatus:
    """检测 Node.js 是否可用"""
    try:
        result = subprocess.run(
            ["node", "--version"], capture_output=True, text=True, timeout=10
        )
        ver = result.stdout.strip()
        return DepStatus(
            name="Node.js",
            installed=True,
            version=ver,
            hint="",
        )
    except FileNotFoundError:
        return DepStatus(
            name="Node.js",
            installed=False,
            version="",
            hint="下载并安装 Node.js: https://nodejs.org/ (推荐 LTS 版本)",
        )


def check_toutiao_publisher_deps() -> list[DepStatus]:
    """检测 toutiao-auto-publisher 的 Python 依赖"""
    deps = []
    for pkg in ["fastapi", "uvicorn", "pydantic_settings", "playwright"]:
        try:
            __import__(pkg.replace("-", "_"))
            deps.append(DepStatus(name=pkg, installed=True, version="installed", hint=""))
        except ImportError:
            deps.append(DepStatus(
                name=pkg,
                installed=False,
                version="",
                hint=f"pip install {pkg}" if pkg != "playwright" else "pip install playwright",
            ))
    return deps


def main() -> int:
    print("=" * 60)
    print("AIToutiao 依赖检测")
    print("=" * 60)

    checks: list[DepStatus] = []

    # 基础工具
    print("\n[基础工具]")
    status = check_node()
    checks.append(status)
    print(f"  Node.js : {'✓ ' + status.version if status.installed else '✗ 未安装'}")

    status = check_ffmpeg()
    checks.append(status)
    print(f"  ffmpeg  : {'✓ ' + status.version if status.installed else '✗ 未安装'}")

    # Python 转录依赖
    print("\n[转录依赖]")
    status = check_faster_whisper()
    checks.append(status)
    print(f"  faster-whisper: {'✓ ' + status.version if status.installed else '✗ 未安装'}")

    status = check_opencc()
    checks.append(status)
    print(f"  opencc : {'✓ ' + status.version if status.installed else '✗ 未安装'}")

    # 浏览器自动化
    print("\n[浏览器自动化]")
    status = check_playwright()
    checks.append(status)
    print(f"  playwright : {'✓ ' + status.version if status.installed else '✗ 未安装'}")

    # 发布端依赖
    print("\n[发布端依赖]")
    for status in check_toutiao_publisher_deps():
        checks.append(status)
        print(f"  {status.name}: {'✓' if status.installed else '✗ 未安装'}")

    # 汇总
    missing = [c for c in checks if not c.installed]
    print("\n" + "=" * 60)
    if missing:
        print(f"✗ {len(missing)} 个依赖缺失，安装指引：\n")
        for m in missing:
            print(f"  [{m.name}]")
            print(f"  {m.hint}\n")
        print("=" * 60)
        return 1
    else:
        print("✓ 所有依赖就绪！")
        print("=" * 60)
        return 0


if __name__ == "__main__":
    sys.exit(main())
