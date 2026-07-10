"""
发布服务模块 — 今日头条浏览器自动化发布
基于 Playwright 实现，不依赖外部脚本模块
"""
import time
import os
import sys
import json
import random
from pathlib import Path
from typing import Optional, Dict, Any

from patchright.sync_api import sync_playwright, Playwright, BrowserContext, Page

# ===== 配置常量 =====
TOUTIAO_LOGIN_URL = "https://mp.toutiao.com/auth/page/login"
TOUTIAO_PUBLISH_URL = "https://mp.toutiao.com/profile_v4/graphic/publish"
TOUTIAO_HOME_URL = "https://mp.toutiao.com/"

# 路径配置
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
BROWSER_STATE_DIR = DATA_DIR / "browser_state"
BROWSER_PROFILE_DIR = BROWSER_STATE_DIR / "browser_profile"
STATE_FILE = BROWSER_STATE_DIR / "state.json"
AUTH_INFO_FILE = DATA_DIR / "auth_info.json"

# 浏览器参数
BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--no-first-run",
    "--no-default-browser-check",
]
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# 确保目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)
BROWSER_STATE_DIR.mkdir(parents=True, exist_ok=True)


# ===== 浏览器工厂 =====
class BrowserFactory:
    """工厂类：创建配置好的浏览器上下文（反检测）"""

    @staticmethod
    def launch_persistent_context(
        playwright: Playwright,
        headless: bool = True,
        user_data_dir: str = str(BROWSER_PROFILE_DIR),
    ) -> BrowserContext:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            channel="chrome",
            headless=headless,
            no_viewport=True,
            ignore_default_args=["--enable-automation"],
            user_agent=USER_AGENT,
            args=BROWSER_ARGS,
        )
        # Cookie 注入（解决 Playwright session cookie 持久化 bug）
        BrowserFactory._inject_cookies(context)
        return context

    @staticmethod
    def _inject_cookies(context: BrowserContext):
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "r") as f:
                    state = json.load(f)
                    if "cookies" in state and len(state["cookies"]) > 0:
                        context.add_cookies(state["cookies"])
            except Exception as e:
                print(f"  ⚠️ Cookie 注入失败：{e}")


# ===== 认证管理器 =====
class AuthManager:
    """管理今日头条登录认证"""

    def __init__(self):
        self.state_file = STATE_FILE
        self.auth_info_file = AUTH_INFO_FILE
        self.browser_state_dir = BROWSER_STATE_DIR

    def is_authenticated(self) -> bool:
        return self.state_file.exists()

    def get_auth_info(self) -> Dict[str, Any]:
        info = {
            "authenticated": self.is_authenticated(),
            "state_exists": self.state_file.exists(),
        }
        if self.auth_info_file.exists():
            try:
                with open(self.auth_info_file, "r") as f:
                    info.update(json.load(f))
            except Exception:
                pass
        if info["state_exists"]:
            age_hours = (time.time() - self.state_file.stat().st_mtime) / 3600
            info["state_age_hours"] = round(age_hours, 1)
        return info

    def setup_auth(self, headless: bool = False, timeout_minutes: int = 10) -> bool:
        """打开浏览器让用户扫码登录"""
        print("🔐 启动登录流程...")
        try:
            with sync_playwright() as p:
                context = BrowserFactory.launch_persistent_context(p, headless=headless)
                page = context.new_page()
                page.goto(TOUTIAO_LOGIN_URL, wait_until="domcontentloaded")

                # 检查是否已登录
                if ("mp.toutiao.com" in page.url and
                        "auth/page/login" not in page.url):
                    print("  ✅ 已登录！")
                    self._save_browser_state(context)
                    self._save_auth_info()
                    context.close()
                    return True

                print("  ⏳ 请扫码登录...")
                start_time = time.time()
                while time.time() - start_time < (timeout_minutes * 60):
                    for p in context.pages:
                        try:
                            url = p.url
                            if ("profile_v4" in url or
                                    ("mp.toutiao.com" in url and "auth/page/login" not in url)):
                                print("  ✅ 登录成功！")
                                time.sleep(2)
                                self._save_browser_state(context)
                                self._save_auth_info()
                                context.close()
                                return True
                        except Exception:
                            continue
                    time.sleep(1)

                print("  ❌ 登录超时")
                context.close()
                return False
        except Exception as e:
            print(f"  ❌ 登录失败：{e}")
            return False

    def _save_browser_state(self, context: BrowserContext):
        try:
            context.storage_state(path=str(self.state_file))
            print(f"  💾 登录状态已保存：{self.state_file}")
        except Exception as e:
            print(f"  ❌ 保存状态失败：{e}")

    def _save_auth_info(self):
        try:
            info = {
                "authenticated_at": time.time(),
                "authenticated_at_iso": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(self.auth_info_file, "w") as f:
                json.dump(info, f, indent=2)
        except Exception:
            pass

    def clear_auth(self) -> bool:
        try:
            if self.state_file.exists():
                self.state_file.unlink()
            if self.auth_info_file.exists():
                self.auth_info_file.unlink()
            if self.browser_state_dir.exists():
                import shutil
                shutil.rmtree(self.browser_state_dir)
                self.browser_state_dir.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            print(f"  ❌ 清除认证失败：{e}")
            return False


# ===== Markdown 转 HTML =====
def convert_markdown_to_html(text: str) -> str:
    """
    简单 Markdown 转 HTML（针对今日头条）
    支持：标题、加粗、列表、段落
    """
    import re
    html = text
    # 标题
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    # 加粗
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    # 列表
    html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    # 段落
    html = re.sub(r'\n\n+', '</p><p>', html)
    html = f'<p>{html}</p>'
    return html


# ===== 发布核心逻辑 =====
def _copy_image_to_clipboard(image_path: str) -> bool:
    """Windows 下将图片复制到剪贴板"""
    import platform
    system = platform.system()
    image_path = str(Path(image_path).resolve())

    if system == "Windows":
        escaped = image_path.replace("'", "''")
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms;"
            "Add-Type -AssemblyName System.Drawing;"
            f"$img = [System.Drawing.Image]::FromFile('{escaped}');"
            "[System.Windows.Forms.Clipboard]::SetImage($img);"
            "$img.Dispose()"
        )
        result = os.system(f'powershell.exe -NoProfile -Sta -Command "{ps}"')
        return result == 0
    return False


