# VirtualBox VM Build (Windows pe, WSL ke bina)

4GB RAM wali machine ke liye optimized steps. VirtualBox needs ~2GB VM RAM,
build ke waqt baaki apps band rakhna.

## 1. Download

- VirtualBox: https://www.virtualbox.org (installer, next-next-finish)
- Arch Linux ISO: https://archlinux.org/download  (archlinux-xxxx.xx.01-x86_64.iso)

## 2. VM banaye

```
New VM:
  Name: KarenBuilder
  Type: Linux, Arch Linux (64-bit)
  RAM: 2048 MB
  Virtual Hard Disk: 16 GB (VDI, dynamic)

Settings -> Storage -> Add optical drive -> arch ISO
Settings -> Shared Folders -> Add:
    Folder path: C:\Users\Admin\Desktop\Brahma-Echo-main
    Name: karen   (auto-mount = ON)
```

## 3. Arch VM me boot karke

```bash
# live environment me:
mount -t vfat /dev/sr0 /mnt 2>/dev/null || mount /dev/sr0 /mnt   # optional

# shared folder mount karo:
mkdir -p /mnt/host
mount -t 9p -o trans=virtio,version=9p2000.L /mnt/karen /mnt/host 2>/dev/null \
  || mount -t vboxsf karen /mnt/host

cd /mnt/host/os
bash scripts/build-in-vm.sh /mnt/host
```

9p/vboxsf dono fail hote hain to Google Drive/disc se `os/` folder copy karo.

## 4. ISO mil gaya

```
os/out/karenos-*.iso
```
Host folder (shared) ke through Windows me copy karo → **Rufus** se USB burn → boot.

> Disk me install nahi karna — bas live boot karo. (Installer roadme me roadmap par hai.)