#!/usr/bin/env python3
"""Karen OS - first launch wizard (Windows-style, Spiderman theme).

Runs once, when /etc/karen/config.json is missing:
   1) Welcome: what should I call you?   (default: Yuvi)
   2) Network: pick a WiFi network like Windows (signal bars, lock, password)
   3) Details: speak replies? Gemini key (optional) -> Finish

Writes /etc/karen/config.json, installs Python deps if missing,
then launches the Karen shell.
"""

import json, socket, subprocess, sys, threading
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QApplication, QCheckBox, QFrame, QHBoxLayout,
                             QInputDialog, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QMessageBox, QPushButton,
                             QStackedWidget, QVBoxLayout, QWidget)

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

CONFIG = Path("/etc/karen/config.json")
PAYLOAD = Path("/opt/karen-linux")
READY = PAYLOAD / ".ready"

DEFAULT_PROVIDERS = [
    {"id": "zen", "name": "OpenCode Zen", "type": "openai",
     "base_url": "https://opencode.ai/zen/v1", "model": "deepseek-v4-flash-free",
     "api_key": "", "allow_empty_key": True},
    {"id": "gemini", "name": "Gemini", "type": "gemini",
     "model": "gemini-2.5-flash", "api_key": ""},
    {"id": "openrouter", "name": "OpenRouter (backup)", "type": "openai",
     "base_url": "https://openrouter.ai/api/v1", "model": "deepseek/deepseek-chat-v3-0324:free", "api_key": ""},
    {"id": "groq", "name": "Groq (backup 2)", "type": "openai",
     "base_url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile", "api_key": ""},
]

BARS = "▁▂▃▄▅▆▇"
QSS = f"""
QWidget {{ background: {NAVY}; color: {WHITE}; font-size: 15px; }}
QListWidget {{ background: {NAVY}; border: none; outline: 0; }}
QListWidget::item {{ background: transparent; border: none; }}
#stepbar {{ background: {NAVY2}; border-right: 2px solid {RED}; }}
#step {{ color: {GREY}; font-size: 14px; padding: 10px; }}
#step.active {{ color: {WHITE}; font-weight: bold; }}
#step.done {{ color: {GREEN}; }}
#title {{ color: {WHITE}; font-size: 26px; font-weight: bold; }}
#sub {{ color: {GREY}; font-size: 14px; }}
#btn {{ background: {RED}; color: {WHITE}; border: none; border-radius: 8px;
       padding: 10px 26px; font-size: 15px; font-weight: bold; }}
#btn:hover {{ background: {DARKRED}; }}
#btn:disabled {{ background: #3A1530; color: #8A91A8; }}
#btnghost {{ background: transparent; color: {GREY}; border: 1px solid #2A3560;
            border-radius: 8px; padding: 10px 18px; }}
#btnghost:hover {{ color: {WHITE}; border-color: {RED}; }}
#input {{ background: {CARD}; border: 1px solid #2A3560; border-radius: 8px;
         padding: 10px 14px; color: {WHITE}; font-size: 16px; }}
#input:focus {{ border-color: {RED}; }}
#netrow {{ background: {CARD}; border-radius: 10px; margin: 4px; }}
#netrow:hover {{ background: {CARD2}; }}
#netconnected {{ background: {CARD}; border: 1px solid {GREEN}; border-radius: 10px; }}
#status {{ color: {GREEN}; font-size: 13px; }}
#warn {{ color: {AMBER}; font-size: 13px; }}
"""


