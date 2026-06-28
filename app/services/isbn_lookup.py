"""
ISBN metadata lookup.
Primary: OpenLibrary Books API (free, no key required).
Secondary: Google Books API (free, no key for basic use).
Both engines are always queried; results are merged so the best
available data fills each field (series in particular).
"""
import logging
import re
import time
import requests

logger = logging.getLogger(__name__)

_HEADERS = {'User-Agent': 'MangaShelf/1.0 (manga-library-management)'}
_TIMEOUT = 6

# Matches volume keywords + number + optional total in the title string, e.g.:
#   "- Band 3", "Band 3/12", "Band 3 von 12", ", Vol. 3", "Tome 3", "#3"
_SERIES_RE = re.compile(
    r'[\s,\-–—]+(?:Band|Bd\.?|Vol\.?|Volume|Tome|Buch|Book|Part|#)\s*\.?\s*(\d+)'
    r'(?:\s*(?:von|of|/)\s*(\d+))?',
    re.IGNORECASE,
)

# Matches a string that IS entirely a volume indicator, e.g. subtitle "Band 3"
_VOLUME_RE = re.compile(
    r'^(?:Band|Bd\.?|Vol\.?|Volume|Tome|Buch|Book|Part|#)\s*\.?\s*(\d+)'
    r'(?:\s*(?:von|of|/)\s*(\d+))?\s*$',
    re.IGNORECASE,
)

def _extract_series(title: str):
    """Strip volume indicator from title. Returns (clean_title, series_num | None)."""
    m = _SERIES_RE.search(title)
    if not m:
        return title, None
    clean = (title[:m.start()] + title[m.end():]).strip().rstrip(',-–— ')
    return clean, m.group(1)


def _parse_volume(s: str):
    """Return volume number if s is entirely a volume indicator, e.g. 'Band 3' → '3'."""
    if not s:
        return None
    m = _VOLUME_RE.match(s.strip())
    return m.group(1) if m else None


def lookup_isbn(isbn):
    """
    Return dict {title, subtitle, series, author, publisher, published, cover_url} or None.
    Queries both OpenLibrary and Google Books; merges results so each field
    is filled from whichever engine has it.
    """
    for candidate in _isbn_variants(isbn):
        ol = _openlibrary(candidate)
        gb = _google_books(candidate)

        # Pick the result with a title as base; merge missing fields from the other
        base  = ol if (ol and ol.get('title')) else gb
        other = gb if base is ol else ol
        if not base or not base.get('title'):
            continue

        if other:
            for key in ('subtitle', 'author', 'publisher', 'published', 'cover_url'):
                if not base.get(key) and other.get(key):
                    base[key] = other[key]

        # Series priority:
        # 1. structured series_num from Google Books seriesInfo
        # 2. regex extraction from base title
        # 3. subtitle that is itself a volume indicator (e.g. Google Books subtitle "Band 3")
        # 4. regex extraction from other engine's title
        # 5. other engine's subtitle as volume indicator
        series = base.pop('series_num', None) or (other or {}).pop('series_num', None)
        if series:
            base['series'] = str(series)
        else:
            base['title'], extracted = _extract_series(base['title'])
            if not extracted:
                extracted = _parse_volume(base.get('subtitle') or '')
            if not extracted and other:
                if other.get('title'):
                    _, extracted = _extract_series(other['title'])
                if not extracted:
                    extracted = _parse_volume(other.get('subtitle') or '')
            if extracted:
                base['series'] = extracted

        base.setdefault('series', None)
        return base

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
            variants.insert(0, alt)
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
        cover_url = (cover.get('large') or cover.get('medium') or cover.get('small'))
        if not cover_url:
            cover_url = f'https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg'

        return {
            'title':     title,
            'subtitle':  book.get('subtitle') or None,
            'author':    author,
            'publisher': publisher,
            'published': book.get('publish_date'),
            'cover_url': cover_url,
        }
    except Exception as exc:
        logger.warning('OpenLibrary lookup failed for %s: %s', isbn, exc)
        return None


# ── Google Books ─────────────────────────────────────────────────────────────

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

        info      = items[0].get('volumeInfo', {})
        authors   = info.get('authors', [])
        img_links = info.get('imageLinks', {})
        cover_url = (img_links.get('large') or img_links.get('medium')
                     or img_links.get('thumbnail'))

        # Structured series info — Google Books uses bookSeries or volumeSeries
        series_num = None
        series_info = info.get('seriesInfo', {})
        for key in ('bookSeries', 'volumeSeries'):
            for entry in series_info.get(key, []):
                if entry.get('orderNumber'):
                    series_num = entry['orderNumber']
                    break
            if series_num:
                break

        subtitle = info.get('subtitle') or None

        # Last-resort: if subtitle is missing, scan description for "Band N" style
        description = info.get('description', '') or ''
        if not subtitle and not series_num:
            m = _SERIES_RE.search(description)
            if m:
                series_num = m.group(1)

        if not series_num and not subtitle:
            logger.debug('GB no series for %s — seriesInfo=%r subtitle=%r title=%r',
                         isbn, series_info, info.get('subtitle'), info.get('title'))

        return {
            'title':      info.get('title', ''),
            'subtitle':   subtitle,
            'author':     ', '.join(authors) if authors else None,
            'publisher':  info.get('publisher'),
            'published':  info.get('publishedDate'),
            'cover_url':  cover_url,
            'series_num': series_num,
        }
    except Exception as exc:
        logger.warning('Google Books lookup failed for %s: %s', isbn, exc)
        return None
