from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.auth import create_access_token, get_current_user, verify_credentials
from app.api.groq_resolve import resolve_groq_api_key
from app.api.routes import candidates, jds, jobs, misc, settings
from app.api.schemas import LoginRequest, TokenResponse, UserPublic
from app.config import ROOT_DIR
from app.db.models import init_db
from app.services.job_service import job_service
from app.services.llm_context import reset_groq_api_key, set_groq_api_key

FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"


def create_app() -> FastAPI:
    init_db()
    job_service.recover_stale_jobs()
    app = FastAPI(title="Recruiting Agent", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def groq_key_middleware(request: Request, call_next):
        key = resolve_groq_api_key(request)
        token = set_groq_api_key(key)
        try:
            return await call_next(request)
        finally:
            reset_groq_api_key(token)

    auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

    @auth_router.post("/login", response_model=TokenResponse)
    def login(body: LoginRequest):
        if not verify_credentials(body.username, body.password):
            raise HTTPException(401, "Invalid username or password")
        return TokenResponse(access_token=create_access_token(body.username))

    @auth_router.get("/me", response_model=UserPublic)
    def me(user: str = Depends(get_current_user)):
        return UserPublic(username=user)

    app.include_router(auth_router)
    app.include_router(jds.router, prefix="/api/v1")
    app.include_router(candidates.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(misc.router, prefix="/api/v1")
    app.include_router(settings.router, prefix="/api/v1")

    if FRONTEND_DIST.is_dir():
        assets_dir = FRONTEND_DIST / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str = ""):
            if full_path.startswith("api"):
                raise HTTPException(404, "Not Found")
            if full_path:
                requested = (FRONTEND_DIST / full_path).resolve()
                dist_root = FRONTEND_DIST.resolve()
                if str(requested).startswith(str(dist_root)) and requested.is_file():
                    return FileResponse(requested)
            index = FRONTEND_DIST / "index.html"
            if index.is_file():
                return FileResponse(index)
            raise HTTPException(404, "Frontend not built")

    return app


app = create_app()
