"""
ISBN metadata lookup for manga (German + international).

Four free, no-key sources are queried in parallel and merged so each
field is filled from whichever source has it:
  - Deutsche Nationalbibliothek (DNB) — near-complete German ISBN coverage.
  - Library of Congress (LoC) — the US/English counterpart to the DNB.
  - Google Books — broad international coverage (needs a country param,
    otherwise it returns empty from many regions).
  - OpenLibrary — supplementary, and a cover-image fallback.
"""
import concurrent.futures
import logging
import re
import time
import xml.etree.ElementTree as ET
import requests

logger = logging.getLogger(__name__)

_HEADERS = {'User-Agent': 'MangaShelf/1.0 (manga-library-management)'}
_TIMEOUT = 6
# Country to present to Google Books. Without it the API returns empty
# results from many regions, dropping international/English editions.
_GB_COUNTRY = 'US'

_FIELDS = ('title', 'subtitle', 'author', 'publisher', 'published', 'cover_url')

# Human names + a per-ISBN research URL for each source, stored/shown with the
# record so a follow-up lookup can jump straight to the right catalogue.
SOURCE_NAMES = {'dnb': 'DNB', 'loc': 'Library of Congress',
                'gb': 'Google Books', 'ol': 'OpenLibrary'}


def source_url(source, isbn):
    isbn = (isbn or '').replace('-', '').replace(' ', '')
    if not source or not isbn:
        return None
    return {
        'gb':  f'https://books.google.com/books?vid=ISBN{isbn}',
        'ol':  f'https://openlibrary.org/isbn/{isbn}',
        'dnb': f'https://portal.dnb.de/opac/simpleSearch?query={isbn}',
        'loc': f'https://catalog.loc.gov/vwebv/search?searchArg={isbn}&searchCode=STNO&searchType=1',
    }.get(source)

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
    Return dict {title, subtitle, series, author, publisher, published, cover_url}
    or None. Queries all sources in parallel and merges.
    """
    return lookup_isbn_verbose(isbn)[0]


def lookup_isbn_verbose(isbn):
    """Like lookup_isbn but also returns which source provided the best hit
    (the base record adopted into the DB): (merged_meta_or_None, source_key)."""
    for candidate in _isbn_variants(isbn):
        merged, source = _merge(_query_all(candidate))
        if merged and merged.get('title'):
            return merged, source
    return None, None


def _query_all(isbn):
    """Run all sources concurrently for one ISBN candidate."""
    sources = {'gb': _google_books, 'dnb': _dnb, 'loc': _loc, 'ol': _openlibrary}
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(sources)) as ex:
        futures = {ex.submit(fn, isbn): key for key, fn in sources.items()}
        for fut in concurrent.futures.as_completed(futures):
            results[futures[fut]] = fut.result()
    return results


def _merge(results):
    """Merge per-source dicts. Base = the title-bearing result with the most
    filled fields; remaining fields filled from the others by priority.
    Returns (merged_or_None, base_source_key_or_None)."""
    priority = ('gb', 'dnb', 'loc', 'ol')
    ordered = [(k, results.get(k)) for k in priority if results.get(k)]
    titled  = [(k, r) for k, r in ordered if r and r.get('title')]
    if not titled:
        return None, None

    base_key, base = max(titled, key=lambda kv: sum(1 for f in _FIELDS if kv[1].get(f)))
    for _, other in ordered:
        if other is base:
            continue
        for f in _FIELDS:
            if not base.get(f) and other.get(f):
                base[f] = other[f]

    # Series priority:
    # 1. structured series_num from Google Books seriesInfo
    # 2. regex extraction from base title
    # 3. subtitle that is itself a volume indicator (e.g. "Band 3")
    # 4. regex / subtitle from any other source
    series = None
    for _, r in ordered:
        if r and r.get('series_num'):
            series = r['series_num']
            break
    if series:
        base['series'] = str(series)
    else:
        base['title'], extracted = _extract_series(base['title'])
        if not extracted:
            extracted = _parse_volume(base.get('subtitle') or '')
        if not extracted:
            for _, other in ordered:
                if other is base:
                    continue
                if other.get('title'):
                    _, extracted = _extract_series(other['title'])
                if not extracted:
                    extracted = _parse_volume(other.get('subtitle') or '')
                if extracted:
                    break
        if extracted:
            base['series'] = extracted

    base.pop('series_num', None)
    base.setdefault('series', None)
    return base, base_key


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


# ── National libraries via SRU / Dublin Core (DNB + Library of Congress) ─────
# Both return the same Dublin-Core-namespaced fields; only endpoint, ISBN index
# and recordSchema name differ. No API key required for either.

_DC = '{http://purl.org/dc/elements/1.1/}'


def _dc_texts(root, tag):
    return [e.text.strip() for e in root.iter(_DC + tag) if (e.text or '').strip()]


def _clean_creator(s):
    """DNB/LoC creators carry dates + role words, e.g.
    'Kishimoto, Masashi, 1974- author, artist.' → 'Kishimoto, Masashi'."""
    s = re.split(r',\s*\d{3,4}', s)[0]
    s = re.sub(r'\b(author|artist|editor|translator|trl|ill|illustrator|creator)\b.*$',
               '', s, flags=re.IGNORECASE)
    return s.strip().rstrip('.,;/ ').strip() or None


def _sru_dc(url, query, schema, source):
    try:
        r = requests.get(
            url,
            params={
                'version': '1.1',
                'operation': 'searchRetrieve',
                'query': query,
                'recordSchema': schema,
                'maximumRecords': '1',
            },
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        if r.status_code != 200 or not r.content:
            return None

        root = ET.fromstring(r.content)
        titles = _dc_texts(root, 'title')
        if not titles:
            return None

        # Titles come as "Haupttitel / Verfasser" or "Naruto /"; keep the title part.
        title = titles[0].split(' / ')[0].rstrip(' /').strip()
        creators = _dc_texts(root, 'creator')
        publishers = _dc_texts(root, 'publisher')
        dates = _dc_texts(root, 'date')

        return {
            'title':     title,
            'subtitle':  None,
            'author':    _clean_creator(creators[0]) if creators else None,
            'publisher': publishers[0] if publishers else None,
            'published': dates[0] if dates else None,
            'cover_url': None,
        }
    except Exception as exc:
        logger.warning('%s lookup failed for %s: %s', source, query, exc)
        return None


def _dnb(isbn):
    return _sru_dc('https://services.dnb.de/sru/dnb', f'NUM={isbn}', 'oai_dc', 'DNB')


def _loc(isbn):
    return _sru_dc('http://lx2.loc.gov:210/lcdb', f'bath.isbn={isbn}', 'dc', 'LoC')


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
        params = {'q': f'isbn:{isbn}', 'country': _GB_COUNTRY}
        r = requests.get('https://www.googleapis.com/books/v1/volumes',
                         params=params, timeout=_TIMEOUT)
        if r.status_code == 429:
            time.sleep(2)
            r = requests.get('https://www.googleapis.com/books/v1/volumes',
                             params=params, timeout=_TIMEOUT)
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
