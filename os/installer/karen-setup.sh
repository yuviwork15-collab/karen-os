#!/usr/bin/env bash
# ===========================================================================
# karen-setup.sh - run INSIDE the freshly installed Karen OS (portable USB)
#
#   curl -fsSL https://raw.githubusercontent.com/yuviwork15-collab/karen-os/main/os/installer/karen-setup.sh | bash
#
# Installs: X + Openbox + tint2 + Karen shell (multi-provider AI, female voice)
# Applies:  zram swap, performance governor, autologin, no-camera policy
# ===========================================================================
set -euo pipefail
export LANG=C.UTF-8
REPO="https://raw.githubusercontent.com/yuviwork15-collab/karen-os/main/os"
LOG=/var/log/karen-setup.log

say() { echo "[karen-setup] $*" | tee -a "$LOG"; }

say "Karen OS post-install setup starting..."

# --- 1) packages (mirror of the ISO lean list) ---------------------------
say "installing desktop + runtime packages..."
pacman -S --noconfirm --needed \
  xorg-server xorg-xinit xorg-xrandr xorg-xdpyinfo xf86-video-vesa \
  openbox tint2 xterm pcmanfm \
  pipewire pipewire-pulse wireplumber alsa-utils portaudio \
  python python-pip python-pyqt6 python-pyaudio mpv \
  networkmanager cpupower zram-generator git sudo openssh \
  >>"$LOG" 2>&1

# --- 2) Karen payload -----------------------------------------------------
say "downloading Karen shell..."
mkdir -p /opt/karen-linux
curl -fsSL "$REPO/desktop/karen_shell.py"           -o /opt/karen-linux/karen_shell.py
curl -fsSL "$REPO/desktop/requirements-linux.txt"   -o /opt/karen-linux/requirements-linux.txt
mkdir -p /opt/karen-linux/etc/tint2 /opt/karen-linux/etc/openbox
python -m pip install --break-system-packages -q -r /opt/karen-linux/requirements-linux.txt >>"$LOG" 2>&1
chmod 755 /opt/karen-linux/karen_shell.py

# --- 3) system services ---------------------------------------------------
cat > /etc/systemd/zram-generator.conf <<'EOF'
# Karen OS - compressed RAM swap for low-end machines
[zram0]
zram-size = ram / 2
compression-algorithm = zstd
EOF

cat > /usr/lib/systemd/system/cpufreq.service <<'EOF'
[Unit]
Description=Karen OS - force performance CPU governor (snappy on low-end)
After=sysinit.target

[Service]
Type=oneshot
ExecStart=/usr/bin/bash -c 'for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do [ -w "$g" ] && echo performance > "$g" 2>/dev/null; done'

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system-preset/90-karen.preset <<'EOF'
# Karen OS - services we want
enable NetworkManager.service
enable cpufreq.service
enable systemd-zram-setup@zram0.service

# bloat off
disable bluetooth.service
disable avahi-daemon.service
disable systemd-journal-upload.service
EOF

mkdir -p /etc/systemd/system/getty@tty1.service.d
cat > /etc/systemd/system/getty@tty1.service.d/autologin.conf <<'EOF'
[Service]
ExecStart=
ExecStart=-/usr/bin/agetty --autologin root --noclear %I $TERM
EOF

# --- 4) shell environment -------------------------------------------------
cat > /etc/profile.d/karen.sh <<'EOF'
# Karen OS shell environment
export KAREN_OS=1
export KAREN_HOME=/opt/karen-linux
export PS1='\e[1;31m[\u@karenos \w]\$ \e[0m'
EOF

# --- 5) X session ----------------------------------------------------------
cat > /root/.bash_profile <<'EOF'
# Karen OS - auto start X on the main console (tty1)
if [ -z "$DISPLAY" ] && [ "$(tty)" = /dev/tty1 ]; then
  exec startx
fi
EOF

