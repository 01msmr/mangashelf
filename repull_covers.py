import os
from app.database import SessionLocal
from app.models import Book
from app.services.cover_cache import get_cover_path, COVER_DIR

os.makedirs(COVER_DIR, exist_ok=True)
db = SessionLocal()
for b in db.query(Book).all():
    path = get_cover_path(b.isbn, None)
    if path and b.cover_path != path:
        b.cover_path = path
    print(f"{'ok' if path else 'miss'}: {b.isbn} — {b.title}", flush=True)
db.commit()
db.close()
print("Done.")
