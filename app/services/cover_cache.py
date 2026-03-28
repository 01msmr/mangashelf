"""Book cover image caching — no Flask dependency."""
from __future__ import annotations
import os
import logging
import requests

logger    = logging.getLogger(__name__)
COVER_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'static', 'covers')
)
_HEADERS  = {'User-Agent': 'MangaShelf/1.0 (manga-library-management)'}
_TIMEOUT  = 10


def get_cover_path(isbn: str, cover_url: str = None) -> str | None:
    os.makedirs(COVER_DIR, exist_ok=True)
    filename    = f'{isbn}.jpg'
    abs_path    = os.path.join(COVER_DIR, filename)
    static_path = f'covers/{filename}'

    if os.path.exists(abs_path):
        return static_path

    urls = []
    if cover_url:
        urls.append(cover_url)
    urls.append(f'https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false')

    for url in urls:
        try:
            r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT, stream=True)
            if r.status_code != 200 or 'image' not in r.headers.get('content-type', ''):
                continue
            with open(abs_path, 'wb') as fh:
                for chunk in r.iter_content(chunk_size=8192):
                    fh.write(chunk)
            logger.info('Cached cover for ISBN %s', isbn)
            return static_path
        except Exception as exc:
            logger.warning('Cover download failed (%s): %s', url, exc)

    return None
