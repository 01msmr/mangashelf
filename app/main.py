"""FastAPI application factory."""
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from .database import Base, engine, run_migrations


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables and run migrations on startup
    Base.metadata.create_all(bind=engine)
    run_migrations()

    from .services.scheduler import start_scheduler
    scheduler = start_scheduler()

    yield

    scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    app = FastAPI(title='MangaStore', lifespan=lifespan)

    # Never cache HTML/CSS/JS so edits are visible on next page load
    class NoCacheMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            response = await call_next(request)
            response.headers['Cache-Control'] = 'no-store'
            return response

    app.add_middleware(NoCacheMiddleware)

    secret_key = os.environ.get('SECRET_KEY', 'mangastore-dev-secret-change-in-production')
    app.add_middleware(SessionMiddleware, secret_key=secret_key, https_only=True)

    from .routers import auth, books, loans, account, admin
    app.include_router(auth.router,    prefix='/api')
    app.include_router(books.router,   prefix='/api')
    app.include_router(loans.router,   prefix='/api')
    app.include_router(account.router, prefix='/api')
    app.include_router(admin.router,   prefix='/api/admin')
    app.include_router(loans.media_router)  # QR image endpoints (not under /api)

    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    app.mount('/static', StaticFiles(directory=static_dir), name='static')

    # Serve index.html for all unmatched paths (SPA-style)
    @app.get('/{full_path:path}', include_in_schema=False)
    async def spa_fallback(full_path: str):
        static_file = os.path.join(static_dir, full_path)
        if os.path.isfile(static_file):
            return FileResponse(static_file)
        return FileResponse(os.path.join(static_dir, 'login.html'))

    return app


app = create_app()
