"""Main FastAPI application"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from api.routes import chat, search, videos
from app.config import get_settings
from app.middleware import TimingMiddleware
from core.database import get_engine
from core.logging_config import setup_logging

settings = get_settings()

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info(f"Starting {settings.app_name} v0.1.0")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Debug mode: {settings.debug}")

    # Test database connection on startup
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection verified on startup")
    except Exception as e:
        logger.error(f"Database connection failed on startup: {e}", exc_info=True)
        raise

    yield

    logger.info(f"Shutting down {settings.app_name}")


app = FastAPI(
    title=settings.app_name,
    description="Barbados Parliamentary Knowledge Graph API",
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TimingMiddleware)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(videos.router)
app.include_router(search.router)
app.include_router(chat.router)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "status": "running",
        "environment": settings.app_env,
    }


@app.get("/health", tags=["Health"])
async def health():
    """Health check endpoint"""
    from sqlalchemy import text

    from core.database import get_engine

    db_connected = False
    db_error = None
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_connected = True
    except Exception as e:
        db_error = str(e)
        logger.error(f"Database health check failed: {e}", exc_info=True)

    return {
        "status": "healthy" if db_connected else "unhealthy",
        "database_connected": db_connected,
        "database_error": db_error,
        "version": "0.1.0",
    }


@app.get("/api", tags=["API"])
async def api_info():
    """API information"""
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "endpoints": {
            "health": "/health",
            "docs": "/docs" if settings.debug else "disabled",
            "videos": "/api/videos",
            "search": "/api/search",
            "chat": "/api/query",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
