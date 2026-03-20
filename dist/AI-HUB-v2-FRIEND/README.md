# AI-HUB v2

A desktop productivity system built on AutoHotkey v2 that integrates clipboard management, AI chat, hotkeys/hotstrings, and web-based UIs into a single unified hub.

## What It Does

**Clipboard Manager** — 20 hotkey slots, pin/tag/search, aggregate copy mode (rapid successive copies auto-stack into one), history with move/reorder, inline editing. Both native AHK GUI and a rich HTML two-pane interface.

**AI Chat** — Claude and OpenAI integration with system prompt management, conversation history, and one-key "smart fix" (select text → Ctrl+Space → grammar/spelling/coherence fix pasted back).

**Prompt Picker** — HTML-based prompt library with categories, tags, and hotkey assignment. Pick a prompt, select text, fire the hotkey — AI processes it and pastes the result.

**Research Links** — Categorized bookmark manager with quick-launch, served as a web UI.

**Hotkeys & Hotstrings** — Full engine with categories, live editing, import/export, and a visual manager.

**BetterTTS** — Text-to-speech tools including OCR reader, voice search, and screen highlighting.

## Architecture

```
AI-HUB.ahk                    ← Entry point (loads everything)
├── hub_core.ahk               ← Core GUI, hotkeys, AI chat (~2400 lines)
├── modules/
│   ├── manifest.ahk           ← Module loader
│   ├── utilities_tab.ahk      ← Settings & utilities tab
│   ├── quick_prompt.ahk       ← AI prompt processing
│   ├── research_links.ahk     ← Research links integration
│   ├── hotkey_menu.ahk        ← Hotkey management
│   ├── autoclicker.ahk        ← Auto-clicker utility
│   ├── overnight_ops.ahk      ← Scheduled operations
│   └── *.html                 ← Web UIs (clipboard, prompts, links, dashboard)
├── clipboard/
│   ├── Clipboard.ahk          ← Entry point (launched as subprocess)
│   ├── clipboard_core.ahk     ← Data engine (history, pins, tags, aggregate)
│   └── clipboard_gui.ahk      ← Native AHK GUI
├── clipsync-bridge/
│   ├── sync_server.py          ← Python bridge server (localhost:3456)
│   ├── clipsync_bridge.ahk     ← Dynamic hotkey registration + launchers
│   ├── clipboard.html          ← Skinny clipboard UI
│   ├── prompt_picker.html      ← Prompt picker UI
│   ├── research_links.html     ← Research links UI
│   ├── start_bridge.bat        ← Server launcher (visible)
│   └── start_bridge_silent.bat ← Server launcher (minimized, auto-start)
├── BetterTTS/
│   ├── BetterTTS.ahk           ← TTS engine
│   ├── OCRReaderGUI.ahk        ← OCR screen reader
│   ├── VoiceSearchGUI.ahk      ← Voice search
│   └── Highlighter/Rectangles  ← Screen annotation tools
└── config/                     ← User settings (gitignored)
    ├── settings.ini             ← API keys, window position
    ├── prompts.json             ← Saved prompts
    ├── hotkeys.ini              ← Hotkey definitions
    └── hotstrings.sav           ← Hotstring definitions
```

## Data Flow

```
You copy something
    ↓
AHK clipboard_core.ahk captures it (OnClipboardChange)
    ↓
Python sync_server.py also captures it → saves to data/clips.json
    ↓
HTML clipboard polls GET /api/clips every 2s → sees new clip → renders it
    ↓
You pin/tag/edit in HTML → PUT /api/clips/:id → server updates JSON
```

The Python bridge server on `localhost:3456` is the nervous system. It connects AHK ↔ HTML interfaces ↔ Cloudflare Workers (optional remote sync).

## Global Hotkeys

| Shortcut | Action |
|----------|--------|
| `Ctrl+Alt+G` | Show/Hide AI-HUB GUI |
| `Ctrl+Space` | Smart Fix (select text first) |
| `Ctrl+Alt+Z` | Prompt Menu |
| `Ctrl+Alt+A` | Quick AI Chat with selection |
| `Ctrl+Alt+P` | Open Prompt Picker |
| `Ctrl+Alt+R` | Open Research Links |
| `Ctrl+Alt+L` | Open Research Links (alias) |
| `Ctrl+Alt+B` | Open Bookmarks |
| `Ctrl+Alt+C` | Open Clipboard v2 |
| `Ctrl+Alt+S` | Server Status |
| `Ctrl+Alt+W` | Toggle Always On Top |
| `Ctrl+Shift+V` | Toggle Clipboard Manager |
| `Ctrl+Shift+1-0` | Paste from clipboard slots 1-10 |
| `Ctrl+Alt+1-0` | Paste from clipboard slots 11-20 |
| `Alt+H` | Dictation mic toggle |

## Requirements

- **AutoHotkey v2.0+** — [autohotkey.com](https://www.autohotkey.com/)
- **Python 3.10+** — for the bridge server
- **Microsoft Edge** — used in `--app` mode for HTML UIs (zero chrome, minimal RAM)
- **Windows 10/11** — uses Win32 APIs for clipboard monitoring, dark title bars

## Setup

1. Clone or extract to any directory
2. Copy `config/settings.example.ini` → `config/settings.ini` and add your API keys
3. Run `AI-HUB.ahk` — it loads everything, including the clipboard subprocess and bridge server

The bridge server auto-starts minimized. To verify: hit `Ctrl+Alt+S` for server status.

## Bridge Server API

The Python server on `localhost:3456` exposes:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/clips` | GET/POST | List or create clips |
| `/api/clips/:id` | PUT/DELETE | Update or delete a clip |
| `/api/clips/reorder` | PUT | Reorder clip list |
| `/api/prompts` | GET/POST | List or create prompts |
| `/api/prompts/:id` | PUT/DELETE | Update or delete a prompt |
| `/api/bookmarks` | GET/POST | List or create bookmarks |
| `/api/bookmarks/:id` | PUT/DELETE | Update or delete a bookmark |
| `/api/hotkeys` | GET | AHK-formatted hotkey map |
| `/api/status` | GET | Health check |

HTML pages served at `/`, `/links`, `/bookmarks`, `/clipboard`, `/clipboard2`.

## License

MIT — do whatever you want with it.

## Author

David Lanzas — [Theophysics Project](https://theophysics.pro) — Moore, Oklahoma
