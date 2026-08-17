# Karen OS — Architecture

```
┌────────────────────────────────────────────────────────────┐
│  USER (boot from USB)                                      │
├────────────────────────────────────────────────────────────┤
│  SYSTEMD BOOT / SYSLINUX        (UEFI + BIOS)              │
├────────────────────────────────────────────────────────────┤
│  LINUX KERNEL          linux + firmware, low-latency       │
│  ──────────────────────────────────────────────            │
│  zram swap (ram/2 zstd)   cpufreq: performance            │
│  NetworkManager          hardened presets (bloat off)     │
├────────────────────────────────────────────────────────────┤
│  XORG  +  OPENBOX  +  TINT2  +  PCManFM                    │
│     (no compositor, no animations — 4GB-RAM friendly)      │
├────────────────────────────────────────────────────────────┤
│  KAREN SHELL (PyQt6 chat UI)                             │
│    ├── Gemini API (text AI)                                │
│    ├── ! weather <city>        (open-meteo)                │
│    ├── ! web_search <query>    (duckduckgo)                │
│    ├── ! open_app <name>       (xdg-open)                  │
│    └── ! sysinfo               (CPU/RAM/OS)                │
├────────────────────────────────────────────────────────────┤
│  PIPE: bootstrap.sh → pip deps (first boot) → karen_shell  │
└────────────────────────────────────────────────────────────┘
```

## How the ISO is assembled (mkarchiso)

1. `packages.x86_64` — lean set: base, X, light WM, Python/Qt, no heavy DE
2. `airootfs/` = root filesystem overlay — systemd presets, autologin, zram,
   openbox autostart, cpufreq, profile.d env
3. `os/desktop/*` copied into `airootfs/opt/karen-linux/` at build time
4. `mkarchiso` → squashfs (zstd) → bootable ISO (UEFI+BIOS)

## Low-end optimization summary

| Resource | Trick | Effect |
|---|---|---|
| RAM 4GB | zram swap (zstd) | ~2GB extra effective memory |
| CPU weak | performance governor | no lag on sleep/wake |
| GPU none | no compositor, DPMS off | less CPU burn |
| Disk | zstd squashfs | smaller ISO, faster USB boot |
| Startup | autologin tty1 → X | boots straight to Karen UI |