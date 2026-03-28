"""
ISBN metadata lookup.
Primary: OpenLibrary Books API (free, no key required).
Fallback: Google Books API (free, no key for basic use).
         Retries once on 429 after a short delay.
"""
import logging
import time
import requests

logger = logging.getLogger(__name__)

_HEADERS = {'User-Agent': 'MangaShelf/1.0 (manga-library-management)'}
_TIMEOUT = 6


def lookup_isbn(isbn):
    """
    Return dict {title, author, publisher, published, cover_url} or None.
    Tries OpenLibrary then Google Books, for both ISBN-13 and ISBN-10 forms.
    """
    for candidate in _isbn_variants(isbn):
        result = _openlibrary(candidate)
        if not result or not result.get('title'):
            result = _google_books(candidate)
        if result and result.get('title'):
            return result
    return None


def _isbn_variants(isbn):
    """Return [isbn, alternate_form] trying both ISBN-13 and ISBN-10."""
    isbn = isbn.replace('-', '').replace(' ', '')
    variants = [isbn]
    if len(isbn) == 13 and isbn.startswith('978'):
        alt = _isbn13_to_isbn10(isbn)
        if alt:
            variants.append(alt)
    elif len(isbn) == 10:
        alt = _isbn10_to_isbn13(isbn)
        if alt:
            variants.insert(0, alt)  # prefer ISBN-13
    return variants


def _isbn13_to_isbn10(isbn13):
    core = isbn13[3:12]
    total = sum((10 - i) * int(d) for i, d in enumerate(core))
    check = (11 - (total % 11)) % 11
    return core + ('X' if check == 10 else str(check))


def _isbn10_to_isbn13(isbn10):
    core = '978' + isbn10[:9]
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(core))
    check = (10 - (total % 10)) % 10
    return core + str(check)


# ── OpenLibrary ──────────────────────────────────────────────────────────────

def _openlibrary(isbn):
    """
    Uses the legacy jscmd=data endpoint — returns rich data including
    author names and cover URLs in a single request.
    """
    try:
        r = requests.get(
            'https://openlibrary.org/api/books',
            params={'bibkeys': f'ISBN:{isbn}', 'format': 'json', 'jscmd': 'data'},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        if r.status_code != 200:
            return None

        data = r.json()
        book = data.get(f'ISBN:{isbn}')
        if not book:
            return None

        title = book.get('title', '')

        authors = book.get('authors', [])
        author  = ', '.join(a['name'] for a in authors if a.get('name')) or None

        publishers = book.get('publishers', [])
        publisher  = publishers[0].get('name') if publishers else None

        cover     = book.get('cover', {})
        cover_url = (cover.get('large')
                     or cover.get('medium')
                     or cover.get('small'))
        if not cover_url:
            # ISBN-based URL; OpenLibrary may return a blank image without ?default=false
            cover_url = f'https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg'

        return {
            'title':     title,
            'author':    author,
            'publisher': publisher,
            'published': book.get('publish_date'),
            'cover_url': cover_url,
        }
    except Exception as exc:
        logger.warning('OpenLibrary lookup failed for %s: %s', isbn, exc)
        return None


# ── Google Books fallback ────────────────────────────────────────────────────

def _google_books(isbn):
    try:
        r = requests.get(
            'https://www.googleapis.com/books/v1/volumes',
            params={'q': f'isbn:{isbn}'},
            timeout=_TIMEOUT,
        )
        if r.status_code == 429:
            time.sleep(2)
            r = requests.get(
                'https://www.googleapis.com/books/v1/volumes',
                params={'q': f'isbn:{isbn}'},
                timeout=_TIMEOUT,
            )
        if r.status_code != 200:
            return None

        items = r.json().get('items', [])
        if not items:
            return None

        info       = items[0].get('volumeInfo', {})
        authors    = info.get('authors', [])
        img_links  = info.get('imageLinks', {})
        cover_url  = (img_links.get('large')
                      or img_links.get('medium')
                      or img_links.get('thumbnail'))

        return {
            'title':     info.get('title', ''),
            'author':    ', '.join(authors) if authors else None,
            'publisher': info.get('publisher'),
            'published': info.get('publishedDate'),
            'cover_url': cover_url,
        }
    except Exception as exc:
        logger.warning('Google Books lookup failed for %s: %s', isbn, exc)
        return None
