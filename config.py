import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'mangashelf.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    COVER_CACHE_DIR = os.path.join(BASE_DIR, 'app', 'static', 'covers')
