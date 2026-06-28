# MangaShelf

A self-hosted manga/book lending kiosk built for a Raspberry Pi touchscreen.

| Login | Book List | Account |
|---|---|---|
| ![Login](style_screenshots/kiosk_Login.png) | ![Books](style_screenshots/kiosk_Book_list.png) | ![Account](style_screenshots/kiosk_Account.png) |

---

## Features

- **Book catalogue** — searchable list with cover images, availability badges, and inline borrow/return actions
- **Barcode scanning** — USB hardware scanner (keypress buffer), camera-based scanning via ZXing (phone or webcam)
- **Borrow / Return** — inline rate picker and confirm/cancel without leaving the page; per-copy tracking, configurable loan period, per-book loan rate, overdue detection
- **Copy numbering** — active copies numbered 1–N, broken copies N+1–M; gaps auto-filled on status changes and startup
- **User accounts** — PIN authentication, balance (Guthaben), top-up, transaction history, active loan overview
- **Deposit system** — new accounts start at 0 €; 10 € deposit must be paid at the kiosk before borrowing unlocks (minimum balance: 10.50 €)
- **Admin panel** — user management, overdue list, broken-copy tracking (with auto-renumbering), settings (max loans, loan days, default rate)
- **QR login** — per-user QR codes for fast kiosk login without a keyboard
- **Phone scanner** — QR code on the account page lets a phone act as a wireless barcode scanner
- **Onscreen keyboard** — toggleable QWERTY/QWERTZ soft keyboard (switches with language)
- **Multilingual** — English, German (MangaRegal), Schwäbisch (MangaBrettl); add more via `lang.json`
- **Auto-logout** — session expires after 90 seconds of inactivity
- **Dark manga theme** — custom CSS with Tailwind-inspired utilities, all fonts and icons served locally (no CDN)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python · FastAPI · SQLAlchemy · SQLite |
| Auth | Starlette session middleware · bcrypt |
| Frontend | Vanilla JS · HTML/CSS (no framework) |
| ISBN lookup | OpenLibrary API · Google Books API (ISBN-13 ↔ ISBN-10 fallback) |
| Scheduler | APScheduler (overdue fee processing) |
| Deployment | Docker · systemd · Chromium kiosk mode · Raspberry Pi OS |

---

## Quick Start — Docker

```bash
git clone https://github.com/01msmr/mangashelf.git
cd mangashelf
cp .env.example .env   # set SECRET_KEY
docker compose up -d
```

Open **http://localhost**. Default login: admin username / PIN **0000** — PIN change required on first login.

```bash
# Update
git pull && docker compose up -d --build
```

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `mangashelf-dev-secret-change-in-production` | Session signing key — **change this in production** |

---

## Quick Start — Local

```bash
git clone https://github.com/01msmr/mangashelf.git
cd mangashelf
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python run.py   # self-signed TLS cert is generated on first run
```

Open **https://localhost:5001** (accept the cert warning).

---

## Raspberry Pi Deployment

Tested on Raspberry Pi OS Bookworm/Bullseye with an 800 × 480 HDMI display.

**Option A — Docker**

```bash
curl -fsSL https://get.docker.com | sh
git clone https://github.com/01msmr/mangashelf.git && cd mangashelf
docker compose up -d
```

**Option B — systemd (no Docker)**

```bash
# Clone to /home/pi/mangashelf, then:
sudo bash deploy/install.sh && sudo reboot
```

The installer sets up a Python virtualenv, seeds the database, installs a systemd service, and configures Chromium kiosk mode (auto-launches on boot at `https://localhost:5001`).

**Useful commands**

```bash
# Docker
docker compose logs -f
docker compose up -d --build

# systemd
sudo systemctl status mangashelf
sudo systemctl restart mangashelf
journalctl -u mangashelf -f
```

---

## Adding Books

Admins see an **Add** button in the book list header. Scanning an unknown ISBN navigates there automatically. On the Add Book page, scan or type an ISBN — title, author, publisher, cover and year are fetched from OpenLibrary / Google Books. If the book already exists, the button becomes **Add Copy** instead. ISBN-13 and ISBN-10 are both tried automatically.

---

## Extending Languages

Edit `app/static/lang.json` and add a new top-level key with the same string keys as `"en"`. The language switcher on the account page picks it up automatically. Set `"_keyboard": "qwerty"` or `"qwertz"` to control the onscreen keyboard layout. Strings support `{{var}}` placeholders resolved at render time.

---

## License

MIT
