"""
通用视觉分析工具
=================
使用 智谱AI GLM-4V-Flash（完全免费）分析图片内容。
可在任意对话中调用，支持图片描述、质量评估、OCR文字识别。

用法:
  python vision_tool.py <图片路径>              # 描述图片
  python vision_tool.py <路径> --quality        # 质量评估
  python vision_tool.py <路径> --ocr            # 文字识别
  python vision_tool.py <路径1> <路径2> --compare # 对比
  python vision_tool.py --setup                 # 配置Key

Python导入:
  from vision_tool import describe, quality, ocr, compare
  result = describe("C:/图片.jpg")
"""

import os, sys, json, base64
import requests

API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MODEL = "glm-4v-flash"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def get_api_key():
    key = os.environ.get("ZHIPU_API_KEY")
    if key: return key
    for p in [os.path.join(SCRIPT_DIR, ".vision_config.json"),
              os.path.join(os.getcwd(), ".vision_config.json")]:
        if os.path.exists(p):
            try: return json.load(open(p)).get("api_key", "")
            except: pass
    return ""

def save_api_key(key):
    with open(os.path.join(SCRIPT_DIR, ".vision_config.json"), "w") as f:
        json.dump({"api_key": key}, f, indent=2)
    print(f"✅ API Key 已保存")

def _analyze(prompt, *paths):
    key = get_api_key()
    if not key: return "❌ 未配置API Key，运行 python vision_tool.py --setup"
    content = [{"type": "text", "text": prompt}]
    for p in paths:
        with open(p, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    resp = requests.post(API_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": MODEL, "messages": [{"role": "user", "content": content}]}, timeout=120)
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"]
    return f"❌ 错误({resp.status_code})"

def describe(path): return _analyze("请用中文分析这张图片：1.【主体】图中是什么？2.【外观】颜色、样式细节 3.【风格】画风、光影 4.【质量】清晰度、细节 每点1-2句", path)
def quality(path): return _analyze("请严格评价这张图片质量：1.【清晰度】2.【主体】有无变形？3.【缺陷】噪点水印？4.【评分】1-10分 5.【结论】", path)
def ocr(path): return _analyze("请识别并提取这张图片中所有可见的文字内容，包括水印。按顺序列出。", path)
def compare(*paths): return _analyze("请分析以下图片的风格一致性：1.【画风统一性】2.【色彩协调性】3.【细节层次】4.【总体评分】满分10分", *paths)

def setup():
    print("="*50+"\n  🔑 配置 智谱AI API Key（完全免费）\n"+"="*50)
    print("\n1. 访问 https://open.bigmodel.cn/\n2. 注册登录 → API密钥 → 新建Key\n")
    k = input("粘贴 API Key: ").strip()
    if k: save_api_key(k); os.environ["ZHIPU_API_KEY"] = k; print("✅ 配置完成！")
    else: print("❌ 取消")

def main():
    args = sys.argv[1:]
    if not args or "--setup" in args:
        if "--setup" in args: setup(); return
        print("视觉分析工具 - 免费\n用法: python vision_tool.py <图片路径>\n选项: --quality, --ocr, --compare, --setup")
        return
    if not get_api_key(): print("❌ 请先配置: python vision_tool.py --setup"); return
    paths = [a for a in args if not a.startswith("--")]
    modes = [a for a in args if a.startswith("--")]
    if not paths: print("❌ 请提供图片路径"); return
    mode = modes[0] if modes else "describe"
    missing = [p for p in paths if not os.path.exists(p)]
    if missing: print(f"❌ 文件不存在: {missing}"); return
    if mode == "--quality": print(quality(paths[0]))
    elif mode == "--ocr": print(ocr(paths[0]))
    elif mode == "--compare" and len(paths) >= 2: print(compare(*paths))
    else: print(describe(paths[0]))

if __name__ == "__main__":
    main()
