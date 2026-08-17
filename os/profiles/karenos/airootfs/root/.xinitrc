# Karen OS - X session
export XDG_RUNTIME_DIR="/run/user/0"
[ -d "$XDG_RUNTIME_DIR" ] || { mkdir -p "$XDG_RUNTIME_DIR"; chmod 700 "$XDG_RUNTIME_DIR"; }

# lighten the desktop for low-end hardware
xset -dpms off
xset s off
xsetroot -solid "#0A0C18"

exec openbox-session
