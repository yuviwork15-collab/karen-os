#!/usr/bin/env python3
"""Karen OS Installer - boots into this. macOS-style, zero terminal.

Flow: Welcome -> pick target USB/disk -> wipe confirmation -> archinstall
(silent, unattended) -> Karen setup inside the fresh system (chroot) -> reboot.
The target system then first-boots into the macOS-style Karen desktop.
"""

import ctypes, json, os, re, secrets, subprocess, sys, threading, time
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QListWidget,
                             QListWidgetItem, QMessageBox, QPlainTextEdit, QProgressBar,
                             QPushButton, QStackedWidget, QVBoxLayout, QWidget)

NAVY = "#0A0C18"
NAVY2 = "#0F1630"
CARD = "#131A33"
CARD2 = "#1B2447"
RED = "#E31C23"
DARKRED = "#B11313"
WHITE = "#F2F4FF"
GREY = "#8A91A8"
GREEN = "#3DDC84"
AMBER = "#FFC53D"

QSS = f"""
QWidget {{ background: {NAVY}; color: {WHITE}; font-size: 15px; }}
#stepbar {{ background: {NAVY2}; border-right: 2px solid {RED}; }}
#step {{ color: {GREY}; font-size: 14px; padding: 12px 16px; }}
#title {{ font-size: 27px; font-weight: bold; color: {WHITE}; }}
#sub {{ color: {GREY}; font-size: 14px; }}
#btn {{ background: {RED}; color: {WHITE}; border: none; border-radius: 8px;
       padding: 10px 26px; font-size: 15px; font-weight: bold; }}
#btn:hover {{ background: {DARKRED}; }}
#btn:disabled {{ background: #3A1530; color: #8A91A8; }}
#btnghost {{ background: transparent; color: {GREY}; border: 1px solid #2A3560;
            border-radius: 8px; padding: 10px 18px; }}
#btnghost:hover {{ color: {WHITE}; border-color: {RED}; }}
#diskrow {{ background: {CARD}; border-radius: 10px; margin: 4px; }}
#diskrow:hover {{ background: {CARD2}; }}
#diskrow.sel {{ background: {CARD2}; border: 2px solid {RED}; }}
#log {{ background: {NAVY}; color: #C7D0E8; font-family: monospace; font-size: 12px;
       border: 1px solid #2A3560; border-radius: 8px; }}
#bar {{ border: none; background: {CARD}; height: 10px; border-radius: 5px; }}
#bar::chunk {{ background: {RED}; border-radius: 5px; }}
"""

SETUP_URL = ("https://raw.githubusercontent.com/yuviwork15-collab/karen-os/"
             "main/os/installer/karen-setup.sh")


def sha512_crypt(password):
    """libcrypt via ctypes (crypt module was removed in Python 3.13+)."""
    salt = "$6$" + secrets.token_hex(8)
    lib = None
    for name in ("libcrypt.so.2", "libcrypt.so.1", "libc.so.6"):
        try:
            lib = ctypes.CDLL(name)
            break
        except OSError:
            continue
    if lib is None:
        return password
    lib.crypt.restype = ctypes.c_char_p
    lib.crypt.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    return lib.crypt(password.encode(), salt.encode()).decode()


class DiskRow(QFrame):
    def __init__(self, dev, name, size, model, page):
        super().__init__()
        self.setObjectName("diskrow")
        self.dev, self.page = dev, page
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(14)
        t = QLabel(f"{name}  <span style='color:{WHITE};font-size:16px;'>{model or 'drive'}</span>")
        t.setTextFormat(Qt.TextFormat.RichText)
        s = QLabel(size)
        s.setStyleSheet(f"color:{WHITE};font-size:15px;font-weight:bold;")
        lay.addWidget(t)
        lay.addStretch(1)
        lay.addWidget(s)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mousePressEvent = lambda _e: page.pick_disk(self)


