"""
ClipSync Bridge Server
======================
The nervous system connecting:
  - HTML interfaces (Prompt Picker, Research Links)
  - AutoHotkey (hotkey registration, clipboard)
  - ClipSync PWA on Cloudflare (remote sync)

Run: python sync_server.py
Serves on: http://localhost:3456

Endpoints:
  GET  /                        → Prompt Picker HTML
  GET  /links                   → Research Links HTML
  GET  /api/prompts             → List all prompts
  POST /api/prompts             → Create prompt
  PUT  /api/prompts/<id>        → Update prompt
  DELETE /api/prompts/<id>      → Delete prompt
  GET  /api/bookmarks           → List all bookmarks
  POST /api/bookmarks           → Create bookmark
  PUT  /api/bookmarks/<id>      → Update bookmark
  DELETE /api/bookmarks/<id>    → Delete bookmark
  GET  /api/clips               → List all clips
  POST /api/clips               → Create clip (or from clipboard monitor)
  DELETE /api/clips/<id>        → Delete clip
  GET  /api/hotkeys             → AHK-formatted hotkey map
  POST /api/sync                → Push/pull with remote ClipSync PWA
  GET  /api/status              → Health check + stats
"""

import json
import os
import uuid
import time
import threading
import sys
import ctypes
import subprocess
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import importlib
from ctypes import wintypes

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

PORT = 3456
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
HTML_DIR = os.path.dirname(os.path.abspath(__file__))
PERSONAL_DASHBOARD_DIR = r"C:\Users\lowes\Desktop\Personal dashboard"
LEGACY_PROMPTS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "prompts.json")
LEGACY_RESEARCH_LINKS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "research_links.json")

# File Vault folders
from pathlib import Path as _Path
_HOME = _Path.home()
FILE_FOLDERS = {
    "documents": str(_HOME / "Documents"),
    "videos": str(_HOME / "Videos"),
    "music": str(_HOME / "Music"),
    "pictures": str(_HOME / "Pictures"),
}

# Remote ClipSync PWA endpoint (set to your Cloudflare worker URL)
REMOTE_API = os.environ.get("CLIPSYNC_REMOTE", "https://clipsync-api.davidokc28.workers.dev")
REMOTE_TOKEN = os.environ.get("CLIPSYNC_TOKEN", "")

# Clipboard monitoring
CLIPBOARD_ENABLED = True
CLIPBOARD_INTERVAL = 1.0  # seconds between checks
CLIPBOARD_MAX_HISTORY = 500

# ---------------------------------------------------------------------------
# AI ENGINE — Claude (manager) + GPT (workhorse)
# ---------------------------------------------------------------------------

import configparser

def _load_ai_config():
    """Read API keys from hub settings.ini"""
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "settings.ini")
    config = configparser.ConfigParser()
    config.read(cfg_path, encoding="utf-8")
    return {
        "openai_key": config.get("Settings", "openaiKey", fallback=""),
        "claude_key": config.get("Settings", "claudeKey", fallback=""),
        "openai_model": config.get("Settings", "openaiModel", fallback="gpt-4o-mini"),
        "claude_model": config.get("Settings", "claudeModel", fallback="claude-sonnet-4-20250514"),
    }

AI_CFG = _load_ai_config()

