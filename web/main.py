"""
量化回测系统 - Web API 服务

FastAPI 后端，提供策略管理、回测执行、结果查询接口
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

# 初始化 FastAPI
app = FastAPI(
    title="量化回测系统",
    description="A 股量化回测平台 - 策略编辑、回测执行、绩效分析",
    version="1.0.0",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
static_dir = project_root / "web" / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 导入 API 路由
from web.api import router as api_router

# 注册 API 路由
app.include_router(api_router)


# ==================== 根路由 ====================

@app.get("/", response_class=HTMLResponse)
async def root():
    """返回前端页面"""
    index_file = project_root / "web" / "static" / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse(content="<h1>量化回测系统</h1><p>访问 /docs 查看 API 文档</p>")


@app.get("/api/health")
async def health_check():
    """健康检查"""
    from datetime import datetime
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# ==================== 启动 ====================

if __name__ == "__main__":
    import uvicorn
    
    # 配置日志
    logger.add(
        project_root / "logs" / "web.log",
        rotation="10 MB",
        retention="7 days",
        level="INFO",
    )
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
