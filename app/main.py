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


def _seed_defaults():
    from .database import SessionLocal
    from .models import User, Transaction, Setting
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == 'dmn').first()
        if not existing:
            print('[seed] creating dmn admin user...', flush=True)
            dmn = User(username='dmn', is_admin=1, setup_required=0, guthaben=10.00)
            dmn.set_pin(os.environ['DEFAULT_DMN_PIN'])
            db.add(dmn)
            db.flush()
            db.add(Transaction(user_id=dmn.id, amount=10.00, type='entry_fee',
                               description='Entry fee added on account creation.'))
            db.commit()
            print('[seed] dmn admin user created.', flush=True)

        if not Setting.get(db, 'admin_pin'):
            print('[seed] seeding admin_pin...', flush=True)
            Setting.set(db, 'admin_pin', os.environ['DEFAULT_ADMIN_PIN'])
            db.commit()
    except Exception as e:
        db.rollback()
        print(f'[seed] ERROR: {e}', flush=True)
        import traceback
        traceback.print_exc()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables and run migrations on startup
    Base.metadata.create_all(bind=engine)
    run_migrations()
    _seed_defaults()

    from .services.scheduler import start_scheduler
    scheduler = start_scheduler()

    yield

    scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    app = FastAPI(title='MangaShelf', lifespan=lifespan)

    # Never cache HTML/CSS/JS so edits are visible on next page load
    class NoCacheMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            response = await call_next(request)
            response.headers['Cache-Control'] = 'no-store'
            return response

    app.add_middleware(NoCacheMiddleware)

    secret_key = os.environ.get('SECRET_KEY', 'mangashelf-dev-secret-change-in-production')
    app.add_middleware(SessionMiddleware, secret_key=secret_key, https_only=False)

    from .routers import auth, books, loans, account, admin
    app.include_router(auth.router,    prefix='/api')
    app.include_router(books.router,   prefix='/api')
    app.include_router(loans.router,   prefix='/api')
    app.include_router(account.router, prefix='/api')
    app.include_router(admin.router,   prefix='/api/admin')
    app.include_router(loans.media_router)  # QR image endpoints (not under /api)

    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    covers_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'covers'))
    os.makedirs(covers_dir, exist_ok=True)
    app.mount('/static/covers', StaticFiles(directory=covers_dir), name='covers')
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
