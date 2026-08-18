#!/usr/bin/env bash
# ===========================================================================
# karen-setup.sh - run INSIDE the freshly installed Karen OS (portable USB)
#
#   curl -fsSL https://raw.githubusercontent.com/yuviwork15-collab/karen-os/main/os/installer/karen-setup.sh | bash
#
# One command, that's it. Installs: X + Openbox + tint2 + Karen shell
# (multi-provider AI, female voice). Applies: zram swap, performance
# governor, autologin, no-camera policy. First boot after reboot ->
# Windows-style setup wizard (WiFi picker) -> Karen speaks.
# ===========================================================================
set -euo pipefail
export LANG=C.UTF-8
REPO="https://raw.githubusercontent.com/yuviwork15-collab/karen-os/main/os"
LOG=/var/log/karen-setup.log
R='\e[1;31m'; B='\e[1;34m'; N='\e[0m'

banner() {
  printf "${R}  ___  _   _ ____  _____ ____  _   _ \n${N}"
  printf "${R} / __|| | | |  _ \| ____|  _ \| \ | |${N}\n"
  printf "${R}| |  _| | | | |_) |  _| | |_) |  \| |${N}\n"
  printf "${R}| |_| | |_| |  _ <| |___|  _ <| |\  |${N}\n"
  printf "${R} \____|\___/|_| \_\_____|_| \_\_| \_|${N}\n"
  printf "${B}        Spider-Sensed. Karen-Styled.${N}\n"
  echo ""
}
say() { echo -e "[karen-setup] $*" | tee -a "$LOG"; }

banner
say "Karen OS setup starting..."

# --- 1) packages ----------------------------------------------------------
say "installing desktop + runtime packages... (few minutes)"
pacman -S --noconfirm --needed \
  xorg-server xorg-xinit xorg-xrandr xorg-xdpyinfo xf86-video-vesa \
  openbox tint2 xterm pcmanfm \
  pipewire pipewire-pulse wireplumber alsa-utils portaudio \
  python python-pip python-pyqt6 python-pyaudio mpv yt-dlp plymouth hsetroot scrot firefox \
  networkmanager cpupower zram-generator git sudo openssh \
  >>"$LOG" 2>&1
say "  [OK] packages"

# --- 2) Karen payload -----------------------------------------------------
say "downloading Karen shell + welcome wizard..."
mkdir -p /opt/karen-linux/etc/tint2 /opt/karen-linux/etc/openbox /opt/karen-linux/assets /opt/karen-linux/media /opt/karen-linux/screenshots
for f in karen_shell.py karen-welcome.py karen-dock.py requirements-linux.txt; do
  curl -fsSL "$REPO/desktop/$f" -o "/opt/karen-linux/$f"
done
curl -fsSL "$REPO/profiles/karenos/airootfs/opt/karen-linux/assets/wallpaper.png" -o /opt/karen-linux/assets/wallpaper.png
curl -fsSL "$REPO/profiles/karenos/airootfs/opt/karen-linux/etc/openbox/menu.xml" -o /opt/karen-linux/etc/openbox/menu.xml
python -m pip install --break-system-packages -q -r /opt/karen-linux/requirements-linux.txt >>"$LOG" 2>&1
curl -fsSL "$REPO/profiles/karenos/airootfs/usr/local/bin/karen-bootstrap.sh" -o /opt/karen-linux/karen-bootstrap.sh
chmod 755 /opt/karen-linux/karen_shell.py /opt/karen-linux/karen-welcome.py \
  /opt/karen-linux/karen-dock.py /opt/karen-linux/karen-bootstrap.sh
say "  [OK] Karen shell"

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

# --- boot splash (plymouth, spidey) + USB durability + speed tuning --------
mkdir -p /usr/share/plymouth/themes/karen-spidey
for f in karen-spidey.plymouth karen-spidey.script spider.png frame0.png frame1.png frame2.png \
         frame3.png frame4.png frame5.png frame6.png frame7.png; do
  curl -fsSL "$REPO/profiles/karenos/airootfs/usr/share/plymouth/themes/karen-spidey/$f" \
    -o "/usr/share/plymouth/themes/karen-spidey/$f" 2>/dev/null || true
