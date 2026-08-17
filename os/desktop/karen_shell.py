"""
karen_shell.py - Karen OS Linux assistant (PyQt6)
Lightweight chat shell for the Karen OS live image.
Uses Gemini API. API key: env GEMINI_API_KEY, /etc/karen/api_key.json or ~/.karen/api_key.json
"""
import json, os, platform, shutil, subprocess, sys, threading
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QApplication, QLabel, QLineEdit, QMainWindow,
                             QPushButton, QScrollArea, QTextBrowser, QVBoxLayout, QWidget)

try:
    from google import genai as _unused  # noqa
    _HAVE_GENAI = True
except ImportError:
    _HAVE_GENAI = False

if _HAVE_GENAI:
    import google.generativeai as genai

BG, PANEL, RED, RED_D, BLUE, WHITE, DIM = (
    "#05060D", "#0A0C18", "#E31C23", "#B11313", "#4F7DFF", "#FFFFFF", "#989FB2"
)

API_PATHS = [
    Path("/etc/karen/api_key.json"),
    Path.home() / ".karen" / "api_key.json",
]

MODEL = "gemini-2.5-flash"
SYSTEM = (
    "You are Karen, a calm, direct, and professional AI assistant running on Karen OS "
    "(a lightweight Arch Linux live desktop). Answer concisely. Prefer action over talk."
)


def load_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        for p in API_PATHS:
            if p.exists():
                try:
                    key = json.loads(p.read_text()).get("api_key", "")
                except Exception:
                    pass
    return key


def tool_web_search(query: str) -> str:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            res = list(ddgs.text(query, max_results=3))
        if not res:
            return "No results."
        return "\n".join(f"- {r.get('title')}: {r.get('href')}" for r in res)
    except Exception as e:
        return f"Search failed: {e}"


def tool_weather(city: str) -> str:
    try:
        import requests
        geo = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                           params={"name": city, "count": 1}, timeout=10).json()
        if not geo.get("results"):
            return f"No location found for {city}."
        loc = geo["results"][0]
        w = requests.get("https://api.open-meteo.com/v1/forecast",
                         params={"latitude": loc["latitude"], "longitude": loc["longitude"],
                                 "current_weather": "true"}, timeout=10).json()
        cw = w.get("current_weather", {})
        return (f"{loc['name']}: {cw.get('temperature')}°C, wind "
                f"{cw.get('windspeed')} km/h, code {cw.get('weathercode')}")
    except Exception as e:
        return f"Weather failed: {e}"


def tool_open_app(name: str) -> str:
    try:
        subprocess.Popen(["sh", "-c", f"nohup xdg-open '{name}' >/dev/null 2>&1 &"])
        return f"Opening {name}..."
    except Exception as e:
        return f"Failed: {e}"


def tool_sysinfo() -> str:
    return (f"{platform.platform()} | CPU: {platform.processor() or 'n/a'} | "
            f"RAM total: {round(os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE') / 2**30, 1)} GB")


TOOLS = [
    {"name": "web_search", "desc": "Search the web. args: query"},
    {"name": "weather", "desc": "Current weather. args: city"},
    {"name": "open_app", "desc": "Open an app or website. args: name"},
    {"name": "sysinfo", "desc": "Show system info. args: none"},
]
TOOL_IMPL = {"web_search": tool_web_search, "weather": tool_weather,
             "open_app": tool_open_app, "sysinfo": tool_sysinfo}


