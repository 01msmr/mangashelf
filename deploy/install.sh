#!/usr/bin/env bash
# MangaStore — Raspberry Pi installer
# Run as root: sudo bash install.sh
# Assumes Raspberry Pi OS Bookworm/Bullseye, user "pi", project cloned to /home/pi/mangastore

set -e

APP_DIR=/home/pi/mangastore
APP_USER=pi

echo "=== MangaStore installer ==="

# ── System packages ────────────────────────────────────────────
echo "[1/6] Installing system packages..."
apt-get update -q
apt-get install -y -q \
    python3-venv \
    python3-pip \
    unclutter \
    chromium-browser \
    xdotool

# ── Python virtualenv + dependencies ──────────────────────────
echo "[2/6] Setting up Python environment..."
sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --upgrade pip -q
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt" -q

# ── Seed database ──────────────────────────────────────────────
echo "[3/6] Seeding database (admin/0000)..."
cd "$APP_DIR"
if [ ! -f "$APP_DIR/mangastore.db" ]; then
    sudo -u "$APP_USER" "$APP_DIR/venv/bin/python" seed.py
else
    echo "    Database already exists — skipping seed."
fi

# ── systemd service ────────────────────────────────────────────
echo "[4/6] Installing systemd service..."
cp "$APP_DIR/deploy/mangastore.service" /etc/systemd/system/mangastore.service
systemctl daemon-reload
systemctl enable mangastore.service
systemctl start mangastore.service
echo "    Service status:"
systemctl is-active mangastore.service && echo "    mangastore: RUNNING" || echo "    mangastore: FAILED"

# ── Kiosk autostart ────────────────────────────────────────────
echo "[5/6] Configuring kiosk autostart..."
AUTOSTART_DIR=/etc/xdg/lxsession/LXDE-pi
mkdir -p "$AUTOSTART_DIR"
cp "$APP_DIR/deploy/autostart" "$AUTOSTART_DIR/autostart"

# Disable screen blanking system-wide
if ! grep -q "consoleblank=0" /boot/cmdline.txt 2>/dev/null; then
    sed -i 's/$/ consoleblank=0/' /boot/cmdline.txt
fi

# ── Auto-login to desktop ──────────────────────────────────────
echo "[6/6] Enabling desktop auto-login for user '$APP_USER'..."
raspi-config nonint do_boot_behaviour B4 2>/dev/null || true

echo ""
echo "=== Installation complete ==="
echo "    Reboot to start in kiosk mode: sudo reboot"
echo "    Logs: journalctl -u mangastore -f"
echo "    Default login: admin / 0000  (you will be forced to change the PIN)"
