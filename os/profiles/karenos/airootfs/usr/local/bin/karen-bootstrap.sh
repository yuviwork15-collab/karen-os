#!/usr/bin/env bash
# Karen OS - first boot bootstrap: network wait -> deps -> Karen shell
# Runs from Openbox autostart on the live image.
set -u
log() { echo "[karen-bootstrap] $*"; }

log "waiting for network..."
for i in $(seq 1 30); do
  ping -c1 -W2 archlinux.org >/dev/null 2>&1 && break
  sleep 2
done

if [ ! -f /opt/karen-linux/.ready ]; then
  log "installing Karen dependencies (first boot only)..."
  pacman -Syy --noconfirm --needed python-pip python-setuptools >/dev/null 2>&1
  python -m pip install --break-system-packages -q -r /opt/karen-linux/requirements-linux.txt || log "pip failed"
  touch /opt/karen-linux/.ready
  log "deps ready"
fi

cd /opt/karen-linux || exit 1
log "launching Karen shell"
nohup python karen_shell.py >>/var/log/karen-session.log 2>&1 &
