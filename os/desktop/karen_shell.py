"""
karen_shell.py - Karen OS Linux assistant (PyQt6) - VOICE-FIRST
- Voice mode: offline speech recognition (vosk) + female neural voice (edge-tts)
- Multi-provider AI: OpenCode Zen / Gemini / OpenRouter / Groq (auto fallback)
- Welcomes you by name ("Welcome back Yuvi") with time-of-day greeting

Config: /etc/karen/config.json  (or ~/.karen/config.json, or env vars)

{
  "user": {"name": "Yuvi"},
  "providers": [
    {"id": "zen",  "name": "OpenCode Zen", "type": "openai",
     "base_url": "https://opencode.ai/zen/v1", "model": "deepseek-v4-flash-free",
     "api_key": "", "allow_empty_key": true},
    ...
  ],
  "voice": {"enabled": true, "voice": "en-US-JennyNeural", "rate": "+0%"}
}
"""
import datetime as _dt
import html as _html
import json, math, os, platform, re, struct, subprocess, sys, tempfile, threading, time, urllib.request, wave, zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (QApplication, QLabel, QLineEdit, QMainWindow,
                             QPushButton, QTextBrowser, QVBoxLayout, QWidget)

import requests

BG, PANEL, RED, RED_D, BLUE, WHITE, DIM = (
    "#05060D", "#0A0C18", "#E31C23", "#B11313", "#4F7DFF", "#FFFFFF", "#989FB2"
)

CONFIG_PATHS = [Path("/etc/karen/config.json"), Path.home() / ".karen" / "config.json"]
VOSK_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
VOSK_DIR = Path("/opt/karen-linux/models/vosk-small")
MEDIA_DIR = Path("/opt/karen-linux/media")
NOTES_FILE = Path("/opt/karen-linux/notes.txt")
SHOTS_DIR = Path("/opt/karen-linux/screenshots")

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

SYSTEM = (
    "You are Karen, a calm, direct, and professional AI assistant on Karen OS. "
    "Answer concisely and naturally. The user's name is {name}. "
    "Prefer action over talk."
)


def load_config():
    cfg = {}
    for p in CONFIG_PATHS:
        if p.exists():
            try:
                cfg.update(json.loads(p.read_text()))
                break
            except Exception:
                pass
    providers = cfg.get("providers") or [dict(p) for p in DEFAULT_PROVIDERS]
    for p in providers:
        p.setdefault("api_key", os.environ.get("KAREN_API_KEY_" + p["id"].upper(), ""))
    voice = cfg.get("voice") or {"enabled": True, "voice": "en-US-JennyNeural", "rate": "+0%"}
    user = cfg.get("user") or {"name": "Yuvi"}
    return providers, voice, user


def load_gemini_key():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        for p in [Path("/etc/karen/api_key.json"), Path.home() / ".karen" / "api_key.json"]:
            if p.exists():
                try:
                    key = json.loads(p.read_text()).get("api_key", "")
                except Exception:
                    pass
    return key


def openai_chat(prov, messages):
    url = prov["base_url"].rstrip("/") + "/chat/completions"
    r = requests.post(url, headers={
        "Authorization": f"Bearer {prov.get('api_key', '')}",
        "Content-Type": "application/json",
    }, json={"model": prov["model"], "messages": messages}, timeout=90)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def gemini_chat(prov, messages):
    import google.generativeai as genai
    genai.configure(api_key=prov["api_key"] or load_gemini_key())
    model = genai.GenerativeModel(prov["model"], system_instruction=SYSTEM)
    parts = [m["content"] for m in messages if m["role"] == "user"]
    return model.generate_content(parts).text


def tool_web_search(query: str) -> str:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            res = list(ddgs.text(query, max_results=3))
        return "\n".join(f"- {r.get('title')}: {r.get('href')}" for r in res) if res else "No results."
    except Exception as e:
        return f"Search failed: {e}"


def tool_weather(city: str) -> str:
    try:
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
    subprocess.Popen(["sh", "-c", f"nohup xdg-open '{name}' >/dev/null 2>&1 &"])
    return f"Opening {name}..."


def tool_sysinfo() -> str:
    return (f"{platform.platform()} | CPU: {platform.processor() or 'n/a'} | "
            f"RAM: {round(os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE') / 2**30, 1)} GB")


