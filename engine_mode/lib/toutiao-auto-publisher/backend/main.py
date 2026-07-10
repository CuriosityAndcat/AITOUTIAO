"""
FastAPI 后端主应用
提供 AI 内容生成、浏览器自动发布、登录状态查询等 API
"""
import sys
import uuid
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# 确保 backend 目录在 Python 路径中
_backend_dir = Path(__file__).parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from config import settings
from models import (
    GenerateRequest, GenerateResponse, PublishRequest, PublishResponse,
    LoginStatusResponse, TaskStatus, TaskInfo, ContentType,
)
from ai_writer import AIWriter
from publisher_service import publish_article, check_login_status, launch_login_browser

# ===== 应用初始化 =====
app = FastAPI(
    title="今日头条自动发布工具",
    description="AI 写作 + 浏览器自动化发布",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== 任务存储（内存，简单实现）=====
tasks: Dict[str, TaskInfo] = {}


def _make_task_id() -> str:
    return str(uuid.uuid4())[:8]


def _save_task(task: TaskInfo):
    tasks[task.task_id] = task


def _get_task(task_id: str) -> Optional[TaskInfo]:
    return tasks.get(task_id)


# ===== API 路由 =====

@app.get("/")
async def root():
    """返回前端页面"""
    frontend_path = Path(__file__).parent.parent / "frontend" / "index.html"
    if frontend_path.exists():
        return FileResponse(frontend_path)
    return {"message": "今日头条自动发布工具 API 正在运行"}


@app.get("/api/health")
async def health():
    """健康检查"""
    return {"status": "ok", "ai_configured": bool(settings.AI_API_KEY)}


@app.get("/api/login-status", response_model=LoginStatusResponse)
async def get_login_status():
    """查询登录状态"""
    return check_login_status()


@app.post("/api/login")
async def trigger_login(headless: bool = False, timeout_minutes: int = 10):
    """
    触发登录流程（打开浏览器让用户扫码）
    注意：此接口会阻塞直到登录完成或超时
    """
    success = launch_login_browser(headless=headless, timeout_minutes=timeout_minutes)
    return {"success": success, "message": "登录成功" if success else "登录失败或超时"}


@app.post("/api/generate", response_model=GenerateResponse)
async def generate_content(req: GenerateRequest):
    """
    AI 生成内容
    - topic: 主题或关键词
    - content_type: "toutie"（微头条）或 "article"（文章）
    """
    try:
        writer = AIWriter()
        result = writer.generate(
            topic=req.topic,
            content_type=req.content_type,
            max_chars=req.max_chars,
            tone=req.tone,
            content_style=req.content_style,
        )
        return GenerateResponse(
            success=True,
            title=result.get("title", ""),
            content=result["content"],
            content_type=req.content_type,
            char_count=result["char_count"],
        )
    except Exception as e:
        return GenerateResponse(
            success=False,
            title=None,
            content="",
            content_type=req.content_type,
            char_count=0,
            error=str(e),
        )


@app.post("/api/publish", response_model=PublishResponse)
async def publish_content(req: PublishRequest):
    """
    发布内容到今日头条
    此接口在后台线程执行，立即返回 task_id 用于查询进度
    """
    import threading

    task_id = _make_task_id()
    task = TaskInfo(
        task_id=task_id,
        task_type="publish",
        status=TaskStatus.RUNNING,
        message="正在启动浏览器...",
        created_at=datetime.now().isoformat(),
    )
    _save_task(task)

    def _do_publish():
        try:
            # 更新任务状态
            task.message = "正在填写内容..."
            task.status = TaskStatus.RUNNING

            result = publish_article(
                title=req.title,
                content=req.content,
                cover_path=req.cover_path,
                auto_publish=req.auto_publish,
                headless=False,  # Windows 下建议非 headless
            )

            if result["success"]:
                task.status = TaskStatus.SUCCESS
                task.message = result["message"]
            else:
                task.status = TaskStatus.FAILED
                task.message = result["message"]
            task.result = result
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.message = f"发布异常：{str(e)}"
            task.result = {"error": str(e)}

    # 后台线程执行
    t = threading.Thread(target=_do_publish, daemon=True)
    t.start()

    return PublishResponse(
        success=True,
        message="发布任务已启动，请查询任务状态",
        task_id=task_id,
    )


@app.get("/api/task/{task_id}")
async def get_task_status(task_id: str):
    """查询任务状态"""
    task = _get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@app.get("/api/tasks")
async def list_tasks(limit: int = 10):
    """最近任务列表"""
    sorted_tasks = sorted(tasks.values(), key=lambda t: t.created_at, reverse=True)
    return sorted_tasks[:limit]


# ===== 静态文件（前端）=====
_frontend_dir = Path(__file__).parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_frontend_dir)), name="static")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA 路由兜底：返回 index.html"""
        index_file = _frontend_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"message": "前端文件不存在"}


# ===== 启动入口 =====
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
