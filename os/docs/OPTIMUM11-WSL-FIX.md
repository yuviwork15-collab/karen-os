# Optimum 11 pe WSL Repair (optional)

Optimum 11 me WSL ka payload remove hai (`VirtualMachinePlatform — Disabled with
Payload Removed`), isliye `wsl --install` silently fail karta hai. Agar WSL hi
chahiye ho to Win11 ISO se feature wapas laga sakte ho:

## Steps (admin PowerShell)

1. **Win11 ISO download** karo (koi bhi official/build) → Explorer me mount karo
   (right-click → Mount). Niche `D:` ki jagah apna mounted letter daalo.

2. Features wapas add karo (source = mounted ISO):

```powershell
dism /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /source:D:\sources\install.wim /limitaccess
dism /online /enable-feature /featurename:VirtualMachinePlatform /all /source:D:\sources\install.wim /limitaccess
```

3. **Reboot** (dono features ke baad)

4. WSL engine install (Store bagair):

```powershell
# WSL MSI - GitHub releases se:
# https://github.com/microsoft/WSL/releases  ->  wsl.x.x.x.x64.msi
start wsl.x.x.x.x64.msi     # install ho jayega, reboot nahi chahiye
wsl --update
```

5. Arch Linux distro (Store ki zaroorat nahi — direct tar):

```powershell
# ArchWSL tarball: https://github.com/yuk7/ArchWSL/releases
# x64_xxx.tar.gz/zip download karke:
tar -xf ... (or right-click extract)
.\Arch.exe            # install + default user
wsl --set-version Arch 2
```

6. systemd enable (mkarchiso ke liye zaroori):

```bash
cd etc
echo -e "[boot]\nsystemd=true" > wsl.conf
```
`wsl --shutdown` (Windows se), phir `wsl -d Arch` wapas — `systemctl list-units | head`

7. Build:

```bash
bash /mnt/c/Users/Admin/Desktop/Brahma-Echo-main/os/scripts/build-in-vm.sh /mnt/c/Users/Admin/Desktop/Brahma-Echo-main
```

> **Zaroori nahi** — GitHub Actions cloud build isse aasan hai (README dekho).