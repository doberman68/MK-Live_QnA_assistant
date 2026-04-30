# MK-Live Q&A Assistant

A cross-platform desktop app (macOS & Windows) that monitors meeting audio in real time and answers questions using your choice of AI provider.

## Features

- **Auto mode** — Automatically detects when a question is asked and provides an answer
- **Manual mode** — Press a button to analyze the last 30–60 seconds and extract + answer the question
- **Multiple AI providers** — Ollama (local/free), OpenAI GPT, Anthropic Claude, Google Gemini
- **Flexible speech-to-text** — Local Whisper (offline) or OpenAI Whisper API
- **Flexible audio capture** — Microphone, system audio loopback, or both
- **Floating overlay** — Always-on-top window that stays visible during meetings

---

## Architecture

```
frontend/   (Electron)        backend/   (Python + FastAPI)
  main.js ─── spawn ────────► main.py
           ─── REST/WS ──────► /api/...  /ws
  overlay/                    audio/capture.py
  settings/                   stt/  (whisper_local, whisper_api)
                               llm/  (ollama, openai, anthropic, gemini)
                               question_detector.py
                               transcript.py
```

---

## Prerequisites

### All platforms
- [Node.js](https://nodejs.org) 18+
- [Python](https://python.org) 3.11+

### macOS — system audio loopback
To capture audio from Zoom/Teams/Meet, install **BlackHole**:
```bash
brew install blackhole-2ch
```
Then open **Audio MIDI Setup** → create a **Multi-Output Device** combining your speakers + BlackHole 2ch → set it as system output.

In the app Settings, select **BlackHole 2ch** as the loopback device.

### Windows — system audio loopback
No extra software needed. The app uses **WASAPI loopback** automatically. Select the loopback device in Settings.

### Local LLM (optional)
Install and run [Ollama](https://ollama.com), then pull a model:
```bash
ollama pull llama3
```

---

## Development Setup

### 1. Install Python dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Start the Python backend
```bash
python backend/main.py --port 8765
```

### 3. Install Electron dependencies
```bash
cd frontend
npm install
```

### 4. Launch the Electron app
```bash
cd frontend
npm start
```

---

## Building for Distribution

### macOS
```bash
./build/build-mac.sh
# Output: frontend/dist/MK Live QnA Assistant-*.dmg
```

### Windows
```bat
build\build-win.bat
REM Output: frontend\dist\MK Live QnA Assistant Setup *.exe
```

> **Note:** PyInstaller must be run on the target platform. Build macOS on a Mac, Windows on Windows.

---

## Settings

| Setting | Description |
|---------|-------------|
| Audio source | Mic, system loopback, or both |
| Mic / Loopback device | Select specific audio devices |
| STT Engine | Local Whisper (offline) or OpenAI Whisper API |
| Whisper model size | `tiny` to `large` (larger = more accurate, slower) |
| LLM Provider | Ollama, OpenAI, Anthropic, Gemini |
| API Keys | Required for cloud providers |
| Manual lookback | How many seconds to review on manual trigger (default: 45s) |
| Auto check interval | How often to check for questions in Auto mode (default: 5s) |

---

## REST API (Backend)

| Endpoint | Description |
|----------|-------------|
| `GET /api/status` | App status |
| `GET /api/config` | Current config |
| `POST /api/config` | Save + hot-reload config |
| `GET /api/devices` | List audio devices |
| `GET /api/ollama/models` | List available Ollama models |
| `POST /api/start` | Start audio capture |
| `POST /api/stop` | Stop audio capture |
| `POST /api/trigger` | Manual Q&A trigger |
| `WS /ws` | WebSocket for real-time events |

---

## License

MIT