def _click_publish_buttons(page: Page) -> bool:
    """点击发布按钮的两步流程"""
    try:
        # Step 1: 点击"预览并发布"
        initial_btn = page.locator("button").filter(has_text="预览并发布").last
        if not initial_btn.is_visible():
            initial_btn = page.locator("button").filter(has_text="发布").last

        if initial_btn.is_visible() and initial_btn.is_enabled():
            initial_btn.click()
            print("  ✅ 初始发布按钮已点击")
        else:
            page.evaluate("document.querySelector('.publish-btn')?.click()")

        time.sleep(8)

        # Step 2: 点击最终确认按钮
        final_btn = page.locator(".publish-btn-last").first
        if final_btn.is_visible():
            final_btn.click()
        else:
            modal_confirm = (
                page.locator(".byte-modal .byte-btn-primary")
                .filter(has_text="确定")
                .or_(page.locator(".byte-modal .byte-btn-primary").filter(has_text="确认发布"))
                .last
            )
            if modal_confirm.is_visible():
                modal_confirm.click()

        time.sleep(5)

        # 检查成功提示
        for text in ["发布成功", "主页查看", "已发布"]:
            try:
                if page.get_by_text(text).is_visible():
                    print(f"  ✨ 发布成功！找到提示：{text}")
                    return True
            except:
                pass
        return True
    except Exception as e:
        print(f"  ❌ 发布按钮点击失败：{e}")
        return False


