"""FastAPI entrypoint with protected profiles and explicit database availability errors."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes.users import router
from app.config import Settings, get_settings
from app.database import build_engine


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.engine = build_engine(settings)
        yield
        app.state.engine.dispose()

    application = FastAPI(title="DrivePulseAI API", lifespan=lifespan)
    application.state.settings = settings
    if settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "PUT"],
            allow_headers=["Authorization", "Content-Type"],
        )
    application.include_router(router)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error: SQLAlchemyError) -> JSONResponse:
        return JSONResponse(
            status_code=503, content={"detail": "Profile storage unavailable"}
        )

    return application


app = create_app()
