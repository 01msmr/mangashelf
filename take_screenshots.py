"""
Take updated screenshots of the main MangaShelf views.
Requires: pip install playwright && playwright install chromium
Run with the server already up on https://localhost:5001
"""
import asyncio
import httpx
import os
from playwright.async_api import async_playwright

BASE      = 'https://localhost:5001/api'
SITE      = 'https://localhost:5001'
SHOTS_DIR = os.path.join(os.path.dirname(__file__), 'style_screenshots')
KIOSK     = {'width': 800,  'height': 480}
MOBILE    = {'width': 390,  'height': 844}

DMN_PIN      = os.getenv('DEFAULT_DMN_PIN', '0099')
ADMIN_PIN    = os.getenv('DEFAULT_ADMIN_PIN', '3369')

TEST_BOOKS = [
    {
        'isbn': '9784088820460', 'title': 'One Piece', 'series': 'One Piece',
        'author': 'Eiichiro Oda', 'publisher': 'Shueisha', 'published': '2000',
        'loan_rate': 0.50,
        'cover_url': 'https://covers.openlibrary.org/b/isbn/9784088820460-L.jpg',
    },
    {
        'isbn': '9784088728124', 'title': 'Naruto', 'series': 'Naruto',
        'author': 'Masashi Kishimoto', 'publisher': 'Shueisha', 'published': '2000',
        'loan_rate': 0.50,
        'cover_url': 'https://covers.openlibrary.org/b/isbn/9784088728124-L.jpg',
    },
    {
        'isbn': '9784088651125', 'title': 'Dragon Ball', 'series': 'Dragon Ball',
        'author': 'Akira Toriyama', 'publisher': 'Shueisha', 'published': '1995',
        'loan_rate': 0.50,
        'cover_url': 'https://covers.openlibrary.org/b/isbn/9784088651125-L.jpg',
    },
    {
        'isbn': '9784063631760', 'title': 'Attack on Titan', 'series': 'Attack on Titan',
        'author': 'Hajime Isayama', 'publisher': 'Kodansha', 'published': '2009',
        'loan_rate': 0.50,
        'cover_url': 'https://covers.openlibrary.org/b/isbn/9784063631760-L.jpg',
    },
    {
        'isbn': '9784088801834', 'title': 'Bleach', 'series': 'Bleach',
        'author': 'Tite Kubo', 'publisher': 'Shueisha', 'published': '2001',
        'loan_rate': 0.50,
        'cover_url': 'https://covers.openlibrary.org/b/isbn/9784088801834-L.jpg',
    },
    {
        'isbn': '9784063199901', 'title': 'Berserk', 'series': 'Berserk',
        'author': 'Kentaro Miura', 'publisher': 'Hakusensha', 'published': '1990',
        'loan_rate': 1.00,
        'cover_url': 'https://covers.openlibrary.org/b/isbn/9784063199901-L.jpg',
    },
]

TEST_USERS = [
    {'username': 'mira',  'pin': '1234'},
    {'username': 'leon',  'pin': '2345'},
    {'username': 'hana',  'pin': '3456'},
]


def seed_data():
    """Seed test books and users via the API (synchronous)."""
    client = httpx.Client(base_url=BASE, verify=False)

    # Login as dmn
    r = client.post('/auth/login', json={'username': 'dmn', 'pin': DMN_PIN})
    r.raise_for_status()
    print('Logged in as dmn')

    # Add books
    for book in TEST_BOOKS:
        r = client.post('/books', json=book)
        if r.status_code == 200:
            print(f"  Added: {book['title']}")
        else:
            print(f"  Skip {book['title']}: {r.text[:60]}")

    # Add test users
    for u in TEST_USERS:
        r = client.post('/auth/register', json={**u, 'pin_confirm': u['pin']})
        if r.status_code == 200:
            print(f"  User: {u['username']}")
        else:
            print(f"  Skip user {u['username']}: {r.text[:60]}")

    client.close()


async def take_screenshots():
    async with async_playwright() as pw:
        for viewport_name, viewport in [('kiosk', KIOSK), ('mobile', MOBILE)]:
            browser = await pw.chromium.launch(headless=True)
            ctx = await browser.new_context(
                viewport=viewport,
                ignore_https_errors=True,
            )
            page = await ctx.new_page()

            # ── Login page ─────────────────────────────────────────────────
            await page.goto(f'{SITE}/login.html', wait_until='networkidle')
            await page.screenshot(
                path=os.path.join(SHOTS_DIR, f'{viewport_name}_Login.png'),
                full_page=False,
            )
            print(f'[{viewport_name}] Login')

            # ── Log in as dmn ──────────────────────────────────────────────
            await page.evaluate("""async () => {
                await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: 'dmn', pin: '""" + DMN_PIN + """'}),
                });
            }""")

            # ── Book list ──────────────────────────────────────────────────
            await page.goto(f'{SITE}/index.html', wait_until='networkidle')
            await page.wait_for_timeout(800)
            await page.screenshot(
                path=os.path.join(SHOTS_DIR, f'{viewport_name}_Book_list.png'),
                full_page=False,
            )
            print(f'[{viewport_name}] Book list')

            # ── Account page ───────────────────────────────────────────────
            await page.goto(f'{SITE}/account.html', wait_until='networkidle')
            await page.wait_for_timeout(600)
            await page.screenshot(
                path=os.path.join(SHOTS_DIR, f'{viewport_name}_Account.png'),
                full_page=False,
            )
            print(f'[{viewport_name}] Account')

            # ── Phone scan page ────────────────────────────────────────────
            await page.goto(f'{SITE}/phone-scan.html', wait_until='networkidle')
            await page.wait_for_timeout(600)
            await page.screenshot(
                path=os.path.join(SHOTS_DIR, f'{viewport_name}_Phone_scan.png'),
                full_page=False,
            )
            print(f'[{viewport_name}] Phone scan')

            # ── Admin — users ──────────────────────────────────────────────
            # Unlock admin section via API, then load the page
            await page.goto(f'{SITE}/admin/users.html', wait_until='networkidle')
            await page.evaluate("""async (combined) => {
                await fetch('/api/admin/verify', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({pin: combined}),
                });
            }""", DMN_PIN + ADMIN_PIN)
            await page.goto(f'{SITE}/admin/users.html', wait_until='networkidle')
            await page.wait_for_timeout(800)
            await page.screenshot(
                path=os.path.join(SHOTS_DIR, f'{viewport_name}_Admin_users.png'),
                full_page=False,
            )
            print(f'[{viewport_name}] Admin users')

            # ── Add book page ──────────────────────────────────────────────
            await page.goto(f'{SITE}/admin/add-book.html', wait_until='networkidle')
            await page.wait_for_timeout(600)
            await page.screenshot(
                path=os.path.join(SHOTS_DIR, f'{viewport_name}_Add_book.png'),
                full_page=False,
            )
            print(f'[{viewport_name}] Add book')

            await browser.close()


if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings()
    os.makedirs(SHOTS_DIR, exist_ok=True)
    print('=== Seeding test data ===')
    seed_data()
    print('\n=== Taking screenshots ===')
    asyncio.run(take_screenshots())
    print('\nDone.')