def publish_article(
    title: str,
    content: str,
    cover_path: Optional[str] = None,
    auto_publish: bool = True,
    headless: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    发布文章到今日头条

    Args:
        title: 文章标题（2-30字）
        content: 文章内容（支持 Markdown）
        cover_path: 封面图片路径
        auto_publish: 是否自动点击发布
        headless: 是否无头模式
        dry_run: 试运行

    Returns:
        dict: {"success": bool, "message": str}
    """
    result = {"success": False, "message": ""}

    # 标题长度处理
    if title and len(title) > 30:
        title = title[:30]
    if title and len(title) < 2:
        title = f"{title}..."

    # Markdown 转 HTML
    print("🔄 转换内容格式...")
    content_html = convert_markdown_to_html(content)

    print(f"🚀 启动浏览器（Headless: {headless}）...")

    with sync_playwright() as p:
        context = BrowserFactory.launch_persistent_context(p, headless=headless)
        page = context.pages[0] if context.pages else context.new_page()

        try:
            # 导航到发布页面
            print(f"🌐 正在访问发布页面...")
            try:
                page.goto(TOUTIAO_PUBLISH_URL, timeout=60000)
                page.wait_for_load_state("domcontentloaded")
            except Exception as e:
                print(f"  ⚠️ 导航警告：{e}")

            # 检查登录状态
            if "auth/page/login" in page.url or "sso.toutiao.com" in page.url:
                result["message"] = "未登录或登录已过期，请先登录"
                print("  ❌ 需要登录")
                return result

            print("  ✅ 发布页面已加载")
            time.sleep(3)

            # 处理遮罩层
            for sel in [".byte-drawer-mask", ".ai-assistant-drawer", ".byte-modal-mask"]:
                try:
                    if page.locator(sel).is_visible():
                        page.evaluate(f"document.querySelector('{sel}')?.remove()")
                except:
                    pass

            # 1. 填写标题
            if title:
                print(f"  ✍️ 填写标题：{title[:20]}...")
                try:
                    title_input = page.locator("textarea").first
                    if title_input.count() > 0:
                        title_input.fill(title)
                    else:
                        page.get_by_placeholder("标题", exact=False).first.fill(title)
                    print("    标题填写完成")
                except Exception as e:
                    print(f"  ⚠️ 标题填写失败：{e}")

            # 2. 填写正文
            print("  📝 填写正文内容...")
            try:
                page.wait_for_selector(".ProseMirror", timeout=5000)
            except:
                pass

            editor = page.locator(".ProseMirror").first
            if editor.count() > 0:
                editor.click()
                editor.clear()
                time.sleep(0.5)

                page.evaluate(
                    """(data) => {
                        const editor = document.querySelector('.ProseMirror');
                        if (editor) {
                            editor.focus();
                            document.execCommand('insertHTML', false, data.html);
                        }
                    }""",
                    {"html": content_html},
                )
                print("    正文填写完成")
                time.sleep(2)

                # 检查保存状态
                for _ in range(10):
                    try:
                        if page.get_by_text("草稿已保存").is_visible():
                            print("  ✅ 草稿已保存")
                            break
                    except:
                        pass
                    time.sleep(1)

            # 3. 上传封面
            if cover_path and os.path.exists(cover_path):
                print(f"  🖼️ 上传封面...")
                try:
                    add_cover_btn = page.locator("div.article-cover-add").first
                    if add_cover_btn.is_visible():
                        add_cover_btn.click()
                        time.sleep(1)

                    upload_tab = page.locator("div.btn-upload-handle.upload-handler").first
                    if upload_tab.is_visible():
                        upload_tab.click()
                    time.sleep(1)

                    file_input = page.locator("input[type='file']").first
                    file_input.set_input_files(cover_path)

                    time.sleep(2)
                    confirm_btn = page.locator("button[data-e2e='imageUploadConfirm-btn']")
                    confirm_btn.wait_for(state="visible", timeout=30000)
                    confirm_btn.click()
                    print("  ✅ 封面上传完成")
                    time.sleep(2)
                except Exception as e:
                    print(f"  ⚠️ 封面上传失败：{e}")

            # 4. 发布
            if dry_run:
                result["success"] = True
                result["message"] = "试运行：内容已填写，未发布"
                return result

            if auto_publish:
                print("  🚀 执行发布...")
                success = _click_publish_buttons(page)
                result["success"] = success
                result["message"] = "发布成功" if success else "发布失败"
            else:
                result["success"] = True
                result["message"] = "内容已填写，请手动发布"

            time.sleep(5)

        except Exception as e:
            result["message"] = f"发布出错：{str(e)}"
            print(f"  ❌ 错误：{e}")
            import traceback
            traceback.print_exc()
        finally:
            try:
                context.close()
            except:
                pass

    return result


def check_login_status() -> Dict[str, Any]:
    """检查登录状态"""
    result = {
        "authenticated": False,
        "auth_age_hours": None,
        "warning": None,
    }

    if not STATE_FILE.exists():
        result["warning"] = "未找到登录状态，请先登录"
        return result

    age_hours = (time.time() - STATE_FILE.stat().st_mtime) / 3600
    result["auth_age_hours"] = round(age_hours, 1)

    if age_hours > 168:
        result["warning"] = f"登录状态已 {age_hours:.1f} 小时，可能已过期"

    # 实际验证
    try:
        with sync_playwright() as p:
            context = BrowserFactory.launch_persistent_context(p, headless=True)
            page = context.new_page()
            page.goto(TOUTIAO_HOME_URL, wait_until="domcontentloaded", timeout=30000)

            if "auth/page/login" in page.url or "sso.toutiao.com" in page.url:
                result["authenticated"] = False
                result["warning"] = "登录已失效"
            else:
                result["authenticated"] = True
            context.close()
    except Exception as e:
        result["warning"] = f"验证失败：{str(e)}"
        result["authenticated"] = age_hours < 168  # 保守判断

    return result


def launch_login_browser(headless: bool = False, timeout_minutes: int = 10) -> bool:
    """启动浏览器让用户登录"""
    auth_manager = AuthManager()
    return auth_manager.setup_auth(headless=headless, timeout_minutes=timeout_minutes)
