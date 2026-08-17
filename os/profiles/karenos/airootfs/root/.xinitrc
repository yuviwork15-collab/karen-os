# Karen OS - X session
export XDG_RUNTIME_DIR="/run/user/0"
[ -d "$XDG_RUNTIME_DIR" ] || { mkdir -p "$XDG_RUNTIME_DIR"; chmod 700 "$XDG_RUNTIME_DIR"; }

# lighten the desktop for low-end hardware
xset -dpms off
xset s off
xsetroot -solid "#0A0C18"

# install Karen desktop configs (avoid package file conflicts in airootfs)
mkdir -p /etc/xdg/tint2 /etc/xdg/openbox
cp -f /opt/karen-linux/etc/tint2/tint2rc /etc/xdg/tint2/tint2rc
cp -f /opt/karen-linux/etc/openbox/autostart /etc/xdg/openbox/autostart

exec openbox-session
