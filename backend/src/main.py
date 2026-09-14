import contextlib
import pathlib
import typing

import fastapi
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.endpoints import router as api_endpoint_router
from src.api.routes.webhooks import router as webhooks_router
from src.config.manager import settings
from src.repository.events import dispose_db_connection, initialize_db_connection


@contextlib.asynccontextmanager
async def lifespan(app: fastapi.FastAPI) -> typing.AsyncIterator[None]:
    await initialize_db_connection(backend_app=app)
    try:
        yield
    finally:
        await dispose_db_connection(backend_app=app)


def initialize_backend_application() -> fastapi.FastAPI:
    app = fastapi.FastAPI(lifespan=lifespan, **settings.set_backend_app_attributes)  # type: ignore

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=settings.IS_ALLOWED_CREDENTIALS,
        allow_methods=settings.ALLOWED_METHODS,
        allow_headers=settings.ALLOWED_HEADERS,
    )

    app.include_router(router=api_endpoint_router, prefix=settings.API_PREFIX)
    # Mounted at the root, not under /api: the URL registered in the ApiPay dashboard
    # is https://api.dopsy.kz/webhooks/apipay, matching the path on the bot side.
    app.include_router(router=webhooks_router)

    media_directory = pathlib.Path(__file__).resolve().parent.parent / "media"
    media_directory.mkdir(exist_ok=True)
    app.mount("/media", StaticFiles(directory=media_directory), name="media")

    return app


backend_app: fastapi.FastAPI = initialize_backend_application()

if __name__ == "__main__":
    uvicorn.run(
        app="main:backend_app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=settings.DEBUG,
        workers=settings.SERVER_WORKERS,
        log_level=settings.LOGGING_LEVEL,
    )
