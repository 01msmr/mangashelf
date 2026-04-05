import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'mangashelf.db')}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations():
    """Safe column-addition migrations for SQLite."""
    migrations = [
        'ALTER TABLE books ADD COLUMN loan_rate REAL DEFAULT 0.50',
        'ALTER TABLE books ADD COLUMN subtitle TEXT',
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass
        # Renumber copies: active first (1…N), broken last (N+1…M), ordered by id
        try:
            conn.execute(text("""
                UPDATE copies SET copy_num = (
                    SELECT new_num FROM (
                        SELECT id,
                               ROW_NUMBER() OVER (
                                   PARTITION BY book_id
                                   ORDER BY CASE WHEN status != 'broken' THEN 0 ELSE 1 END, id
                               ) AS new_num
                        FROM copies
                    ) AS ranked WHERE ranked.id = copies.id
                )
            """))
            conn.commit()
        except Exception:
            pass
