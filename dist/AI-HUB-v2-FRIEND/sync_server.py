"""
POF 2828 — Clipboard Sync Server (Desktop Tier)
Port 3456 — Lightweight Python backend for clipboard3.html PWA
Features: Clips CRUD, bookmarks, tags, window pin/position
"""
import json, os, sqlite3, threading, uuid, subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from datetime import datetime
from pathlib import Path

PORT = 3456
BASE = Path(__file__).parent
DB_PATH = BASE / "Data" / "clipboard.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── File Vault folders ────────────────────────
HOME = Path.home()
FILE_FOLDERS = {
    "documents": HOME / "Documents",
    "videos": HOME / "Videos",
    "music": HOME / "Music",
    "pictures": HOME / "Pictures",
}

# ── Database ──────────────────────────────────
def get_db():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS clips (
        id TEXT PRIMARY KEY,
        content TEXT NOT NULL DEFAULT '',
        title TEXT DEFAULT '',
        category TEXT DEFAULT 'clipboard',
        pinned INTEGER DEFAULT 0,
        starred INTEGER DEFAULT 0,
        deleted INTEGER DEFAULT 0,
        slot INTEGER,
        tags TEXT DEFAULT '[]',
        fields TEXT DEFAULT '[]',
        categories TEXT DEFAULT '[]',
        ts TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS bookmarks (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        url TEXT NOT NULL,
        description TEXT DEFAULT '',
        category TEXT DEFAULT 'other',
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS tags (
        id TEXT PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        color TEXT DEFAULT '#888'
    );
    """)
    db.commit()
    return db

DB = init_db()
LOCK = threading.Lock()

# Window state (in-memory, persisted to JSON)
WIN_STATE_FILE = BASE / "Data" / "window_state.json"
def load_win_state():
    try: return json.loads(WIN_STATE_FILE.read_text())
    except: return {}
def save_win_state(s):
    WIN_STATE_FILE.write_text(json.dumps(s, indent=2))
WIN_STATE = load_win_state()

# ── Helpers ───────────────────────────────────
def row_to_dict(row):
    if row is None: return None
    d = dict(row)
    for k in ('tags', 'fields', 'categories'):
        if k in d and isinstance(d[k], str):
            try: d[k] = json.loads(d[k])
            except: d[k] = []
    for k in ('pinned', 'starred', 'deleted'):
        if k in d: d[k] = bool(d[k])
    return d

def new_id():
    return f"c_{int(datetime.now().timestamp()*1000)}_{uuid.uuid4().hex[:6]}"

# ── HTTP Handler ──────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass  # quiet

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _no_content(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0: return {}
        return json.loads(self.rfile.read(length))

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        p = self.path.split("?")[0]

        # GET /api/clips
        if p == "/api/clips":
            with LOCK:
                rows = DB.execute("SELECT * FROM clips ORDER BY created_at DESC LIMIT 500").fetchall()
            self._json(200, [row_to_dict(r) for r in rows])

        # GET /api/clips/:id
        elif p.startswith("/api/clips/"):
            cid = p.split("/")[-1]
            with LOCK:
                row = DB.execute("SELECT * FROM clips WHERE id=?", (cid,)).fetchone()
            if row: self._json(200, row_to_dict(row))
            else: self._json(404, {"error": "not found"})

        # GET /api/bookmarks
        elif p == "/api/bookmarks":
            with LOCK:
                rows = DB.execute("SELECT * FROM bookmarks ORDER BY created_at DESC").fetchall()
            self._json(200, [dict(r) for r in rows])

        # GET /api/tags
        elif p == "/api/tags":
            with LOCK:
                rows = DB.execute("SELECT * FROM tags").fetchall()
            self._json(200, [dict(r) for r in rows])

        # GET /api/window-state
        elif p == "/api/window-state":
            self._json(200, WIN_STATE)

        # GET /api/files/:folder
        elif p.startswith("/api/files/"):
            folder_key = p.split("/")[-1]
            folder_path = FILE_FOLDERS.get(folder_key)
            if not folder_path or not folder_path.exists():
                self._json(404, {"error": f"folder '{folder_key}' not found"})
                return
            try:
                files = []
                for entry in sorted(folder_path.iterdir(), key=lambda e: e.stat().st_mtime, reverse=True):
                    if entry.is_file() and not entry.name.startswith('.'):
                        st = entry.stat()
                        files.append({
                            "name": entry.name,
                            "path": str(entry),
                            "size": st.st_size,
                            "modified": datetime.fromtimestamp(st.st_mtime).isoformat(),
                        })
                    if len(files) >= 100:
                        break
                self._json(200, files)
            except Exception as e:
                self._json(500, {"error": str(e)})

        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        p = self.path.split("?")[0]
        body = self._read_body()

        # POST /api/clips
        if p == "/api/clips":
            cid = body.get("id") or new_id()
            now = datetime.utcnow().isoformat() + "Z"
            with LOCK:
                DB.execute("""INSERT OR REPLACE INTO clips
                    (id,content,title,category,pinned,starred,deleted,slot,tags,fields,categories,ts,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (cid, body.get("content",""), body.get("title",""),
                     body.get("category","clipboard"),
                     int(body.get("pinned",False)), int(body.get("starred",False)),
                     int(body.get("deleted",False)), body.get("slot"),
                     json.dumps(body.get("tags",[])), json.dumps(body.get("fields",[])),
                     json.dumps(body.get("categories",[])),
                     body.get("ts", now), now, now))
                DB.commit()
            self._json(201, {"id": cid})

        # POST /api/bookmarks
        elif p == "/api/bookmarks":
            bid = body.get("id") or new_id()
            now = datetime.utcnow().isoformat() + "Z"
            with LOCK:
                DB.execute("INSERT OR REPLACE INTO bookmarks (id,title,url,description,category,created_at) VALUES (?,?,?,?,?,?)",
                    (bid, body.get("title",""), body.get("url",""),
                     body.get("description",""), body.get("category","other"), now))
                DB.commit()
            self._json(201, {"id": bid})

        # POST /api/tags
        elif p == "/api/tags":
            tid = body.get("id") or new_id()
            with LOCK:
                DB.execute("INSERT OR IGNORE INTO tags (id,name,color) VALUES (?,?,?)",
                    (tid, body.get("name",""), body.get("color","#888")))
                DB.commit()
            self._json(201, {"id": tid})

        # POST /api/files/open
        elif p == "/api/files/open":
            file_path = body.get("path", "")
            if not file_path or not Path(file_path).exists():
                self._json(404, {"error": "file not found"})
                return
            # Security: only allow opening files within known folders
            resolved = Path(file_path).resolve()
            allowed = any(str(resolved).startswith(str(fp.resolve())) for fp in FILE_FOLDERS.values())
            if not allowed:
                self._json(403, {"error": "path not in allowed folders"})
                return
            try:
                os.startfile(str(resolved))  # Windows-specific
                self._json(200, {"ok": True, "opened": str(resolved)})
            except Exception as e:
                self._json(500, {"error": str(e)})

        # POST /window/pin
        elif p == "/window/pin":
            WIN_STATE["pin"] = body
            save_win_state(WIN_STATE)
            self._json(200, {"ok": True})

        # POST /window/position
        elif p == "/window/position":
            WIN_STATE["position"] = body
            save_win_state(WIN_STATE)
            self._json(200, {"ok": True})

        else:
            self._json(404, {"error": "not found"})

    def do_PUT(self):
        p = self.path.split("?")[0]
        body = self._read_body()

        # PUT /api/clips/:id
        if p.startswith("/api/clips/"):
            cid = p.split("/")[-1]
            now = datetime.utcnow().isoformat() + "Z"
            sets, vals = [], []
            for k in ("content","title","category"):
                if k in body: sets.append(f"{k}=?"); vals.append(body[k])
            for k in ("pinned","starred","deleted"):
                if k in body: sets.append(f"{k}=?"); vals.append(int(body[k]))
            if "slot" in body: sets.append("slot=?"); vals.append(body["slot"])
            for k in ("tags","fields","categories"):
                if k in body: sets.append(f"{k}=?"); vals.append(json.dumps(body[k]) if isinstance(body[k], list) else body[k])
            sets.append("updated_at=?"); vals.append(now)
            vals.append(cid)
            if sets:
                with LOCK:
                    DB.execute(f"UPDATE clips SET {','.join(sets)} WHERE id=?", vals)
                    DB.commit()
            self._json(200, {"id": cid})
        else:
            self._json(404, {"error": "not found"})

    def do_PATCH(self):
        self.do_PUT()

    def do_DELETE(self):
        p = self.path.split("?")[0]

        if p.startswith("/api/clips/"):
            cid = p.split("/")[-1]
            with LOCK:
                DB.execute("DELETE FROM clips WHERE id=?", (cid,))
                DB.commit()
            self._no_content()

        elif p.startswith("/api/bookmarks/"):
            bid = p.split("/")[-1]
            with LOCK:
                DB.execute("DELETE FROM bookmarks WHERE id=?", (bid,))
                DB.commit()
            self._no_content()

        elif p.startswith("/api/tags/"):
            tid = p.split("/")[-1]
            with LOCK:
                DB.execute("DELETE FROM tags WHERE id=?", (tid,))
                DB.commit()
            self._no_content()

        else:
            self._json(404, {"error": "not found"})

# ── Main ──────────────────────────────────────
if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"POF 2828 Sync Server running on port {PORT}")
    print(f"DB: {DB_PATH}")
    print(f"Serving clipboard3.html PWA backend")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutdown.")
        server.server_close()