class KarenShell(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Karen OS")
        self.setGeometry(60, 60, 920, 620)
        self._model = None
        self._history = []

        root = QWidget(); root.setStyleSheet(f"background: {BG};")
        lay = QVBoxLayout(root); lay.setContentsMargins(14, 14, 14, 14); lay.setSpacing(10)

        head = QLabel(f'<span style="color:{RED};font-size:22px;font-weight:800;">KAREN</span>'
                      f'<span style="color:{DIM};font-size:12px;">   os  ·  low-end optimized</span>')
        lay.addWidget(head)

        self.feed = QTextBrowser()
        self.feed.setOpenExternalLinks(True)
        self.feed.setStyleSheet(f"QTextBrowser {{ background: {PANEL}; border: 1px solid {RED_D}; "
                                f"border-radius: 12px; color: {WHITE}; padding: 10px; }}")
        lay.addWidget(self.feed, 1)

        row = QVBoxLayout(); row.setSpacing(8)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask Karen anything... (web, weather, apps, system)")
        self.input.setStyleSheet(f"QLineEdit {{ background: {PANEL}; color: {WHITE}; border: 1px solid {RED_D}; "
                                 f"border-radius: 10px; padding: 10px; font-size: 13px; }}")
        self.input.returnPressed.connect(self.send)
        row.addWidget(self.input)

        btns = QVBoxLayout(); btns.setSpacing(8)
        self.send_btn = QPushButton("Send")
        self.send_btn.setStyleSheet(f"QPushButton {{ background: {RED}; color: {WHITE}; border: none; "
                                    f"border-radius: 10px; padding: 9px; font-weight: 700; }}"
                                    f"QPushButton:hover {{ background: {RED_D}; }}")
        self.send_btn.clicked.connect(self.send)
        btns.addWidget(self.send_btn)
        self.status = QLabel()
        self.status.setStyleSheet(f"color: {DIM}; font-size: 11px;")
        btns.addWidget(self.status)
        row.addLayout(btns)
        lay.addLayout(row)

        self.setCentralWidget(root)
        self.status.setText("Karen starting...")
        QTimer.singleShot(0, self._init_ai)
        self._push("assistant", "Hi, I'm <b>Karen</b>. Ask me anything — weather, web search, opening apps, "
                                "or system info. (Type <i>help</i> to see what I can do.)")

    def _init_ai(self):
        key = load_key()
        if not _HAVE_GENAI:
            self.status.setText("google-generativeai missing - install deps first")
            return
        if not key:
            self.status.setText("No GEMINI_API_KEY - set it or create /etc/karen/api_key.json")
            return
        genai.configure(api_key=key)
        self._model = genai.GenerativeModel(MODEL, system_instruction=SYSTEM)
        self.status.setText("Karen online - Gemini ready")

    def _push(self, role, html):
        color = RED if role == "assistant" else "#7FD1FF"
        name = "Karen" if role == "assistant" else "You"
        self.feed.append(f'<div style="color:{color};font-weight:700;">{name}</div>'
                         f'<div style="color:{WHITE};">{html}</div><br>')
        self._history.append({"role": "user" if role == "user" else "model", "parts": [html]})

    def send(self):
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self._push("user", text.replace("<", "&lt;"))
        self.send_btn.setEnabled(False)
        self.status.setText("Karen is thinking...")
        threading.Thread(target=self._answer, args=(text,), daemon=True).start()

    def _answer(self, text):
        try:
            if text.lower() == "help":
                out = ("I can: <b>web_search &lt;query&gt;</b> · <b>weather &lt;city&gt;</b> · "
                       "<b>open_app &lt;name&gt;</b> · <b>sysinfo</b> · or just chat.")
                self._done(out)
                return
            low = text.lower()
            for t in TOOLS:
                if low.startswith(t["name"]) or low.startswith("! " + t["name"]):
                    arg = text.split(" ", 1)[1] if " " in text else ""
                    out = TOOL_IMPL[t["name"]](arg) if t["name"] != "sysinfo" else TOOL_IMPL["sysinfo"]()
                    self._done(f'<b>[{t["name"]}]</b> {out.replace("<", "&lt;")}')
                    return
            if not self._model:
                self._done("AI not configured (no API key). Use ! tools: weather <city>, web_search <q>.")
                return
            chat = self._model.start_chat(history=self._history[-8:])
            resp = chat.send_message(text)
            self._done(resp.text.replace("\n", "<br>").replace("<", "&lt;"))
        except Exception as e:
            self._done(f"Error: {e}")

    def _done(self, html):
        def apply():
            self._push("assistant", html)
            self.send_btn.setEnabled(True)
            self.status.setText("Karen online")
            self.feed.verticalScrollBar().setValue(self.feed.verticalScrollBar().maximum())
        QTimer.singleShot(0, apply)


def main():
    app = QApplication(sys.argv)
    app.setApplicationDisplayName("Karen OS")
    w = KarenShell()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
