# Karen — AI Assistant Summary

> **Naam:** Karen (pehle "Brahma Echo" / "Brahma AI - Lite")
> **Type:** Windows 10/11 desktop AI assistant — voice-first
> **AI providers:** Gemini (primary) + OpenRouter (fallback)
> **UI:** PyQt6 desktop app (+ browser dashboard + Discord bridge + Android companion)

---

## 1. Ye kya hai?

Karen ek premium Windows desktop assistant hai jo **voice aur text dono** se kaam karta hai.
Bole to sunta hai (wake word: **"Karen"**, "hey karen", "hi karen", "hello karen"), screen
dekh kar samajhta hai, aur automation/workflow tools se desktop par asli kaam kar deta hai —
presentation banana, website build karna, files organize karna, app kholna, smart home control, sab kuch.

## 2. Main features

| Category | Kya karta hai |
|---|---|
| **Voice assistant** | Wake word, voice commands, Edge TTS voice replies, live mic listening |
| **AI brain** | Gemini 2.5 Flash primary + OpenRouter fallback; `core/prompt.txt` system prompt |
| **Screen awareness** | OpenCV + Mediapipe se screen/camera/elements inspect karke context-aware answers |
| **Desktop automation** | Apps open/control, windows, browser (Playwright), clicks, typing, shortcuts |
| **Office / content** | PPTX presentations, Word/DOCX, XLSX spreadsheets, PDF reports — prompt se banta hai |
| **Website builder** | Full-stack landing pages / dashboards generate karke local preview me launch |
| **Smart home** | python-kasa + Atomberg fans/lights/plugs voice commands se control (smart_home page) |
| **Memory** | User turn + assistant turn se memory extract/store hoti hai (`memory/`) |
| **Remote** | Dashboard web-UI, Discord bot, aur Brahma Connect mobile companion (pairing QR, mDNS discovery) |
| **Plugin system** | `plugins/` me Python plugins — `on_startup`, `on_text_command` hooks |
| **Extra tools** | Reminders, meeting assistant, YouTube transcript/summary, weather, flight finder, gestures, qrcode, file organizer, dev agent, game updater, social/Instagram messaging, edge-tts voice |

## 3. Project structure

| Folder/File | Role |
|---|---|
| `main.py` | Entry point — `BrahmaLive` core: wake word, tool routing, TTS, memory pipeline |
| `ui.py` | PyQt6 desktop UI (chat feed, dashboard, settings, tray) |
| `core/prompt.txt` | System prompt (LLM ko batata hai ki wo "Karen" hai aur kaise behave kare) |
| `actions/` | ~50 action modules — har ek ek tool (app launcher, office builder, website builder…) |
| `agent/` | Planner + error recovery prompts |
| `config/` | `api_keys.json`, `app_settings.json`, `brahma_connect.json`, certs, shortcut script |
| `memory/` | Memory extraction/storage manager |
| `dashboard/` | Local Web dashboard + FastAPI server (remote commands, TLS, AES session) |
| `discord_bot.py` | Discord bridge (Karen se server me baat karo) |
| `smart_home_page_new.py` | Smart home voice control page |
| `brahma_connect/` | Local gateway: pairing, mDNS discovery, WebSocket routing (companion app) |
| `assets/web_background/` | 3D WebGL "living" background (Karen orb) |
| `homescreen background/` | Next.js orb UI (hand tracking) for home screen |
| `brahma-connect-android/` | Android companion app source (Brahma Connect) |
| `plugin_manager.py` | Plugin registration/dispatch |
| `or_client.py` | OpenRouter client |

## 4. Tech stack

Python 3.11+, PyQt6, sounddevice/pyaudio (mic+audio), Edge TTS (voice out),
google-genai / google-generativeai, playwright (browser), pyautogui (desktop clicks),
opencv-python + mediapipe (vision), python-kasa (smart home), fastapi + uvicorn (dashboard),
discord.py, Pillow, qrcode, cryptography, reportlab/python-pptx/python-docx/openpyxl
(office docs), mss, psutil, pywinauto.

## 5. Kaise chalta hai

```
python main.py            (ya start_brahma.bat)
```

1. Startup par UI + mic + AI connect hota hai
2. "Karen, ..." bolo — wake word detect hota hai
3. Command routing hone ke baad `actions/` ka sahi tool chalta hai
4. Reply Edge TTS se bola jata hai aur chat feed me dikhta hai
5. Har baat memory me save hoti hai taaki aage context milta rahe

## 6. Setup (quick)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install          # browser automation ke liye
```

`config/api_keys.json` me **Gemini API key** (zaroori) aur **OpenRouter key** (fallback) daalo.
`start_brahma.bat` / `start_brahma.vbs` se launch karo.

## 7. Naam change ki note

- Ab har jagah assistant ka naam **"Karen"** hai (UI, wake word, prompts, logs, launcher, dashboard, docs).
- **Internal technical names** (class `BrahmaUI`, package `brahma_connect`, mDNS `_BRAHMA._tcp.local.`,
  AES salt `BRAHMA-DASHBOARD-v1`, asset files `Brahma_Lite_Logo.*`) **isliye wahi rakhe** gaye taaki
  app, pairing aur Android companion toot na jaye — ye user ko na dikhne wale internal identifiers hain.
- **"Brahma Connect"** naam separate mobile companion app ka hai, isliye wahi hai.
- `extra/` folder me legacy backup files (purani `ui.py` copies, rename scripts) abhi bhi old name se hain —
  ye app me chalti nahi, chaaho to delete kar do.