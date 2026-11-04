#!/usr/bin/env bash
# Non-Docker install for Ubuntu 22.04/24.04. Run as root from the repo directory.
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
apt-get update && apt-get install -y python3-venv tesseract-ocr nginx
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"
[ -f "$APP_DIR/.env" ] || cp "$APP_DIR/.env.example" "$APP_DIR/.env"
mkdir -p "$APP_DIR/data"
sed "s#/opt/fieldcast-invoice-desk#$APP_DIR#g" "$APP_DIR/deploy/fieldcast-agent.service" > /etc/systemd/system/fieldcast-invoice-desk.service
cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/fieldcast-invoice-desk
ln -sf /etc/nginx/sites-available/fieldcast-invoice-desk /etc/nginx/sites-enabled/fieldcast-invoice-desk
rm -f /etc/nginx/sites-enabled/default
systemctl daemon-reload && systemctl enable --now fieldcast-invoice-desk && systemctl reload nginx
echo "Running on http://$(hostname -I | awk '{print $1}')/"