class Installer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Karen OS Installer")
        self.resize(900, 590)
        self.setStyleSheet(QSS)
        self.disks = []
        self.target = None
        self.installing = False
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        sb = QWidget()
        sb.setObjectName("stepbar")
        sb.setFixedWidth(200)
        sv = QVBoxLayout(sb)
        sv.setSpacing(2)
        logo = QLabel("KAREN OS")
        logo.setStyleSheet(f"color:{RED};font-size:20px;font-weight:bold;padding:24px 0 10px 18px;")
        sv.addWidget(logo)
        self.steps = []
        for t in ["Welcome", "Choose disk", "Confirm", "Installing", "Done"]:
            l = QLabel("•  " + t)
            l.setObjectName("step")
            sv.addWidget(l)
            self.steps.append(l)
        sv.addStretch(1)
        note = QLabel("Direct install →\nyour other USB.\nNo live desktop.")
        note.setStyleSheet(f"color:{GREY};font-size:12px;padding:0 14px 16px 18px;")
        sv.addWidget(note)
        outer.addWidget(sb)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.page_welcome())
        self.stack.addWidget(self.page_disk())
        self.stack.addWidget(self.page_confirm())
        self.stack.addWidget(self.page_progress())
        self.stack.addWidget(self.page_done())
        outer.addWidget(self.stack, 1)
        self.step(0)

    def step(self, n):
        for i, s in enumerate(self.steps):
            s.setStyleSheet(
                f"color:{GREEN if i < n else WHITE if i == n else GREY};font-size:14px;"
                f"padding:12px 16px;font-weight:{'bold' if i == n else 'normal'};"
                f"background:{CARD2 if i == n else 'transparent'};"
                f"border-left:3px solid {'transparent' if i != n else RED};")
        self.stack.setCurrentIndex(n)

    def _nav(self, back=None, nxt=None, nxt_label="Next"):
        h = QHBoxLayout()
        h.addStretch(1)
        if back:
            b = QPushButton("Back")
            b.setObjectName("btnghost")
            b.clicked.connect(back)
            h.addWidget(b)
        if nxt:
            n = QPushButton(nxt_label)
            n.setObjectName("btn")
            n.clicked.connect(nxt)
            h.addWidget(n)
        return h

    def page_welcome(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(60, 60, 60, 40)
        v.addStretch(1)
        t = QLabel("Install Karen OS")
        t.setObjectName("title")
        v.addWidget(t)
        s = QLabel("Plug in the USB where Karen should LIVE (e.g. SanDisk 32GB).\n"
                   "It will be wiped clean. The installer handles everything - no terminal needed.")
        s.setObjectName("sub")
        v.addWidget(s)
        v.addSpacing(8)
        warn = QLabel("⚠ The disk you pick will be erased completely.")
        warn.setStyleSheet(f"color:{AMBER};font-size:14px;")
        v.addWidget(warn)
        v.addStretch(1)
        v.addLayout(self._nav(nxt=self.step1, nxt_label="Choose disk"))
        return w

    # ---------------- disk selection ----------------
    def step1(self):
        self.step(1)
        self.rescan()

    def rescan(self):
        self.list_disk.clear()
        self.disks = []
        boot_dev = self._boot_device()
        try:
            out = subprocess.run(["lsblk", "-J", "-o", "NAME,SIZE,MODEL,TYPE"],
                                 capture_output=True, text=True, timeout=15).stdout
            data = json.loads(out)

            def walk(node):
                if node.get("type") == "disk":
                    name = node["name"]
                    if name != boot_dev and not name.startswith("loop") and not name.startswith("zram"):
                        self.disks.append((name, node.get("size", "?"), node.get("model", "")))
                for c in node.get("children", []):
                    walk(c)
            for d in data.get("blockdevices", []):
                walk(d)
        except Exception as e:
            self.lab_disk.setText(f"Could not list disks: {e}")
            return
        self.lab_disk.setText("Choose where to install Karen")
        for name, size, model in self.disks:
            row = DiskRow(f"/dev/{name}", f"/dev/{name}", size, model, self)
            item = QListWidgetItem()
            item.setSizeHint(row.sizeHint())
            self.list_disk.addItem(item)
            self.list_disk.setItemWidget(item, row)
        if not self.disks:
            self.lab_disk.setText("No installable disk found. Plug in your USB and press Refresh.")

    def _boot_device(self):
        try:
            for line in subprocess.run(["sh", "-c", "mount | grep /run/archiso/bootmnt"],
                                       capture_output=True, text=True).stdout.splitlines():
                m = re.search(r"^/dev/([a-z0-9]+)", line)
                if m:
                    return m.group(1)
        except Exception:
            pass
        return ""

    def pick_disk(self, row):
        for i in range(self.list_disk.count()):
            w = self.list_disk.itemWidget(self.list_disk.item(i))
            if isinstance(w, DiskRow):
                w.setObjectName("diskrow")
                w.style().unpolish(w)
                w.style().polish(w)
        self.target = row.dev
        row.setObjectName("diskrow sel")
        row.style().unpolish(row)
        row.style().polish(row)
        self.lab_pick.setText(f"Target: {row.dev} ({row.findChildren(QLabel)[1].text()})")

    def confirm_go(self):
        if not self.target:
            QMessageBox.warning(self, "Karen OS", "Pick a disk first.")
            return
        r = QMessageBox.question(
            self, "Erase everything?",
            f"ALL data on <b>{self.target}</b> will be destroyed.\n"
            f"Make sure it is EMPTY or a backup already exists.\n\nContinue?",)
        if r != QMessageBox.StandardButton.Yes:
            return
        self.step(3)
        self.installing = True
        threading.Thread(target=self._install, daemon=True).start()

    # ---------------- install ----------------
    def _install(self):
        try:
            disk = self.target
            work = "/tmp/karen-ai"
            os.makedirs(work, exist_ok=True)
            root_pass = sha512_crypt("karen")
            with open(f"{work}/creds.json", "w") as f:
                json.dump({"!root-password": root_pass}, f)
            with open(f"{work}/config.json", "w") as f:
                json.dump({
                    "script": "guided",
                    "hostname": "karenos",
                    "bootloader": "grub",
                    "bootloader_config": {"bootloader": "grub"},
                    "locale_config": {"sys_lang": "en_US", "sys_enc": "UTF-8", "kb_layout": "us"},
                    "kernels": ["linux"],
                    "network_config": {"type": "nm"},
                    "audio_config": None,
                    "gfx_driver": "All open-source (default)",
                    "packages": [],
                    "timezone": "Asia/Kolkata",
                    "ntp": True,
                    "swap": True,
                    "debug": False,
                    "offline": False,
                    "disk_config": {
                        "config_type": "default_layout",
                        "device_modifications": [
                            {"device": disk, "wipe": True,
                             "partitions": {"filesystem": {"format": "ext4"}}}
                        ],
                    },
                }, f, indent=2)
            self._log("Wiping + partitioning " + disk, stage=0)
            cmd = ["archinstall", "--silent", "--config", f"{work}/config.json",
                   "--creds", f"{work}/creds.json"]
            self._stream(cmd, stage=(10, 60), what="Installing base system...")
            root_mount = self._find_mounted_root(disk)
            if not root_mount:
                self._fail("Could not find the fresh install mountpoint")
                return
            self._log("Configuring Karen on the new system...", stage=70)
            self._chroot_setup(root_mount)
            self._log("Install complete!", stage=100)
            QTimer.singleShot(0, lambda: (self.step(4), self.done_btn.setEnabled(True)))
        except Exception as e:
            self._fail(str(e))

    def _find_mounted_root(self, disk):
        try:
            out = subprocess.run(["sh", "-c", f"lsblk -rn -o MOUNTPOINT {disk}"],
                                 capture_output=True, text=True).stdout.splitlines()
            for mp in out:
                mp = mp.strip()
                if mp and mp.startswith("/mnt"):
                    return mp
        except Exception:
            pass
        return "/mnt/archinstall"

    def _chroot_setup(self, mount):
        subprocess.run(["sh", "-c",
                        f"cp -f /etc/resolv.conf {mount}/etc/resolv.conf 2>/dev/null; "
                        f"mount --bind /dev {mount}/dev 2>/dev/null; "
                        f"mount --bind /proc {mount}/proc 2>/dev/null; "
                        f"mount --bind /sys {mount}/sys 2>/dev/null; "
                        f"mount --bind /run {mount}/run 2>/dev/null"], check=False)
        subprocess.run(["sh", "-c",
                        f"curl -fsSL '{SETUP_URL}' -o {mount}/root/karen-setup.sh"],
                       check=False)
        subprocess.run(["sh", "-c",
                        f"echo 'nameserver 8.8.8.8' > {mount}/etc/resolv.conf; "
                        f"chmod 755 {mount}/root/karen-setup.sh"],
                       check=False)
        self._run(["sh", "-c", f"chroot {mount} env LANG=C.UTF-8 bash /root/karen-setup.sh"],
                  cb=self._log)

    def _stream(self, cmd, stage, what):
        self._log(what, stage=stage[0])
        self._run(cmd, cb=lambda line: self._silent())

    def _silent(self):
        pass

    def _run(self, cmd, cb=None):
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in p.stdout:
            line = line.rstrip()
            if cb and line:
                cb(line)
        p.wait()
        if p.returncode != 0:
            raise RuntimeError(f"command failed: {' '.join(cmd)}")

    def _log(self, txt, stage=None):
        if stage is not None:
            QTimer.singleShot(0, lambda: (self.bar.setValue(stage),
                                          self.lab_stage.setText(txt[:60])))
        QTimer.singleShot(0, lambda: (self.logbox.appendPlainText(str(txt)[:500]),
                                      self.logbox.verticalScrollBar().setValue(
                                          self.logbox.verticalScrollBar().maximum())))

    def _fail(self, msg):
        QTimer.singleShot(0, lambda: (self.logbox.appendPlainText("\nERROR: " + msg),
                                      self.lab_stage.setText("Install failed"),
                                      self.retry_btn.setVisible(True),
                                      self.done_btn.setEnabled(False)))

    # ---------------- pages ----------------
    def page_disk(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(60, 40, 60, 40)
        t = QLabel("Choose disk")
        t.setObjectName("title")
        v.addWidget(t)
        self.lab_disk = QLabel("Scanning...")
        self.lab_disk.setObjectName("sub")
        v.addWidget(self.lab_disk)
        v.addSpacing(12)
        self.list_disk = QListWidget()
        self.list_disk.setFixedHeight(300)
        v.addWidget(self.list_disk)
        h = QHBoxLayout()
        ref = QPushButton("Refresh")
        ref.setObjectName("btnghost")
        ref.clicked.connect(self.rescan)
        h.addWidget(ref)
        h.addStretch(1)
        v.addLayout(h)
        self.lab_pick = QLabel("")
        self.lab_pick.setStyleSheet(f"color:{AMBER};font-size:14px;")
        v.addWidget(self.lab_pick)
        v.addLayout(self._nav(back=lambda: self.step(0), nxt=lambda: self.step(2),
                              nxt_label="Continue"))
        return w

    def page_confirm(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(60, 60, 60, 40)
        v.addStretch(1)
        t = QLabel("Last look before wipe")
        t.setObjectName("title")
        v.addWidget(t)
        v.addSpacing(16)
        box = QFrame()
        box.setStyleSheet(f"background:{CARD};border-radius:10px;")
        bv = QVBoxLayout(box)
        for lbl in [
            "Target disk : will be wiped completely",
            "Boot        : GRUB (works on BIOS + UEFI)",
            "Partitions  : 2MiB bios_grub + 512MiB EFI + rest ext4",
            "Root password : karen  (change later)",
            "After install: reboot straight into Karen OS",
        ]:
            l = QLabel(lbl)
            l.setStyleSheet(f"color:{WHITE};font-size:15px;padding:5px 0;")
            bv.addWidget(l)
        v.addWidget(box)
        v.addStretch(1)
        v.addLayout(self._nav(back=lambda: self.step(1), nxt=self.confirm_go,
                              nxt_label="Erase & Install"))
        return w

    def page_progress(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(60, 40, 60, 40)
        t = QLabel("Installing Karen OS")
        t.setObjectName("title")
        v.addWidget(t)
        self.lab_stage = QLabel("Preparing...")
        self.lab_stage.setObjectName("sub")
        v.addWidget(self.lab_stage)
        v.addSpacing(12)
        self.bar = QProgressBar()
        self.bar.setObjectName("bar")
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        v.addWidget(self.bar)
        v.addSpacing(12)
        self.logbox = QPlainTextEdit()
        self.logbox.setObjectName("log")
        self.logbox.setReadOnly(True)
        v.addWidget(self.logbox, 1)
        self.retry_btn = QPushButton("Reboot and retry later")
        self.retry_btn.setObjectName("btn")
        self.retry_btn.setVisible(False)
        self.retry_btn.clicked.connect(lambda: subprocess.run(["systemctl", "reboot", "-i"]))
        v.addWidget(self.retry_btn)
        return w

    def page_done(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(60, 60, 60, 40)
        v.addStretch(1)
        t = QLabel("Karen OS installed!")
        t.setObjectName("title")
        v.addWidget(t)
        s = QLabel("Remove this installer USB, then reboot.\n"
                   "Karen will greet you with a macOS-style desktop - in her voice.")
        s.setObjectName("sub")
        v.addWidget(s)
        v.addSpacing(30)
        self.done_btn = QPushButton("Reboot now")
        self.done_btn.setObjectName("btn")
        self.done_btn.setEnabled(False)
        self.done_btn.clicked.connect(lambda: subprocess.run(["systemctl", "reboot", "-i"]))
        v.addWidget(self.done_btn)
        v.addStretch(1)
        return w


def main():
    app = QApplication(sys.argv)
    w = Installer()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()