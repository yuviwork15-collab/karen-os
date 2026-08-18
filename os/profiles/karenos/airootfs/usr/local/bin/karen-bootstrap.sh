#!/usr/bin/env bash
# Karen OS - first boot bootstrap: network wait -> deps -> wizard or Karen shell
# Runs from Openbox autostart (live ISO and installed system).
set -u
log() { echo "[karen-bootstrap] $*"; }

log "waiting for network..."
for i in $(seq 1 45); do
  ping -c1 -W2 archlinux.org >/dev/null 2>&1 && break
  sleep 2
done

# --- self-update: pull the latest Karen (silent, only when online) ---
if ping -c1 -W2 archlinux.org >/dev/null 2>&1; then
  log "checking for Karen updates..."
  for f in karen_shell.py karen-welcome.py; do
    curl -fsSL --time-cond "/opt/karen-linux/$f" -o "/opt/karen-linux/$f" \
      "https://raw.githubusercontent.com/yuviwork15-collab/karen-os/main/os/desktop/$f" 2>/dev/null && {
        chmod 755 "/opt/karen-linux/$f"; log "updated $f"; } || true
  done
fi

if [ ! -f /opt/karen-linux/.ready ]; then
  log "installing Karen dependencies (first boot only)..."
  pacman -Syy --noconfirm --needed python-pip python-setuptools >/dev/null 2>&1
  python -m pip install --break-system-packages -q -r /opt/karen-linux/requirements-linux.txt || log "pip failed (no internet yet - wizard can retry)"
  touch /opt/karen-linux/.ready
  log "deps ready"
fi

cd /opt/karen-linux || exit 1
if [ ! -f /etc/karen/config.json ]; then
  log "first launch - starting setup wizard"
  nohup python karen-welcome.py >>/var/log/karen-welcome.log 2>&1 &
else
  log "launching Karen shell"
  nohup python karen_shell.py >>/var/log/karen-session.log 2>&1 &
fi