# Karen OS

Custom **Arch Linux** live desktop OS, made for **low-end PCs** — har resource
(CPU, RAM, swap) optimized hai. Boot karo → automatic Karen shell khul jata hai.

## OS specs

| Item | Value |
|---|---|
| Base | Arch Linux (x86_64), live ISO |
| Kernel | linux + linux-firmware (LTS-friendly) |
| Desktop | Xorg + Openbox + tint2 panel (no DE bloat) |
| Assistant | Karen shell (PyQt6) — auto-start on boot |
| Swap | zram (compressed RAM swap, `ram / 2`, zstd) |
| CPU | performance governor (snappy on weak CPUs) |
| Audio | PipeWire (lightweight) |
| ISO size | ~700MB (zstd squashfs) |
| Boot | UEFI + legacy BIOS (GRUB/syslinux) |

## Folder layout

```
os/
├── build.ps1                  <- Windows launcher (WSL/VM/cloud — auto-detect)
├── profiles/karenos/
│   ├── profile.conf           <- ISO config
│   ├── pacman.conf
│   ├── packages.x86_64        <- lean package list
│   └── airootfs/              <- system overlay (configs go into the ISO)
│       ├── etc/systemd/...    <- autologin, zram, presets
│       ├── etc/xdg/openbox/   <- autostart (tint2 + Karen)
│       └── opt/karen-linux/   <- Karen payload (filled at build time)
├── desktop/
│   ├── karen_shell.py         <- the OS assistant (runs on Linux)
│   └── requirements-linux.txt
├── scripts/
│   └── build-in-vm.sh         <- ISO build (Arch Linux / WSL2 / Docker/VM)
├── .github/workflows/         <- cloud build (no local Linux needed)
└── docs/
    ├── ARCHITECTURE.md
    ├── VM-BUILD.md
    └── OPTIMUM11-WSL-FIX.md
```

## Build — 3 raaste (koi bhi chuno)

### Option 1: GitHub Actions (recommended — zero local Linux)
1. Folder ko GitHub repo me push karo
2. Actions tab → **Build Karen OS ISO** → *Run workflow*
3. ~10 min me `karenos-*.iso` **artifact** download karo
4. Rufus (Windows) se USB me burn karke boot karo

### Option 2: VirtualBox VM (4GB RAM ke liye setup)
- `docs/VM-BUILD.md` dekho — Arch ISO VM me, shared folder, ek command me ISO banega

### Option 3: WSL2 (agar kisi normal Windows build me ho)
- `sysd check` ho to bas:
  ```
  bash /path/to/os/scripts/build-in-vm.sh /path/to/project
  ```
- Optimum 11 me WSL ka payload remove hai → `docs/OPTIMUM11-WSL-FIX.md` (DISM se Win11 ISO se wapas)

## Boot karne ke baad

- **tty1 autologin** → X + Openbox + tint2 + Karen shell automatically
- Karen API key: boot ke baad (internet chahiye pehli baar):
  ```
  mkdir -p /etc/karen
  echo '{"api_key": "AIza...."}' > /etc/karen/api_key.json
  ```
- Pehli boot par bootstrap: pip deps install hota hai (ek baar), phir shell khulta hai
- `Ctrl+Alt+F2-F6` = text consoles · `exit` in shell = poweroff
- `!` tools: `weather delhi` · `web_search news` · `open_app firefox` · `sysinfo`

## Low-end notes

- zram = `ram/2` zstd — 4GB RAM pe ~2GB compressed swap, disk swap se 2-3x fast
- PNG/JPEG mohat: matlab koi compositor nahi, animations off
- CPU governor `performance` — low-end pe snappy feel
- Baaki bloat (bluetooth/avahi etc.) ISO me hi `disable` preset kiya hai

## Roadmap

- [ ] Voice input (wake word) — pyaudio + vosk (light)
- [ ] Playwright browser automation (chromium)
- [ ] Smart home controller (python-kasa works on Linux)
- [ ] Installer (archinstall profile) → USB se permanent install
- [ ] Karen full-feature parity port to Linux (Windows app ka Linux edition)

> Note: Windows app (`main.py`/`ui.py`) Windows-only APIs (winreg, win10toast,
> pywinauto) use karta hai — ye Linux pe nahi chalta. Karen OS me iska
> **Linux edition** (`karen_shell.py`) chalta hai, dheere-dheere full parity ho rahi hai.