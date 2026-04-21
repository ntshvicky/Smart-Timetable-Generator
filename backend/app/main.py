from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, data, rules, timetables
from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.services.bootstrap_service import ensure_superadmin


def create_app() -> FastAPI:
    settings = get_settings()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        ensure_superadmin(db)
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router, prefix="/api")
    app.include_router(data.router, prefix="/api")
    app.include_router(rules.router, prefix="/api")
    app.include_router(timetables.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
