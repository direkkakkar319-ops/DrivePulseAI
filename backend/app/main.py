"""FastAPI entrypoint with protected profiles and explicit database availability errors."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes.onboarding import router as onboarding_router
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
            allow_methods=["GET", "PUT", "POST", "DELETE"],
            allow_headers=[
                "Authorization",
                "Content-Type",
                "X-Account-UID",
                "X-Vehicle-ID",
            ],
        )
    application.include_router(router)
    application.include_router(onboarding_router)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/health/db")
    def database_health(request: Request) -> JSONResponse:
        try:
            with request.app.state.engine.connect() as connection:
                connection.execute(text("SELECT 1")).scalar_one()
        except SQLAlchemyError:
            return JSONResponse(
                status_code=503, content={"detail": "Database unavailable"}
            )
        return JSONResponse(content={"status": "ok", "database": "connected"})

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error: SQLAlchemyError) -> JSONResponse:
        return JSONResponse(
            status_code=503, content={"detail": "Profile storage unavailable"}
        )

    return application


app = create_app()