def nmcli(args, timeout=25):
    try:
        r = subprocess.run(["nmcli"] + args, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout
    except Exception:
        return False, ""


def online():
    try:
        socket.create_connection(("archlinux.org", 443), 2).close()
        return True
    except OSError:
        return False


class NetRow(QFrame):
    def __init__(self, ssid, signal, security, page):
        super().__init__()
        self.setObjectName("netrow")
        self.ssid, self.security = ssid, security
        self.page = page
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 9, 16, 9)
        lay.setSpacing(12)
        name = QLabel(ssid)
        name.setStyleSheet(f"color:{WHITE};font-size:15px;font-weight:bold;")
        idx = max(0, min(6, (int(signal) if signal.isdigit() else 0) * 7 // 100))
        color = GREEN if idx >= 4 else AMBER if idx >= 2 else RED
        bars = QLabel(BARS[idx])
        bars.setStyleSheet(f"color:{color};font-size:16px;")
        sec = (security or "-") != "-"
        lock = QLabel("  [PW]" if sec else "  open")
        lock.setStyleSheet(
            f"color:{WHITE};background:{DARKRED};border-radius:8px;padding:2px 9px;font-size:11px;" if sec
            else f"color:{WHITE};background:#232B4D;border-radius:8px;padding:2px 9px;font-size:11px;")
        self.state = QLabel("")
        self.state.setStyleSheet(f"color:{GREEN};font-size:12px;font-weight:bold;")
        lay.addWidget(name)
        lay.addStretch(1)
        lay.addWidget(self.state)
        lay.addWidget(bars)
        lay.addWidget(lock)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mousePressEvent = lambda _e: page.connect_net(self)


class Wizard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Karen OS - Setup")
        self.resize(880, 560)
        self.setStyleSheet(QSS)
        self.nets = []
        self.name = "Yuvi"
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.stepbar = QVBoxLayout()
        sb = QWidget()
        sb.setObjectName("stepbar")
        sb.setFixedWidth(190)
        sb.setLayout(self.stepbar)
        logo = QLabel("🕷  KAREN OS")
        logo.setStyleSheet(f"color:{RED};font-size:19px;font-weight:bold;padding:22px 0 6px 16px;")
        self.stepbar.addWidget(logo)
        self.steps = []
        for i, t in enumerate(["Welcome", "Network", "Ready"], 1):
            l = QLabel(f"s{i}   {t}")
            l.setObjectName("step")
            l.setProperty("idx", i)
            self.stepbar.addWidget(l)
            self.steps.append(l)
        self.stepbar.addStretch(1)
        self.stepbar.addWidget(self._foot())
        outer.addWidget(sb)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.page_welcome())
        self.stack.addWidget(self.page_network())
        self.stack.addWidget(self.page_finish())
        outer.addWidget(self.stack, 1)

        self.set_step(1)

    def _foot(self):
        l = QLabel("Setup and install - power by Karen")
        l.setStyleSheet(f"color:{GREY};font-size:11px;padding:0 0 14px 16px;")
        return l

    def set_step(self, n):
        for i, s in enumerate(self.steps, 1):
            cls = "done" if i < n else "active" if i == n else "step"
            s.setStyleSheet(f"color:{GREEN if i < n else WHITE if i == n else GREY};"
                            f"font-size:14px;padding:10px 16px;"
                            f"font-weight:{'bold' if i <= n else 'normal'};"
                            f"{'background:' + CARD2 if i == n else ''};"
                            f"border-left:3px solid {'transparent' if i != n else RED};")
        self.stack.setCurrentIndex(n - 1)

    def page_welcome(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(60, 70, 60, 40)
        v.addStretch(1)
        t = QLabel("Welcome to Karen OS")
        t.setObjectName("title")
        v.addWidget(t)
        s = QLabel("Let's get you set up - just like Windows.")
        s.setObjectName("sub")
        v.addSpacing(8)
        v.addWidget(s)
        v.addSpacing(34)
        v.addWidget(self._lab("What should Karen call you?"))
        self.namebox = QLineEdit("Yuvi")
        self.namebox.setObjectName("input")
        self.namebox.setMaxLength(24)
        self.namebox.setFixedWidth(320)
        self.namebox.returnPressed.connect(self._next)
        v.addWidget(self.namebox)
        v.addStretch(1)
        v.addLayout(self._nav(back=None, nxt="Next"))
        return w

    def page_network(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(60, 50, 60, 40)
        t = QLabel("Connect to the internet")
        t.setObjectName("title")
        v.addWidget(t)
        s = QLabel("Pick a network - same as Windows. Karen needs internet on first run.")
        s.setObjectName("sub")
        v.addWidget(s)
        v.addSpacing(18)
        self.nstatus = QLabel("")
        self.nstatus.setObjectName("warn")
        v.addWidget(self.nstatus)
        self.nlist = QListWidget()
        self.nlist.setFixedHeight(280)
        v.addWidget(self.nlist)
        h = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.setObjectName("btnghost")
        refresh.clicked.connect(self.scan)
        h.addWidget(refresh)
        h.addStretch(1)
        note = QLabel("Want WPA2-Enterprise (office)? Type the SSID in the box below.")
        note.setStyleSheet(f"color:{GREY};font-size:12px;")
        h.addWidget(note)
        v.addLayout(h)
        self.ssid_box = QLineEdit()
        self.ssid_box.setObjectName("input")
        self.ssid_box.setPlaceholderText("Or type network name to connect directly...")
        self.ssid_box.returnPressed.connect(self._connect_typed)
        v.addWidget(self.ssid_box)
        v.addStretch(1)
        v.addLayout(self._nav(back=lambda: self.set_step(1), nxt="Next"))
        QTimer.singleShot(200, self.scan)
        return w

    def page_finish(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(60, 70, 60, 40)
        v.addStretch(1)
        t = QLabel("All set - Karen is almost yours")
        t.setObjectName("title")
        v.addWidget(t)
        s = QLabel("One last thing...")
        s.setObjectName("sub")
        v.addWidget(s)
        v.addSpacing(26)
        self.speak = QCheckBox("Speak replies aloud (female voice)")
        self.speak.setChecked(True)
        self.speak.setStyleSheet(f"color:{WHITE};font-size:15px;")
        v.addWidget(self.speak)
        self.keylab = self._lab("Gemini API key (optional - Zen free provider works without it)")
        v.addSpacing(8)
        v.addWidget(self.keylab)
        self.keybox = QLineEdit()
        self.keybox.setObjectName("input")
        self.keybox.setEchoMode(QLineEdit.EchoMode.Password)
        self.keybox.setPlaceholderText("AIza... (from aistudio.google.com/apikey)")
        self.keybox.setFixedWidth(420)
        v.addWidget(self.keybox)
        v.addStretch(1)
        v.addLayout(self._nav(back=lambda: self.set_step(2), nxt="Finish"))
        return w

    def _lab(self, txt):
        l = QLabel(txt)
        l.setStyleSheet(f"color:{GREY};font-size:13px;")
        return l

    def _nav(self, back, nxt):
        h = QHBoxLayout()
        h.addStretch(1)
        if back:
            b = QPushButton("Back")
            b.setObjectName("btnghost")
            b.clicked.connect(back)
            h.addWidget(b)
        n = QPushButton(nxt)
        n.setObjectName("btn")
        n.clicked.connect(self._next)
        h.addWidget(n)
        return h

    def _next(self):
        cur = self.stack.currentIndex()
        if cur == 0:
            self.name = self.namebox.text().strip() or "Yuvi"
            self.set_step(2)
        elif cur == 1:
            self.set_step(3)
        else:
            self.finish()

    # ---- network page ----------------------------------------------------
    def scan(self):
        self.nlist.clear()
        self.nets = []
        self.nstatus.setText("")
        nmcli(["dev", "wifi", "rescan"])
        ok, out = nmcli(["-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list"])
        if not ok:
            ok2, out2 = nmcli(["-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list"])
            if not ok2:
                self.nstatus.setText("NetworkManager not reachable. Plug in an ethernet cable or check WiFi is on.")
                return
            out = out2
        seen = {}
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) < 3:
                continue
            ssid = parts[0].strip().strip("'").strip('"')
            signal, sec = parts[1], parts[2]
            if not ssid or ssid in seen:
                continue
            seen[ssid] = True
            row = NetRow(ssid, signal, sec, self)
            item = QListWidgetItem()
            item.setSizeHint(row.sizeHint())
            self.nlist.addItem(item)
            self.nlist.setItemWidget(item, row)
            self.nets.append(row)
        if not seen:
            self.nstatus.setText("No networks found. Turn on the WiFi switch (as root: nmcli radio wifi on), then Refresh.")
        QTimer.singleShot(0, self._check_connected)

    def _check_connected(self):
        ok, out = nmcli(["-t", "-f", "STATE", "g"])
        state = (out.strip().splitlines() or [""])[0] if ok else ""
        if state == "connected":
            self.nstatus.setObjectName("status")
            self.nstatus.setText("Connected to WiFi - you're ready to continue.")
            self.nstatus.setStyleSheet(f"color:{GREEN};font-size:13px;")

    def _connect_typed(self):
        ssid = self.ssid_box.text().strip()
        if not ssid:
            return
        pw, ok = QInputDialog.getText(self, "WiFi password",
                                      f"Password for \"{ssid}\":",
                                      QLineEdit.EchoMode.Password, "")
        if not ok:
            return
        args = ["dev", "wifi", "connect", ssid]
        if pw:
            args += ["password", pw]
        self.nstatus.setObjectName("warn")
        self.nstatus.setStyleSheet(f"color:{AMBER};font-size:13px;")
        self.nstatus.setText(f"Connecting to {ssid}...")
        ok2, out2 = nmcli(args, timeout=40)
        if ok2:
            self._check_connected()
        else:
            self.nstatus.setText(f"Could not connect: {out2.strip()[:160]}")

    def connect_net(self, row):
        pw = None
        if row.security and row.security != "-":
            pw, ok = QInputDialog.getText(self, "WiFi password", f"Password for \"{row.ssid}\":",
                                          QLineEdit.EchoMode.Password)
            if not ok:
                return
        args = ["dev", "wifi", "connect", row.ssid]
        if pw is not None:
            args += ["password", pw]
        row.state.setText("Connecting...")
        row.state.setStyleSheet(f"color:{AMBER};font-size:12px;font-weight:bold;")
        ok2, out2 = nmcli(args, timeout=40)
        if ok2:
            row.state.setText("Connected")
            self._check_connected()
        else:
            row.state.setText("Failed")
            QMessageBox.warning(self, "Karen OS",
                                f"Could not connect to \"{row.ssid}\".\n{out2.strip()[:200]}")

    # ---- finish -----------------------------------------------------------
    def finish(self):
        cfg = {"user": {"name": self.name},
               "voice": {"enabled": self.speak.isChecked(), "voice": "en-US-JennyNeural", "rate": "+0%"},
               "providers": DEFAULT_PROVIDERS}
        for p in cfg["providers"]:
            if p["id"] == "gemini":
                p["api_key"] = self.keybox.text().strip()
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(json.dumps(cfg, indent=2))
        self._boot_deps()
        QApplication.instance().quit()

    def _boot_deps(self):
        def work():
            if not READY.exists():
                subprocess.run([sys.executable, "-m", "pip", "install",
                                "--break-system-packages", "-q",
                                "-r", str(PAYLOAD / "requirements-linux.txt")])
                READY.touch()
            subprocess.Popen([sys.executable, str(PAYLOAD / "karen_shell.py")],
                             stdout=open("/var/log/karen-session.log", "ab"),
                             stderr=subprocess.STDOUT)
        threading.Thread(target=work).start()


def main():
    app = QApplication(sys.argv)
    w = Wizard()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()