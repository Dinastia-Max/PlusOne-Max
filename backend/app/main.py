from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers.fields import router as fields_router
from app.routers.slots import router as slots_router
from app.routers.users import router as users_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="PlusOne API",
        version="0.1.0",
        description="API мини-приложения PlusOne в MAX",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(fields_router)
    app.include_router(slots_router)
    app.include_router(users_router)
    return app


app = create_app()
