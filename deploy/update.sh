#!/usr/bin/env bash
# update server from git
set -euo pipefail

APP=/opt/switchboard
PORT=2222
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ "$(id -u)" -eq 0 ]; then
    echo "run this as a normal user NOT as root." >&2
    exit 1
fi
if [ ! -d "$APP/.venv" ]; then
    echo "$APP/.venv not found"
fi

cd "$SRC"
echo "==> pulling from repo"
git pull --ff-only
echo "    now at: $(git log --oneline -1)"

echo "==> saving copy to $APP.prev"
sudo rm -rf "$APP.prev"
sudo rsync -a --exclude=.venv "$APP/" "$APP.prev/"

echo "==> stopping service"
sudo systemctl stop switchboard

echo "==> installing new code"
sudo rsync -a --delete --exclude=.venv --exclude=.git --exclude=data \
    --exclude=__pycache__ "$SRC/" "$APP/"
sudo chown -R root:root "$APP"
sudo "$APP/.venv/bin/python" -m pip install -q -r "$APP/requirements.lock"
sudo "$APP/.venv/bin/python" -m pip install -q --force-reinstall --no-deps "$APP"

echo "==> starting service"
sudo systemctl start switchboard
sleep 2

banner="$(timeout 3 bash -c "exec 3<>/dev/tcp/127.0.0.1/$PORT && head -c 7 <&3" 2>/dev/null || true)"
if systemctl is-active --quiet switchboard && [ "$banner" = "SSH-2.0" ]; then
    echo "==> OK: switchboard is running and answering on port $PORT"
    sudo journalctl -u switchboard -n 5 --no-pager
else
    echo "==> FAILED: service not healthy after update." >&2
    sudo journalctl -u switchboard -n 25 --no-pager >&2 || true
    echo "Roll back to the previous version:" >&2
    echo "  sudo systemctl stop switchboard" >&2
    echo "  sudo rsync -a --delete --exclude=.venv $APP.prev/ $APP/" >&2
    echo "  sudo systemctl start switchboard" >&2
fi