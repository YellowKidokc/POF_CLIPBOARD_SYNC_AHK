# ClipSync Bridge

Local bridge connecting HTML interfaces, AutoHotkey, and ClipSync PWA.

## Quick Start

### 1. Start the Python server
```
cd clipsync-bridge
python sync_server.py
```
Server starts on http://localhost:3456

### 2. Add AHK module to your AI-HUB
Copy `clipsync_bridge.ahk` to your AI-HUB `modules/` folder.
Add to your manifest.ahk:
```
#include .\clipsync_bridge.ahk
```

### 3. Use it

| Hotkey | Action |
|--------|--------|
| Ctrl+Alt+P | Open Prompt Picker |
| Ctrl+Alt+L | Open Research Links |
| Ctrl+Alt+S | Server status + hotkey list |
| (your custom) | Any prompt with a hotkey assigned |

## Architecture

```
prompt_picker.html ─┐
research_links.html ┤     ┌─ data/prompts.json
AHK hotkeys ────────┼──→  │  data/bookmarks.json
Clipboard monitor ──┤     │  data/clips.json
                    │     └─ ClipSync PWA (remote sync)
              sync_server.py
              localhost:3456
```

- **HTML** = your interface (create, edit, search, copy)
- **Python** = the nervous system (serves HTML, API, clipboard, sync)
- **AHK** = invisible muscle (hotkeys, keyboard shortcuts)
- **JSON files** = the shared truth (both HTML and AHK read/write)
- **Remote PWA** = cloud sync (push/pull with Cloudflare)

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/prompts | List prompts |
| POST | /api/prompts | Create prompt |
| PUT | /api/prompts/:id | Update prompt |
| DELETE | /api/prompts/:id | Delete prompt |
| GET | /api/bookmarks | List bookmarks |
| POST | /api/bookmarks | Create bookmark |
| PUT | /api/bookmarks/:id | Update bookmark |
| DELETE | /api/bookmarks/:id | Delete bookmark |
| GET | /api/clips | List clips |
| POST | /api/clips | Create clip |
| DELETE | /api/clips/:id | Delete clip |
| GET | /api/hotkeys | AHK hotkey map |
| POST | /api/sync | Push/pull with remote PWA |
| GET | /api/status | Health check |

## Remote Sync

Set environment variables before starting:
```
set CLIPSYNC_REMOTE=https://clipsync-api.davidokc28.workers.dev
set CLIPSYNC_TOKEN=your-bearer-token
python sync_server.py
```

Then trigger sync:
```
curl -X POST http://localhost:3456/api/sync -H "Content-Type: application/json" -d "{\"direction\":\"both\"}"
```

## Files

| File | Purpose |
|------|---------|
| sync_server.py | Python bridge server (zero dependencies) |
| prompt_picker.html | Prompt management UI |
| research_links.html | Bookmark/links UI |
| clipsync_bridge.ahk | AHK module for hotkeys |
| data/prompts.json | Prompt storage |
| data/bookmarks.json | Bookmark storage |
| data/clips.json | Clipboard history |

## Notes

- Server uses zero external dependencies (stdlib only)
- Clipboard monitor uses ctypes on Windows (no pip install needed)
- HTML falls back to localStorage if server is offline
- AHK polls server every 30s for hotkey changes
- All data is human-readable JSON — edit by hand if needed