def _call_openai(prompt, system="You are a helpful clipboard assistant.", max_tokens=1000):
    """Call OpenAI API (workhorse for bulk ops)"""
    key = AI_CFG.get("openai_key", "")
    if not key:
        return {"error": "No OpenAI key in settings.ini"}
    import urllib.request
    body = json.dumps({
        "model": AI_CFG.get("openai_model", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return {"response": data["choices"][0]["message"]["content"]}
    except Exception as e:
        return {"error": str(e)}

def _call_claude(prompt, system="You are a clipboard management AI.", max_tokens=1000):
    """Call Claude API (manager for orchestration)"""
    key = AI_CFG.get("claude_key", "")
    if not key:
        # Fall back to OpenAI if no Claude key
        return _call_openai(prompt, system, max_tokens)
    import urllib.request
    body = json.dumps({
        "model": AI_CFG.get("claude_model", "claude-sonnet-4-20250514"),
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            text = "".join(b.get("text", "") for b in data.get("content", []))
            return {"response": text}
    except Exception as e:
        return {"error": str(e)}

def ai_dedupe(store_ref):
    """Remove exact duplicate clips, keep first occurrence. Preserves pinned/slotted."""
    seen = set()
    dupes = []
    keep = []
    for c in store_ref.clips:
        key = (c.get("content") or "").strip()
        if not key:
            dupes.append(c["id"])
            continue
        if key in seen and not c.get("pinned") and not c.get("slot"):
            dupes.append(c["id"])
        else:
            seen.add(key)
            keep.append(c)
    if not dupes:
        return {"message": "No duplicates found.", "removed": 0}
    store_ref.clips = keep
    store_ref.save_clips()
    return {"message": f"Removed {len(dupes)} duplicate clips.", "removed": len(dupes), "remaining": len(keep), "reloaded": True}

def ai_summarize(store_ref):
    """Use GPT to summarize the last 50 clips into a digest."""
    recent = store_ref.clips[:50]
    if not recent:
        return {"message": "No clips to summarize."}
    clip_text = "\n---\n".join([f"[{i+1}] {(c.get('content',''))[:200]}" for i, c in enumerate(recent)])
    prompt = f"Summarize these {len(recent)} clipboard entries into a brief digest. Group related items. Be concise.\n\n{clip_text}"
    result = _call_openai(prompt, system="You are a clipboard analyst. Summarize clipboard history concisely.", max_tokens=500)
    return {"message": result.get("response", result.get("error", "Failed"))}

def ai_categorize(store_ref):
    """Use GPT to auto-tag the most recent untagged clips."""
    untagged = [c for c in store_ref.clips[:100] if not c.get("tags")]
    if not untagged:
        return {"message": "All recent clips already tagged."}
    batch = untagged[:20]  # Process 20 at a time
    clip_text = "\n".join([f"ID:{c['id']}|{(c.get('content',''))[:150]}" for c in batch])
    prompt = f"""Tag each clipboard entry with 1-2 short category tags. Respond ONLY with JSON array like:
[{{"id":"xxx","tags":["code","python"]}}, ...]
No markdown, no explanation.

Entries:
{clip_text}"""
    result = _call_openai(prompt, system="You tag clipboard entries. Return only JSON.", max_tokens=800)
    resp = result.get("response", "")
    try:
        # Strip markdown fences if present
        clean = resp.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        tags_data = json.loads(clean.strip())
        updated = 0
        id_map = {c["id"]: c for c in store_ref.clips}
        for item in tags_data:
            cid = item.get("id")
            tags = item.get("tags", [])
            if cid in id_map and tags:
                id_map[cid]["tags"] = tags
                updated += 1
        if updated:
            store_ref.save_clips()
        return {"message": f"Tagged {updated} clips.", "updated": updated, "reloaded": True}
    except Exception as e:
        return {"message": f"Categorize failed: {str(e)}. Raw: {resp[:200]}"}

def ai_archive(store_ref):
    """Placeholder for R2 archive — will be wired when R2 is configured."""
    return {"message": "Archive to R2 not yet configured. Add CLOUDFLARE_R2_* env vars to enable."}

def ai_chat(store_ref, message, clip_count):
    """Free-form chat about clips. Claude manages, GPT does heavy lifting."""
    # Give context about the clip store
    recent_preview = "\n".join([f"- {(c.get('content',''))[:80]}" for c in store_ref.clips[:10]])
    system = f"""You are the AI assistant for POF 2828's clipboard manager.
The user has {clip_count} clips stored. Here are the 10 most recent:
{recent_preview}

You can help find clips, suggest organization, answer questions about stored content.
Be concise and direct."""
    result = _call_openai(message, system=system, max_tokens=500)
    return {"response": result.get("response", result.get("error", "Failed"))}



def _find_window_by_title_fragment(fragment):
    fragment = (fragment or "").strip().lower()
    if not fragment:
        return None

    user32 = ctypes.windll.user32
    matches = []
    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value
        if fragment in title.lower():
            matches.append((hwnd, title))
        return True

    user32.EnumWindows(enum_proc(callback), 0)
    return matches[0] if matches else None


def set_window_topmost(title_fragment, pinned):
    found = _find_window_by_title_fragment(title_fragment)
    if not found:
        return {"ok": False, "message": f"Window not found: {title_fragment}"}

    hwnd, title = found
    user32 = ctypes.windll.user32

    # Find the top-level window — Chrome nests content in child frames
    # Use GA_ROOTOWNER to get the real top-level owner window
    root = hwnd
    for _ in range(10):
        parent = user32.GetParent(root)
        if not parent:
            break
        root = parent
    if root:
        hwnd = root

    # Try SetWindowPos with HWND_TOPMOST / HWND_NOTOPMOST
    SWP_NOMOVE    = 0x0002
    SWP_NOSIZE    = 0x0001
    HWND_TOPMOST  = ctypes.c_void_p(-1)
    HWND_NOTOPMOST = ctypes.c_void_p(-2)
    target = HWND_TOPMOST if pinned else HWND_NOTOPMOST

    user32.SetForegroundWindow(hwnd)
    import time; time.sleep(0.05)
    ok = user32.SetWindowPos(hwnd, target, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)

    # Fallback: use AHK subprocess for stubborn Chrome windows
    if not ok:
        import subprocess, os
        ahk_script = f"""
#Requires AutoHotkey v2.0+
WinSetAlwaysOnTop({"1" if pinned else "0"}, "ahk_id {hwnd}")
ExitApp()
"""
        tmp = os.path.join(os.environ.get("TEMP","C:\\Temp"), "pin_window.ahk")
        with open(tmp, "w") as f:
            f.write(ahk_script)
        result = subprocess.run(
            [r"C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe", tmp],
            timeout=3, capture_output=True
        )
        ok = result.returncode == 0

    return {"ok": bool(ok), "title": title, "pinned": bool(pinned)}


def move_window(title_fragment, x, y, w=None, h=None):
    found = _find_window_by_title_fragment(title_fragment)
    if not found:
        return {"ok": False, "message": f"Window not found: {title_fragment}"}

    hwnd, title = found
    user32 = ctypes.windll.user32
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    width = int(w if w is not None else rect.right - rect.left)
    height = int(h if h is not None else rect.bottom - rect.top)
    ok = user32.MoveWindow(hwnd, int(x), int(y), width, height, True)
    return {"ok": bool(ok), "title": title, "x": int(x), "y": int(y), "w": width, "h": height}

# ---------------------------------------------------------------------------
# DATA STORE (in-memory + JSON file persistence)
# ---------------------------------------------------------------------------

class DataStore:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.prompts = self._load("prompts.json", [])
        self.bookmarks = self._load("bookmarks.json", [])
        self.clips = self._load("clips.json", [])
        self.window_state = self._load("window_state.json", {})
        self._lock = threading.Lock()
        self._import_legacy_slash_prompts()
        self._import_legacy_research_links()
        self.sync_legacy_slash_prompts()
        self.sync_legacy_research_links()

    def _load(self, filename, default):
        path = os.path.join(self.data_dir, filename)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return default
        return default

    def _save(self, filename, data):
        path = os.path.join(self.data_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def save_prompts(self):
        with self._lock:
            self._save("prompts.json", self.prompts)

    def _load_legacy_slash_prompts(self):
        if not os.path.exists(LEGACY_PROMPTS_FILE):
            return []
        try:
            with open(LEGACY_PROMPTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

        results = []
        for item in data if isinstance(data, list) else []:
            name = (item.get("name") or "").strip()
            template = item.get("template", "")
            if not name or not template:
                continue
            if not name.startswith("/"):
                name = "/" + name.lstrip("/")
            results.append({
                "id": f"legacy_{item.get('shortcut') or name.lower().strip('/').replace(' ', '_')}",
                "name": name,
                "category": "General",
                "content": template,
                "hotkey": None,
                "tags": item.get("tags", []),
                "description": template[:80],
                "meta": {"slash": True, "source": "legacy-ahk"},
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
        return results

    def _is_slash_prompt(self, prompt):
        name = (prompt.get("name") or "").strip()
        meta = prompt.get("meta") or {}
        return name.startswith("/") or bool(meta.get("slash"))

    def _import_legacy_slash_prompts(self):
        legacy_prompts = self._load_legacy_slash_prompts()
        if not legacy_prompts:
            return

        existing = {
            (p.get("name", "").strip().lower(), (p.get("content") or "").strip())
            for p in self.prompts
        }
        changed = False
        for prompt in legacy_prompts:
            key = (prompt["name"].strip().lower(), prompt["content"].strip())
            if key in existing:
                continue
            self.prompts.append(prompt)
            existing.add(key)
            changed = True
        if changed:
            self.save_prompts()

    def sync_legacy_slash_prompts(self):
        slash_prompts = []
        for prompt in self.prompts:
            if not self._is_slash_prompt(prompt):
                continue
            name = (prompt.get("name") or "").strip()
            shortcut = name.lstrip("/").lower()
            if not shortcut:
                continue
            slash_prompts.append({
                "name": "/" + shortcut,
                "template": prompt.get("content", ""),
                "shortcut": shortcut,
                "replace": True,
                "popup": False,
            })
        try:
            os.makedirs(os.path.dirname(LEGACY_PROMPTS_FILE), exist_ok=True)
            with open(LEGACY_PROMPTS_FILE, "w", encoding="utf-8") as f:
                json.dump(slash_prompts, f, indent=2, ensure_ascii=False)
        except IOError:
            pass

    def save_bookmarks(self):
        with self._lock:
            self._save("bookmarks.json", self.bookmarks)

    def _load_legacy_research_links(self):
        if not os.path.exists(LEGACY_RESEARCH_LINKS_FILE):
            return []
        try:
            with open(LEGACY_RESEARCH_LINKS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

        results = []
        for item in data if isinstance(data, list) else []:
            title = (item.get("name") or "").strip()
            url = (item.get("url") or "").strip()
            if not title or not url:
                continue
            tags = item.get("tags", "")
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            elif not isinstance(tags, list):
                tags = []
            results.append({
                "id": f"legacy_{uuid.uuid5(uuid.NAMESPACE_URL, url).hex[:8]}",
                "title": title,
                "url": url,
                "category": item.get("category", "General"),
                "tags": tags,
                "created_at": item.get("added") or datetime.now(timezone.utc).isoformat(),
            })
        return results

    def _import_legacy_research_links(self):
        legacy_links = self._load_legacy_research_links()
        if not legacy_links:
            return
        existing_urls = {(b.get("url") or "").strip().lower() for b in self.bookmarks}
        changed = False
        for bookmark in legacy_links:
            key = (bookmark.get("url") or "").strip().lower()
            if not key or key in existing_urls:
                continue
            self.bookmarks.append(bookmark)
            existing_urls.add(key)
            changed = True
        if changed:
            self.save_bookmarks()

    def sync_legacy_research_links(self):
        legacy_links = []
        for bookmark in self.bookmarks:
            tags = bookmark.get("tags", [])
            if isinstance(tags, list):
                tags_str = ", ".join(str(t) for t in tags if str(t).strip())
            else:
                tags_str = str(tags or "")
            legacy_links.append({
                "category": bookmark.get("category", "General"),
                "name": bookmark.get("title", "Untitled"),
                "url": bookmark.get("url", ""),
                "notes": bookmark.get("description", ""),
                "tags": tags_str,
                "added": bookmark.get("created_at", ""),
            })
        try:
            os.makedirs(os.path.dirname(LEGACY_RESEARCH_LINKS_FILE), exist_ok=True)
            with open(LEGACY_RESEARCH_LINKS_FILE, "w", encoding="utf-8") as f:
                json.dump(legacy_links, f, indent=2, ensure_ascii=False)
        except IOError:
            pass

    def save_clips(self):
        with self._lock:
            self._save("clips.json", self.clips)

    def save_window_state(self):
        with self._lock:
            self._save("window_state.json", self.window_state)

    # -- Prompts --
    def get_prompts(self, category=None, tag=None):
        results = self.prompts
        if category:
            results = [p for p in results if p.get("category", "").lower() == category.lower()]
        if tag:
            results = [p for p in results if tag.lower() in [t.lower() for t in p.get("tags", [])]]
        return results

    def create_prompt(self, data):
        now = datetime.now(timezone.utc).isoformat()
        prompt = {
            "id": data.get("id", f"p{uuid.uuid4().hex[:8]}"),
            "name": data.get("name", "Untitled"),
            "category": data.get("category", "General"),
            "content": data.get("content", ""),
            "hotkey": data.get("hotkey", None),
            "tags": data.get("tags", []),
            "description": data.get("description", ""),
            "meta": data.get("meta", {}),
            "created_at": data.get("created_at", now),
            "updated_at": now,
        }
        self.prompts.append(prompt)
        self.save_prompts()
        self.sync_legacy_slash_prompts()
        return prompt

    def update_prompt(self, prompt_id, data):
        for i, p in enumerate(self.prompts):
            if p["id"] == prompt_id:
                for key in ("name", "category", "content", "hotkey", "tags", "description", "meta"):
                    if key in data:
                        self.prompts[i][key] = data[key]
                self.prompts[i]["updated_at"] = datetime.now(timezone.utc).isoformat()
                self.save_prompts()
                self.sync_legacy_slash_prompts()
                return self.prompts[i]
        return None

    def delete_prompt(self, prompt_id):
        before = len(self.prompts)
        self.prompts = [p for p in self.prompts if p["id"] != prompt_id]
        if len(self.prompts) < before:
            self.save_prompts()
            self.sync_legacy_slash_prompts()
            return True
        return False

    # -- Bookmarks --
    def get_bookmarks(self, category=None):
        if category:
            return [b for b in self.bookmarks if b.get("category", "").lower() == category.lower()]
        return self.bookmarks

    def create_bookmark(self, data):
        now = datetime.now(timezone.utc).isoformat()
        bookmark = {
            "id": data.get("id", f"b{uuid.uuid4().hex[:8]}"),
            "title": data.get("title", "Untitled"),
            "url": data.get("url", ""),
            "category": data.get("category", "General"),
            "tags": data.get("tags", []),
            "created_at": data.get("created_at", now),
        }
        self.bookmarks.append(bookmark)
        self.save_bookmarks()
        self.sync_legacy_research_links()
        return bookmark

    def update_bookmark(self, bm_id, data):
        for i, b in enumerate(self.bookmarks):
            if b["id"] == bm_id:
                for key in ("title", "url", "category", "tags"):
                    if key in data:
                        self.bookmarks[i][key] = data[key]
                self.save_bookmarks()
                self.sync_legacy_research_links()
                return self.bookmarks[i]
        return None

    def delete_bookmark(self, bm_id):
        before = len(self.bookmarks)
        self.bookmarks = [b for b in self.bookmarks if b["id"] != bm_id]
        if len(self.bookmarks) < before:
            self.save_bookmarks()
            self.sync_legacy_research_links()
            return True
        return False

    # -- Clips --
    def get_clips(self, search=None, limit=50):
        results = self.clips
        if search:
            search_lower = search.lower()
            results = [c for c in results if search_lower in c.get("content", "").lower()
                       or search_lower in c.get("title", "").lower()]
        return results[:limit]

    def create_clip(self, data):
        now = datetime.now(timezone.utc).isoformat()
        content = data.get("content", "")

        # Dedupe: don't save if identical to last clip
        if self.clips and self.clips[0].get("content") == content:
            return None

        clip = {
            "id": data.get("id", f"c{uuid.uuid4().hex[:8]}"),
            "title": data.get("title", content[:60].strip()),
            "content": content,
            "source": data.get("source", "manual"),
            "tags": data.get("tags", []),
            "pinned": data.get("pinned", False),
            "slot": data.get("slot", None),
            "created_at": now,
        }
        self.clips.insert(0, clip)  # newest first

        # Enforce max history
        if len(self.clips) > CLIPBOARD_MAX_HISTORY:
            self.clips = self.clips[:CLIPBOARD_MAX_HISTORY]

        self.save_clips()
        return clip

    def update_clip(self, clip_id, data):
        for i, c in enumerate(self.clips):
            if c["id"] == clip_id:
                for key in ("content", "title", "tags", "pinned", "slot", "source"):
                    if key in data:
                        self.clips[i][key] = data[key]
                if self.clips[i].get("pinned"):
                    clip = self.clips.pop(i)
                    self.clips.insert(0, clip)
                self.save_clips()
                return next((clip for clip in self.clips if clip["id"] == clip_id), None)
        return None

    def reorder_clips(self, ordered_ids):
        """Reorder clips to match the given list of IDs."""
        id_map = {c["id"]: c for c in self.clips}
        reordered = [id_map[cid] for cid in ordered_ids if cid in id_map]
        # Append any clips not in the order list (shouldn't happen, but safe)
        seen = set(ordered_ids)
        for c in self.clips:
            if c["id"] not in seen:
                reordered.append(c)
        self.clips = reordered
        self.save_clips()

    def delete_clip(self, clip_id):
        before = len(self.clips)
        self.clips = [c for c in self.clips if c["id"] != clip_id]
        if len(self.clips) < before:
            self.save_clips()
            return True
        return False

    # -- Hotkeys (for AHK) --
    def get_hotkeys(self):
        """Returns only prompts that have a hotkey assigned, formatted for AHK."""
        return [
            {"id": p["id"], "name": p["name"], "hotkey": p["hotkey"], "content": p["content"]}
            for p in self.prompts if p.get("hotkey")
        ]


# ---------------------------------------------------------------------------
# CLIPBOARD MONITOR (Windows only, graceful fallback)
# ---------------------------------------------------------------------------

class ClipboardMonitor:
    def __init__(self, store, interval=1.0):
        self.store = store
        self.interval = interval
        self.last_content = ""
        self.running = False
        self._thread = None
        self._get_clipboard = None

        # Try to prepare Windows clipboard access
        try:
            # Prefer ctypes (zero subprocess overhead) over PowerShell
            import ctypes
            ctypes.windll.user32.OpenClipboard(0)
            ctypes.windll.user32.CloseClipboard()
            self._get_clipboard = self._win32_get_clipboard
            print("[clipboard] Windows clipboard monitor ready (ctypes mode)")
        except Exception:
            try:
                import subprocess
                # Try xclip on Linux (for testing)
                self._get_clipboard = self._xclip_get_clipboard
                print("[clipboard] xclip clipboard monitor ready")
            except Exception:
                print("[clipboard] No clipboard access available — monitor disabled")

    def _win32_get_clipboard(self):
        """Read clipboard using ctypes (Windows, no dependencies)."""
        import ctypes
        import ctypes.wintypes as wt
        CF_UNICODETEXT = 13
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # Fix 64-bit pointer truncation: declare proper return/arg types
        user32.GetClipboardData.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]

        if not user32.OpenClipboard(0):
            return None
        try:
            h = user32.GetClipboardData(CF_UNICODETEXT)
            if not h:
                return None
            ptr = kernel32.GlobalLock(h)
            if not ptr:
                return None
            try:
                return ctypes.wstring_at(ptr)
            finally:
                kernel32.GlobalUnlock(h)
        finally:
            user32.CloseClipboard()

    def _powershell_get_clipboard(self):
        """Fallback clipboard read through PowerShell for stubborn Windows cases."""
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode != 0:
                return None
            return result.stdout
        except Exception:
            return None

    def _xclip_get_clipboard(self):
        """Fallback for Linux testing."""
        import subprocess
        try:
            result = subprocess.run(["xclip", "-selection", "clipboard", "-o"],
                                    capture_output=True, text=True, timeout=2)
            return result.stdout if result.returncode == 0 else None
        except Exception:
            return None

    def start(self):
        if not self._get_clipboard:
            return
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    def _loop(self):
        while self.running:
            try:
                content = self._get_clipboard() if self._get_clipboard else None
                if content and content != self.last_content and len(content.strip()) > 0:
                    self.last_content = content
                    self.store.create_clip({
                        "content": content,
                        "source": "clipboard",
                    })
            except Exception as e:
                pass  # Silently continue — clipboard access can be flaky
            time.sleep(self.interval)


# ---------------------------------------------------------------------------
# HTTP SERVER
# ---------------------------------------------------------------------------

store = DataStore(DATA_DIR)

class BridgeHandler(SimpleHTTPRequestHandler):
    """Single-file HTTP handler for the bridge API + HTML serving."""

    def log_message(self, format, *args):
        # Quieter logging — only show API calls, not static file serves
        msg = format % args
        if "/api/" in msg:
            print(f"[api] {msg}")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # --- HTML pages ---
        # Lookup order: PERSONAL_DASHBOARD_DIR (if exists) → modules/ → clipsync-bridge/
        MODULES_DIR = os.path.join(os.path.dirname(HTML_DIR), "modules")

        if path == "/" or path == "/prompts":
            return self._serve_html("prompt_picker.html", MODULES_DIR)
        if path == "/links" or path == "/bookmarks":
            return self._serve_html("research_links.html", MODULES_DIR)
        if path in ("/clipboard", "/clipboard2", "/clipboard3"):
            return self._serve_html("clipboard3.html", MODULES_DIR)
        if path == "/calendar" or path == "/tasks":
            return self._serve_html("task-calendar.html", MODULES_DIR)
        if path == "/dashboard" or path == "/nexus":
            return self._serve_html("nexus-dashboard.html", MODULES_DIR)

        # --- API ---
        if path == "/api/prompts":
            category = params.get("category", [None])[0]
            tag = params.get("tag", [None])[0]
            return self._json_response(store.get_prompts(category, tag))

        if path == "/api/bookmarks":
            category = params.get("category", [None])[0]
            return self._json_response(store.get_bookmarks(category))

        if path == "/api/clips":
            search = params.get("search", [None])[0]
            limit = int(params.get("limit", [50])[0])
            return self._json_response(store.get_clips(search, limit))

        if path == "/api/hotkeys":
            return self._json_response(store.get_hotkeys())

        if path == "/api/status":
            return self._json_response({
                "status": "running",
                "prompts": len(store.prompts),
                "bookmarks": len(store.bookmarks),
                "clips": len(store.clips),
                "hotkeys": len(store.get_hotkeys()),
                "remote": REMOTE_API,
                "clipboard_monitor": CLIPBOARD_ENABLED,
            })

        if path == "/api/window-state":
            return self._json_response(store.window_state)

        # --- File Vault ---
        if path.startswith("/api/files/"):
            folder_key = path.split("/")[-1]
            folder_path = FILE_FOLDERS.get(folder_key)
            if not folder_path or not os.path.isdir(folder_path):
                return self._json_response({"error": f"folder '{folder_key}' not found"}, 404)
            try:
                entries = []
                for name in os.listdir(folder_path):
                    fp = os.path.join(folder_path, name)
                    if os.path.isfile(fp) and not name.startswith('.'):
                        st = os.stat(fp)
                        entries.append({"name": name, "path": fp, "size": st.st_size, "modified": datetime.fromtimestamp(st.st_mtime).isoformat()})
                entries.sort(key=lambda e: e["modified"], reverse=True)
                return self._json_response(entries[:100])
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        # --- Static files (CSS, JS, images) ---
        if path.startswith("/data/"):
            return self._serve_file(path.lstrip("/"))

        # Fallback
        self.send_error(404, f"Not found: {path}")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_body()

        if path == "/api/prompts":
            result = store.create_prompt(body)
            return self._json_response(result, 201)

        if path == "/api/bookmarks":
            result = store.create_bookmark(body)
            return self._json_response(result, 201)

        if path == "/api/clips":
            result = store.create_clip(body)
            return self._json_response(result or {"status": "duplicate"}, 201 if result else 200)


        # --- AI Endpoints ---
        if path.startswith("/api/ai/"):
            action = path.split("/")[-1]
            if action == "dedupe":
                return self._json_response(ai_dedupe(store))
            if action == "summarize":
                return self._json_response(ai_summarize(store))
            if action == "categorize":
                return self._json_response(ai_categorize(store))
            if action == "archive":
                return self._json_response(ai_archive(store))
            if action == "chat":
                msg = body.get("message", "")
                cc = body.get("clip_count", len(store.clips))
                return self._json_response(ai_chat(store, msg, cc))
            return self._json_response({"error": f"Unknown AI action: {action}"}, 400)
        if path == "/api/files/open":
            file_path = body.get("path", "")
            if not file_path or not os.path.exists(file_path):
                return self._json_response({"error": "file not found"}, 404)
            resolved = os.path.realpath(file_path)
            allowed = any(resolved.startswith(os.path.realpath(fp)) for fp in FILE_FOLDERS.values())
            if not allowed:
                return self._json_response({"error": "path not in allowed folders"}, 403)
            try:
                os.startfile(resolved)
                return self._json_response({"ok": True, "opened": resolved})
            except Exception as e:
                return self._json_response({"error": str(e)}, 500)

        if path == "/api/sync":
            return self._handle_sync(body)

        if path == "/window/pin":
            title = body.get("title", "Clipboard")
            pinned = bool(body.get("pinned", False))
            result = set_window_topmost(title, pinned)
            if result.get("ok"):
                store.window_state["pin"] = {
                    "title": title,
                    "pinned": pinned,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                store.save_window_state()
            return self._json_response(result, 200 if result.get("ok") else 404)

        if path == "/window/position":
            title = body.get("title", "Clipboard")
            x = body.get("x")
            y = body.get("y")
            if x is None or y is None:
                return self.send_error(400, "Missing x/y")
            result = move_window(title, x, y, body.get("w"), body.get("h"))
            if result.get("ok"):
                store.window_state["position"] = {
                    "title": title,
                    "x": int(x),
                    "y": int(y),
                    "w": result["w"],
                    "h": result["h"],
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                store.save_window_state()
            return self._json_response(result, 200 if result.get("ok") else 404)

        self.send_error(404, f"Not found: {path}")

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_body()

        # /api/prompts/<id>
        if path.startswith("/api/prompts/"):
            item_id = path.split("/")[-1]
            result = store.update_prompt(item_id, body)
            if result:
                return self._json_response(result)
            return self.send_error(404, "Prompt not found")

        if path.startswith("/api/bookmarks/"):
            item_id = path.split("/")[-1]
            result = store.update_bookmark(item_id, body)
            if result:
                return self._json_response(result)
            return self.send_error(404, "Bookmark not found")

        if path.startswith("/api/clips/"):
            item_id = path.split("/")[-1]
            result = store.update_clip(item_id, body)
            if result:
                return self._json_response(result)
            return self.send_error(404, "Clip not found")

        if path == "/api/clips/reorder":
            ids = body.get("ids", [])
            if ids:
                store.reorder_clips(ids)
                return self._json_response({"status": "reordered"})
            return self.send_error(400, "Missing ids")

        self.send_error(404, f"Not found: {path}")

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/prompts/"):
            item_id = path.split("/")[-1]
            if store.delete_prompt(item_id):
                return self._json_response({"deleted": item_id})
            return self.send_error(404, "Prompt not found")

        if path.startswith("/api/bookmarks/"):
            item_id = path.split("/")[-1]
            if store.delete_bookmark(item_id):
                return self._json_response({"deleted": item_id})
            return self.send_error(404, "Bookmark not found")

        if path.startswith("/api/clips/"):
            item_id = path.split("/")[-1]
            if store.delete_clip(item_id):
                return self._json_response({"deleted": item_id})
            return self.send_error(404, "Clip not found")

        self.send_error(404, f"Not found: {path}")

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(204)
        self._add_cors_headers()
        self.end_headers()

    # --- Helpers ---

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _json_response(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._add_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _serve_html(self, filename, modules_dir):
        """Serve an HTML file, checking: PERSONAL_DASHBOARD_DIR → modules/ → clipsync-bridge/"""
        for folder in [PERSONAL_DASHBOARD_DIR, modules_dir, HTML_DIR]:
            candidate = os.path.join(folder, filename)
            if os.path.exists(candidate):
                return self._serve_file_abs(candidate)
        return self.send_error(404, f"{filename} not found")

    def _serve_file(self, filename):
        filepath = os.path.join(HTML_DIR, filename)
        if not os.path.exists(filepath):
            return self.send_error(404, f"File not found: {filename}")
        return self._serve_file_abs(filepath)

    def _serve_file_abs(self, filepath):
        """Serve an HTML file from an absolute path."""
        if not os.path.exists(filepath):
            return self.send_error(404, f"File not found: {filepath}")

        with open(filepath, "rb") as f:
            content = f.read()

        ext = filepath.rsplit(".", 1)[-1].lower()
        content_types = {
            "html": "text/html", "css": "text/css", "js": "application/javascript",
            "json": "application/json", "png": "image/png", "svg": "image/svg+xml",
        }
        ct = content_types.get(ext, "application/octet-stream")

        self.send_response(200)
        self.send_header("Content-Type", f"{ct}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self._add_cors_headers()
        self.end_headers()
        self.wfile.write(content)

    def _add_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _handle_sync(self, body):
        """Sync local data with remote ClipSync PWA."""
        if not REMOTE_API:
            return self._json_response({
                "status": "error",
                "message": "CLIPSYNC_REMOTE env var not set"
            }, 400)

        direction = body.get("direction", "push")  # push, pull, or both
        types = body.get("types", ["clips", "prompts", "bookmarks"])

        results = {}
        try:
            import urllib.request

            headers = {
                "Content-Type": "application/json",
                "User-Agent": "ClipSync-Bridge/1.0",
            }
            if REMOTE_TOKEN:
                headers["Authorization"] = f"Bearer {REMOTE_TOKEN}"

            if "push" in direction or direction == "both":
                # Push local data to remote (individual POSTs)
                for dtype in types:
                    local_data = getattr(store, dtype, [])
                    pushed, errors = 0, 0
                    for item in local_data:
                        try:
                            # Transform to worker format per type
                            if dtype == "prompts":
                                payload = {
                                    "title": item.get("name", ""),
                                    "content": item.get("content", ""),
                                    "folder": "prompts",
                                    "tags": item.get("tags", ["prompt"]),
                                    "template": item.get("content", ""),
                                    "shortcut": item.get("hotkey", ""),
                                }
                            elif dtype == "clips":
                                payload = {
                                    "title": (item.get("title") or item.get("content", ""))[:80],
                                    "content": item.get("content", ""),
                                    "type": "clip",
                                    "folder": "clips",
                                    "tags": item.get("tags", ["clipboard"]),
                                }
                            else:
                                payload = item
                            # Clips go to /api/items; others to /api/{type}
                            endpoint = "items" if dtype == "clips" else dtype
                            req = urllib.request.Request(
                                f"{REMOTE_API}/api/{endpoint}",
                                data=json.dumps(payload).encode("utf-8"),
                                headers=headers,
                                method="POST",
                            )
                            with urllib.request.urlopen(req, timeout=10) as resp:
                                resp.read()
                            pushed += 1
                        except Exception:
                            errors += 1
                    results[f"push_{dtype}"] = {"pushed": pushed, "errors": errors}

            if "pull" in direction or direction == "both":
                # Pull remote data to local
                for dtype in types:
                    req = urllib.request.Request(
                        f"{REMOTE_API}/api/{dtype}",
                        headers=headers,
                    )
                    try:
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            raw = json.loads(resp.read())
                            # Worker returns {"items":[...]} or bare array
                            remote_data = raw.get("items", raw) if isinstance(raw, dict) else raw
                            results[f"pull_{dtype}"] = {"count": len(remote_data)}
                            # Merge: remote items not in local get added
                            local_ids = {item.get("id", "") for item in getattr(store, dtype, [])}
                            new_items = [item for item in remote_data if item.get("id", "") not in local_ids]
                            if new_items:
                                getattr(store, dtype).extend(new_items)
                                getattr(store, f"save_{dtype}")()
                                results[f"pull_{dtype}"]["new"] = len(new_items)
                    except Exception as e:
                        results[f"pull_{dtype}"] = {"error": str(e)}

            return self._json_response({"status": "ok", "results": results})

        except Exception as e:
            return self._json_response({"status": "error", "message": str(e)}, 500)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  ClipSync Bridge Server")
    print("=" * 60)
    print(f"  Local:      http://localhost:{PORT}")
    print(f"  Prompts:    http://localhost:{PORT}/")
    print(f"  Links:      http://localhost:{PORT}/links")
    print(f"  Clipboard:  http://localhost:{PORT}/clipboard")
    print(f"  API:        http://localhost:{PORT}/api/status")
    print(f"  Remote:     {REMOTE_API}")
    print(f"  Data dir:   {DATA_DIR}")
    print(f"  Prompts:    {len(store.prompts)} loaded")
    print(f"  Bookmarks:  {len(store.bookmarks)} loaded")
    print(f"  Clips:      {len(store.clips)} loaded")
    print(f"  Hotkeys:    {len(store.get_hotkeys())} registered")
    print("=" * 60)

    # Start clipboard monitor
    if CLIPBOARD_ENABLED:
        monitor = ClipboardMonitor(store, CLIPBOARD_INTERVAL)
        monitor.start()
        print("[clipboard] Monitor started")

    # Start auto-sync to Cloudflare (every 5 minutes)
    if REMOTE_API:
        import threading, urllib.request as _urllib_req

        # Persist synced IDs to file so we don't re-push after restart
        SYNC_STATE_FILE = os.path.join(DATA_DIR, "sync_state.json")

        def _load_sync_state():
            """Load set of already-synced IDs from disk."""
            try:
                with open(SYNC_STATE_FILE, "r") as f:
                    data = json.load(f)
                return {
                    "bookmarks": set(data.get("bookmarks", [])),
                    "prompts": set(data.get("prompts", [])),
                    "clips": set(data.get("clips", [])),
                }
            except (FileNotFoundError, json.JSONDecodeError):
                return {"bookmarks": set(), "prompts": set(), "clips": set()}

        def _save_sync_state(state):
            """Persist synced IDs to disk."""
            try:
                with open(SYNC_STATE_FILE, "w") as f:
                    json.dump({k: list(v) for k, v in state.items()}, f)
            except IOError:
                pass

        def _auto_sync_loop():
            """Push local bookmarks, prompts, and clips to Cloudflare every 5 minutes.
            Only pushes items whose local ID hasn't been synced yet (persisted across restarts)."""
            import time as _time
            SYNC_INTERVAL = 300  # seconds
            synced = _load_sync_state()
            _time.sleep(10)  # initial delay to let server fully start
            while True:
                try:
                    headers = {
                        "Content-Type": "application/json",
                        "User-Agent": "ClipSync-Bridge/1.0",
                    }
                    if REMOTE_TOKEN:
                        headers["Authorization"] = f"Bearer {REMOTE_TOKEN}"

                    changed = False

                    for dtype in ("bookmarks", "prompts"):
                        local_data = getattr(store, dtype, [])
                        new_items = [i for i in local_data if i.get("id", "") not in synced[dtype]]
                        pushed = 0
                        for item in new_items:
                            try:
                                if dtype == "prompts":
                                    payload = {
                                        "title": item.get("name", ""),
                                        "content": item.get("content", ""),
                                        "folder": "prompts",
                                        "tags": item.get("tags", ["prompt"]),
                                        "template": item.get("content", ""),
                                        "shortcut": item.get("hotkey", ""),
                                    }
                                else:
                                    payload = item
                                req = _urllib_req.Request(
                                    f"{REMOTE_API}/api/{dtype}",
                                    data=json.dumps(payload).encode("utf-8"),
                                    headers=headers,
                                    method="POST",
                                )
                                with _urllib_req.urlopen(req, timeout=10) as resp:
                                    resp.read()
                                synced[dtype].add(item.get("id", ""))
                                pushed += 1
                                changed = True
                            except Exception:
                                pass
                        if new_items:
                            print(f"[auto-sync] Pushed {pushed}/{len(new_items)} new {dtype}")

                    # Sync clipboard history — only push NEW clips since last sync
                    clips = getattr(store, "clips", [])
                    new_clips = [c for c in clips if c.get("id", "") not in synced["clips"]]
                    clip_pushed = 0
                    for clip in new_clips:
                        try:
                            payload = {
                                "title": (clip.get("title") or clip.get("content", ""))[:80],
                                "content": clip.get("content", ""),
                                "type": "clip",
                                "folder": "clips",
                                "tags": clip.get("tags", ["clipboard"]),
                            }
                            req = _urllib_req.Request(
                                f"{REMOTE_API}/api/items",
                                data=json.dumps(payload).encode("utf-8"),
                                headers=headers,
                                method="POST",
                            )
                            with _urllib_req.urlopen(req, timeout=10) as resp:
                                resp.read()
                            synced["clips"].add(clip.get("id", ""))
                            clip_pushed += 1
                            changed = True
                        except Exception:
                            pass
                    if new_clips:
                        print(f"[auto-sync] Pushed {clip_pushed}/{len(new_clips)} new clips")

                    # Save state so we don't re-push after restart
                    if changed:
                        _save_sync_state(synced)

                except Exception as e:
                    print(f"[auto-sync] Error: {e}")
                _time.sleep(SYNC_INTERVAL)

        sync_thread = threading.Thread(target=_auto_sync_loop, daemon=True)
        sync_thread.start()
        print(f"[auto-sync] Background sync to {REMOTE_API} every 5 min")

    # Start HTTP server — suppress noisy ConnectionResetError from polling clients
    class QuietHTTPServer(HTTPServer):
        def handle_error(self, request, client_address):
            import sys
            exc = sys.exc_info()[1]
            if isinstance(exc, ConnectionResetError):
                return  # silently ignore client disconnects
            super().handle_error(request, client_address)

    server = QuietHTTPServer(("127.0.0.1", PORT), BridgeHandler)
    print(f"\n[server] Listening on http://localhost:{PORT}\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