cat > /root/.xinitrc <<'EOF'
# Karen OS - X session
export XDG_RUNTIME_DIR="/run/user/0"
[ -d "$XDG_RUNTIME_DIR" ] || { mkdir -p "$XDG_RUNTIME_DIR"; chmod 700 "$XDG_RUNTIME_DIR"; }
xset -dpms off
xset s off
xsetroot -solid "#0A0C18"
mkdir -p /etc/xdg/tint2 /etc/xdg/openbox
cp -f /opt/karen-linux/etc/tint2/tint2rc /etc/xdg/tint2/tint2rc
cp -f /opt/karen-linux/etc/openbox/autostart /etc/xdg/openbox/autostart
exec openbox-session
EOF

cat > /opt/karen-linux/etc/openbox/autostart <<'EOF'
# Karen OS - Openbox autostart (panel + Karen assistant)
tint2 &
/opt/karen-linux/karen-bootstrap.sh >/var/log/karen-boot.log 2>&1 &
EOF

cp -f /usr/local/bin/karen-bootstrap.sh /opt/karen-linux/karen-bootstrap.sh 2>/dev/null || \
curl -fsSL "$REPO/profiles/karenos/airootfs/usr/local/bin/karen-bootstrap.sh" -o /opt/karen-linux/karen-bootstrap.sh
chmod 755 /opt/karen-linux/karen-bootstrap.sh

cat > /opt/karen-linux/etc/tint2/tint2rc <<'EOF'
# Karen OS - tint2 panel (spider theme: red accent on navy)
panel_items = clock
panel_size = 100% 26
panel_margin = 0 0 0 0
panel_padding = 4 2 4 2
panel_background_id = 1
font_shadow = 0
rounded = 0
border_width = 0
background_color = #0A0C18 90
border_color = #E31C23 45
time1_format = %H:%M
time1_font = DejaVu Sans 9
time1_timezone =
time2_format = %a %d %b
time2_font = DejaVu Sans 8
clock_fg_color = #FFFFFF 100
clock_padding = 8 0 8 0
clock_background_id = 0
tooltip_show = 0
EOF

# --- 6) privacy: block webcam entirely ------------------------------------
cat > /etc/udev/rules.d/90-karen-nocamera.rules <<'EOF'
# Karen OS - block webcam/camera access completely (privacy)
KERNEL=="video*", MODE="0000"
KERNEL=="uvcvideo*", MODE="0000"
KERNEL=="media*", MODE="0000"
EOF

# --- 7) apply -------------------------------------------------------------
systemctl preset-all >>"$LOG" 2>&1 || true
systemctl daemon-reload >>"$LOG" 2>&1 || true
udevadm control --reload >>"$LOG" 2>&1 || true

# --- 8) starter Karen config (user + providers) ---------------------------
mkdir -p /etc/karen
if [ ! -f /etc/karen/config.json ]; then
cat > /etc/karen/config.json <<'EOF'
{
  "user": {"name": "Yuvi"},
  "voice": {"enabled": true, "voice": "en-US-JennyNeural", "rate": "+0%"},
  "providers": [
    {"id": "zen", "name": "OpenCode Zen", "type": "openai",
     "base_url": "https://opencode.ai/zen/v1", "model": "deepseek-v4-flash-free",
     "api_key": "", "allow_empty_key": true},
    {"id": "gemini", "name": "Gemini", "type": "gemini",
     "model": "gemini-2.5-flash", "api_key": ""},
    {"id": "openrouter", "name": "OpenRouter (backup)", "type": "openai",
     "base_url": "https://openrouter.ai/api/v1", "model": "deepseek/deepseek-chat-v3-0324:free", "api_key": ""},
    {"id": "groq", "name": "Groq (backup 2)", "type": "openai",
     "base_url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile", "api_key": ""}
  ]
}
EOF
fi

say ""
say "======================================================"
say " DONE! Karen OS ready."
say " Next: reboot -> desktop auto-starts with Karen shell."
say " API keys: edit /etc/karen/config.json  (see README)"
say "======================================================"