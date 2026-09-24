from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers.slots import router as slots_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="PlusOne API",
        version="0.1.0",
        description="API мини-приложения PlusOne в MAX",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            origin.strip()
            for origin in settings.cors_origins.split(",")
            if origin.strip()
        ],
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    app.include_router(slots_router)
    return app


app = create_app()
