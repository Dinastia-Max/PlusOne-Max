from fastapi import FastAPI


def create_app() -> FastAPI:
    return FastAPI(
        title="PlusOne API",
        version="0.1.0",
        description="API мини-приложения PlusOne в MAX",
    )


app = create_app()
