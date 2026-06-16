"""FastAPI application factory and entry point"""
import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import get_settings
from backend.app.database import init_db
from backend.auth.deps import get_current_user
from backend.routers import tasks, agents, features, knowledge, templates, agent_chat, auth, projects


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    settings = get_settings()
    os.makedirs(settings.data_dir, exist_ok=True)
    init_db()
    yield


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    settings = get_settings()

    app = FastAPI(
        title="风险特征挖掘系统 API",
        description="风控团队特征工程管理平台 — 支持批量生产、评估、部署全流程",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Public routes (no auth)
    @app.get("/api/health")
    def health_check():
        return {"status": "ok", "version": "1.0.0"}

    app.include_router(auth.router, prefix="/api/auth", tags=["认证"])

    # JWT-protected routes
    app.include_router(tasks.router, prefix="/api/tasks", tags=["任务管理"], dependencies=[Depends(get_current_user)])
    app.include_router(projects.router, prefix="/api/projects", tags=["项目管理"], dependencies=[Depends(get_current_user)])
    app.include_router(agents.router, prefix="/api/agents", tags=["Agent状态"], dependencies=[Depends(get_current_user)])
    app.include_router(features.router, prefix="/api/features", tags=["特征管理"], dependencies=[Depends(get_current_user)])
    app.include_router(knowledge.router, prefix="/api/knowledge", tags=["知识管理"], dependencies=[Depends(get_current_user)])
    app.include_router(templates.router, prefix="/api/templates", tags=["模板管理"], dependencies=[Depends(get_current_user)])
    app.include_router(agent_chat.router, prefix="/api/agents", tags=["Agent聊天"], dependencies=[Depends(get_current_user)])

    return app


app = create_app()


if __name__ == "__main__":

    # 本地 debug
    import uvicorn

    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
