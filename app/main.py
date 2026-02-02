"""Main FastAPI application"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from core.logging_config import setup_logging
from app.middleware import TimingMiddleware

settings = get_settings()

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info(f"Starting {settings.app_name} v0.1.0")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Debug mode: {settings.debug}")

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
    from core.database import engine

    db_connected = False
    try:
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
            db_connected = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")

    return {
        "status": "healthy" if db_connected else "unhealthy",
        "database_connected": db_connected,
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
            "api_root": "/api",
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