done
cat > /etc/plymouth/plymouthd.conf <<'EOF'
[Daemon]
Theme=karen-spidey
ShowDelay=0
DeviceTimeout=8
EOF

cat > /etc/mkinitcpio.conf <<'EOF'
# Karen OS - initramfs with plymouth boot splash
MODULES=()
BINARIES=()
FILES=()
HOOKS=(base udev autodetect modconf kms keyboard keymap consolefont plymouth block filesystems)
COMPRESSION="zstd"
EOF
mkinitcpio -P >>"$LOG" 2>&1 || true

sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT=.*/GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"/' /etc/default/grub

# Karen spidey GRUB theme (background + red highlights)
mkdir -p /boot/grub/themes/karen
cp -f /opt/karen-linux/assets/wallpaper.png /boot/grub/themes/karen/wallpaper.png
if ! grep -q '^GRUB_BACKGROUND=' /etc/default/grub; then
  printf 'GRUB_BACKGROUND="/boot/grub/themes/karen/wallpaper.png"\n' >> /etc/default/grub
fi
if ! grep -q '^GRUB_COLOR_NORMAL=' /etc/default/grub; then
  printf 'GRUB_COLOR_NORMAL="white/black"\nGRUB_COLOR_HIGHLIGHT="light-red/dark-gray"\n' >> /etc/default/grub
fi
grub-mkconfig -o /boot/grub/grub.cfg >>"$LOG" 2>&1 || true

cat > /etc/systemd/journald.conf <<'EOF'
# Karen OS - keep logs in RAM: portable USB write wear + speed
[Journal]
Storage=volatile
Compress=yes
SystemMaxUse=32M
EOF

echo 'tmpfs /var/log tmpfs defaults,noatime,nosuid,noexec,size=64M 0 0' >> /etc/fstab

cat > /etc/sysctl.d/99-karen.conf <<'EOF'
# Karen OS - snappier on 4GB RAM
vm.swappiness=10
vm.vfs_cache_pressure=50
EOF

cat > /etc/systemd/system-preset/90-karen.preset <<'EOF'
# Karen OS - services we want
enable NetworkManager.service
enable cpufreq.service
enable systemd-zram-setup@zram0.service
enable plymouth-start.service
enable plymouth-quit.service
enable plymouth-quit-wait.service

# bloat off
disable bluetooth.service
disable avahi-daemon.service
disable systemd-journal-upload.service
EOF
say "  [OK] boot splash + durability + speed"

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
[ -f /opt/karen-linux/assets/wallpaper.png ] && hsetroot -fill /opt/karen-linux/assets/wallpaper.png || xsetroot -solid "#0A0C18"
mkdir -p /etc/xdg/tint2 /etc/xdg/openbox
cp -f /opt/karen-linux/etc/tint2/tint2rc /etc/xdg/tint2/tint2rc
cp -f /opt/karen-linux/etc/openbox/autostart /etc/xdg/openbox/autostart
cp -f /opt/karen-linux/etc/openbox/menu.xml /etc/xdg/openbox/menu.xml
exec openbox-session
EOF

cat > /opt/karen-linux/etc/openbox/autostart <<'EOF'
# Karen OS - Openbox autostart (panel + dock + Karen assistant)
tint2 &
/opt/karen-linux/karen-dock.py >/var/log/karen-dock.log 2>&1 &
/opt/karen-linux/karen-bootstrap.sh >/var/log/karen-boot.log 2>&1 &
EOF

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
time2_format = %a %d %b
time2_font = DejaVu Sans 8
clock_fg_color = #FFFFFF 100
clock_padding = 8 0 8 0
clock_background_id = 0
tooltip_show = 0
EOF
say "  [OK] X desktop + spider theme"

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
say "  [OK] camera blocked + services applied"

printf "${R}"
say ""
say "======================================================"
say " DONE! Karen OS is ready."
say "======================================================"
printf "${N}"
say "  Next: reboot."
say "  First boot = Windows-style wizard:"
say "    step 1: your name (e.g. Yuvi)"
say "    step 2: pick WiFi from the list (signal bars + lock)"
say "    step 3: Finish -> Karen speaks: Welcome back, <name>!"
say "  API keys later: nano /etc/karen/config.json  (see README)"
say ""
echo -e "${R}  Reboot now to start the wizard: ${N}reboot"