TOOLS = [
    {"name": "web_search", "desc": "Search the web. args: query"},
    {"name": "weather", "desc": "Current weather. args: city"},
    {"name": "open_app", "desc": "Open an app or website. args: name"},
    {"name": "sysinfo", "desc": "Show system info. args: none"},
]
TOOL_IMPL = {"web_search": tool_web_search, "weather": tool_weather,
             "open_app": tool_open_app, "sysinfo": tool_sysinfo}


def _rms(data) -> int:
    import array
    samples = array.array("h", data)
    if not samples:
        return 0
    return int((sum(s * s for s in samples) / len(samples)) ** 0.5)


class SoundFx:
    """Situation-based sound effects - generated as WAV at first run, played via aplay."""

    SR = 22050

    def __init__(self):
        self._dir = Path("/opt/karen-linux/sounds")
        self._ok = subprocess.run(["sh", "-c", "command -v aplay"],
                                  capture_output=True).returncode == 0
        self._lock = threading.Lock()
        if self._ok:
            threading.Thread(target=self._ensure, daemon=True).start()

    def _ensure(self):
        with self._lock:
            self._dir.mkdir(parents=True, exist_ok=True)
            if not (self._dir / "startup.wav").exists():
                self._gen("startup.wav", [(523.25, 0.18), (659.25, 0.18), (783.99, 0.30)], 0.5)
                self._gen("reply.wav", [(659.25, 0.12), (783.99, 0.22)], 0.45)
                self._gen("send.wav", [(987.77, 0.07)], 0.35)
                self._gen("error.wav", [(196.0, 0.35)], 0.45, wobble=True)
                self._gen("mic_on.wav", [(523.25, 0.09), (659.25, 0.09)], 0.4)
                self._gen("mic_off.wav", [(659.25, 0.09), (523.25, 0.09)], 0.4)
                self._gen("alarm.wav", [(880.0, 0.15), (None, 0.12), (880.0, 0.15),
                                        (None, 0.12), (880.0, 0.30)], 0.5)

    @staticmethod
    def _tone(freq, dur, vol, phase=0.0, wobble=False):
        n = int(SoundFx.SR * dur)
        out = []
        for i in range(n):
            t = i / SoundFx.SR
            env = min(1.0, t * 30) * min(1.0, (dur - t) * 8)
            f = freq * (1 + 0.03 * math.sin(2 * math.pi * 4 * t)) if wobble else freq
            out.append(int(32767 * vol * env * math.sin(2 * math.pi * f * t + phase)))
        return out

    def _gen(self, name, notes, vol, wobble=False):
        samples = []
        phase = 0.0
        for freq, dur in notes:
            if freq is None:
                samples += [0] * int(SoundFx.SR * dur)
            else:
                chunk = self._tone(freq, dur, vol, phase, wobble)
                samples += chunk
                phase += 2 * math.pi * freq * dur
        with wave.open(str(self._dir / name), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.SR)
            w.writeframes(struct.pack("<%dh" % len(samples), *samples))

    def play(self, name):
        if not self._ok:
            return
        f = self._dir / f"{name}.wav"
        if f.exists():
            threading.Thread(target=lambda: subprocess.run(
                ["aplay", "-q", str(f)], capture_output=True), daemon=True).start()


