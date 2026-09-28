from fastapi import FastAPI

from app.routers.slots import router as slots_router
from app.routers.users import router as users_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="PlusOne API",
        version="0.1.0",
        description="API мини-приложения PlusOne в MAX",
    )
    app.include_router(slots_router)
    app.include_router(users_router)
    return app


app = create_app()
