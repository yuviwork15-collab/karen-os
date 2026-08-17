#!/usr/bin/env bash
# ===========================================================================
# Karen OS - ISO build script (run INSIDE Linux: WSL2, VirtualBox VM, or any
# Arch Linux machine). Produces os/profiles/karenos/out/karenos-*.iso
#
# Usage:
#   On Arch Linux:      bash scripts/build-in-vm.sh /path/to/karen-project
#   On Ubuntu VM:       use the official archlinux Docker image instead
#                       (see README.md "Cloud build" / Docker instructions)
# ===========================================================================
set -euo pipefail

KAREN_PROJECT="$(realpath "${1:-.}")"
OS_DIR="$KAREN_PROJECT/os"
PROFILE="$OS_DIR/profiles/karenos"

echo "==> Karen OS builder"
echo "    project : $KAREN_PROJECT"
echo "    profile : $PROFILE"

# --- must be Arch Linux (mkarchiso is Arch-specific) ----------------------
if ! command -v pacman >/dev/null 2>&1; then
  echo "ERROR: This script needs Arch Linux (pacman)."
  echo "Use the GitHub Actions cloud build, or run an Arch VM / archlinux Docker image."
  exit 1
fi

# --- archiso ---------------------------------------------------------------
if ! command -v mkarchiso >/dev/null 2>&1; then
  echo "==> installing archiso..."
  pacman -Syy --noconfirm --needed archiso
fi

# --- populate the karen-linux payload from os/desktop/ ---------------------
echo "==> copying Karen shell payload..."
mkdir -p "$PROFILE/airootfs/opt/karen-linux"
cp -f "$OS_DIR/desktop/karen_shell.py"        "$PROFILE/airootfs/opt/karen-linux/"
cp -f "$OS_DIR/desktop/karen-welcome.py"      "$PROFILE/airootfs/opt/karen-linux/"
cp -f "$OS_DIR/desktop/requirements-linux.txt" "$PROFILE/airootfs/opt/karen-linux/"
rm -f "$PROFILE/airootfs/opt/karen-linux/.ready"

# --- build ----------------------------------------------------------------
cd "$OS_DIR"
echo "==> mkarchiso building ISO (zstd, low-RAM friendly)..."
mkarchiso -v -w work -o out "$PROFILE"

ISO="$(ls out/karenos-*.iso 2>/dev/null | head -n1)"
echo ""
echo "=================================================================="
if [ -n "$ISO" ]; then
  echo "DONE! ISO ready: $ISO"
  echo "    size : $(du -h "$ISO" | cut -f1)"
  echo "    Burn it to USB with Rufus (Windows) or Ventoy."
else
  echo "BUILD FAILED - check logs above."
fi
echo "=================================================================="