class MediaPlayer:
    """Speech-driven music/video: yt-dlp search+download (cached in MEDIA_DIR), mpv playback."""

    def __init__(self):
        self.proc = None
        self._lock = threading.Lock()

    def playing(self):
        return self.proc is not None and self.proc.poll() is None

    def stop(self):
        with self._lock:
            if self.proc and self.proc.poll() is None:
                try:
                    self.proc.terminate()
                except Exception:
                    pass
            self.proc = None

    def play(self, query, video=False):
        self.stop()
        threading.Thread(target=self._work, args=(query, video), daemon=True).start()

    def _work(self, query, video):
        try:
            MEDIA_DIR.mkdir(parents=True, exist_ok=True)
            fmt = "bestvideo*+bestaudio/best" if video else "bestaudio/best"
            subprocess.run(["yt-dlp", "-f", fmt, "--no-playlist", "-o",
                            str(MEDIA_DIR / "%(title).50s.%(ext)s"),
                            f"ytsearch1:{query}"], capture_output=True, timeout=600)
            files = sorted(MEDIA_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not files:
                return
            f = files[0]
            args = ["mpv", "--no-terminal", "--really-quiet", "--no-video", str(f)] if not video else \
                   ["mpv", "--no-terminal", "--really-quiet", str(f)]
            self.proc = subprocess.Popen(args)
            self.proc.wait()
        except Exception:
            pass

    def status(self):
        if self.playing():
            return "Music playing (say <b>stop</b> to stop)"
        return ""


class VoiceInput:
    """Offline speech recognition (vosk) with silence-based sentence detection."""

    def __init__(self):
        self._model = None
        self._rec = None
        self._stream = None
        self._pa = None
        self.available = False

    def ensure_model(self):
        if self._model:
            return True
        try:
            import vosk  # noqa
        except ImportError:
            return False
        if VOSK_DIR.exists():
            for child in VOSK_DIR.iterdir():
                if child.is_dir():
                    self._model = vosk.Model(str(child))
                    self.available = True
                    return True
        return False

    def download_model(self, status_cb=None):
        try:
            VOSK_DIR.parent.mkdir(parents=True, exist_ok=True)
            tmp = VOSK_DIR.parent / "vosk.zip"
            if status_cb:
                status_cb("Downloading voice model (40MB)...")
            urllib.request.urlretrieve(VOSK_URL, tmp)
            with zipfile.ZipFile(tmp) as z:
                z.extractall(VOSK_DIR)
            tmp.unlink()
            return self.ensure_model()
        except Exception:
            return False

    def start(self, on_text, on_state):
        if not self.ensure_model():
            if not self.download_model(on_state):
                on_state("Voice model unavailable - using text only")
                return
        try:
            import pyaudio
            import vosk
            vosk.SetLogLevel(-1)
            if self._stream:
                return
            self._rec = vosk.KaldiRecognizer(self._model, 16000)
            self._pa = pyaudio.PyAudio()
            self._stream = self._pa.open(format=pyaudio.paInt16, channels=1,
                                         rate=16000, input=True, frames_per_buffer=4000)
            self._run(on_text, on_state)
        except Exception as e:
            on_state(f"Mic error: {e}")

    def _run(self, on_text, on_state):
        on_state("Listening... (voice mode)")
        buf = b""
        silent_for = 0.0
        got_partial = False
        while self._stream:
            try:
                data = self._stream.read(4000, exception_on_overflow=False)
            except Exception:
                break
            buf += data
            if self._rec.AcceptWaveform(data):
                text = json.loads(self._rec.Result()).get("text", "").strip()
                if text:
                    on_text(text)
                buf = b""
                got_partial = False
                continue
            rms = _rms(data)
            if rms < 400:
                silent_for += 0.25
            else:
                silent_for = 0.0
            if silent_for > 1.5 and got_partial:
                text = json.loads(self._rec.FinalResult()).get("text", "").strip()
                if text:
                    on_text(text)
                buf = b""
                got_partial = False
            elif buf and self._rec.PartialResult():
                got_partial = True

    def stop(self):
        try:
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
            if self._pa:
                self._pa.terminate()
        except Exception:
            pass
        self._stream = None


class KarenShell(QMainWindow):
    def __init__(self):
        super().__init__()
        self._providers, self._voice_cfg, self._user = load_config()
        self._history = []
        self._active = None
        self._busy = False
        self._voice_mode = True
        self._muted = not self._voice_cfg.get("enabled", True)
        self._tts_ok = subprocess.run(["sh", "-c", "command -v mpv"], capture_output=True).returncode == 0
        self._mic = VoiceInput()
        self._sfx = SoundFx()
        self._media = MediaPlayer()
        self._reminders = []
        self._confirm = None
        rt = QTimer(self)
        rt.timeout.connect(self._check_reminders)
        rt.start(1000)

        self.setWindowTitle("Karen OS")
        self.setGeometry(60, 60, 960, 660)

        root = QWidget(); root.setStyleSheet(f"background: {BG};")
        lay = QVBoxLayout(root); lay.setContentsMargins(14, 14, 14, 14); lay.setSpacing(10)

        head = QVBoxLayout(); head.setSpacing(2)
        title = QLabel(f'<span style="color:{RED};font-size:22px;font-weight:800;">KAREN</span>'
                       f'<span style="color:{DIM};font-size:12px;">   os  ·  voice first</span>')
        head.addWidget(title)
        self.prov_label = QLabel()
        self.prov_label.setStyleSheet(f"color: {BLUE}; font-size: 11px;")
        head.addWidget(self.prov_label)
        lay.addLayout(head)

        self.feed = QTextBrowser()
        self.feed.setOpenExternalLinks(True)
        self.feed.setStyleSheet(f"QTextBrowser {{ background: {PANEL}; border: 1px solid {RED_D}; "
                                f"border-radius: 12px; color: {WHITE}; padding: 10px; }}")
        lay.addWidget(self.feed, 1)

        row = QVBoxLayout(); row.setSpacing(8)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type here... or just talk to Karen")
        self.input.setStyleSheet(f"QLineEdit {{ background: {PANEL}; color: {WHITE}; border: 1px solid {RED_D}; "
                                 f"border-radius: 10px; padding: 10px; font-size: 13px; }}")
        self.input.returnPressed.connect(self.send)
        row.addWidget(self.input)

        btns = QVBoxLayout(); btns.setSpacing(8)
        self.send_btn = QPushButton("Send")
        self.send_btn.setStyleSheet(f"QPushButton {{ background: {RED}; color: {WHITE}; border: none; "
                                    f"border-radius: 10px; padding: 8px; font-weight: 700; }}"
                                    f"QPushButton:hover {{ background: {RED_D}; }}")
        self.send_btn.clicked.connect(self.send)
        btns.addWidget(self.send_btn)

        self.voice_btn = QPushButton("Voice Mode: ON")
        self.voice_btn.setStyleSheet(self._btn_style(BLUE, BLUE))
        self.voice_btn.clicked.connect(self.toggle_voice)
        btns.addWidget(self.voice_btn)

        self.mute_btn = QPushButton("Speak: " + ("OFF" if self._muted else "ON"))
        self.mute_btn.setStyleSheet(self._btn_style(BLUE, BLUE))
        self.mute_btn.clicked.connect(self.toggle_mute)
        btns.addWidget(self.mute_btn)

        self.status = QLabel()
        self.status.setStyleSheet(f"color: {DIM}; font-size: 11px;")
        btns.addWidget(self.status)
        row.addLayout(btns)
        lay.addLayout(row)

        self.setCentralWidget(root)
        self._greet()

    @staticmethod
    def _btn_style(color, border):
        return (f"QPushButton {{ background: {PANEL}; color: {color}; border: 1px solid {border}; "
                f"border-radius: 10px; padding: 7px; font-size: 11px; }}")

    def _greet(self):
        self._sfx.play("startup")
        hour = _dt.datetime.now().hour
        part = "Good morning" if hour < 12 else ("Good afternoon" if hour < 17 else "Good evening")
        name = self._user.get("name", "Yuvi")
        self._push("assistant", f"<b>{part}, welcome back {name}!</b><br>"
                                f"<span style='color:{DIM};'>I'm Karen - just talk to me, or type below.</span>")
        self._refresh_provider_label()
        self.status.setText("Karen ready")
        self._speak(f"{part} Yoo-vee! Welcome back! This is Karen. How can I help you today?")
        if self._voice_mode and self._tts_ok:
            QTimer.singleShot(2500, self._start_listening)

    def _refresh_provider_label(self):
        active = self._active or self._find_first_ready()
        name = active["name"] if active else "none configured"
        self.prov_label.setText(f"Provider: {name} | Voice: {self._voice_cfg.get('voice')} (female)")

    def _find_first_ready(self):
        for p in self._providers:
            key = p.get("api_key") or (load_gemini_key() if p["type"] == "gemini" else "")
            if p["type"] == "openai" and not p.get("base_url"):
                continue
            if p["type"] == "openai" and not key and not p.get("allow_empty_key"):
                continue
            if key or p.get("allow_empty_key") or p["type"] == "gemini":
                return p
        return None

    def _push(self, role, html):
        color = RED if role == "assistant" else "#7FD1FF"
        name = "Karen" if role == "assistant" else "You"
        self.feed.append(f'<div style="color:{color};font-weight:700;">{name}</div>'
                         f'<div style="color:{WHITE};">{html}</div><br>')
        self._history.append({"role": "user" if role == "user" else "model", "content": html})

    def toggle_voice(self):
        self._voice_mode = not self._voice_mode
        self.voice_btn.setText("Voice Mode: " + ("ON" if self._voice_mode else "OFF"))
        self._sfx.play("mic_on" if self._voice_mode else "mic_off")
        if self._voice_mode:
            self._start_listening()
        else:
            self._mic.stop()
            self.status.setText("Voice mode off")

    def toggle_mute(self):
        self._muted = not self._muted
        self.mute_btn.setText("Speak: " + ("OFF" if self._muted else "ON"))

    def _start_listening(self):
        if not self._voice_mode or self._busy:
            return
        threading.Thread(target=self._mic.start, args=(self._on_voice_text, self._on_mic_state),
                         daemon=True).start()

    def _on_mic_state(self, msg):
        self.status.setText(msg)

    def _on_voice_text(self, text):
        if not text:
            return
        self._sfx.play("send")
        self._push("user", text.replace("<", "&lt;"))
        self.send_btn.setEnabled(False)
        self.status.setText("Karen is thinking...")
        self._busy = True
        threading.Thread(target=self._answer, args=(text,), daemon=True).start()

    def send(self):
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self._sfx.play("send")
        self._push("user", text.replace("<", "&lt;"))
        self.send_btn.setEnabled(False)
        self.status.setText("Karen is thinking...")
        self._busy = True
        threading.Thread(target=self._answer, args=(text,), daemon=True).start()

    def _try_media(self, low, text):
        """Voice/text media routing: 'play <song>', 'playv', 'stop'. Returns HTML or None."""
        if low == "stop" or low.startswith("stop ") or low == "stop music":
            self._media.stop()
            return "<b>[media]</b> Playback stopped."
        if low.startswith("play ") or low.startswith("playv ") or low.startswith("bajao "):
            query = text.split(" ", 1)[1].strip() if " " in text else ""
            if not query:
                return "<b>[media]</b> What should I play? Try: play <i>song name</i>"
            video = low.startswith("playv ")
            self._media.play(query, video)
            return "<b>[media]</b> Playing <i>%s</i>... (first time: downloading)" % query.replace("<", "&lt;")
        return None

    # ---- reminders --------------------------------------------------------
    _UNIT = {"s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
             "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
             "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600}

    def _check_reminders(self):
        now = time.time()
        for fire, msg in list(self._reminders):
            if now >= fire:
                self._reminders.remove((fire, msg))
                self._sfx.play("alarm")
                self._push("assistant", f"<b>[reminder]</b> {msg}")
                self.status.setText("Reminder fired")
                self._speak(f"Reminder: {msg}")
                if self._voice_mode:
                    self._start_listening()

    def _try_remind(self, low, text):
        m = re.match(r"remind me in (\d+)\s*([a-z]+)?[ ,]*(?:to |that )?(.*)$", low)
        if not m:
            m = re.match(r"remind me (?:to |that )?(.+?) in (\d+)\s*([a-z]+)?$", low)
            if m:
                task, n, unit = m.group(1), m.group(2), m.group(3)
            else:
                if not re.match(r"alarm in (\d+)", low):
                    return None
                n, unit, task = re.match(r"alarm in (\d+)\s*([a-z]+)?", low).group(1), \
                                re.match(r"alarm in (\d+)\s*([a-z]+)?", low).group(2), ""
        else:
            n, unit, task = m.group(1), m.group(2), m.group(3)
        mult = self._UNIT.get((unit or "m").lower(), 60)
        secs = max(1, int(n) * mult)
        msg = (task or "alarm").strip() or "alarm"
        self._reminders.append((time.time() + secs, msg))
        return f"<b>[reminder]</b> Set for {n} {unit or 'minute(s)'}: <i>{msg}</i>"

    # ---- notes (Karen memory) ---------------------------------------------
    def _try_notes(self, low, text):
        if low.startswith("remember "):
            note = text.split(" ", 1)[1].strip()
            NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(NOTES_FILE, "a") as f:
                f.write(f"{_dt.datetime.now():%Y-%m-%d %H:%M} - {note}\n")
            return f"<b>[notes]</b> I'll remember that: <i>{note}</i>"
        if low in ("my notes", "read my notes", "what did i remember", "show notes"):
            return self._read_notes()
        if low in ("clear my notes", "forget everything"):
            if NOTES_FILE.exists():
                NOTES_FILE.unlink()
            return "<b>[notes]</b> Memory cleared."
        return None

    def _read_notes(self, n=6):
        if not NOTES_FILE.exists():
            return "<b>[notes]</b> Nothing saved yet. Say: remember <i>something</i>"
        lines = NOTES_FILE.read_text().strip().splitlines()
        body = "<br>".join("&bull; " + l.replace("<", "&lt;") for l in lines[-n:])
        return f"<b>[notes]</b> Last {min(n, len(lines))} notes:<br>{body}"

    # ---- system control -----------------------------------------------------
    def _try_system(self, low, text):
        if self._confirm is not None and low in ("yes", "confirm", "haan", "yup", "yeah"):
            act = self._confirm
            self._confirm = None
            threading.Thread(target=lambda: subprocess.run(["systemctl", act, "-i"],
                                                           capture_output=True), daemon=True).start()
            return "Goodbye! " + ("Rebooting now." if act == "reboot" else "Shutting down.")
        if low in ("shutdown", "poweroff", "power off") or low.startswith("shutdown "):
            self._confirm = "poweroff"
            return "Are you sure? Say <b>yes</b> to shut down."
        if low in ("reboot", "restart") or low.startswith("reboot "):
            self._confirm = "reboot"
            return "Are you sure? Say <b>yes</b> to reboot."
        if low.startswith("volume up"):
            subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "+10%"], capture_output=True)
            return "<b>[system]</b> Volume up."
        if low.startswith("volume down"):
            subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "-10%"], capture_output=True)
            return "<b>[system]</b> Volume down."
        if low in ("mute", "volume off"):
            subprocess.run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"], capture_output=True)
            return "<b>[system]</b> Muted."
        if low in ("unmute", "volume on"):
            subprocess.run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"], capture_output=True)
            return "<b>[system]</b> Unmuted."
        if low == "screenshot" or low.startswith("screenshot "):
            SHOTS_DIR.mkdir(parents=True, exist_ok=True)
            path = SHOTS_DIR / f"shot_{_dt.datetime.now():%Y%m%d_%H%M%S}.png"
            ok = subprocess.run(["scrot", str(path)], capture_output=True).returncode
            if ok == 0:
                return f"<b>[system]</b> Screenshot saved: <i>{path.name}</i>"
            return "<b>[system]</b> Screenshot failed (scrot missing?)."
        return None

    # ---- news ---------------------------------------------------------------
    def _try_news(self, low):
        if not (low in ("news", "news headlines", "headlines", "breaking news") or low.startswith("news ")):
            return None
        for url in ("https://feeds.bbci.co.uk/news/world/rss.xml",
                    "https://feeds.bbci.co.uk/news/world/asia/rss.xml"):
            try:
                r = requests.get(url, timeout=15)
                root = ET.fromstring(r.content)
                items = root.findall(".//item")[:3]
                titles = [re.sub(r"<[^>]+>", "", _html.unescape(it.findtext("title") or ""))
                          for it in items if it.findtext("title")]
                if titles:
                    return "<b>[news]</b> " + "<br>".join(
                        f"{i+1}. {t}" for i, t in enumerate(titles))
            except Exception:
                continue
        return "<b>[news]</b> Could not fetch headlines."

    def _answer(self, text):
        try:
            if text.lower() == "help":
                self._done("Tools: <b>web_search &lt;q&gt;</b> · <b>weather &lt;city&gt;</b> · "
                           "<b>open_app &lt;name&gt;</b> · <b>sysinfo</b> · <b>providers</b> · "
                           "<b>play &lt;song&gt;</b> · <b>stop</b> · <b>remind me in X minutes to ...</b> · "
                           "<b>remember ...</b> · <b>news</b> · <b>volume up/down</b> · <b>screenshot</b> · "
                           "<b>reboot/shutdown</b> · or just chat.")
                return
            low = text.lower()
            media = self._try_media(low, text)
            if media is not None:
                self._done(media)
                return
            out = self._try_remind(low, text) or self._try_notes(low, text) or \
                  self._try_system(low, text) or self._try_news(low)
            if out:
                self._done(out)
                return
            if low.startswith("providers"):
                lines = []
                for i, p in enumerate(self._providers):
                    key = p.get("api_key") or (load_gemini_key() if p["type"] == "gemini" else "")
                    ready = bool(key or p.get("allow_empty_key") or (p["type"] == "gemini" and key))
                    lines.append(f"{i+1}. {p['name']} [{p['type']}] {p['model']} "
                                 f"{'<b>READY</b>' if ready else 'no key'}")
                self._done("<br>".join(lines))
                return
            low = text.lower()
            for t in TOOLS:
                if low.startswith(t["name"]) or low.startswith("! " + t["name"]):
                    arg = text.split(" ", 1)[1] if " " in text else ""
                    out = TOOL_IMPL[t["name"]](arg) if t["name"] != "sysinfo" else TOOL_IMPL["sysinfo"]()
                    self._done(f'<b>[{t["name"]}]</b> {out.replace("<", "&lt;")}')
                    return
            system = SYSTEM.format(name=self._user.get("name", "Yuvi"))
            msgs = [{"role": "user", "content": m["content"]} for m in self._history[-10:]]
            msgs.insert(0, {"role": "system", "content": system})
            self._active = None
            errors = []
            for p in self._providers:
                key = p.get("api_key") or (load_gemini_key() if p["type"] == "gemini" else "")
                if p["type"] == "openai" and not p.get("base_url"):
                    continue
                if p["type"] == "openai" and not key and not p.get("allow_empty_key"):
                    continue
                if p["type"] == "gemini" and not key:
                    continue
                try:
                    if p["type"] == "gemini":
                        out = gemini_chat(p, msgs)
                    else:
                        send = [{"role": "system", "content": system}] + \
                               ([m for m in msgs if m["role"] == "user"] if p["id"] == "zen" else msgs)
                        out = openai_chat(p, send)
                    self._active = p
                    self._done(out.replace("\n", "<br>").replace("<", "&lt;"))
                    return
                except Exception as e:
                    errors.append(f"{p['name']}: {e}")
                    continue
            self._done("All providers failed:<br>" + "<br>".join(errors[:4]))
        except Exception as e:
            self._done(f"Error: {e}")

    def _speak(self, text):
        if self._muted or not self._tts_ok:
            return
        try:
            plain = " ".join(text.split())
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                tmp = f.name
            threading.Thread(target=self._tts_run, args=(plain, tmp), daemon=True).start()
        except Exception:
            pass

    def _tts_run(self, text, tmp):
        try:
            import asyncio
            from edge_tts import Communicate
            voice = self._voice_cfg.get("voice", "en-US-JennyNeural")
            rate = self._voice_cfg.get("rate", "+0%")
            asyncio.run(Communicate(text, voice=voice, rate=rate).save(tmp))
            subprocess.run(["mpv", "--no-video", "--really-quiet", tmp], timeout=120)
        except Exception:
            pass
        finally:
            try:
                os.unlink(tmp)
            except Exception:
                pass

    def _done(self, html):
        def apply():
            self._push("assistant", html)
            self.send_btn.setEnabled(True)
            self._busy = False
            if self._active:
                self._refresh_provider_label()
            if html.startswith("Error:") or html.startswith("All providers failed:"):
                self._sfx.play("error")
                self.status.setText("Something went wrong")
            else:
                self._sfx.play("reply")
                self.status.setText("Karen online" if not self._voice_mode else "Listening...")
            self.feed.verticalScrollBar().setValue(self.feed.verticalScrollBar().maximum())
            self._speak(html)
            if self._voice_mode:
                QTimer.singleShot(600, self._start_listening)
        QTimer.singleShot(0, apply)


def main():
    app = QApplication(sys.argv)
    app.setApplicationDisplayName("Karen OS")
    w = KarenShell()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
